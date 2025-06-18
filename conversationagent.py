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
            "You are a conversation agent that can assist with web navigation or page analysis. "
            "You have access to these tools:\n\n"
            f"{self.tools_description}\n"
            "**Behavioral Rules (Important):**"
            "1. When you receive reference ID information from page_analysis_agent, **store it mentally** and **re-use it** in future tool calls."
            "2. If you're clicking or interacting with an element and its reference ID is known, **always include both `element` and `ref`** in the `navigation_agent` tool call."
            "3. Use the page_analysis_agent first if the `ref` for a requested page element is not already known and after you navigated to the page."
            "4. If no tool is needed, reply directly.\n\n"
            "5. You must ONLY respond with a JSON object when invoking a tool, in the following format (no extra text):"
            "{\n"
            '    \"tool\": \"tool-name\",\n'
            '    \"arguments\": {\n'
            '        \"argument-name\": \"value\"\n'
            "    }\n"
            "}\n\n"
            "After receiving a tool result, provide only a brief status update like 'You are now on github.com. What would you like to do next?'.\n"
        )

    async def execute_tool(self, tool_name: str, arguments: dict):
        if tool_name == "navigation_agent":
            webtask_result = await self.navigation_agent.process_task(str(arguments))
            self.page_context = webtask_result.context
            logging.info(f"Web task executed: {webtask_result.response}, page context updated. (length: {len(self.page_context)})")
            return webtask_result.response
        elif tool_name == "page_analysis_agent":
            self.page_analysis_agent.set_page_context(self.page_context)
            page_analysis_result = await self.page_analysis_agent.process_task(str(arguments))
            logging.info(f"Page analysis executed: {page_analysis_result.response}, page context length: {len(self.page_context) if self.page_context else 'N/A'}")
            return page_analysis_result.response
        else:
            raise ValueError(f"Unknown tool: {tool_name}")
        
    async def get_tools(self) -> list[Tool]:
        return [
            Tool(
                name="navigation_agent",
                description="Perform navigation or interaction on the current page.",
                input_schema={ "properties": {
                    "action": {
                        "type": "string",
                        "description": "The user instruction, e.g., 'navigate to github.com' or 'click on sign in link'.",
                    },
                    "element": {
                        "type": "string",
                        "description": "A human-readable label of the element to act on, e.g., 'sign in link' or 'github.com page'.",
                    },
                    "ref": {
                        "type": "string",
                        "description": "The known reference ID for the element, obtained from page analysis. If known, you **must include it** in your tool call.",
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