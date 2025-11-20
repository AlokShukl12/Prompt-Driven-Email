import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

# Ensure the backend package is importable when running from the frontend folder
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from backend.draft_store import DraftStore
from backend.email_processor import EmailProcessor
from backend.inbox_loader import find_email, load_mock_inbox
from backend.llm_client import MockLLMClient
from backend.prompts_store import PromptsStore


ASSETS_DIR = BASE_DIR / "assets"
PROCESSED_PATH = ASSETS_DIR / "processed.json"


@st.cache_data
def load_mock_emails(inbox_path: Path) -> List[Dict[str, Any]]:
    return load_mock_inbox(inbox_path)


def ensure_session_defaults(prompts_store: PromptsStore, processor: EmailProcessor) -> None:
    if "emails" not in st.session_state:
        st.session_state["emails"] = load_mock_emails(ASSETS_DIR / "mock_inbox.json")
    if "processed" not in st.session_state:
        st.session_state["processed"] = processor.state.get("processed", [])
    if "prompts" not in st.session_state:
        st.session_state["prompts"] = prompts_store.get_all()
    if "draft_editor" not in st.session_state:
        st.session_state["draft_editor"] = {"subject": "", "body": "", "email_id": None, "metadata": {}, "followups": []}
    st.session_state.setdefault("draft_subject", st.session_state["draft_editor"].get("subject", ""))
    st.session_state.setdefault("draft_body", st.session_state["draft_editor"].get("body", ""))


def render_prompt_editor(prompts_store: PromptsStore) -> None:
    st.subheader("Prompt Brain")
    with st.form("prompt_editor"):
        categorization = st.text_area(
            "Categorization Prompt",
            st.session_state["prompts"].get("categorization_prompt", ""),
            height=120,
        )
        action_prompt = st.text_area(
            "Action Item Prompt",
            st.session_state["prompts"].get("action_item_prompt", ""),
            height=120,
        )
        auto_reply = st.text_area(
            "Auto-Reply Draft Prompt",
            st.session_state["prompts"].get("auto_reply_prompt", ""),
            height=120,
        )
        submitted = st.form_submit_button("Save Prompts")
        if submitted:
            updates = {
                "categorization_prompt": categorization,
                "action_item_prompt": action_prompt,
                "auto_reply_prompt": auto_reply,
            }
            prompts_store.update(updates)
            st.session_state["prompts"] = prompts_store.get_all()
            st.success("Prompts saved.")


