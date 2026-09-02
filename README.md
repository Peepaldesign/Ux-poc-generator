# UX POC Generator

A tool to generate UX Proof of Concept guidebooks and wireframes from a simple text brief.

## Pipeline Architecture

The system uses a 4+1 phase architecture powered by LangGraph:
1. **Orchestrator**: Classifies the scenario to determine required depth
2. **Frame**: Defines problem statement, goals, assumptions, and stakeholders
3. **Research**: Generates market overview, competitor analysis, and feature matrix (Can be skipped based on scenario)
4. **Synthesis**: Defines personas and Jobs to be Done
5. **Structure**: Creates task flows, sitemap, metrics, and backlog
6. **Wireframe**: Generates grey-box structural screen layouts (JSON rendered via CSS)

## Features

- **Zero-Token Export**: Reports are generated synchronously from state without making any LLM calls
- **CSS Wireframe Rendering**: Grey-box wireframes are rendered directly from JSON using CSS Grid/Flexbox
- **Fallback Modes**: Degraded fallback handling to ensure the pipeline continues even if an agent fails
- **Dark Theme Dashboard**: A comprehensive UI for tracking pipeline execution and inspecting payload data

## Environment Variables

- `GOOGLE_API_KEY`: Your Gemini API key
- `GEMINI_FLASH_MODEL`: (Default: gemini-3.6-flash) Model for complex reasoning phases
- `GEMINI_LITE_MODEL`: (Default: gemini-2.0-flash-lite) Model for simpler classification phases
- `WIREFRAME_MODEL`: (Default: gemini-3.6-flash) Model for generating wireframe layouts
- `RPM_SLEEP_SECONDS`: (Default: 4) Sleep delay to prevent rate limiting
- `MAX_WIREFRAME_SCREENS`: (Default: 5) Max number of screens generated in wireframe phase

## Local Development

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn backend.main:app --reload
```

Open `http://localhost:8000` to access the dashboard.

## Deployment

Deploy directly to Render using the provided `render.yaml`.
