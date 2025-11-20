# Prompt-Driven Email Productivity Agent

This app demonstrates a three-phase email agent:
- **Inbox processing**: load a mock inbox, categorize emails, extract action items, and prepare auto-reply drafts.
- **Agent Q&A**: select an email and ask questions like "Summarize this email" or "What tasks do I need to do?" plus inbox-level asks like "Show me all urgent emails".
- **Draft generation**: generate, edit, and save reply drafts. Drafts are stored locally and never sent automatically.

## Project structure
```
frontend/
├── backend/        # Processing pipeline and stores
├── ui/             # Streamlit UI
├── assets/         # Prompts, mock inbox, drafts, processed state
├── requirements.txt
└── README.md
```

## Setup
1) Create a virtual environment (optional but recommended):
```
python -m venv .venv
.venv\Scripts\activate
```
2) Install dependencies:
```
pip install -r requirements.txt
```

## Run the app
```
streamlit run ui/streamlit_app.py
```

## Notes
- The mock LLM client is offline and uses simple heuristics for categorization, actions, and drafting.
- Prompts and drafts persist to `assets/default_prompts.json` and `assets/drafts.json`.
- Processed pipeline state is written to `assets/processed.json` when you click **Process Inbox**. Inbox-agent queries can read from this processed state.