def render_inbox(processor: EmailProcessor) -> Dict[str, Dict[str, Any]]:
    st.subheader("Inbox")
    if st.button("Process Inbox", use_container_width=True):
        processed = processor.ingest(st.session_state["emails"], st.session_state["prompts"])
        st.session_state["processed"] = processed
        st.success("Inbox processed with current prompts.")

    processed_map: Dict[str, Dict[str, Any]] = {str(item.get("id")): item for item in st.session_state.get("processed", [])}
    rows = []
    for email in st.session_state["emails"]:
        processed = processed_map.get(str(email.get("id")), {})
        rows.append(
            {
                "ID": email.get("id"),
                "From": email.get("from"),
                "Subject": email.get("subject"),
                "Timestamp": email.get("timestamp"),
                "Categories": ", ".join(processed.get("categories", [])),
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
    with st.expander("Processed details (actions & drafts)"):
        for email in st.session_state["emails"]:
            processed = processed_map.get(str(email.get("id")), {})
            st.markdown(f"**#{email.get('id')} {email.get('subject','')}**")
            st.caption(email.get("timestamp", ""))
            st.write("Categories:", processed.get("categories", []))
            st.write("Actions:", processed.get("actions", []))
            if processed.get("draft"):
                st.json(processed["draft"])
            st.markdown("---")
    return processed_map


def render_email_detail(processed_map: Dict[str, Dict[str, Any]], key_prefix: str = "") -> Dict[str, Any]:
    email_ids = [str(email.get("id")) for email in st.session_state["emails"]]
    widget_key = f"{key_prefix}email_select"
    selected_id = st.selectbox("Select Email", email_ids, key=widget_key) if email_ids else None
    if not selected_id:
        st.info("No emails loaded.")
        return {}
    email = find_email(st.session_state["emails"], selected_id) or {}
    st.markdown(f"**From:** {email.get('from')}  \n**Subject:** {email.get('subject')}")
    st.caption(email.get("timestamp", ""))
    st.text_area(
        "Email Content",
        email.get("body", ""),
        height=180,
        disabled=True,
        key=f"{key_prefix}email_body",
    )
    processed = processed_map.get(str(email.get("id")), {})
    st.write("Categories:", processed.get("categories", []))
    st.write("Actions:", processed.get("actions", []))
    return email


def render_email_agent(llm_client: MockLLMClient, processed_map: Dict[str, Dict[str, Any]]) -> None:
    st.subheader("Email Agent (single email)")
    email = render_email_detail(processed_map, key_prefix="agent_")
    if not email:
        return
    user_query = st.text_input("Ask the agent", placeholder="Summarize this email", key="agent_question")
    if st.button("Ask", use_container_width=True, key="agent_ask"):
        processed = processed_map.get(str(email.get("id")))
        answer = llm_client.answer_question(email, user_query, st.session_state["prompts"], processed=processed)
        st.write(answer)


def render_inbox_agent(llm_client: MockLLMClient, processor: EmailProcessor) -> None:
    st.subheader("Inbox Agent (all emails)")
    user_query = st.text_input(
        "Ask about your inbox",
        placeholder="Show me all urgent emails",
        key="inbox_question",
    )
    if st.button("Ask Inbox Agent", use_container_width=True, key="inbox_ask"):
        if not st.session_state.get("processed"):
            st.session_state["processed"] = processor.ingest(st.session_state["emails"], st.session_state["prompts"])
        answer = llm_client.answer_inbox_question(
            st.session_state["emails"],
            st.session_state["processed"],
            user_query,
            st.session_state["prompts"],
        )
        st.write(answer)


def render_inbox_insights(
    llm_client: MockLLMClient,
    processor: EmailProcessor,
    processed_map: Dict[str, Dict[str, Any]],
) -> None:
    st.subheader("Inbox Insights (quick answers)")
    if not processed_map:
        if st.button("Process Inbox Now", use_container_width=True, key="insight_process"):
            st.session_state["processed"] = processor.ingest(st.session_state["emails"], st.session_state["prompts"])
            st.experimental_rerun()
        else:
            st.info("Process the inbox to generate insights.")
        return

    emails = st.session_state["emails"]
    processed_lookup = processed_map

    urgent = [
        f"#{email.get('id')} {email.get('subject')} — {email.get('timestamp', '')}"
        for email in emails
        if "urgent" in processed_lookup.get(str(email.get("id")), {}).get("categories", [])
    ]
    actions_rollup = [
        f"#{email.get('id')} {email.get('subject')}: " + "; ".join(
            processed_lookup.get(str(email.get("id")), {}).get("actions", [])
        )
        for email in emails
    ]

    st.write("Urgent emails:")
    st.write("\n".join(urgent) if urgent else "None detected.")
    st.write("Action items:")
    st.write("\n".join(actions_rollup))


def render_draft_tools(
    draft_store: DraftStore,
    llm_client: MockLLMClient,
    processed_map: Dict[str, Dict[str, Any]],
) -> None:
    st.subheader("Draft Generation")
    email = render_email_detail(processed_map, key_prefix="draft_")
    if email:
        if st.button("Generate Reply Draft", use_container_width=True, key="generate_draft"):
            processed = processed_map.get(str(email.get("id")), {})
            draft = llm_client.draft_reply(
                email,
                st.session_state["prompts"].get("auto_reply_prompt", ""),
                categories=processed.get("categories"),
                actions=processed.get("actions"),
            )
            st.session_state["draft_editor"] = {
                "subject": draft.get("subject", ""),
                "body": draft.get("body", ""),
                "email_id": email.get("id"),
                "metadata": draft.get("metadata", {}),
                "followups": draft.get("followups", []),
            }
            st.session_state["draft_subject"] = draft.get("subject", "")
            st.session_state["draft_body"] = draft.get("body", "")
            st.success("Draft generated.")

    if st.button("New Blank Draft", use_container_width=True, key="new_blank_draft"):
        st.session_state["draft_editor"] = {"subject": "", "body": "", "email_id": None, "metadata": {}, "followups": []}
        st.session_state["draft_subject"] = ""
        st.session_state["draft_body"] = ""

    st.text_input("Draft Subject", key="draft_subject")
    st.text_area("Draft Body", key="draft_body", height=200)

    if st.button("Save Draft", use_container_width=True, key="save_draft"):
        draft = {
            "id": st.session_state["draft_editor"].get("id"),
            "subject": st.session_state["draft_subject"],
            "body": st.session_state["draft_body"],
            "email_id": st.session_state["draft_editor"].get("email_id"),
            "metadata": st.session_state["draft_editor"].get("metadata", {}),
            "followups": st.session_state["draft_editor"].get("followups", []),
        }
        draft_store.add_or_update(draft)
        st.success("Draft saved.")

    st.caption("Saved Drafts")
    if draft_store.all():
        st.json(draft_store.all())
    else:
        st.write("No drafts saved yet.")


def main() -> None:
    st.set_page_config(page_title="Prompt-Driven Email Agent", layout="wide")
    st.title("Prompt-Driven Email Productivity Agent")
    st.caption("Phase 1-3: categorization, agent Q&A, and draft generation.")

    prompts_store = PromptsStore(ASSETS_DIR / "default_prompts.json")
    draft_store = DraftStore(ASSETS_DIR / "drafts.json")
    llm_client = MockLLMClient()
    processor = EmailProcessor(PROCESSED_PATH, llm_client=llm_client)

    ensure_session_defaults(prompts_store, processor)

    with st.sidebar:
        st.header("Inbox Controls")
        source = st.radio("Email Source", ["Mock Inbox", "Upload JSON", "Connect to Service (coming soon)"])
        uploaded_emails: List[Dict[str, Any]] = []
        uploaded_file = None
        if source == "Upload JSON":
            uploaded_file = st.file_uploader("Upload inbox JSON", type=["json"])
        if st.button("Load Inbox"):
            if source == "Mock Inbox":
                st.session_state["emails"] = load_mock_emails(ASSETS_DIR / "mock_inbox.json")
                st.success("Loaded mock inbox.")
            elif source == "Upload JSON":
                if uploaded_file:
                    try:
                        uploaded_emails = json.load(uploaded_file)
                        if isinstance(uploaded_emails, list):
                            st.session_state["emails"] = uploaded_emails
                            st.success("Loaded uploaded inbox JSON.")
                        else:
                            st.error("Uploaded file must be a JSON array of email objects.")
                    except Exception as exc:  # noqa: BLE001
                        st.error(f"Failed to parse JSON: {exc}")
                else:
                    st.warning("Please upload a JSON file first.")
            else:
                st.info("External email connectors are not implemented in this demo.")

    processed_map = render_inbox(processor)
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    with col1:
        render_email_agent(llm_client, processed_map)
        st.markdown("---")
        render_inbox_agent(llm_client, processor)
        st.markdown("---")
        render_inbox_insights(llm_client, processor, processed_map)

    with col2:
        render_prompt_editor(prompts_store)
        st.markdown("---")
        render_draft_tools(draft_store, llm_client, processed_map)


if __name__ == "__main__":
    main()
