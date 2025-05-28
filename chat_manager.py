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

    def __init__(self, servers: list[MCPManager], llm_client: LLMClient, verbose_logging: bool) -> None:
        self.servers: list[MCPManager] = servers
        self.llm_client: LLMClient = llm_client
        self.tools_description: str = ""
        self.initialized: bool = False
        self.conversation: list[dict[str, str]] = []
        self.verbose_logging: bool = verbose_logging
        self.tool_log_file: str = "tool.log"
        self.max_tool_response_length: int = 8000

    def get_tools_description(self):
        return self.tools_description

    def get_system_message(self):
        return {
            "role": "system",
            "content": (
                "You are a helpful assistant with access to these tools:\n\n"
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
                "1. Transform the raw data into a natural, conversational response\n"
                "2. Keep responses concise but informative\n"
                "3. Focus on the most relevant information\n"
                "4. Use appropriate context from the user's question\n"
                "5. Avoid simply repeating the raw data\n\n"
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
        response = self.llm_client.get_response(self.conversation + [self.get_system_message()])
        self.conversation.append({"role": "assistant", "content": response})
        logging.info(f"Got LLM response:{response}")

        result = await self.process_llm_response(response)
        if (len(result) > self.max_tool_response_length):
            logging.info(f"Tool response is longer than {self.max_tool_response_length} characters, truncating")
            if (self.verbose_logging):
                logging.info("Writing tool response to log file")   
                with open(self.tool_log_file, "w") as file:
                    file.write(result)
        result = result[:self.max_tool_response_length]

        if result != response:
            # Tool was called, so get final LLM response
            response = self.llm_client.get_response(self.conversation + [{"role": "system", "content": result}] + [self.get_system_message()])
            self.conversation.append({"role": "assistant", "content": response})
            
        logging.info("Responded to user")
        return response

