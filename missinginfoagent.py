from typing import Any
from baseagent import BaseAgent
from tool import Tool

class MissingInfoAgent(BaseAgent):
    """Agent responsible for finding missing information in automation task."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)

    def get_system_prompt(self) -> str:
        return "Review steps that you need to accomplish the task requested by the user using web browser automation and list set of questions you absolutely need to know before you can complete this action. For each question, provide the reason why it is necessary to be answered to successfully complete the task. Output questions as a JSON in the following format:\n\n[\n{\n  \"question\": \"What level of access should Kartik Talamadupula have?\",\n  \"possible_answers\": [\"Read\", \"Write\", \"Admin\"],\n  \"reason\": \"This information is required to configure the correct permissions level in the system and ensure the user has appropriate access rights for their role.\"\n}\n]\n\nDo not include \"unknown\" in the list of possible answers. Ensure no two questions ask for the same underlying information in different ways.\nOnly respond with JSON and nothing else."    

    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("MissingInfoAgent does not support tool execution directly.")