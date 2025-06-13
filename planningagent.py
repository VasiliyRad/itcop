from typing import Any
from baseagent import BaseAgent
from tool import Tool

class PlanningAgent(BaseAgent):
    """Agent responsible for planning tasks."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)

    def get_system_prompt(self) -> str:
        return "Review steps that you need to accomplish the task requested by the user using web browser automation and list set of questions you absolutely need to know before you can complete this action. Output questions as a JSON in the following format:\n\n[\n{\u201cquestion\u201d: \u201cWhat level of access should Kartik Talamadupula have?\u201d, \u201cpossible_answers\u201d [\u201cRead\u201d, \u201cWrite\u201d, \u201cAdmin\u201d]}\n]\nDo not include \u201cunknown\u201d in the list of possible answers. Ensure no two questions ask for the same underlying information in different ways.\nOnly respond with JSON and nothing else."
    
    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("PlanningAgent does not support tool execution directly.")