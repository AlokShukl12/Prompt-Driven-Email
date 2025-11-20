import re
from datetime import datetime
from typing import Any, Dict, List, Optional


class MockLLMClient:
    """Lightweight, offline LLM client used for demos and testing."""

    def __init__(self) -> None:
        self.now = datetime.utcnow

    def categorize_email(self, email: Dict[str, Any], prompt: str) -> List[str]:
        """Infer simple category tags based on keyword heuristics."""
        text = f"{email.get('subject', '')} {email.get('body', '')}".lower()
        tags: List[str] = []
        if any(word in text for word in ["urgent", "asap", "immediately"]):
            tags.append("urgent")
        if any(word in text for word in ["meeting", "schedule", "calendar"]):
            tags.append("meeting")
        if any(word in text for word in ["invoice", "payment", "billing", "budget"]):
            tags.append("finance")
        if any(word in text for word in ["update", "status", "progress"]):
            tags.append("status")
        if not tags:
            tags.append("general")
        return tags

    def extract_actions(self, email: Dict[str, Any], prompt: str) -> List[str]:
        """Pull out basic action items by scanning for imperative or request cues."""
        body = email.get("body", "")
        actions: List[str] = []
        for line in body.splitlines():
            lowered = line.strip().lower()
            if not lowered:
                continue
            if lowered.startswith(("please", "kindly", "action:", "todo:", "request:")):
                actions.append(line.strip())
            elif any(token in lowered for token in ["due", "deadline", "send", "review", "approve"]):
                actions.append(line.strip())
        if not actions:
            actions.append("No explicit action items detected.")
        return actions

    def summarize(self, email: Dict[str, Any], prompt: str) -> str:
        """Return a short, human-readable summary."""
        sender = email.get("from", "Unknown")
        subject = email.get("subject", "No subject")
        body = email.get("body", "")
        first_sentence = re.split(r"[.!?]", body)[0][:140] if body else ""
        summary = f"{sender} wrote about '{subject}'. {first_sentence}".strip()
        return summary

    def draft_reply(
        self,
        email: Dict[str, Any],
        prompt: str,
        tone: str = "neutral",
        include_followups: bool = True,
        categories: Optional[List[str]] = None,
        actions: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a basic reply draft using tone guidance and available context."""
        subject = email.get("subject", "Re: (no subject)")
        sender = email.get("from", "Recipient")
        summary = self.summarize(email, prompt)
        categories = categories or []
        actions = actions or []
        body_lines = [
            f"Hi {sender},",
            "",
            "Thanks for the update." if "thank" not in email.get("body", "").lower() else "Appreciate the details.",
            "Here's my quick reply based on the current thread.",
            "",
            f"(Tone: {tone})",
            "",
            "Best,",
            "Your Email Agent",
        ]
        draft = {
            "subject": f"Re: {subject}",
            "body": "\n".join(body_lines),
        }
        if include_followups:
            draft["followups"] = [
                f"Confirm next steps for '{subject}'.",
                f"Schedule a call with {sender}.",
            ]
            if actions:
                draft["followups"].append(f"Review action items: {', '.join(actions[:3])}")
        draft["metadata"] = {
            "summary": summary,
            "generated_at": self.now().isoformat() + "Z",
            "tone": tone,
            "categories": categories,
            "actions": actions,
            "prompt_used": prompt,
        }
        return draft

    def answer_question(
        self,
        email: Dict[str, Any],
        user_query: str,
        prompts: Dict[str, str],
    ) -> str:
        """Route the user query to the appropriate helper."""
        lowered = user_query.lower()
        if "summarize" in lowered:
            return self.summarize(email, prompts.get("categorization_prompt", ""))
        if "task" in lowered or "action" in lowered:
            actions = self.extract_actions(email, prompts.get("action_item_prompt", ""))
            return "\n".join(actions)
        if "reply" in lowered or "draft" in lowered:
            draft = self.draft_reply(
                email,
                prompts.get("auto_reply_prompt", ""),
                tone="friendly" if "friendly" in lowered else "neutral",
            )
            return f"Subject: {draft['subject']}\n\n{draft['body']}"
        if "urgent" in lowered or "show me all urgent" in lowered:
            tags = self.categorize_email(email, prompts.get("categorization_prompt", ""))
            if "urgent" in tags:
                return "This email is tagged as urgent."
            return "This email does not appear urgent."
        return "Here's a quick summary: " + self.summarize(email, prompts.get("categorization_prompt", ""))
