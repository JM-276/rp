"""
OPC-UA LangChain Tool — Targeted Node Lookup
----------------------------------------------
Browses the OPC-UA folder tree but stops and returns as soon as a variable
whose name fuzzy-matches the user's query is found. No unnecessary reads.

Dependencies:
    pip install asyncua langchain
"""

import asyncio
import json
from difflib import SequenceMatcher
from langchain.agents import tool
from asyncua import Client
from asyncua.ua import NodeClass

DEFAULT_SERVER_URL = "opc.tcp://SiemensWOProduction:53530/OPCUA/SimulationServer"
DEFAULT_FOLDER_NODE_ID = "ns=3;i=1013"
MATCH_THRESHOLD = 0.5  # 0.0–1.0; lower = more lenient fuzzy matching


def _similarity(a: str, b: str) -> float:
    """Return a 0–1 similarity score between two strings (case-insensitive)."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _is_match(query: str, name: str) -> bool:
    """True if the variable name is a close-enough match for the query."""
    query_l, name_l = query.lower(), name.lower()
    # Exact substring match wins immediately
    if query_l in name_l or name_l in query_l:
        return True
    # Fall back to fuzzy ratio for typos / partial words
    return _similarity(query_l, name_l) >= MATCH_THRESHOLD


@tool
def opcua_folder_reader(text: str) -> str:
    """Connects to an OPC-UA server and finds the variable that best matches
    the user's query, returning only that variable's current value.
    Walks the folder tree and stops as soon as a match is found — it does NOT
    read every node.

    Args:
        text: A natural-language description of the data point to look up,
              e.g. 'temperature', 'pump speed', 'tank level'.
    """

    async def find_variable(query: str):
        client = Client(DEFAULT_SERVER_URL)
        await client.connect()
        try:
            best = {"score": 0.0, "name": None, "node_id": None, "value": None}

            async def browse(node):
                for child in await node.get_children():
                    node_class = await child.read_node_class()
                    name = (await child.read_browse_name()).Name
                    node_id = child.nodeid.to_string()

                    if node_class == NodeClass.Variable:
                        score = _similarity(query, name)
                        # Exact / substring match — return immediately
                        if _is_match(query, name) and score > best["score"]:
                            try:
                                value = await child.read_value()
                                best.update(
                                    score=score,
                                    name=name,
                                    node_id=node_id,
                                    value=str(value) if hasattr(value, "__dict__") else value,
                                )
                                # Short-circuit on a near-perfect match
                                if score >= 0.9:
                                    return True  # signal to stop
                            except Exception as e:
                                best.update(
                                    score=score,
                                    name=name,
                                    node_id=node_id,
                                    value=f"Error reading: {e}",
                                )

                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        done = await browse(child)
                        if done:
                            return True  # propagate short-circuit

                return False

            folder_node = client.get_node(DEFAULT_FOLDER_NODE_ID)
            await browse(folder_node)

            if best["name"] is None:
                return json.dumps({"error": f"No variable matching '{query}' was found."})

            return json.dumps(
                {
                    "query": query,
                    "matched_variable": best["name"],
                    "node_id": best["node_id"],
                    "value": best["value"],
                    "match_confidence": round(best["score"], 2),
                },
                indent=2,
                default=str,
            )
        finally:
            await client.disconnect()

    try:
        return asyncio.run(find_variable(text.strip()))
    except Exception as e:
        return json.dumps({"error": str(e)})

    print(result)v
