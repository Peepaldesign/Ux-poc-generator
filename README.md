# UX POC-Generation Pipeline

An agentic workflow driven by LangGraph, FastAPI, and Gemini to dynamically generate UX research and product documentation from a simple design brief.

## Deploy to Render

You can instantly deploy this entire full-stack application (FastAPI backend + HTML/JS frontend) to Render for free by clicking the button below:

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

**Note during deployment:** Render will prompt you to enter a value for `GOOGLE_API_KEY`. Paste your Gemini API key there.

## Run Locally

1. Create a virtual environment and install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Export your API key:
   ```bash
   export GOOGLE_API_KEY="your_api_key_here"
   ```
3. Start the server:
   ```bash
   python -m uvicorn backend.main:app --reload
   ```
4. Open your browser to `http://localhost:8000`
