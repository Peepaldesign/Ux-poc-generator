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

async def run_wireframes(job_id: str):
    state = jobs_store.get(job_id)
    if not state: return
    
    state.wireframe.status = "running"
    jobs_store[job_id] = state
    
    try:
        from backend.workflow import wireframe_node
        result_dict = await wireframe_node(state)
        state.wireframe = result_dict["wireframe"]
        jobs_store[job_id] = state
    except Exception as e:
        print(f"Wireframes failed: {e}")
        state.wireframe.status = "degraded"
        state.wireframe.error_message = str(e)
        jobs_store[job_id] = state

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
    
    # It's done if cancelled, or if structure is finished AND wireframes isn't currently running
    structure_done = state.structure.status != "pending"
    wireframe_running = state.wireframe.status == "running"
    
    is_done = state.cancelled or (structure_done and not wireframe_running)
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
