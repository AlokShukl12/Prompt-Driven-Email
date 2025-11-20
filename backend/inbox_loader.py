import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_mock_inbox(inbox_path: Path) -> List[Dict[str, Any]]:
    """Load mock inbox JSON from assets."""
    if not inbox_path.exists():
        return []
    with inbox_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_email(emails: List[Dict[str, Any]], email_id: str) -> Optional[Dict[str, Any]]:
    """Return an email by id if present."""
    for email in emails:
        if str(email.get("id")) == str(email_id):
            return email
    return None

