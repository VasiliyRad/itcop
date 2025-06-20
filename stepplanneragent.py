from typing import Any
from baseagent import BaseAgent
import logging

class StepPlannerAgent(BaseAgent):
    """Agent responsible for planning steps to accomplish a task."""

    def __init__(self, llm_client: Any) -> None:
        super().__init__(llm_client)
        self.task_description: str = ""
        self.credentials_description = "GitHub credentials: username is 'vasiliy@live.com' and password is 'password123'."

    def set_task_description(self, task_description: str) -> None:
        """Set the question and answer for processing."""
        self.task_description = task_description
        logging.info("Set task description: %s", task_description)

    def get_system_prompt(self) -> str:
        return f"""You are a web browser automation expert. Your task is to create a detailed, step-by-step plan for accomplishing the given task.

TASK DESCRIPTION:
{self.task_description}

AVAILABLE CREDENTIALS:
{self.credentials_description}

REQUIREMENTS:
1. Break down the task into clear, actionable steps
2. Each step must represent EXACTLY ONE atomic action - never combine multiple actions into a single step
3. When credentials are needed, use the specific values from AVAILABLE CREDENTIALS (e.g., "Type 'vasiliy@live.com' into username input field" not "Type username into username input field")
4. For each prerequisite, include a verification step to check if it's already met
5. For every navigation/interaction step, include a validation step to confirm the browser is in the expected state
6. Use specific, unambiguous language for actions (e.g., "Click the blue 'Submit' button" rather than "Submit")
7. Include error handling considerations where appropriate
8. Assume the browser starts from a blank page unless specified otherwise

ATOMIC ACTION RULE:
Each action must be ONE of these types:
- Navigate to a URL
- Click on a specific element
- Type text into a specific input field
- Select an option from a dropdown
- Wait for an element to appear/disappear
- Take a screenshot
- Verify/check a condition

NEVER combine actions like:
❌ "Enter username and password, then click the 'Sign in' button"
✅ Three separate steps:
   1. "Type 'vasiliy@live.com' into the username input field"
   2. "Type 'mypassword123' into the password input field" 
   3. "Click the 'Sign in' button"

USE SPECIFIC CREDENTIALS:
When filling in forms, always use the exact values from AVAILABLE CREDENTIALS:
❌ "Type username into the username input field"
✅ "Type 'vasiliy@live.com' into the username input field"

OUTPUT FORMAT:
Respond with a JSON array only. Each step should be an object with these fields:
- "step_description": Brief description of what this step accomplishes
- "action": Specific atomic action to perform (e.g., "Navigate to https://example.com", "Click element with text 'Login'", "Type 'username' into username input field")
- "validation_action": How to verify the step succeeded (e.g., "Page title contains 'Dashboard'", "Login button is no longer visible")

EXAMPLE:
[
  {{
    "step_description": "Navigate to the main page",
    "action": "Navigate to https://github.com",
    "validation_action": "GitHub logo is visible"
  }},
  {{
    "step_description": "Enter username for login",
    "action": "Type 'vasiliy@live.com' into the username input field",
    "validation_action": "Username field contains 'vasiliy@live.com'"
  }},
  {{
    "step_description": "Enter password for login", 
    "action": "Type 'mypassword123' into the password input field",
    "validation_action": "Password field shows masked characters"
  }},
  {{
    "step_description": "Submit login form",
    "action": "Click the 'Sign in' button",
    "validation_action": "User avatar is visible in the top-right corner"
  }}
]

Output only the JSON array, no additional text or explanations."""

    async def get_tools(self):
        return []
    
    async def execute_tool(self, tool_name: str, arguments: dict) -> Any:
        raise NotImplementedError("StepPlannerAgent does not support tool execution directly.")
    