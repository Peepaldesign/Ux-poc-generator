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
        # Run the compiled LangGraph workflow asynchronously
        # astream allows us to update the state after every node executes
        async for output in workflow_app.astream(initial_state):
            # Output is a dict with node name as key and state updates as value
            for node_name, state_update in output.items():
                print(f"Finished {node_name}")
                # Update our in-memory state so the frontend can poll it
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

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Return the current state of the workflow
    state = jobs_store[job_id]
    
    # Determine if overall job is done by checking if the last agent is not pending
    # Or if a fatal error happened early. This is a simplification.
    is_done = state.a13_success_matrix.status != "pending"
    
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
