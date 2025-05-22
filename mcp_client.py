import asyncio
import json
import logging
import shutil
from contextlib import AsyncExitStack
from typing import Any

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from configuration import Configuration

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class Server:
    """Manages MCP server connections and tool execution."""

    def __init__(self, name: str, config: dict[str, Any]) -> None:
        self.name: str = name
        self.config: dict[str, Any] = config
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self.exit_stack: AsyncExitStack = AsyncExitStack()

    async def initialize(self) -> None:
        """Initialize the server connection."""
        command = (
            shutil.which("npx")
            if self.config["command"] == "npx"
            else self.config["command"]
        )
        if command is None:
            raise ValueError("The command must be a valid string and cannot be None.")

        server_params = StdioServerParameters(
            command=command,
            args=self.config["args"],
            env={**os.environ, **self.config["env"]}
            if self.config.get("env")
            else None,
        )
        try:
            stdio_transport = await self.exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            read, write = stdio_transport
            session = await self.exit_stack.enter_async_context(
                ClientSession(read, write)
            )
            await session.initialize()
            self.session = session
        except Exception as e:
            logging.error(f"Error initializing server {self.name}: {e}")
            await self.cleanup()
            raise

    async def list_tools(self) -> list[Any]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        tools_response = await self.session.list_tools()
        tools = []

        for item in tools_response:
            if isinstance(item, tuple) and item[0] == "tools":
                tools.extend(
                    Tool(tool.name, tool.description, tool.inputSchema)
                    for tool in item[1]
                )

        return tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
    ) -> Any:
        """Execute a tool with retry mechanism.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.session:
            raise RuntimeError(f"Server {self.name} not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name}...")
                result = await self.session.call_tool(tool_name, arguments)

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {e}. Attempt {attempt} of {retries}."
                )
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        async with self._cleanup_lock:
            try:
                await self.exit_stack.aclose()
                self.session = None
                self.stdio_context = None
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")


class Tool:
    """Represents a tool with its properties and formatting."""

    def __init__(
        self, name: str, description: str, input_schema: dict[str, Any]
    ) -> None:
        self.name: str = name
        self.description: str = description
        self.input_schema: dict[str, Any] = input_schema

    def format_for_llm(self) -> str:
        """Format tool information for LLM.

        Returns:
            A formatted string describing the tool.
        """
        args_desc = []
        if "properties" in self.input_schema:
            for param_name, param_info in self.input_schema["properties"].items():
                arg_desc = (
                    f"- {param_name}: {param_info.get('description', 'No description')}"
                )
                if param_name in self.input_schema.get("required", []):
                    arg_desc += " (required)"
                args_desc.append(arg_desc)

        return f"""
Tool: {self.name}
Description: {self.description}
Arguments:
{chr(10).join(args_desc)}
"""


class LLMClient:
    """Manages communication with the LLM provider."""

    def __init__(self, api_key: str) -> None:
        self.api_key: str = api_key

    def get_response_claude(self, messages: list[dict[str, str]]) -> str:
        url = "https://api.anthropic.com/v1/messages"

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01"
        }

        # Claude expects a single 'system' prompt and a list of user/assistant turns
        system_prompt = None
        structured_messages = []

        for message in messages:
            role = message["role"]
            content = message["content"]
            if role == "system":
                system_prompt = content
            else:
                structured_messages.append({"role": role, "content": content})

        payload = {
            "model": "claude-3-7-sonnet-20250219",
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0,
            "system": system_prompt,
            "messages": structured_messages,
        }

        timeout = httpx.Timeout(60.0) 

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["content"][0]["text"]

        except httpx.RequestError as e:
            error_message = f"Error getting Claude response: {str(e)}"
            logging.error(error_message)

            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                logging.error(f"Status code: {status_code}")
                logging.error(f"Response details: {e.response.text}")

            return (
                f"I encountered an error: {error_message}. "
                "Please try again or rephrase your request."
            )
    def get_response(self, messages: list[dict[str, str]]) -> str:
        url = "https://api.openai.com/v1/chat/completions"

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        structured_messages = []

        # Extract system message and format messages list accordingly
        for message in messages:
            role = message["role"]
            content = message["content"]
            structured_messages.append({"role": role, "content": content})

        payload = {
            "model": "gpt-4",  # or "gpt-4-turbo", "gpt-3.5-turbo", etc.
            "messages": structured_messages,
            "max_tokens": 4096,
            "temperature": 0.7,
            "top_p": 1.0
        }

        timeout = httpx.Timeout(60.0) 

        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
                return data["choices"][0]["message"]["content"]

        except httpx.RequestError as e:
            error_message = f"Error getting ChatGPT response: {str(e)}"
            logging.error(error_message)

            if isinstance(e, httpx.HTTPStatusError):
                status_code = e.response.status_code
                logging.error(f"Status code: {status_code}")
                logging.error(f"Response details: {e.response.text}")

            return (
                f"I encountered an error: {error_message}. "
                "Please try again or rephrase your request."
            )

class ChatSession:
    """Orchestrates the interaction between user, LLM, and tools."""

    def __init__(self, servers: list[Server], llm_client: LLMClient) -> None:
        self.servers: list[Server] = servers
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

    async def initialize(self):
        if self.initialized:
            return
        for server in self.servers:
            try:
                await server.initialize()
            except Exception as e:
                raise RuntimeError(f"Failed to initialize server: {e}")
        all_tools = []
        for server in self.servers:
            tools = await server.list_tools()
            all_tools.extend(tools)
        self.tools_description = "\n".join([tool.format_for_llm() for tool in all_tools])
        self.initialized = True

    async def process_llm_response(self, llm_response: str) -> str:
        import json
        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                for server in self.servers:
                    tools = await server.list_tools()
                    if any(tool.name == tool_call["tool"] for tool in tools):
                        try:
                            result = await server.execute_tool(
                                tool_call["tool"], tool_call["arguments"]
                            )
                            return f"Tool execution result: {result}"
                        except Exception as e:
                            return f"Error executing tool: {str(e)}"
                return f"No server found with tool: {tool_call['tool']}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    def process_message_sync(self, user_input: str) -> list[dict]:
        """
        Synchronous wrapper for Streamlit:
        - Accepts user input and conversation history (list of dicts with 'role' and 'content')
        - Returns updated conversation (including assistant/tool responses)
        """
        import asyncio

        async def _process():
            if not self.initialized:
                await self.initialize()

            self.conversation.append({"role": "user", "content": user_input})
            llm_response = self.llm_client.get_response(self.conversation + [self.get_system_message()])
            self.conversation.append({"role": "assistant", "content": llm_response})

            result = await self.process_llm_response(llm_response)

            if result != llm_response:
                # Tool was called, so get final LLM response
                self.conversation.append({"role": "system", "content": result})
                final_response = self.llm_client.get_response(self.conversation + [self.get_system_message()])
                self.conversation.append({"role": "assistant", "content": final_response})
            return self.conversation

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            # No event loop running
            return asyncio.run(_process())
        else:
            # Reuse existing loop (Streamlit case)
            return loop.run_until_complete(_process())


