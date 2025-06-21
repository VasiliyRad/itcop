import json
import os
import logging
from typing import List
from automation_task import AutomationTask

class TaskStorage:
    def __init__(self, file_path: str = "tasks.json", tmp_file_path: str = "tasks_tmp.json"):
        self.file_path = file_path
        self.tmp_file_path = tmp_file_path
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
        except Exception as e:
            logging.error("Failed to load tasks from %s: %s", self.file_path, str(e))
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

    def removeTask(self, index: int):
        if 0 <= index < len(self.tasks):
            del self.tasks[index]
            self._save_tasks()

    def updateTask(self, updated_task: AutomationTask):
        for i, t in enumerate(self.tasks):
            if t.id == updated_task.id:
                self.tasks[i] = updated_task
                self._save_tasks()
                break

    def _save_tasks(self):
        try:
            with open(self.tmp_file_path, "w", encoding="utf-8") as f:
                json.dump([task.to_dict() for task in self.tasks], f, indent=2)
            os.replace(self.tmp_file_path, self.file_path)
        except Exception as e:
            logging.error("Failed to save tasks to %s: %s", self.file_path, str(e))
