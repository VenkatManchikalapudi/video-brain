# Video Brain — Minimal Streamlit scaffold

This repository contains a minimal Streamlit frontend and lightweight backend scaffolding for the "Video Brain" project.

Quick start:

1. Create a virtual environment and install dependencies:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the Streamlit app:

```bash
streamlit run src/streamlit_app.py
```

Notes:
- The `src/gemini_client.py` contains a simple optional integration with Google Gemini. Set `GEMINI_API_KEY` in your environment and adapt the client call to your chosen model.
- Uploaded videos are temporarily stored in `temp_uploads/`.
