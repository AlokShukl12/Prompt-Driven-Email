import json
from pathlib import Path
from typing import Any, Dict, List

import streamlit as st

from backend.draft_store import DraftStore
from backend.email_processor import EmailProcessor
from backend.inbox_loader import find_email, load_mock_inbox
from backend.llm_client import MockLLMClient
from backend.prompts_store import PromptsStore


BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"


@st.cache_data
def load_mock_emails() -> List[Dict[str, Any]]:
    return load_mock_inbox(ASSETS_DIR / "mock_inbox.json")


def ensure_session_defaults(prompts_store: PromptsStore) -> None:
    if "emails" not in st.session_state:
        st.session_state["emails"] = load_mock_emails()
    if "processed" not in st.session_state:
        st.session_state["processed"] = []
    if "prompts" not in st.session_state:
        st.session_state["prompts"] = prompts_store.get_all()
    if "draft_editor" not in st.session_state:
        st.session_state["draft_editor"] = {"subject": "", "body": "", "email_id": None}


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


def render_inbox(processor: EmailProcessor) -> None:
    st.subheader("Inbox")
    if st.button("Process Inbox", use_container_width=True):
        processed = processor.ingest(st.session_state["emails"], st.session_state["prompts"])
        st.session_state["processed"] = processed
        st.success("Inbox processed with current prompts.")

    rows = []
    processed_map = {str(item.get("id")): item for item in st.session_state.get("processed", [])}
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


def render_email_detail(key_prefix: str = "") -> Dict[str, Any]:
    email_ids = [str(email.get("id")) for email in st.session_state["emails"]]
    widget_key = f"{key_prefix}email_select"
    selected_id = st.selectbox("Select Email", email_ids, key=widget_key) if email_ids else None
    if not selected_id:
        st.info("No emails loaded.")
        return {}
    email = find_email(st.session_state["emails"], selected_id) or {}
    st.markdown(f"**From:** {email.get('from')}  \n**Subject:** {email.get('subject')}")
    st.caption(email.get("timestamp", ""))
    st.text_area("Email Content", email.get("body", ""), height=200, disabled=True)
    return email


def render_email_agent(llm_client: MockLLMClient) -> None:
    st.subheader("Email Agent")
    email = render_email_detail(key_prefix="agent_")
    if not email:
        return
    user_query = st.text_input("Ask the agent", placeholder="Summarize this email", key="agent_question")
    if st.button("Ask", use_container_width=True, key="agent_ask"):
        answer = llm_client.answer_question(email, user_query, st.session_state["prompts"])
        st.write(answer)


def render_draft_tools(draft_store: DraftStore, llm_client: MockLLMClient) -> None:
    st.subheader("Draft Generation")
    email = render_email_detail(key_prefix="draft_")
    if email:
        if st.button("Generate Reply Draft", use_container_width=True, key="generate_draft"):
            draft = llm_client.draft_reply(email, st.session_state["prompts"].get("auto_reply_prompt", ""))
            st.session_state["draft_editor"] = {
                "subject": draft.get("subject", ""),
                "body": draft.get("body", ""),
                "email_id": email.get("id"),
                "metadata": draft.get("metadata", {}),
                "followups": draft.get("followups", []),
            }
            st.success("Draft generated.")

    st.text_input(
        "Draft Subject",
        key="draft_subject",
        value=st.session_state["draft_editor"]["subject"],
    )
    st.text_area(
        "Draft Body",
        key="draft_body",
        value=st.session_state["draft_editor"]["body"],
        height=200,
    )

    if st.button("Save Draft", use_container_width=True):
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
    processor = EmailProcessor(ASSETS_DIR / "processed.json", llm_client=llm_client)

    ensure_session_defaults(prompts_store)

    with st.sidebar:
        st.header("Inbox Controls")
        source = st.radio("Email Source", ["Mock Inbox", "Connect to Service (coming soon)"])
        if st.button("Load Inbox"):
            if source == "Mock Inbox":
                st.session_state["emails"] = load_mock_emails()
                st.success("Loaded mock inbox.")
            else:
                st.info("External email connectors are not implemented in this demo.")

    col1, col2 = st.columns([2, 1])
    with col1:
        render_inbox(processor)
        st.markdown("---")
        render_email_agent(llm_client)

    with col2:
        render_prompt_editor(prompts_store)
        st.markdown("---")
        render_draft_tools(draft_store, llm_client)


if __name__ == "__main__":
    main()
