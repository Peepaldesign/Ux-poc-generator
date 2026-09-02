# UX POC-Generation Pipeline - Implementation Walkthrough

I have successfully built the architecture for your UX POC-generation pipeline based on the detailed diagrams, agent prompts, and routing matrix you provided. 

## What was built:

1. **Python Virtual Environment (`/venv`)**
   - Initialized and installed required dependencies: `langgraph`, `fastapi`, `uvicorn`, `pydantic`, `langchain-google-genai`.

2. **Backend Structure (`/backend`)**
   - **`models.py`**: A massive file mapping every single one of your required JSON payloads to strict `Pydantic` models. This guarantees the LLM outputs exactly what you expect (e.g., `A12FeaturePrioritizationOutput` must contain a `moscow` field constrained to "must/should/could/wont").
   - **`prompts.py`**: Houses the system prompts for the Orchestrator and Agents 1-13, as well as the dictionary of human-actionable fallback seeds.
   - **`degradation.py`**: The core execution engine. It wraps LLM calls in a try-catch block. If an agent fails to generate the required JSON, it catches the error and gracefully triggers the Degradation Contract, setting status to "degraded" and injecting the fallback instruction.
   - **`workflow.py`**: The LangGraph state machine. It defines a sequential flow where each node (Agent) checks the `SKIP_MAP` (derived from your Scenario Matrix). For example, if the scenario is "Feature addition", Agents 3, 7, and 11 automatically bypass themselves.
   - **`main.py`**: A FastAPI application providing an async `/api/generate` endpoint and a `/api/status` polling endpoint.

3. **Frontend Dashboard (`/frontend`)**
   - **`index.html` & `app.js`**: A clean, 3-column UI.
     - **Left Column**: Text input for the raw design brief.
     - **Middle Column**: A live, auto-updating visualization of the LangGraph DAG. Agents change color based on their status (Pending, Success, Skipped, Degraded).
     - **Right Column**: Click on any agent to view its generated JSON payload, or the bright yellow Degradation Contract fallback box if it failed.

## How to Run It

To test the system locally, you need to set your `GOOGLE_API_KEY` (since we are using `gemini-2.5-pro` for reliable structured JSON output) and start the backend server.

1. **Open a terminal in the project folder:** `/Users/pankaj/Downloads/MVP Guidebook Generator`
2. **Export your API Key:** `export GOOGLE_API_KEY="your_api_key_here"`
3. **Start the Backend:** `source venv/bin/activate && python -m uvicorn backend.main:app --reload`
4. **Open the Frontend:** Simply open `/Users/pankaj/Downloads/MVP Guidebook Generator/frontend/index.html` in your web browser.

You can now paste a brief like *"We need to launch a brand new AI-powered dog walking app"* to test the Orchestrator's classification and watch the agents execute!
