import asyncio
import logging
from typing import Any
from llm_client import LLMClient
from mcp_manager import MCPManager
from tool import Tool
from baseagent import BaseAgent

class NavigationAgent(BaseAgent):
    """Navigation Agent, which uses MCPManager to execute browser commands."""
    def __init__(self, servers: list[MCPManager], llm_client: LLMClient) -> None:
        super().__init__(llm_client)
        self.servers: list[MCPManager] = servers

    async def initialize(self):
        for server in self.servers:
            try:
                await server.initialize()
            except Exception as e:
                logging.exception(f"Failed to initialize server {getattr(server, 'name', str(server))}: {e}")
                raise RuntimeError(f"Failed to initialize server: {e}")
        await super().initialize()
        logging.info("Navigation agent initialized with tools")

    def get_system_prompt(self) -> str:
        return (
                "You are a browser automation assistant. Your ONLY job is to execute commands and confirm completion.\n"
                "CRITICAL RULES:\n"
                "- Execute the requested action using the appropriate tool\n"
                "- Respond with ONLY a brief confirmation (e.g., 'Navigated to github.com' or 'Error: [description]')\n"
                "- DO NOT analyze, summarize, or describe page content\n"
                "- DO NOT provide additional commentary unless explicitly asked\n"
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
                "EXAMPLES:\n\n"
            "Input: Navigate to github.com\n"
            "Output: {\n"
            '    \"tool\": \"browser_navigate\",\n'
            '    \"arguments\": {\n'
            '        \"url\": \"https://github.com\"\n'
            "    }\n"
            "}\n\n"
            "Input: Click on sign in link\n"
            "Output: {\n"
            '    \"tool\": \"browser_click\",\n'
            '    \"arguments\": {\n'
            '        \"element\": \"Sign in link\",\n'
            '        \"ref\": \"e70\"\n'
            "    }\n"
            "}\n\n"
            "Input: Find username input box on the page\n"
            "Output: {\n"
            '    \"tool\": \"browser_snapshot\",\n'
            '    \"arguments\": {}\n'
            "}\n\n"
            "Input: Slowly fill in username as vasiliy@live.com into username input box\n"
            "Output: {\n"
            '    \"tool\": \"browser_type\",\n'
            '    \"arguments\": {\n'
            '        \"element\": \"Username input box\",\n'
            '        \"ref\": \"e60\",\n'
            '        \"text\": \"vasiliy@live.com\"\n'
            "    }\n"
            "}\n\n"
                "Please use only the tools that are explicitly defined above."
            )

    async def cleanup(self):
        """Cleanup resources and close connections."""
        await super().cleanup()
        for server in self.servers:
            try:
                await server.cleanup()
            except Exception as e:
                logging.exception(f"Failed to cleanup server {getattr(server, 'name', str(server))}: {e}")
                raise RuntimeError(f"Failed to cleanup server: {e}")
        self.servers = []
        logging.info("Navigation agent cleaned up")

    async def get_tools(self) -> list[Tool]:
        """
        Get the list of tools available for this agent.
        This method aggregates tools from all servers.
        """
        all_tools = []
        for server in self.servers:
            try:
                tools = await server.list_tools()
                all_tools.extend(tools)
            except Exception as e:
                logging.exception(f"Error listing tools on server {getattr(server, 'name', str(server))}: {e}")
        return all_tools
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """
        Find the server that has the tool and execute it.
        This method knows about servers; process_llm_response does not.
        """
        for server in self.servers:
            try:
                tools = await server.list_tools()
                if any(tool.name == tool_name for tool in tools):
                    return await server.execute_tool(tool_name, arguments)
            except Exception as e:
                logging.exception(f"Error listing tools or executing tool on server: {e}")
        raise RuntimeError(f"No server found with tool: {tool_name}")
