import asyncio
import json
from typing import Dict, Any
from asyncua import Client
from asyncua.ua import NodeClass

# Configuration
SERVER_URL = "opc.tcp://Junmin:53530/OPCUA/SimulationServer"
FOLDER_NODE_ID = "ns=3;i=1013"  # Change this to your folder's node ID

class OPCUA_DataClient:
    def __init__(self, server_url: str = None):
        self.server_url = server_url or SERVER_URL
        self.client = None

    async def connect(self):
        self.client = Client(self.server_url)
        await self.client.connect()

    async def disconnect(self):
        if self.client:
            await self.client.disconnect()

    async def browse_folder_recursive(self, node, results: Dict[str, Any] = None) -> Dict[str, Any]:
        """Recursively browse a folder node and extract all variable values."""
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
                        # It's a variable — read its value
                        try:
                            value = await child.read_value()
                            # Convert to JSON-serialisable type where needed
                            if hasattr(value, '__class__') and hasattr(value, '__dict__'):
                                value = str(value)
                            results[f"{name} ({node_id})"] = value
                        except Exception as e:
                            results[f"{name} ({node_id})"] = f"Error reading: {e}"

                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        # It's a folder/object — recurse into it
                        sub_results = {}
                        await self.browse_folder_recursive(child, sub_results)
                        if sub_results:
                            results[name] = sub_results

                except Exception as e:
                    results[f"unknown ({child.nodeid.to_string()})"] = f"Browse error: {e}"

        except Exception as e:
            print(f"Error browsing node: {e}")
            raise

        return results

    async def get_folder_data(self, folder_node_id: str = FOLDER_NODE_ID) -> Dict[str, Any]:
        """Entry point: fetch all data under a folder node."""
        folder_node = self.client.get_node(folder_node_id)
        browse_name = await folder_node.read_browse_name()
        print(f"Browsing folder: {browse_name.Name} ({folder_node_id})")
        return await self.browse_folder_recursive(folder_node)


async def main():
    opcua_client = OPCUA_DataClient()
    await opcua_client.connect()
    try:
        folder_data = await opcua_client.get_folder_data()
        print(json.dumps(folder_data, indent=2, default=str))
    finally:
        await opcua_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
