from langchain.agents import initialize_agent, AgentType
from langchain.chat_models import ChatOpenAI
from langchain.schema import SystemMessage
from opcua_tool import opcua_convfolder_reader, opcua_magfolder_reader

llm_model = "gpt-4o"
llm = ChatOpenAI(temperature=0, model=llm_model)

system_message = SystemMessage(content="""
You are an industrial automation assistant with access to a live OPC-UA server.
When answering questions:
- Always call both the opcua_convfolder_reader and opcua_magfolder_reader tools to fetch live data before answering.
- Never guess or assume values — only report what the tools return.
- Interpret values clearly, labelling engineering units where obvious (e.g. temperature, pressure, speed).
- If a variable or node is not found, say so clearly.
- Summarise data in plain English unless the user asks for raw values.
""")

agent = initialize_agent(
    [opcua_convfolder_reader, opcua_magfolder_reader],
    llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    handle_parsing_errors=True,
    verbose=True,
    agent_kwargs={"system_message": system_message}
)

try:
    result = agent("What variables are available on the OPC-UA server and what are their current values?")
except:
    print("exception on external access")

try:
    result = agent("Is there anything that looks like a temperature reading on the OPC-UA server, \
    and if so what is its current value?")
except:
    print("exception on external access")
