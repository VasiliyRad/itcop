from dataclasses import dataclass, asdict
from typing import Optional

@dataclass
class AutomationTask:
    id: str
    name: str
    description: Optional[str] = None

    def to_dict(self):
        return asdict(self)

    @staticmethod
    def from_dict(data: dict) -> "AutomationTask":
        return AutomationTask(
            id=data.get("id", ""),
            name=data.get("name", ""),
            description=data.get("description")
        )