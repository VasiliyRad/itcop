

import asyncio
import json
import logging
from answerhandlingagent import AnswerHandlingAgent
from automation_task import AutomationTask
from missinginfoagent import MissingInfoAgent
from stepplanneragent import StepPlannerAgent


class TaskPlanner:
    def __init__(self, loop, llm_client):
        self.questions = []
        self.possible_answers = []
        self.reason = ""
        self.loop = loop
        self.missing_info_agent = MissingInfoAgent(llm_client)
        self.answer_agent = AnswerHandlingAgent(llm_client)
        self.step_planner_agent = StepPlannerAgent(llm_client)

    def start_conversation(self):
        self.questions = []
    
    def is_empty_response(self, response):
        return not response or response.strip() == "[]"

    def _run_async_safely(self, coro, timeout=210):
        """Helper method to run async coroutines safely from sync context."""
        try:
            future = asyncio.run_coroutine_threadsafe(coro, self.loop)
            return future.result(timeout=timeout)
        except asyncio.TimeoutError:
            logging.error(f"Command timed out after {timeout} seconds")
            return None
        except Exception as e:
            logging.error(f"Error running async operation: {e}")
            return None

    def check_for_missing_information(self, task_description: str) -> bool:
        logging.info(f"Processing task description: {task_description}")
        response = self._run_async_safely(self.missing_info_agent.process_message(task_description))

        if response is None:
            logging.error("Failed to get response from MissingInfoAgent")
            return False

        if self.is_empty_response(response):
            return False
        
        try:
            data = json.loads(response)
            if not data or "question" not in data[0] or "possible_answers" not in data[0]:
                logging.error("Invalid response format")
                return False
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return False

        first_question = data[0]["question"]
        self.questions.append(first_question)

        self.possible_answers = data[0]["possible_answers"]
        self.reason = data[0].get("reason", "")

        return True
    
    def process_answer(self, answer: str) -> str:
        if len(self.questions) == 0:
            logging.error("No question to process")
            return ""
        
        self.answer_agent.set_question_and_answer(self.questions[-1], answer)
        logging.info(f"Processing answer for question: {self.questions[-1]}")
        result = self._run_async_safely(self.answer_agent.process_message("?"))

        if result is None:
            logging.error("Failed to process answer")
            return ""
    
        return result

    def prepare_question(self):
        agent_question = f"Question: {self.questions[-1]}"
        if self.possible_answers and len(self.possible_answers) > 0:
            agent_question = agent_question + f"\nPossible answers: {', '.join(self.possible_answers)}"
        if self.reason:
            agent_question = agent_question + f"\nReason: {self.reason}"
        return agent_question
    
    def prepare_plan(self, id: str, name: str, task_description: str) -> AutomationTask:
        if (len(task_description) == 0):
            logging.error("Task description is empty")
            return None
        
        self.step_planner_agent.set_task_description(task_description)
        logging.info(f"Preparing plan for task description: {task_description}")
        result = self._run_async_safely(self.step_planner_agent.process_message("?"))
        if result is None:
            logging.error("Failed to prepare plan")
            return None
        
        try:
            json_result = json.loads(result)
        except json.JSONDecodeError as e:
            logging.error(f"JSON decode error: {e}")
            return None
        
        logging.info(f"Plan prepared: {json_result}")
        logging.info(f"id={id}, name={name}, task_description={task_description}, result={result}")
        return AutomationTask(id=id, name=name, description=task_description, steps=result)

    