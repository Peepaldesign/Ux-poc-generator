import os
import json
import asyncio
from langgraph.graph import StateGraph, START, END
from backend.models import (
    WorkflowState, AgentResult, OrchestratorOutput, 
    FramePhaseOutput, ResearchPhaseOutput, SynthesisPhaseOutput, 
    StructurePhaseOutput, VisualDesignSystem, HiFiScreen
)
from backend.prompts import (
    ORCHESTRATOR_PROMPT, FRAME_PROMPT, RESEARCH_PROMPT, 
    SYNTHESIS_PROMPT, STRUCTURE_PROMPT, DESIGN_SYSTEM_PROMPT, HIFI_PROMPT, FALLBACKS
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

async def design_system_node(state: WorkflowState):
    print("Running Design System Phase...")
    ds_context = {}
    if state.synthesis.payload:
        dump = state.synthesis.payload.model_dump()
        ds_context["personas"] = dump.get("personas", [])[:2]  # top 2 personas for context
    if state.structure.payload:
        dump = state.structure.payload.model_dump()
        ds_context["sitemap"] = dump.get("sitemap", [])
    if state.research.payload:
        ds_context["market_overview"] = state.research.payload.market_overview[:200] if state.research.payload.market_overview else ""
    if state.frame.payload:
        ds_context["problem_statement"] = state.frame.payload.problem_statement
    
    header = f"SOURCE BRIEF (authoritative — produce content ONLY about this; never substitute another domain):\n{state.brief}\n\nSUPPLEMENTARY CONTEXT:\n"
    ctx = header + json.dumps(ds_context, separators=(',', ':'))
    result = await call_agent_with_degradation(
        DESIGN_SYSTEM_PROMPT, ctx, VisualDesignSystem, FALLBACKS["design_system"], tier='hifi', raw_brief=state.brief
    )
    await asyncio.sleep(RPM_SLEEP_SECONDS)
    return {"design_system": result}

async def hifi_screen_node(state: WorkflowState, screen_ref: str, device: str = "desktop"):
    """Generate a single hi-fi screen on demand. Called from the API, not from the graph."""
    print(f"Running Hi-Fi Screen for: {screen_ref} ({device})...")
    
    # Build screen spec from structure
    screen_spec = {"name": screen_ref, "device": device}
    if state.structure.payload:
        for flow in state.structure.payload.flows:
            for node in flow.nodes:
                if node.type == "screen" and (node.label.lower() in screen_ref.lower() or screen_ref.lower() in node.label.lower()):
                    screen_spec["purpose"] = f"Screen in flow '{flow.name}' serving job '{flow.serves_job}'"
                    break
    if "purpose" not in screen_spec:
        screen_spec["purpose"] = f"Application screen: {screen_ref}"
    
    # Build context with design system tokens + screen spec
    ds_json = state.design_system.payload.model_dump_json() if state.design_system.payload else "{}"
    ctx = f"VISUAL DESIGN SYSTEM:\n{ds_json}\n\nTARGET DEVICE: {device}\n\nSCREEN SPECIFICATION:\n{json.dumps(screen_spec, separators=(',', ':'))}\n\nBRIEF: {state.brief[:300]}"
    
    result = await call_agent_with_degradation(
        HIFI_PROMPT, ctx, HiFiScreen, FALLBACKS["hifi"], tier='hifi', raw_brief=state.brief
    )
    return result

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
builder.add_node("design_system", design_system_node)

builder.add_edge(START, "orchestrator")
builder.add_conditional_edges("orchestrator", router_after_orch)
builder.add_conditional_edges("frame", router_after_frame)
builder.add_edge("research", "synthesis")
builder.add_edge("synthesis", "structure")
builder.add_edge("structure", "design_system")
builder.add_edge("design_system", END)

workflow_app = builder.compile()
