from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import asyncio
from typing import Dict, Any

from backend.models import WorkflowState
from backend.workflow import workflow_app

app = FastAPI(title="UX POC-Generation API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory store for jobs
jobs_store: Dict[str, WorkflowState] = {}

class GenerateRequest(BaseModel):
    brief: str

class GenerateResponse(BaseModel):
    job_id: str
    status: str

async def run_workflow(job_id: str, brief: str):
    initial_state = WorkflowState(brief=brief, job_id=job_id)
    jobs_store[job_id] = initial_state
    
    try:
        async for output in workflow_app.astream(initial_state):
            if jobs_store[job_id].cancelled:
                print(f"Job {job_id} cancelled by user.")
                break
                
            for node_name, state_update in output.items():
                print(f"Finished {node_name}")
                current_state = jobs_store[job_id]
                for key, value in state_update.items():
                    setattr(current_state, key, value)
                jobs_store[job_id] = current_state
    except Exception as e:
        print(f"Workflow {job_id} failed: {e}")

@app.post("/api/generate", response_model=GenerateResponse)
async def generate_poc(request: GenerateRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    background_tasks.add_task(run_workflow, job_id, request.brief)
    return GenerateResponse(job_id=job_id, status="started")

@app.post("/api/stop/{job_id}")
async def stop_workflow(job_id: str):
    if job_id in jobs_store:
        jobs_store[job_id].cancelled = True
        return {"status": "cancelled"}
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/history")
async def get_history():
    # Return a list of all jobs (just id and brief preview)
    history = []
    for j_id, state in jobs_store.items():
        brief_preview = state.brief[:100] + "..." if len(state.brief) > 100 else state.brief
        history.append({"job_id": j_id, "brief": brief_preview})
    # Most recent first
    return list(reversed(history))

async def run_wireframes(job_id: str):
    state = jobs_store.get(job_id)
    if not state: return
    
    # Mark as working
    state.a15_wireframes.status = "working"
    jobs_store[job_id] = state
    
    try:
        from backend.prompts import A15_PROMPT
        from backend.models import A15WireframeOutput
        from backend.degradation import call_agent_with_degradation
        from backend.workflow import _get_upstream_context
        
        ctx = _get_upstream_context(state, ["a14_compiler"])
        result = call_agent_with_degradation(A15_PROMPT, ctx, A15WireframeOutput, "Unable to generate wireframes. Please review report manually.")
        state.a15_wireframes = result
        jobs_store[job_id] = state
    except Exception as e:
        print(f"Wireframes failed: {e}")
        state.a15_wireframes.status = "degraded"
        state.a15_wireframes.error_message = str(e)

@app.post("/api/generate_wireframes/{job_id}")
async def generate_wireframes(job_id: str, background_tasks: BackgroundTasks):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    background_tasks.add_task(run_wireframes, job_id)
    return {"status": "started"}

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    state = jobs_store[job_id]
    
    # It's done if a14 finished (or skipped/degraded) or if it's cancelled
    is_done = state.cancelled or state.a14_compiler.status != "pending"
    
    return {
        "job_id": job_id,
        "is_done": is_done,
        "state": state.model_dump()
    }

from fastapi.staticfiles import StaticFiles
import os

# Serve the frontend statically
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
