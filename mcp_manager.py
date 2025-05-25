import os
import logging
import asyncio
import shutil
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from contextlib import AsyncExitStack
from typing import Any
from configuration import Configuration
from tool import Tool

class MCPManager:
    """Manages MCP server connections and tool execution."""
    def __init__(self, name: str, config: dict[str, Any], exit_stack: AsyncExitStack) -> None:
        self.name: str = name
        self.config: dict[str, Any] = config
        self.stdio_context: Any | None = None
        self.session: ClientSession | None = None
        self._cleanup_lock: asyncio.Lock = asyncio.Lock()
        self._cached_tools: list[Any] = []
        self.exit_stack: AsyncExitStack = exit_stack

    async def initialize(self) -> None:
        """Initialize the server connection."""
        if "command" in self.config:
            # --- STDIO mode ---
            command = (
                shutil.which("npx")
                if self.config["command"] == "npx"
                else self.config["command"]
            )
            if command is None:
                logging.exception("Invalid command")
                raise ValueError("The command must be a valid string and cannot be None.")

            server_params = StdioServerParameters(
                command=command,
                args=self.config["args"],
                env={**os.environ, **self.config["env"]}
                if self.config.get("env")
                else None,
            )

            logging.info("Calling stdio client")
            stdio_transport_cm = stdio_client(server_params)
            logging.info("Entering stdio_client context")
            stdio_transport = await self.exit_stack.enter_async_context(stdio_transport_cm)
            logging.info("Got stdio transport")
            read, write = stdio_transport

        elif "url" in self.config:
            # --- HTTP mode ---
            url = self.config["url"]
            raise NotImplementedError("HTTP mode is not implemented yet.")
        else:
            raise ValueError("MCP config must include either 'command' or 'url'.")

        # Shared session initialization for both transport types
        self.session = await self.exit_stack.enter_async_context(ClientSession(read, write))
        logging.info("Created client session")
        try:
            init_result = await asyncio.wait_for(self.session.initialize(), timeout=20)
            logging.info("Client session is initialized")
            logging.info(f"Initialization result: {init_result}")
        except asyncio.TimeoutError:
            logging.error("Timeout while initializing client session")
        except Exception as e:
            logging.error(f"Error initializing client session: {e}")
            raise

    async def test(self) -> None:
            logging.info("Test tool execution")
            tool_name = "browser_navigate"
            arguments = {
                "url": "https://www.bing.com"
            }
            await self.session.call_tool(tool_name, arguments)

            logging.info("Done step 1")

            arguments = {
                "url": "https://www.google.com"
            }
            await self.session.call_tool(tool_name, arguments)
            logging.info("Done step 2")

            arguments = {
                "url": "https://www.msn.com",
                "waitUntil": ["load", "domcontentloaded"],
                "timeout": 10000,
            }
            await self.session.call_tool(tool_name, arguments)
            logging.info("Done step 3")


    async def list_tools(self) -> list[Any]:
        """List available tools from the server.

        Returns:
            A list of available tools.

        Raises:
            RuntimeError: If the server is not initialized.
        """
        if not self.session:
            logging.exception("Exception: server is not initialized")
            raise RuntimeError(f"Server {self.name} is not initialized")

        logging.info("Getting list of tools")
        if self._cached_tools == []:
            tools_response = await self.session.list_tools()
            self._cached_tools = []

            for item in tools_response:
                if isinstance(item, tuple) and item[0] == "tools":
                    self._cached_tools.extend(
                        Tool(tool.name, tool.description, tool.inputSchema)
                        for tool in item[1]
                    )

        logging.info("Listed tools")

        return self._cached_tools

    async def execute_tool(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        retries: int = 2,
        delay: float = 1.0,
        timeout: float = 60.0,
    ) -> Any:
        """Execute a tool with retry mechanism and session recovery.

        Args:
            tool_name: Name of the tool to execute.
            arguments: Tool arguments.
            retries: Number of retry attempts.
            delay: Delay between retries in seconds.
            timeout: Timeout for tool execution in seconds.

        Returns:
            Tool execution result.

        Raises:
            RuntimeError: If server is not initialized.
            Exception: If tool execution fails after all retries.
        """
        if not self.session:
            logging.exception("Exception: server is not initialized")
            raise RuntimeError(f"Server {self.name} is not initialized")

        attempt = 0
        while attempt < retries:
            try:
                logging.info(f"Executing {tool_name} with arguments: {arguments}")
                result = await asyncio.wait_for(
                    self.session.call_tool(tool_name, arguments),
                    timeout=timeout
                )
                logging.info("Tool execution is done")

                return result

            except Exception as e:
                attempt += 1
                logging.warning(
                    f"Error executing tool: {type(e).__name__}: {str(e)}. Attempt {attempt} of {retries}."
                )
                # Attempt to recover session on error or timeout
                try:
                    logging.info("Attempting to recover session...")
                    await self.cleanup()
                    await self.initialize()
                    logging.info("Session recovered successfully.")
                except Exception as init_e:
                    logging.error(f"Error during session recovery: {init_e}")
                if attempt < retries:
                    logging.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                else:
                    logging.error("Max retries reached. Failing.")
                    raise

    async def cleanup(self) -> None:
        """Clean up server resources."""
        import traceback
        logging.info(f"cleanup() called for server {self.name}")
        logging.info(f"Call stack:\n{''.join(traceback.format_stack())}")

        async with self._cleanup_lock:
            try:
                logging.info(f"Cleaning up server {self.name}...")
                self.session = None
                self.stdio_context = None
                logging.info(f"Server {self.name} cleaned up successfully.")
            except RuntimeError as e:
                if "Attempted to exit cancel scope in a different task" in str(e):
                    # Suppress the known anyio async generator cleanup error
                    logging.debug(f"Ignored known anyio cleanup error: {e}")
                else:
                    logging.error(f"Error during cleanup of server {self.name}: {e}")
            except Exception as e:
                logging.error(f"Error during cleanup of server {self.name}: {e}")
