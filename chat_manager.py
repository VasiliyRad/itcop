import asyncio
import logging
from typing import Optional
from pydantic import BaseModel, Field
from pydantic.networks import HttpUrl
from typing import Any
from llm_client import LLMClient
from mcp_manager import MCPManager
from tool import Tool

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class ChatManager:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[MCPManager], llm_client: LLMClient) -> None:
        self.servers: list[MCPManager] = servers
        self.llm_client: LLMClient = llm_client
        self.tools_description: str = ""
        self.initialized: bool = False
        self.conversation: list[dict[str, str]] = []

    def get_tools_description(self):
        return self.tools_description
    
    def get_system_message(self):
        return {
            "role": "system",
            "content": (
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
        }

    def get_system_message_old(self):
        return {
            "role": "system",
            "content": (
                "You are a web browser automation agent with access to these tools:\n\n"
                f"{self.tools_description}\n"
                "Choose the appropriate tool based on the user's question. "
                "If no tool is needed, reply directly.\n\n"
                "IMPORTANT: When you need to use a tool, you must ONLY respond with "
                "the exact JSON object format below, nothing else:\n"
                "{\n"
                '    \"tool\": \"tool-name\",\n'
                '    \"arguments\": {\n'
                '        \"argument-name\": \"value\"\n'
                "    }\n"
                "}\n\n"
                "After receiving a tool's response:\n"
                "1. Explain what action was taken using a natural, conversational response\n"
                "2. Keep responses concise but informative\n"
                "3. Focus on the most relevant information\n"
                "4. Use appropriate context from the user's question\n"
                "5. Avoid simply repeating the raw data\n\n"
                "6. Inform the user about any errors or issues with the tool execution\n"
                "Please use only the tools that are explicitly defined above."
            )
        }
    
    async def cleanup(self):
        """Cleanup resources and close connections."""
        for server in self.servers:
            try:
                await server.cleanup()
            except Exception as e:
                logging.exception("Failed to cleanup server")
                raise RuntimeError(f"Failed to cleanup server: {e}")
        self.initialized = False
        self.conversation = []
        self.tools_description = ""

    async def initialize(self):
        if self.initialized:
            return
        for server in self.servers:
            try:
                await server.initialize()
                tools = await server.list_tools()
            except Exception as e:
                logging.exception("Failed to initialize server")
                raise RuntimeError(f"Failed to initialize server: {e}")
        self.initialized = True
        logging.info("Chat manager initialized")

    async def process_llm_response(self, llm_response: str) -> str:
        import json
        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                for server in self.servers:
                    logging.info(f"Checking tools on server: {server.name}")
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            logging.info("Executing tool")
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )
                            logging.info("Tool was executed successfully")

                            return f"Tool execution result: {result}"
                        except Exception as e:
                            logging.exception(f"Error executing tool: {e}")
                            return f"Error executing tool: {str(e)}"
                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    async def process_message(self, user_input: str) -> str:
        if not self.initialized:
            await self.initialize()

        if self.tools_description == "":
            all_tools = []
            for server in self.servers:
                tools = await server.list_tools()
                all_tools.extend(tools)
            self.tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])

        logging.info("Processing user input:" + user_input)
        self.conversation.append({"role": "user", "content": user_input})
        response = self.llm_client.get_response(self.get_system_message(), self.conversation)
        self.conversation.append({"role": "assistant", "content": response})
        logging.info(f"Got LLM response:{response}")

        max_iterations = 20
        iteration_count = 0

        while iteration_count < max_iterations:
            result = await self.process_llm_response(response)

            if result == response:
                logging.info("No tool called, ending loop")
                break

            iteration_count += 1
            logging.info(f"Tool iteration {iteration_count}: processing tool result")
        
            # Append tool result to conversation history
            messages = self.llm_client.append_tool_response(result, self.conversation)

            # Get next LLM response based on tool result
            response = self.llm_client.get_response(self.get_system_message(), messages=messages)
            self.conversation.append({"role": "assistant", "content": response})
            logging.info(f"Got LLM response after tool call {iteration_count}: {response}")

        if iteration_count >= max_iterations:
            logging.warning(f"Reached maximum tool iterations ({max_iterations})")
            
        logging.info("Responded to user")
        return response

