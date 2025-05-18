# task_manager.py
from datetime import datetime

TASKS = []

def add_task(task_type, username):
    task = {
        "id": len(TASKS) + 1,
        "type": task_type,
        "username": username,
        "status": "pending",
        "started_at": datetime.now(),
        "result": None,
    }
    TASKS.append(task)
    return task

def complete_task(task_id, result):
    for t in TASKS:
        if t["id"] == task_id:
            t["status"] = "completed"
            t["result"] = result
            return t

def get_tasks():
    return TASKS

