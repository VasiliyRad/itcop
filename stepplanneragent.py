from typing import Any
from baseagent import BaseAgent
import logging

class StepPlannerAgent(BaseAgent):
    """Agent responsible for planning steps to accomplish a task."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)
        self.task_description: str = ""

    def set_task_description(self, task_description: str) -> None:
        """Set the question and answer for processing."""
        self.task_description = task_description
        logging.info(f"Set task description: {self.task_description}")

    def get_system_prompt(self) -> str:
        return f"""You are a web browser automation expert. Your task is to create a detailed, step-by-step plan for accomplishing the given task.

TASK DESCRIPTION:
{self.task_description}

REQUIREMENTS:
1. Break down the task into clear, actionable steps
2. For each prerequisite, include a verification step to check if it's already met
3. For every navigation/interaction step, include a validation step to confirm the browser is in the expected state
4. Use specific, unambiguous language for actions (e.g., "Click the blue 'Submit' button" rather than "Submit")
5. Include error handling considerations where appropriate
6. Assume the browser starts from a blank page unless specified otherwise

OUTPUT FORMAT:
Respond with a JSON array only. Each step should be an object with these fields:
- "step_description": Brief description of what this step accomplishes
- "action": Specific action to perform (e.g., "Navigate to https://example.com", "Click element with text 'Login'")
- "validation_action": How to verify the step succeeded (e.g., "Page title contains 'Dashboard'", "Login button is no longer visible")
- "error_handling": (optional) What to do if the step fails

EXAMPLE:
[
  {{
    "step_description": "Navigate to the main page",
    "action": "Navigate to https://github.com",
    "validation_action": "GitHub logo is visible"
  }},
  {{
    "step_description": "Access repository settings",
    "action": "Click on the 'Settings' tab in the repository navigation",
    "validation_action": "'General' section is visible"
  }}
]

Output only the JSON array, no additional text or explanations."""

    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("StepPlannerAgent does not support tool execution directly.")
    