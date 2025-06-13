import asyncio
import logging
from typing import Optional, Any
from llm_client import LLMClient
from tool import Tool
from abc import ABC, abstractmethod
from taskresult import TaskResult

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

class AgentConfig:
    MAX_TOOL_ITERATIONS = 20
    TOOL_RESULT_DEBUG_LIMIT = 2000

class BaseAgent(ABC):
    """Base Agent class."""

    def __init__(self, llm_client: LLMClient) -> None:
        self.llm_client: LLMClient = llm_client
        self.tools: list[Tool] = []
        self.tools_description: str = ""
        self.initialized: bool = False
        self.conversation: list[dict[str, str]] = []

    @abstractmethod
    async def get_tools(self) -> list[Tool]:
        """Get tools available for the agent."""
        pass

    @abstractmethod    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        """Execute a tool with the given name and arguments."""
        pass

    @abstractmethod
    def get_system_prompt(self) -> str:
        """Get system prompt for the agent."""
        pass

    def get_system_message(self) -> dict[str, str]:
        """Get system message for the agent."""
        return {
            "role": "system",
            "content": self.get_system_prompt()
        }

    async def cleanup(self):
        """Cleanup resources and close connections."""
        self.initialized = False
        self.conversation = []
        self.tools_description = ""

    def reset_conversation(self):
        """Reset the conversation history for the agent."""
        self.conversation = []

    async def initialize(self):
        if self.initialized:
            return
        # Aggregate tools and build description
        self.tools = await self.get_tools()
        self.tools_description = "\n".join([tool.format_for_llm() for tool in self.tools])
        self.initialized = True

    async def process_llm_response(self, llm_response: str) -> str:
        import json
        try:
            tool_call = json.loads(llm_response)
            if "tool" in tool_call and "arguments" in tool_call:
                tool_name = tool_call["tool"]
                if any(tool.name == tool_name for tool in self.tools):
                    try:
                        result = await self.execute_tool(tool_name, tool_call["arguments"])
                        return f"Tool execution result: {result}"
                    except Exception as e:
                        logging.exception(f"Error executing tool: {e}")
                        return f"Error executing tool: {str(e)}"
                else:
                    return f"Unknown tool: {tool_name}"
            return llm_response
        except json.JSONDecodeError:
            return llm_response

    async def process_message(self, user_input: str) -> str:
        if not self.initialized:
            await self.initialize()

        logging.info("Processing user input:" + user_input + " by agent " + self.__class__.__name__)
        self.conversation.append({"role": "user", "content": user_input})
        response = self.llm_client.get_response(self.get_system_message(), self.conversation)
        self.conversation.append({"role": "assistant", "content": response})
        logging.info(f"Got LLM response:{response}")

        max_iterations = AgentConfig.MAX_TOOL_ITERATIONS
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

    async def process_task(self, request: str) -> TaskResult:
        """
        Process a single-turn task with the LLM and tools.
        Args:
            request (str): The user request.
        Returns:
            TaskResult: Contains the final response and last tool context (if any).
        """
        if not self.initialized:
            await self.initialize()

        logging.info("Processing single-turn task: " + request + " by agent " + self.__class__.__name__)

        # Prepare conversation: system + single user turn
        conversation = [{"role": "user", "content": request}]
        system_message = self.get_system_message()
        response = self.llm_client.get_response(system_message, conversation)
        logging.info(f"Got LLM response: {response}")

        max_iterations = AgentConfig.MAX_TOOL_ITERATIONS
        iteration_count = 0
        last_tool_result = ""

        while iteration_count < max_iterations:
            result = await self.process_llm_response(response)

            if result == response:
                logging.info("No tool called, ending loop")
                break

            iteration_count += 1
            logging.info(f"Tool iteration {iteration_count}: processing tool result")

            # Save last tool result for context
            last_tool_result = result

            # Prepare new messages: system + user + tool result
            # Debugging: reduce tool result to first 2000 characters
            messages = self.llm_client.append_tool_response(result[:AgentConfig.TOOL_RESULT_DEBUG_LIMIT], [{"role": "user", "content": request}])
            response = self.llm_client.get_response(system_message, messages=messages)
            logging.info(f"Got LLM response after tool call {iteration_count}: {response}")

        if iteration_count >= max_iterations:
            logging.warning(f"Reached maximum tool iterations ({max_iterations})")

        logging.info("Responded to single-turn task")
        return TaskResult(response=response, context=last_tool_result)
