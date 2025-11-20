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
        """Create a basic reply draft using tone guidance."""
        categories = categories or self.categorize_email(email, prompt)
        actions = actions or self.extract_actions(email, prompt)
        subject = email.get("subject", "Re: (no subject)")
        sender = email.get("from", "Recipient")
        summary = self.summarize(email, prompt)
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
        draft: Dict[str, Any] = {
            "subject": f"Re: {subject}",
            "body": "\n".join(body_lines),
            "followups": [],
            "metadata": {
                "summary": summary,
                "generated_at": self.now().isoformat() + "Z",
                "tone": tone,
                "categories": categories,
                "actions": actions,
            },
        }
        if include_followups:
            draft["followups"] = [
                f"Confirm next steps for '{subject}'.",
                f"Schedule a call with {sender}.",
            ]
        return draft

    def _ensure_processed_entry(
        self,
        email: Dict[str, Any],
        prompts: Dict[str, str],
        processed_lookup: Dict[str, Dict[str, Any]],
        tone: str = "neutral",
    ) -> Dict[str, Any]:
        email_id = str(email.get("id"))
        if email_id in processed_lookup:
            return processed_lookup[email_id]
        categories = self.categorize_email(email, prompts.get("categorization_prompt", ""))
        actions = self.extract_actions(email, prompts.get("action_item_prompt", ""))
        draft = self.draft_reply(
            email,
            prompts.get("auto_reply_prompt", ""),
            tone=tone,
            categories=categories,
            actions=actions,
        )
        processed_lookup[email_id] = {
            "id": email.get("id"),
            "categories": categories,
            "actions": actions,
            "draft": draft,
        }
        return processed_lookup[email_id]

    def answer_question(
        self,
        email: Dict[str, Any],
        user_query: str,
        prompts: Dict[str, str],
        processed: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Route the user query to the appropriate helper for a single email."""
        lowered = user_query.lower()
        categories = processed.get("categories") if processed else None
        actions = processed.get("actions") if processed else None
        if "summarize" in lowered:
            return self.summarize(email, prompts.get("categorization_prompt", ""))
        if "task" in lowered or "action" in lowered:
            use_actions = actions or self.extract_actions(email, prompts.get("action_item_prompt", ""))
            return "\n".join(use_actions)
        if "reply" in lowered or "draft" in lowered:
            tone = "friendly" if "friendly" in lowered else "neutral"
            draft = self.draft_reply(
                email,
                prompts.get("auto_reply_prompt", ""),
                tone=tone,
                categories=categories,
                actions=actions,
            )
            return f"Subject: {draft['subject']}\n\n{draft['body']}"
        if "urgent" in lowered or "priority" in lowered:
            tags = categories or self.categorize_email(email, prompts.get("categorization_prompt", ""))
            return "This email is tagged as urgent." if "urgent" in tags else "This email does not appear urgent."
        return "Here's a quick summary: " + self.summarize(email, prompts.get("categorization_prompt", ""))

    def answer_inbox_question(
        self,
        emails: List[Dict[str, Any]],
        processed: List[Dict[str, Any]],
        user_query: str,
        prompts: Dict[str, str],
    ) -> str:
        """Handle inbox-level questions such as urgent filter or task rollups."""
        lowered = user_query.lower()
        processed_lookup = {str(item.get("id")): item for item in processed}
        for email in emails:
            self._ensure_processed_entry(email, prompts, processed_lookup, tone="neutral")

        def fmt_email_line(email_obj: Dict[str, Any]) -> str:
            return f"#{email_obj.get('id')} {email_obj.get('subject')} — {email_obj.get('timestamp', '')}"

        if "urgent" in lowered:
            urgent = [
                fmt_email_line(email)
                for email in emails
                if "urgent" in processed_lookup[str(email.get("id"))]["categories"]
            ]
            return "\n".join(urgent) if urgent else "No urgent emails at the moment."

        if "task" in lowered or "action" in lowered:
            lines: List[str] = []
            for email in emails:
                proc = processed_lookup[str(email.get("id"))]
                lines.append(f"{fmt_email_line(email)} -> " + "; ".join(proc.get("actions", [])))
            return "\n".join(lines)

        if "summarize" in lowered or "overview" in lowered:
            summaries = [
                f"{fmt_email_line(email)} :: {self.summarize(email, prompts.get('categorization_prompt', ''))}"
                for email in emails
            ]
            return "\n".join(summaries)

        if "draft" in lowered or "reply" in lowered:
            tone = "friendly" if "friendly" in lowered else "neutral"
            lines: List[str] = []
            for email in emails:
                proc = processed_lookup[str(email.get("id"))]
                draft = self.draft_reply(
                    email,
                    prompts.get("auto_reply_prompt", ""),
                    tone=tone,
                    categories=proc.get("categories", []),
                    actions=proc.get("actions", []),
                )
                lines.append(f"{fmt_email_line(email)} -> {draft['subject']}")
            return "\n".join(lines)

        total = len(emails)
        processed_count = len(processed_lookup)
        return f"Processed {processed_count} of {total} emails. Try asking for urgent emails, summaries, or tasks."

