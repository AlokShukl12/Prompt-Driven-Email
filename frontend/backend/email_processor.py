import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.llm_client import MockLLMClient


class EmailProcessor:
    """Coordinate ingestion pipeline: categorize, extract actions, and draft replies."""

    def __init__(self, state_path: Path, llm_client: Optional[MockLLMClient] = None) -> None:
        self.state_path = state_path
        self.llm = llm_client or MockLLMClient()
        self.state: Dict[str, Any] = self.load_state()

    def load_state(self) -> Dict[str, Any]:
        if not self.state_path.exists():
            return {"processed": []}
        with self.state_path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        with self.state_path.open("w", encoding="utf-8") as f:
            json.dump(self.state, f, indent=2)

    def process_email(self, email: Dict[str, Any], prompts: Dict[str, str]) -> Dict[str, Any]:
        categories = self.llm.categorize_email(email, prompts.get("categorization_prompt", ""))
        actions = self.llm.extract_actions(email, prompts.get("action_item_prompt", ""))
        draft = self.llm.draft_reply(
            email,
            prompts.get("auto_reply_prompt", ""),
            categories=categories,
            actions=actions,
        )
        processed = {
            "id": email.get("id"),
            "categories": categories,
            "actions": actions,
            "draft": draft,
        }
        return processed

    def ingest(self, emails: List[Dict[str, Any]], prompts: Dict[str, str]) -> List[Dict[str, Any]]:
        processed_emails: List[Dict[str, Any]] = []
        for email in emails:
            processed = self.process_email(email, prompts)
            processed_emails.append(processed)
        self.state["processed"] = processed_emails
        self.save_state()
        return processed_emails

    def get_processed(self, email_id: Any) -> Optional[Dict[str, Any]]:
        for item in self.state.get("processed", []):
            if str(item.get("id")) == str(email_id):
                return item
        return None
