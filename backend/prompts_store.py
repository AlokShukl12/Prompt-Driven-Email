import json
from pathlib import Path
from typing import Dict


class PromptsStore:
    """Simple JSON-backed storage for user-editable prompts."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.prompts = self.load()

    def load(self) -> Dict[str, str]:
        if not self.path.exists():
            return {
                "categorization_prompt": "",
                "action_item_prompt": "",
                "auto_reply_prompt": "",
            }
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.prompts, f, indent=2)

    def update(self, updates: Dict[str, str]) -> None:
        self.prompts.update(updates)
        self.save()

    def get_all(self) -> Dict[str, str]:
        return dict(self.prompts)

