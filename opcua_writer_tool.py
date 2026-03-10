from langchain.agents import tool
from asyncua import Client
from asyncua.ua import NodeClass, DataValue, Variant, VariantType
import asyncio
import json

DEFAULT_SERVER_URL = "opc.tcp://SiemensWOProduction:53530/OPCUA/SimulationServer"

# Folder node IDs sourced directly from PLCSIM_write_enabled.uasim
# Namespace is ns=1 (http://www.prosysopc.com/OPCUA/SimulationNodes/)
PLCSIM_ROOT_NODE_ID      = "ns=1;i=1001"  # PLCSIM         — top-level, contains all folders
INPUTS_FOLDER_NODE_ID    = "ns=1;i=1007"  # INPUTS         — DI_00 .. DI_04 (Boolean)
AI_FOLDER_NODE_ID        = "ns=1;i=1008"  # ANALOG_INPUTS  — AI_00 .. AI_03 (Float)
COUNTERS_FOLDER_NODE_ID  = "ns=1;i=1013"  # COUNTERS       — C001_Count1, C002_Count2 (UInt64)
REGISTERS_FOLDER_NODE_ID = "ns=1;i=1016"  # REGISTERS      — DB1_W001, DB1_W002 (Int32), DB1_R001 (Float)

# OPC-UA built-in DataType node ID -> VariantType
# Covers every DataType present in the .uasim NodeSet plus common extras
_DATATYPE_TO_VARIANT: dict[str, VariantType] = {
    "i=1":  VariantType.Boolean,
    "i=4":  VariantType.Int16,
    "i=5":  VariantType.UInt16,
    "i=6":  VariantType.Int32,
    "i=7":  VariantType.UInt32,
    "i=8":  VariantType.Int64,
    "i=9":  VariantType.UInt64,
    "i=10": VariantType.Float,
    "i=11": VariantType.Double,
    "i=12": VariantType.String,
    "i=27": VariantType.UInt64,
}


def _coerce(value, variant_type: VariantType):
    """Cast value to the correct Python type for the given VariantType."""
    if variant_type == VariantType.Boolean:
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes")
    if variant_type in (VariantType.Float, VariantType.Double):
        return float(value)
    if variant_type == VariantType.String:
        return str(value)
    return int(value)  # all integer types


async def _browse_variables(node) -> dict[str, tuple]:
    """
    Recursively browse a folder node and return a flat dict of:
        { display_name: (node_object, variant_type) }
    Only Variable nodes are included; type is read live from the server.
    """
    found = {}
    for child in await node.get_children():
        node_class = await child.read_node_class()
        name = (await child.read_browse_name()).Name
        if node_class == NodeClass.Variable:
            try:
                data_type_id = (await child.read_data_type()).to_string()
                variant_type = _DATATYPE_TO_VARIANT.get(data_type_id, VariantType.Variant)
                found[name] = (child, variant_type)
            except Exception:
                pass
        elif node_class in (NodeClass.Object, NodeClass.ObjectType):
            found.update(await _browse_variables(child))
    return found


async def _write_to_folder(folder_node_id: str, writes: list[dict]) -> list[dict]:
    """
    Open one connection, browse the folder, then apply all writes.
    Returns a list of per-write result dicts.
    """
    client = Client(DEFAULT_SERVER_URL)
    await client.connect()
    results = []
    try:
        folder = client.get_node(folder_node_id)
        variables = await _browse_variables(folder)

        for item in writes:
            name = str(item.get("node", "")).strip()
            raw_value = item.get("value")

            if not name or raw_value is None:
                results.append({"node": name, "error": '"node" and "value" are required.'})
                continue

            if name not in variables:
                results.append({
                    "node": name,
                    "error": f"Node '{name}' not found. Available in this folder: {list(variables.keys())}",
                })
                continue

            node, variant_type = variables[name]
            try:
                coerced = _coerce(raw_value, variant_type)
                await node.write_value(DataValue(Variant(coerced, variant_type)))
                results.append({
                    "status": "success",
                    "node": name,
                    "node_id": node.nodeid.to_string(),
                    "written_value": coerced,
                    "type": variant_type.name,
                })
            except Exception as e:
                results.append({"node": name, "node_id": node.nodeid.to_string(), "error": str(e)})
    finally:
        await client.disconnect()
    return results


