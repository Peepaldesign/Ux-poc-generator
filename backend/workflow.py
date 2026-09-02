import os
import json
import asyncio
from langgraph.graph import StateGraph, START, END
from backend.models import (
    WorkflowState, AgentResult, OrchestratorOutput, 
    FramePhaseOutput, ResearchPhaseOutput, SynthesisPhaseOutput, 
    StructurePhaseOutput, WireframeOutput
)
from backend.prompts import (
    ORCHESTRATOR_PROMPT, FRAME_PROMPT, RESEARCH_PROMPT, 
    SYNTHESIS_PROMPT, STRUCTURE_PROMPT, WIREFRAME_PROMPT, FALLBACKS
)
from backend.degradation import call_agent_with_degradation, RPM_SLEEP_SECONDS

SKIP_MAP = {
    "New product (0->1)": [
        "competitor_issues", "client_audit"
    ],
    "Feature addition": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "personas", "persona_status", "persona_grounding", "persona_open_questions",
        "sitemap", "nav_model", "content_groups", "handoff_uncertain_nav_items"
    ],
    "Multi-platform extension": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "personas", "persona_status", "persona_grounding", "persona_open_questions"
    ],
    "Redesign / Revamp": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations"
    ],
    "Consolidation / migration": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "feature_matrix", "pattern_inventory", "teardown_notes", "gaps", "handoff_top_3_gaps"
    ],
    "Usability & accessibility remediation": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "feature_matrix", "pattern_inventory", "teardown_notes", "gaps", "handoff_top_3_gaps",
        "personas", "persona_status", "persona_grounding", "persona_open_questions",
        "jobs",
        "sitemap", "nav_model", "content_groups", "handoff_uncertain_nav_items",
        "backlog"
    ],
    "Onboarding / activation": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "sitemap", "nav_model", "content_groups", "handoff_uncertain_nav_items"
    ],
    "Conversion / funnel optimization": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "personas", "persona_status", "persona_grounding", "persona_open_questions",
        "sitemap", "nav_model", "content_groups", "handoff_uncertain_nav_items"
    ],
    "Retention / engagement": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "feature_matrix", "pattern_inventory", "teardown_notes", "gaps", "handoff_top_3_gaps",
        "sitemap", "nav_model", "content_groups", "handoff_uncertain_nav_items"
    ],
    "Design system creation": [
        "market_overview", "trends", "regulatory", "conventions", "key_players", "citations",
        "feature_matrix", "pattern_inventory", "teardown_notes", "gaps", "handoff_top_3_gaps",
        "pain_themes",
        "personas", "persona_status", "persona_grounding", "persona_open_questions",
        "jobs",
        "journeys", "journey_status", "handoff_highest_friction_stage",
        "flows", "handoff_implied_screens",
        "backlog"
    ]
}

def _get_skip_text(state: WorkflowState) -> str:
    if state.orchestrator.status != "success" or not state.orchestrator.payload:
        return ""
    scenario = state.orchestrator.payload.primary_scenario
    for key, skips in SKIP_MAP.items():
        if key.lower() in scenario.lower():
            if skips:
                return f"\nNote: for this scenario, skip the following sub-sections (leave arrays/fields empty): {', '.join(skips)}"
    return ""

def _get_upstream_context(state: WorkflowState, fields: list) -> str:
    context = {}
    for f in fields:
        attr = getattr(state, f, None)
        if attr and attr.payload:
            dump = attr.payload.model_dump(exclude={'thinking_process'})
            extracted = {}
            for k, v in dump.items():
                if k.startswith("handoff_") or k in ("success_definition", "problem_statement", "primary_scenario", "existence", "objective", "signals"):
                    extracted[k] = v
            if extracted:
                context[f] = extracted
            else:
                dump_str = json.dumps(dump, separators=(',', ':'))
                context[f] = dump_str[:200] + ("..." if len(dump_str) > 200 else "")
    return json.dumps(context, separators=(',', ':'))

