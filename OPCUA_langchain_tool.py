"""
OPC-UA LangChain Tool
----------------------
Wraps OPCUA_DataClient as a callable LangChain @tool.

Dependencies:
    pip install asyncua langchain
"""

import asyncio
import json
from typing import Any, Dict, Optional

from asyncua import Client
from asyncua.ua import NodeClass
from langchain.tools import tool

DEFAULT_SERVER_URL = "opc.tcp://Junmin:53530/OPCUA/SimulationServer"
DEFAULT_FOLDER_NODE_ID = "ns=3;i=1013"


# ---------------------------------------------------------------------------
# Core async OPC-UA client
# ---------------------------------------------------------------------------
class OPCUA_DataClient:
    def __init__(self, server_url: str = DEFAULT_SERVER_URL):
        self.server_url = server_url
        self.client: Optional[Client] = None

    async def connect(self) -> None:
        self.client = Client(self.server_url)
        await self.client.connect()

    async def disconnect(self) -> None:
        if self.client:
            await self.client.disconnect()
            self.client = None

    async def browse_folder_recursive(
        self, node, results: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        if results is None:
            results = {}
        try:
            children = await node.get_children()
            for child in children:
                try:
                    node_class = await child.read_node_class()
                    browse_name = await child.read_browse_name()
                    name = browse_name.Name
                    node_id = child.nodeid.to_string()

                    if node_class == NodeClass.Variable:
                        try:
                            value = await child.read_value()
                            if hasattr(value, "__dict__"):
                                value = str(value)
                            results[f"{name} ({node_id})"] = value
                        except Exception as exc:
                            results[f"{name} ({node_id})"] = f"Error reading: {exc}"

                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        sub: Dict[str, Any] = {}
                        await self.browse_folder_recursive(child, sub)
                        if sub:
                            results[name] = sub

                except Exception as exc:
                    results[f"unknown ({child.nodeid.to_string()})"] = f"Browse error: {exc}"

        except Exception as exc:
            raise RuntimeError(f"Error browsing node: {exc}") from exc

        return results

    async def fetch(self, folder_node_id: str) -> str:
        await self.connect()
        try:
            folder_node = self.client.get_node(folder_node_id)
            data = await self.browse_folder_recursive(folder_node)
            return json.dumps(data, indent=2, default=str)
        finally:
            await self.disconnect()


# ---------------------------------------------------------------------------
# LangChain @tool
# ---------------------------------------------------------------------------
@tool
def opcua_folder_reader(
    folder_node_id: str = DEFAULT_FOLDER_NODE_ID,
    server_url: str = DEFAULT_SERVER_URL,
) -> str:
    """Connects to an OPC-UA server and recursively reads all variable values
    inside a specified folder node. Returns a JSON object mapping variable
    names to their current values.

    Args:
        folder_node_id: OPC-UA NodeId of the folder to browse, e.g. 'ns=3;i=1013'.
        server_url: OPC-UA server endpoint URL, e.g. 'opc.tcp://hostname:4840/OPCUA/Server'.
    """
    client = OPCUA_DataClient(server_url=server_url)
    try:
        return asyncio.run(client.fetch(folder_node_id))
    except Exception as exc:
        return json.dumps({"error": str(exc)})


# ---------------------------------------------------------------------------
# Quick test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    result = opcua_folder_reader.invoke({
        "folder_node_id": DEFAULT_FOLDER_NODE_ID,
        "server_url": DEFAULT_SERVER_URL,
    })
    print(result)
