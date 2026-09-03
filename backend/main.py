from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import json
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
                print(f"Job {job_id} cancelled.")
                break
            for node_name, state_update in output.items():
                print(f"Finished {node_name}")
                current = jobs_store[job_id]
                for key, value in state_update.items():
                    setattr(current, key, value)
                jobs_store[job_id] = current
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
    history = []
    for j_id, state in jobs_store.items():
        bp = state.brief[:100] + "..." if len(state.brief) > 100 else state.brief
        history.append({"job_id": j_id, "brief": bp})
    return list(reversed(history))

def _derive_screen_list(state: WorkflowState) -> list:
    """Derive screen list from structure phase task_flows + sitemap. Cap to MAX_HIFI_SCREENS."""
    import os
    max_screens = int(os.getenv("MAX_HIFI_SCREENS", "5"))
    screens = []
    seen = set()
    
    # Extract screens from task flows
    if state.structure.payload and state.structure.payload.flows:
        for flow in state.structure.payload.flows:
            for node in flow.nodes:
                if node.type == "screen" and node.label not in seen:
                    seen.add(node.label)
                    screens.append({"ref": node.label, "device": "desktop", "flow": flow.name})
    
    # If not enough from flows, pad from sitemap
    if len(screens) < max_screens and state.structure.payload and state.structure.payload.sitemap:
        for snode in state.structure.payload.sitemap:
            if snode.node not in seen:
                seen.add(snode.node)
                screens.append({"ref": snode.node, "device": "desktop", "flow": ""})
    
    # Infer device from persona context
    if state.synthesis.payload and state.synthesis.payload.personas:
        top_persona_ctx = state.synthesis.payload.personas[0].context.lower()
        if any(w in top_persona_ctx for w in ["mobile", "phone", "on-the-go", "field"]):
            for s in screens:
                s["device"] = "mobile"
    
    return screens[:max_screens]

async def run_hifi_screen(job_id: str, screen_ref: str, device: str):
    state = jobs_store.get(job_id)
    if not state: return
    
    # Mark as running
    from backend.models import AgentResult
    state.hifi_screens[screen_ref] = AgentResult(status="running")
    jobs_store[job_id] = state
    
    try:
        from backend.workflow import hifi_screen_node
        result = await hifi_screen_node(state, screen_ref, device)
        state.hifi_screens[screen_ref] = result
        jobs_store[job_id] = state
    except Exception as e:
        print(f"Hi-Fi screen {screen_ref} failed: {e}")
        state.hifi_screens[screen_ref] = AgentResult(
            status="degraded",
            error_message=str(e),
            fallback_instruction="Provide a basic HTML structural layout."
        )
        jobs_store[job_id] = state

@app.get("/api/hifi/{job_id}/screens")
async def get_hifi_screens(job_id: str):
    """Return the derived screen list for this job."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"screens": _derive_screen_list(jobs_store[job_id])}

@app.post("/api/hifi/{job_id}/{screen_ref}")
async def generate_hifi_screen(job_id: str, screen_ref: str, background_tasks: BackgroundTasks, device: str = "desktop"):
    """Generate ONE hi-fi screen on demand."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs_store[job_id]
    if state.design_system.status != "success":
        raise HTTPException(status_code=400, detail="Design system not ready. Wait for the pipeline to complete.")
    
    background_tasks.add_task(run_hifi_screen, job_id, screen_ref, device)
    return {"status": "started", "screen_ref": screen_ref}

@app.post("/api/hifi/{job_id}")
async def generate_all_hifi_screens(job_id: str, background_tasks: BackgroundTasks):
    """Generate ALL derived hi-fi screens on demand."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs_store[job_id]
    if state.design_system.status != "success":
        raise HTTPException(status_code=400, detail="Design system not ready.")
    
    screens = _derive_screen_list(state)
    for s in screens:
        background_tasks.add_task(run_hifi_screen, job_id, s["ref"], s["device"])
    return {"status": "started", "count": len(screens)}

@app.get("/api/hifi/{job_id}/{screen_ref}/html")
async def get_hifi_html(job_id: str, screen_ref: str):
    """Download a single hi-fi screen as standalone HTML."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs_store[job_id]
    screen_result = state.hifi_screens.get(screen_ref)
    if not screen_result or screen_result.status != "success" or not screen_result.payload:
        raise HTTPException(status_code=404, detail="Screen not generated yet")
    return HTMLResponse(
        screen_result.payload.html,
        headers={"Content-Disposition": f"attachment; filename={screen_ref}.html"}
    )

@app.get("/api/hifi/{job_id}/design-tokens.json")
async def get_design_tokens_json(job_id: str):
    """Download design system tokens as JSON."""
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs_store[job_id]
    if state.design_system.status != "success" or not state.design_system.payload:
        raise HTTPException(status_code=404, detail="Design system not ready")
    from fastapi.responses import JSONResponse
    return JSONResponse(
        content=state.design_system.payload.model_dump(),
        headers={"Content-Disposition": f"attachment; filename=design-tokens-{job_id[:8]}.json"}
    )

