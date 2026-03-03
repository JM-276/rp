import asyncio
import json
from enum import IntEnum
from typing import Dict, Any
from asyncua import Client 
from asyncua.ua import NodeId

# Configuration
SERVER_URL = "opc.tcp://Junmin:53530/OPCUA/SimulationServer"

GOOD_PIECES_NODE_ID = "ns=3;i=1010"

class OPCUA_DataClient:
  def __init__(self, server_url: str = None):
    self.server_url = SERVER_URL
    self.client = None

  async def connect(self):
    self.client = Client (self.server_url)
    await self.client.connect()

  async def disconnect(self):
    if self.client:
      await self.client.disconnect()

  async def get_goodpieces_count(self) -> Dict[str, int]:
    try: 
      goodpieces_count_node = self.client.get_node(GOOD_PIECES_NODE_ID)

      goodpieces_count_value = await goodpieces_count_node.read_value()

      result = {
        "goodpieces_count": int(goodpieces_count_value)
      }

      return result 
    
    except Exception as e:
      print(f"Error reading values: {e}")
      raise

async def main():
    opcua_client = OPCUA_DataClient()
    await opcua_client.connect()

    try:
      goodpieces_count = await opcua_client.get_goodpieces_count()
      print(json.dumps(goodpieces_count, indent=2))
    finally:
      await opcua_client.disconnect()
      
if __name__ == "__main__":
    asyncio.run(main())
    
