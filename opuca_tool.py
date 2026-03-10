import os
import asyncio
import json
from typing import Dict, Any
from asyncua import Client
from asyncua.ua import NodeClass
from langchain.tools import tool

DEFAULT_SERVER_URL = os.getenv("OPCUA_SERVER_URL", "opc.tcp://SiemensWOProduction:53530/OPCUA/SimulationServer")
DEFAULT_CONVFOLDER_NODE_ID = "ns=3;i=1013"
DEFAULT_MAGFOLDER_NODE_ID = "ns=3;i=1016"

async def _browse(node, container):
    for child in await node.get_children():
        node_class = await child.read_node_class()
        name = (await child.read_browse_name()).Name
        node_id = child.nodeid.to_string()
        if node_class == NodeClass.Variable:
            try:
                value = await child.read_value()
                container[name] = str(value) if hasattr(value, "__dict__") else value
            except Exception as e:
                container[f"{name} ({node_id})"] = f"Error reading: {e}"
        elif node_class in (NodeClass.Object, NodeClass.ObjectType):
            sub = {}
            await _browse(child, sub)
            if sub:
                container[name] = sub
    

@tool
def opcua_convfolder_reader(user_query: str = "") -> str:
    """Connects to an OPC-UA server and recursively reads all variable values
    inside the conveyor folder node. Returns a JSON object mapping variable
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
                            container[name] = str(value) if hasattr(value, "__dict__") else value
                        except Exception as e:
                            container[f"{name} ({node_id})"] = f"Error reading: {e}"
                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        sub = {}
                        await browse(child, sub)
                        if sub:
                            container[name] = sub

            folder_node = client.get_node(DEFAULT_CONVFOLDER_NODE_ID)
            await browse(folder_node, results)

            # Optional: filter results based on keywords in user_query
            if user_query:
                query_lower = user_query.lower()
                filtered = {k: v for k, v in results.items() if any(word in k.lower() for word in query_lower.split())}
                return json.dumps(filtered or results, indent=2, default=str)

            return json.dumps(results, indent=2, default=str)

        finally:
            await client.disconnect()

    try:
        return asyncio.run(fetch())
    except Exception as e:
        return json.dumps({"error": str(e)})

@tool
def opcua_magfolder_reader(user_query: str = "") -> str:
    """Connects to an OPC-UA server and recursively reads all variable values
    inside the magazine folder node. Returns a JSON object mapping variable
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
                            container[name] = (
                                str(value) if hasattr(value, "__dict__") else value
                            )
                        except Exception as e:
                            container[name] = f"Error reading: {e}"

                    elif node_class in (NodeClass.Object, NodeClass.ObjectType):
                        sub = {}
                        await browse(child, sub)
                        if sub:
                            container[name] = sub

            folder_node = client.get_node(DEFAULT_MAGFOLDER_NODE_ID)
            await browse(folder_node, results)

            # Optional filtering based on query
            if user_query:
                query_lower = user_query.lower()
                filtered = {
                    k: v for k, v in results.items()
                    if any(word in k.lower() for word in query_lower.split())
                }
                return json.dumps(filtered or results, indent=2, default=str)

            return json.dumps(results, indent=2, default=str)

        finally:
            await client.disconnect()

    try:
        return asyncio.run(fetch())
    except Exception as e:
        return json.dumps({"error": str(e)})
    
