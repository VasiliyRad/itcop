from baseagent import BaseAgent
from tool import Tool

class ConversationAgent(BaseAgent):
    """
    Agent that coordinates navigation and page analysis.
    """

    def __init__(self, llm_client, navigation_agent, page_analysis_agent):
        super().__init__(llm_client)
        self.navigation_agent = navigation_agent
        self.page_analysis_agent = page_analysis_agent

    def get_system_prompt(self) -> str:
        return (
            "You are a conversation agent. You can browse the web or analyze the current page. "
            "You have access to these tools:\n\n"
            f"{self.tools_description}\n"
            "Choose the appropriate tool based on the user's question. "
            "If no tool is needed, reply directly.\n\n"
            "IMPORTANT: When you need to use a tool, you must ONLY respond with"
            "the exact JSON object format below, nothing else:\n"
            "{\n"
            '    \"tool\": \"tool-name\",\n'
            '    \"arguments\": {\n'
            '        \"argument-name\": \"value\"\n'
            "    }\n"
            "}\n\n"
            "After receive tools response, provide only a brief status update.\n"
        )

    async def execute_tool(self, tool_name: str, arguments: dict):
        if tool_name == "browse_web":
            self.navigation_agent.reset_conversation()
            return await self.navigation_agent.process_message(arguments.get("action", ""))
        elif tool_name == "analyze_page":
            self.page_analysis_agent.reset_conversation()
            return await self.page_analysis_agent.process_message(arguments.get("analysis_type", ""))
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
        
    async def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="browse_web",
                description="Navigate to a new page or perform actions like clicking on the current page.",
                input_schema={ "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to perform, e.g., 'navigate to github.com' or 'click on sign in link'."
                    }
                },
                "required": ["action"]
                }
            ),
            Tool(
                name="analyze_page",
                description="Analyze the current page and find IDs of page elements.",
                input_schema={ "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform, e.g., 'find element IDs' or 'inspect page structure'."
                    }
                },
                "required": ["analysis_type"]
                }
            ),
        ]