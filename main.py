# main.py
from langchain.agents import initialize_agent, AgentType
from langchain.tools import Tool
from langchain_openai import ChatOpenAI
from tools.user_tools import create_email_account, add_to_slack, provision_github, check_flight_status

llm = ChatOpenAI(temperature=0, model="gpt-4.1")

tools = [
    Tool.from_function(check_flight_status, name="Check Flight Status", description="Checks status of a given flight."),
#    Tool.from_function(create_email_account, name="Create Email Account", description="Creates a new email account for a user."),
#    Tool.from_function(add_to_slack),
#    Tool.from_function(provision_github),
]

agent_executor = initialize_agent(
    tools, llm, agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION, verbose=True
)

username = "jane.doe"
response = agent_executor.run(f"Check flight status for alaska airlines flight number 1078")
print(response)


