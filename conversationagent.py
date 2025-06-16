from baseagent import BaseAgent
from tool import Tool
from taskresult import TaskResult
import logging

class ConversationAgent(BaseAgent):
    """
    Agent that coordinates navigation and page analysis.
    """

    def __init__(self, llm_client, navigation_agent, page_analysis_agent):
        super().__init__(llm_client)
        self.navigation_agent = navigation_agent
        self.page_analysis_agent = page_analysis_agent
        self.page_context = None

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
        if tool_name == "navigation_agent":
            webtask_result = await self.navigation_agent.process_task(arguments.get("action", ""))
            self.page_context = webtask_result.context
            logging.info(f"Web task executed: {webtask_result.response}, page context updated. (length: {len(self.page_context)})")
            return webtask_result.response
        elif tool_name == "page_analysis_agent":
            self.page_analysis_agent.set_page_context(self.page_context)
            page_analysis_result = await self.page_analysis_agent.process_task(arguments.get("analysis_type", ""))
            logging.info(f"Page analysis executed: {page_analysis_result.response}, page context length: {len(self.page_context) if self.page_context else 'N/A'}")
            return page_analysis_result.response
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
        
    async def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="navigation_agent",
                description="Navigate to a new page or perform actions like clicking on the current page.",
                input_schema={ "properties": {
                    "action": {
                        "type": "string",
                        "description": "The action to perform, e.g., 'navigate to github.com' or 'click on sign in link'.",
                        "reason": "The reason for taking this action, e.g., 'user requested to navigate to this page' or 'user requested to click on this link'."
                    }
                },
                "required": ["action"]
                }
            ),
            Tool(
                name="page_analysis_agent",
                description="Analyze the current page and find IDs of page elements.",
                input_schema={ "properties": {
                    "analysis_type": {
                        "type": "string",
                        "description": "Type of analysis to perform, e.g., 'find element ID for sign in button', 'find element ID for search input field', 'find element ID for submit button', 'inspect page structure', 'find all clickable elements'. Always include the specific element you're looking for when searching for particular elements.",
                        "reason": "The reason for performing this analysis, e.g., 'looking for ID of the link that the user requested to click on'"
                    }
                },
                "required": ["analysis_type"]
                }
            ),
        ]