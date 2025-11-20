import json
from pathlib import Path
from typing import Any, Dict, List


class DraftStore:
    """Persist drafts locally as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.drafts = self.load()

    def load(self) -> List[Dict[str, Any]]:
        if not self.path.exists():
            return []
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(self.drafts, f, indent=2)

    def add_or_update(self, draft: Dict[str, Any]) -> None:
        draft_id = draft.get("id")
        if draft_id is None:
            draft["id"] = len(self.drafts) + 1
            self.drafts.append(draft)
        else:
            for idx, existing in enumerate(self.drafts):
                if existing.get("id") == draft_id:
                    self.drafts[idx] = draft
                    break
            else:
                self.drafts.append(draft)
        self.save()

    def all(self) -> List[Dict[str, Any]]:
        return list(self.drafts)

