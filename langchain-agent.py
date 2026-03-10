import sys
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

# Add the folder containing opcua_tool.py (works on any OS / Docker container)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from opcua_tool import opcua_folder_reader

from langchain.agents import create_agent
from langchain_ollama import ChatOllama

llm = ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "qwen3"),
    base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
    temperature=0,
)

agent = create_agent(
    model=llm,
    tools=[opcua_folder_reader],
    system_prompt="""
You are an industrial automation assistant with access to tools.

Available tools:

1) opcua_folder_reader
   - Reads variables from a live OPC-UA server folder.
   - Use this tool whenever the user asks about machine data, sensors, variables, or current values.

Rules:
- For any question about OPC-UA data, ALWAYS call opcua_folder_reader first to retrieve live data.
- Never guess or fabricate values.
- Only report values that come from the OPC-UA tool.
- If a variable or node is missing, clearly state that it was not found.
- Interpret values in a human-friendly way and include engineering units if obvious (e.g. temperature, pressure, speed).
- Summarise results clearly unless the user asks for raw data.
"""
)

# ── FastAPI REST API ──────────────────────────────────────────────────────────
app = FastAPI(title="LangChain OPC-UA Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str

class ChatResponse(BaseModel):
    reply: str

@app.post("/api/agent/chat", response_model=ChatResponse)
async def chat(body: ChatRequest):
    message = body.message.strip()
    if not message:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No message provided")

    result = agent.invoke({"messages": [{"role": "user", "content": message}]})

    if isinstance(result, dict) and "messages" in result:
        reply = result["messages"][-1].content
    else:
        reply = str(result)

    return ChatResponse(reply=reply)

@app.get("/health")
async def health():
    return {"status": "ok"}

if __name__ == "__main__":
    uvicorn.run("langchain-agent:app", host="0.0.0.0", port=8000, reload=False)
