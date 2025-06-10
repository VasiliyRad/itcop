from typing import Any
from baseagent import BaseAgent
from tool import Tool

class PageAnalysisAgent(BaseAgent):
    """Agent responsible for analyzing the current page."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)
        self.page_context: str = ""

    def set_page_context(self, page_context: str) -> None:
        """Set the current page context for analysis."""
        self.page_context = page_context

    def get_system_prompt(self) -> str:
        return "You are a browser automation agent.\nPAGE CONTEXT INFORMATION {self.page_context}.\nINSTRUCTIONS:\n - Use the context above to answer user questions\n - If information isn't in the context, say so clearly."
    
    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("PageAnalysisAgent does not support tool execution directly.")