async def orchestrator_node(state: WorkflowState):
    print("Running Orchestrator...")
    result = await call_agent_with_degradation(
        ORCHESTRATOR_PROMPT,
        state.brief,
        OrchestratorOutput,
        "Manual classification required.",
        tier='lite'
    )
    if result.status == "success" and result.payload and result.payload.needs_disambiguation:
        result.status = "degraded"
        result.error_message = "Vague brief: " + (result.payload.clarifying_question or "Please provide more details.")
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"orchestrator": result}

def _build_context(state: WorkflowState, deps: list) -> str:
    header = f"SOURCE BRIEF (authoritative — produce content ONLY about this; never substitute another domain):\n{state.brief}\n\nSUPPLEMENTARY CONTEXT (Handoffs & upstream):\n"
    return header + _get_upstream_context(state, deps) + _get_skip_text(state)

async def frame_node(state: WorkflowState):
    print("Running Frame Phase...")
    ctx = _build_context(state, ["orchestrator"])
    result = await call_agent_with_degradation(
        FRAME_PROMPT, ctx, FramePhaseOutput, FALLBACKS["frame"], tier='lite', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"frame": result}

async def research_node(state: WorkflowState):
    print("Running Research Phase...")
    ctx = _build_context(state, ["orchestrator", "frame"])
    result = await call_agent_with_degradation(
        RESEARCH_PROMPT, ctx, ResearchPhaseOutput, FALLBACKS["research"], tier='flash', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"research": result}

async def synthesis_node(state: WorkflowState):
    print("Running Synthesis Phase...")
    ctx = _build_context(state, ["orchestrator", "frame", "research"])
    result = await call_agent_with_degradation(
        SYNTHESIS_PROMPT, ctx, SynthesisPhaseOutput, FALLBACKS["synthesis"], tier='flash', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"synthesis": result}

async def structure_node(state: WorkflowState):
    print("Running Structure Phase...")
    ctx = _build_context(state, ["orchestrator", "frame", "research", "synthesis"])
    result = await call_agent_with_degradation(
        STRUCTURE_PROMPT, ctx, StructurePhaseOutput, FALLBACKS["structure"], tier='flash', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"structure": result}

async def wireframe_node(state: WorkflowState):
    print("Running Wireframe Phase...")
    wf_context = {}
    if state.structure.payload:
        dump = state.structure.payload.model_dump()
        wf_context["flows"] = dump.get("flows")
        wf_context["sitemap"] = dump.get("sitemap")
        wf_context["nav_model"] = dump.get("nav_model")
    if state.synthesis.payload:
        dump = state.synthesis.payload.model_dump()
        wf_context["top_persona"] = dump.get("personas")[0] if dump.get("personas") else None
        wf_context["top_job"] = dump.get("jobs")[0] if dump.get("jobs") else None
    
    header = f"SOURCE BRIEF (authoritative — produce content ONLY about this; never substitute another domain):\n{state.brief}\n\nSUPPLEMENTARY CONTEXT (Handoffs & upstream):\n"
    ctx = header + json.dumps(wf_context, separators=(',', ':')) + _get_skip_text(state)
    result = await call_agent_with_degradation(
        WIREFRAME_PROMPT, ctx, WireframeOutput, FALLBACKS["wireframe"], tier='wireframe', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"wireframe": result}

def router_after_orch(state: WorkflowState):
    if state.orchestrator.status == "degraded" or not state.orchestrator.payload:
        return END
    return "frame"

def router_after_frame(state: WorkflowState):
    if state.frame.status == "degraded" or not state.frame.payload:
        return END
    return "research"

# --- Build Graph ---
builder = StateGraph(WorkflowState)
builder.add_node("orchestrator", orchestrator_node)
builder.add_node("frame", frame_node)
builder.add_node("research", research_node)
builder.add_node("synthesis", synthesis_node)
builder.add_node("structure", structure_node)
builder.add_node("wireframe", wireframe_node)

builder.add_edge(START, "orchestrator")
builder.add_conditional_edges("orchestrator", router_after_orch)
builder.add_conditional_edges("frame", router_after_frame)
builder.add_edge("research", "synthesis")
builder.add_edge("synthesis", "structure")
builder.add_edge("structure", END)

workflow_app = builder.compile()
