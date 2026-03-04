from langchain.agents import tool
from asyncua import Client
from asyncua.ua import NodeClass
import asyncio
import json

DEFAULT_SERVER_URL = "opc.tcp://SiemensWOProduction:53530/OPCUA/SimulationServer"
DEFAULT_FOLDER_NODE_ID = "ns=3;i=1013"

@tool
def opcua_folder_reader(text: str) -> str:
    """Connects to an OPC-UA server and recursively reads all variable values
    inside a specified folder node. Returns a JSON object mapping variable
    names to their current values. The input should always be an empty string,
    and this function will always return the current live OPC-UA server data."""
    
    async def fetch():
        client = Client(DEFAULT_SERVER_URL)
        await client.connect()
        try:
            results = {}
            async def browse(node, container):
                for child in await node.get_children():
                    node_class = await child.read_node_class()
                    name = (await child.read_browse_name()).Name
                    node_id = child.nodeid.to_string()
                    if node_class == NodeClass.Variable:
                        try:
                            value = await child.read_value()
                            container[f"{name} ({node_id})"] = str(value) if hasattr(value, "__dict__") else value
                        except Exception as e:
                            container[f"{name} ({node_id})"] = f"Error reading: {e}"
                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        sub = {}
                        await browse(child, sub)
                        if sub:
                            container[name] = sub

            folder_node = client.get_node(DEFAULT_FOLDER_NODE_ID)
            await browse(folder_node, results)
            return json.dumps(results, indent=2, default=str)
        finally:
            await client.disconnect()

    try:
        return asyncio.run(fetch())
    except Exception as e:
        return json.dumps({"error": str(e)})
