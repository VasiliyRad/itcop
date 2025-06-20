import json
import os
from typing import List
from automation_task import AutomationTask

class TaskStorage:
    def __init__(self, file_path: str = "tasks.json"):
        self.file_path = file_path
        self.tasks: List[AutomationTask] = []

    def initialize(self):
        """Read tasks from local file tasks.json"""
        if not os.path.exists(self.file_path):
            self.tasks = []
            return
        try:
            with open(self.file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.tasks = [AutomationTask.from_dict(item) for item in data]
        except Exception:
            self.tasks = []

    def addTask(self, task: AutomationTask):
        """Add a task and update local file tasks.json"""
        if task is None:
            raise ValueError("Cannot add None as a task")
        self.tasks.append(task)
        self._save_tasks()

    def listTasks(self) -> List[AutomationTask]:
        """Return the list of current tasks"""
        return self.tasks

    def _save_tasks(self):
        with open(self.file_path, "w", encoding="utf-8") as f:
            json.dump([task.to_dict() for task in self.tasks], f, indent=2)