def _run(coro):
    try:
        return asyncio.run(coro)
    except Exception as e:
        return json.dumps({"error": str(e)})


def _parse_writes(text: str):
    """Parse input as a JSON array or single object. Returns (list, error_str)."""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            parsed = [parsed]
        return parsed, None
    except json.JSONDecodeError as e:
        return None, f"Invalid JSON input: {e}"


# ---------------------------------------------------------------------------
# LangChain tools — one per folder, mirroring the reader convention
# ---------------------------------------------------------------------------

@tool
def opcua_inputs_writer(text: str) -> str:
    """Writes one or more Boolean values to digital input variables (DI_00–DI_04)
    inside the INPUTS folder of the OPC-UA PLCSIM server.

    Input: JSON array (or single object) of write requests, each with:
      - "node"  : variable display name, e.g. "DI_00"
      - "value" : Boolean — true/false, 1/0, "true"/"false"

    Returns a JSON array with the result of each write.

    Example: [{"node": "DI_00", "value": true}, {"node": "DI_02", "value": false}]
    """
    async def run():
        writes, err = _parse_writes(text)
        if err:
            return json.dumps({"error": err})
        return json.dumps(await _write_to_folder(INPUTS_FOLDER_NODE_ID, writes), indent=2, default=str)
    return _run(run())


@tool
def opcua_analog_inputs_writer(text: str) -> str:
    """Writes one or more Float values to analog input variables (AI_00–AI_03)
    inside the ANALOG_INPUTS folder of the OPC-UA PLCSIM server.

    Input: JSON array (or single object) of write requests, each with:
      - "node"  : variable display name, e.g. "AI_00"
      - "value" : numeric float value

    Returns a JSON array with the result of each write.

    Example: [{"node": "AI_00", "value": 3.14}, {"node": "AI_03", "value": 0.0}]
    """
    async def run():
        writes, err = _parse_writes(text)
        if err:
            return json.dumps({"error": err})
        return json.dumps(await _write_to_folder(AI_FOLDER_NODE_ID, writes), indent=2, default=str)
    return _run(run())


@tool
def opcua_counters_writer(text: str) -> str:
    """Writes one or more UInt64 values to counter variables (C001_Count1, C002_Count2)
    inside the COUNTERS folder of the OPC-UA PLCSIM server.

    Input: JSON array (or single object) of write requests, each with:
      - "node"  : variable display name, e.g. "C001_Count1"
      - "value" : non-negative integer

    Returns a JSON array with the result of each write.

    Example: [{"node": "C001_Count1", "value": 10}, {"node": "C002_Count2", "value": 0}]
    """
    async def run():
        writes, err = _parse_writes(text)
        if err:
            return json.dumps({"error": err})
        return json.dumps(await _write_to_folder(COUNTERS_FOLDER_NODE_ID, writes), indent=2, default=str)
    return _run(run())


@tool
def opcua_registers_writer(text: str) -> str:
    """Writes values to register variables (DB1_W001, DB1_W002 as Int32;
    DB1_R001 as Float) inside the REGISTERS folder of the OPC-UA PLCSIM server.

    Input: JSON array (or single object) of write requests, each with:
      - "node"  : variable display name, e.g. "DB1_W001"
      - "value" : integer for DB1_W001/DB1_W002, float for DB1_R001

    Returns a JSON array with the result of each write.

    Example: [{"node": "DB1_W001", "value": 42}, {"node": "DB1_R001", "value": 1.5}]
    """
    async def run():
        writes, err = _parse_writes(text)
        if err:
            return json.dumps({"error": err})
        return json.dumps(await _write_to_folder(REGISTERS_FOLDER_NODE_ID, writes), indent=2, default=str)
    return _run(run())
