from typing import Any
from baseagent import BaseAgent
from tool import Tool

class PageAnalysisAgent(BaseAgent):
    """Agent responsible for analyzing the current page."""

    def get_system_prompt(self) -> str:
        return "You are a page analysis agent. Analyze the current page and provide insights or element IDs as requested."
    
    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("PageAnalysisAgent does not support tool execution directly.")