@app.get("/api/status/{job_id}")
async def get_status(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    state = jobs_store[job_id]
    
    # Pipeline is done when design_system finishes (or earlier if cancelled/degraded)
    ds_done = state.design_system.status != "pending"
    any_hifi_running = any(s.status == "running" for s in state.hifi_screens.values())
    
    is_done = state.cancelled or (ds_done and not any_hifi_running)
    return {"job_id": job_id, "is_done": is_done, "state": state.model_dump()}

def _build_markdown_report(state: WorkflowState) -> str:
    """Build a Markdown report from WorkflowState. Zero LLM calls."""
    lines = []
    lines.append(f"# UX POC Research Report")
    lines.append(f"**Brief:** {state.brief}\n")
    
    # Orchestrator
    if state.orchestrator.status == 'success' and state.orchestrator.payload:
        o = state.orchestrator.payload
        lines.append("## Scenario Classification")
        lines.append(f"- **Primary Scenario:** {o.primary_scenario}")
        lines.append(f"- **Confidence:** {o.confidence}")
        lines.append(f"- **Existence:** {o.existence}")
        lines.append(f"- **Objective:** {o.objective}")
        lines.append(f"- **Rationale:** {o.rationale}\n")
    
    # Frame Phase
    if state.frame.status == 'success' and state.frame.payload:
        p = state.frame.payload
        lines.append("## 1. Brief Framing & Business Goals")
        lines.append(f"### Problem Statement\n{p.problem_statement}\n")
        if p.assumptions: lines.append("### Assumptions\n" + "\n".join(f"- {a}" for a in p.assumptions) + "\n")
        if p.constraints: lines.append("### Constraints\n" + "\n".join(f"- {c}" for c in p.constraints) + "\n")
        if p.unknowns: lines.append("### Unknowns\n" + "\n".join(f"- {u}" for u in p.unknowns) + "\n")
        lines.append(f"### Success Definition\n{p.success_definition}\n")
        if p.goal_hierarchy:
            lines.append("### Goal Hierarchy")
            for g in p.goal_hierarchy: lines.append(f"- [{g.level}] {g.goal}")
            lines.append("")
        if p.stakeholder_map:
            lines.append("### Stakeholder Map")
            lines.append("| Role | Interest | Assumed? |")
            lines.append("|------|----------|----------|")
            for s in p.stakeholder_map: lines.append(f"| {s.role} | {s.likely_interest} | {'Yes' if s.assumption else 'No'} |")
            lines.append("")
    elif state.frame.status == 'degraded':
        lines.append("## 1. Brief Framing & Business Goals")
        lines.append(f"> **Degraded:** {state.frame.fallback_instruction}\n")
    
    # Research Phase
    if state.research.status == 'success' and state.research.payload:
        p = state.research.payload
        lines.append("## 2. Research & Competitive Analysis")
        if p.market_overview: lines.append(f"### Market Overview\n{p.market_overview}\n")
        if p.trends:
            lines.append("### Market Trends")
            for t in p.trends: lines.append(f"- **{t.trend}** ({t.source})")
            lines.append("")
        if p.feature_matrix:
            lines.append("### Feature Matrix")
            # Get all competitor names
            competitors = set()
            for fm in p.feature_matrix:
                competitors.update(fm.by_competitor.keys())
            comp_list = sorted(competitors)
            header = "| Feature | " + " | ".join(comp_list) + " |"
            sep = "|---------|" + "|".join(["------" for _ in comp_list]) + "|"
            lines.append(header)
            lines.append(sep)
            for fm in p.feature_matrix:
                row = f"| {fm.feature} | " + " | ".join(fm.by_competitor.get(c, '-') for c in comp_list) + " |"
                lines.append(row)
            lines.append("")
        if p.gaps:
            lines.append("### Competitive Gaps")
            for g in p.gaps: lines.append(f"- **{g.gap}** [{g.opportunity_size}] — {g.evidence}")
            lines.append("")
        if p.pain_themes:
            lines.append("### User Pain Themes")
            for pt in p.pain_themes: lines.append(f"- **{pt.theme}** ({pt.frequency}) — {pt.representative_signal}")
            lines.append("")
    elif state.research.status == 'degraded':
        lines.append("## 2. Research & Competitive Analysis")
        lines.append(f"> **Degraded:** {state.research.fallback_instruction}\n")
    elif state.research.status == 'skipped':
        lines.append("## 2. Research & Competitive Analysis\n*Skipped by scenario.*\n")
    
    # Synthesis Phase
    if state.synthesis.status == 'success' and state.synthesis.payload:
        p = state.synthesis.payload
        lines.append("## 3. User Synthesis")
        if p.personas:
            lines.append("### Personas")
            for persona in p.personas:
                lines.append(f"#### {persona.name} ({persona.role})")
                lines.append(f"{persona.context}")
                if persona.goals: lines.append("**Goals:** " + ", ".join(g.goal for g in persona.goals))
                if persona.pains: lines.append("**Pains:** " + ", ".join(p2.pain for p2 in persona.pains))
                lines.append("")
        if p.jobs:
            lines.append("### Jobs to Be Done")
            for j in p.jobs: lines.append(f"- **[{j.priority}]** {j.job_statement}")
            lines.append("")
    elif state.synthesis.status == 'degraded':
        lines.append("## 3. User Synthesis")
        lines.append(f"> **Degraded:** {state.synthesis.fallback_instruction}\n")
    
    # Structure Phase
    if state.structure.status == 'success' and state.structure.payload:
        p = state.structure.payload
        lines.append("## 4. Structure & Prioritization")
        if p.flows:
            lines.append("### Key Task Flows")
            for f in p.flows: lines.append(f"- **{f.name}** (serves: {f.serves_job})")
            lines.append("")
        if p.sitemap:
            lines.append("### Sitemap")
            for n in p.sitemap: lines.append(f"- **{n.node}** → {', '.join(n.children)}")
            lines.append("")
        if p.backlog:
            lines.append("### Feature Backlog")
            lines.append("| Feature | MoSCoW | RICE Score | Serves Goal |")
            lines.append("|---------|--------|------------|-------------|")
            for b in p.backlog: lines.append(f"| {b.item} | {b.moscow.upper()} | {b.rice.score} | {b.serves_goal} |")
            lines.append("")
        if p.metrics_tree:
            lines.append("### Success Metrics")
            lines.append("| Business Goal | Metric | Framework | Target |")
            lines.append("|--------------|--------|-----------|--------|")
            for m in p.metrics_tree: lines.append(f"| {m.business_goal} | {m.metric} | {m.framework} | {m.target} |")
            lines.append("")
    elif state.structure.status == 'degraded':
        lines.append("## 4. Structure & Prioritization")
        lines.append(f"> **Degraded:** {state.structure.fallback_instruction}\n")
    
    lines.append("---")
    lines.append("*Report generated from UX POC Generator. No LLM tokens spent on this export.*")
    return "\n".join(lines)

@app.get("/api/report/{job_id}.md")
async def get_report_md(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    md = _build_markdown_report(jobs_store[job_id])
    return PlainTextResponse(md, headers={"Content-Disposition": f"attachment; filename=ux-report-{job_id[:8]}.md"}, media_type="text/markdown")

@app.get("/api/report/{job_id}.html")
async def get_report_html(job_id: str):
    if job_id not in jobs_store:
        raise HTTPException(status_code=404, detail="Job not found")
    md = _build_markdown_report(jobs_store[job_id])
    # Simple markdown-to-HTML via basic conversion + print styles
    import re
    html_body = md
    # Convert headers
    html_body = re.sub(r'^#### (.+)$', r'<h4>\1</h4>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html_body, flags=re.MULTILINE)
    html_body = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html_body, flags=re.MULTILINE)
    # Convert bold
    html_body = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html_body)
    # Convert italic
    html_body = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html_body)
    # Convert list items
    html_body = re.sub(r'^- (.+)$', r'<li>\1</li>', html_body, flags=re.MULTILINE)
    # Convert blockquotes
    html_body = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html_body, flags=re.MULTILINE)
    # Convert tables (simple)
    lines = html_body.split('\n')
    in_table = False
    new_lines = []
    for line in lines:
        if line.strip().startswith('|') and '---' not in line:
            cells = [c.strip() for c in line.split('|')[1:-1]]
            if not in_table:
                new_lines.append('<table border="1" cellpadding="8" cellspacing="0" style="border-collapse:collapse;width:100%;margin:12px 0">')
                new_lines.append('<tr>' + ''.join(f'<th>{c}</th>' for c in cells) + '</tr>')
                in_table = True
            else:
                new_lines.append('<tr>' + ''.join(f'<td>{c}</td>' for c in cells) + '</tr>')
        elif line.strip().startswith('|') and '---' in line:
            continue  # skip separator
        else:
            if in_table:
                new_lines.append('</table>')
                in_table = False
            new_lines.append(line)
    if in_table:
        new_lines.append('</table>')
    html_body = '\n'.join(new_lines)
    # Wrap paragraphs
    html_body = html_body.replace('\n\n', '</p><p>')
    html_body = f'<p>{html_body}</p>'
    
    html = f"""<!DOCTYPE html>
<html><head><meta charset='utf-8'><title>UX POC Report</title>
<style>
  body {{ font-family: -apple-system, sans-serif; max-width: 900px; margin: 40px auto; padding: 20px; color: #1a1a1a; line-height: 1.6; }}
  h1 {{ border-bottom: 2px solid #333; padding-bottom: 8px; }}
  h2 {{ color: #2563eb; margin-top: 32px; }}
  h3 {{ color: #4b5563; }}
  table {{ font-size: 0.9rem; }}
  th {{ background: #f3f4f6; }}
  blockquote {{ border-left: 4px solid #f59e0b; padding: 8px 16px; background: #fef3c7; margin: 16px 0; }}
  li {{ margin: 4px 0; }}
  @media print {{ body {{ margin: 0; }} }}
</style></head><body>{html_body}</body></html>"""
    return HTMLResponse(html)

from fastapi.staticfiles import StaticFiles
import os
frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
