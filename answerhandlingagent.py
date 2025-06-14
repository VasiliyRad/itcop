from typing import Any
from baseagent import BaseAgent
import logging

class AnswerHandlingAgent(BaseAgent):
    """Agent responsible for handling answers."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)
        self.question: str = ""
        self.answer: str = ""

    def set_question_and_answer(self, question: str, answer: str) -> None:
        """Set the question and answer for processing."""
        self.question = question
        self.answer = answer
        logging.info(f"Set question: {self.question}, answer: {self.answer}")

    def get_system_prompt(self) -> str:
        return f"Create a statement from question '{self.question}' and answer '{self.answer}'. Respond with that statement and nothing else."
    
    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("AnswerHandlingAgent does not support tool execution directly.")
    