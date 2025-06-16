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
        return "\n".join([f"You are a browser automation agent.\nPAGE CONTEXT INFORMATION {self.page_context}.",
"        Page context includes structured YAML with element descriptions. Each element may contain:",
"- a visible label (like \"Sign in\")",
"- a type (like link, button, listitem, etc.)",
"- and a reference identifier in the form [ref=e63]",
"IMPORTANT:",
"- The [ref=...] field acts as a unique ID for the element and can be used to identify it programmatically.",
"- When asked to find an element by name or function (e.g. \"Sign in link\"), respond with the value of its `ref`, such as `e63`.",
"- If the exact element is found, reply with:  ",
"  `<name> <type> id is <ref>`  ",
"  Example: `Sign in link id is e63`",
"- If multiple elements match, return all matching ref IDs and explain.",
"- If no match is found, clearly state that the element is not present in the context.",
"INSTRUCTIONS:",
"- Use the context above to answer user questions.",
"- If the needed information is not in the context, say so clearly.",
"- Do not fabricate IDs or selectors."])
    
    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("PageAnalysisAgent does not support tool execution directly.")