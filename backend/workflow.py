import os
import json
from langgraph.graph import StateGraph, START, END
from backend.models import (
    WorkflowState, AgentResult, OrchestratorOutput, A01BriefFramingOutput,
    A02BusinessGoalsOutput, A03DomainMarketResearchOutput, A04CompetitiveAnalysisOutput,
    A05SecondaryUserResearchOutput, A06UxAuditOutput, A07PersonaBuildingOutput,
    A08JTBDOutput, A09JourneyMappingOutput, A10KeyTaskFlowsOutput, A11IAOutput,
    A12FeaturePrioritizationOutput, A13SuccessMatrixOutput, A14ReportCompilerOutput
)
from backend.prompts import (
    ORCHESTRATOR_PROMPT, A01_PROMPT, A02_PROMPT, A03_PROMPT, A04_PROMPT,
    A05_PROMPT, A06_PROMPT, A07_PROMPT, A08_PROMPT, A09_PROMPT, A10_PROMPT,
    A11_PROMPT, A12_PROMPT, A13_PROMPT, A14_PROMPT, FALLBACKS
)
from backend.degradation import call_agent_with_degradation

# Matrix mapping Scenario string to a list of agent keys to SKIP.
# If a scenario is missing, assume no skips (though the 10 cover everything).
SKIP_MAP = {
    "New product (0->1)": ["a06_ux_audit"],
    "Feature addition": ["a03_domain_market", "a07_persona", "a11_ia"],
    "Multi-platform extension": ["a03_domain_market", "a07_persona"],
    "Redesign / Revamp": ["a03_domain_market"],
    "Consolidation / migration": ["a03_domain_market", "a04_competitive"],
    "Usability & accessibility remediation": ["a03_domain_market", "a04_competitive", "a07_persona", "a08_jtbd", "a11_ia", "a12_prioritization"],
    "Onboarding / activation": ["a03_domain_market", "a11_ia"],
    "Conversion / funnel optimization": ["a03_domain_market", "a07_persona", "a11_ia"],
    "Retention / engagement": ["a03_domain_market", "a04_competitive", "a11_ia"],
    "Design system creation": ["a03_domain_market", "a04_competitive", "a05_secondary_research", "a07_persona", "a08_jtbd", "a09_journey", "a10_task_flows", "a12_prioritization"]
}

def _should_skip(state: WorkflowState, agent_key: str) -> bool:
    if state.orchestrator.status != "success" or not state.orchestrator.payload:
        return False # Safest to not skip if orchestrator failed
    scenario = state.orchestrator.payload.primary_scenario
    # We do a loose match in case the LLM outputs slight variations
    for key, skips in SKIP_MAP.items():
        if key.lower() in scenario.lower():
            return agent_key in skips
    return False

def _get_upstream_context(state: WorkflowState, fields: list) -> str:
    """Helper to dump relevant state for the LLM input"""
    context = {}
    for f in fields:
        attr = getattr(state, f, None)
        if attr and attr.payload:
            context[f] = attr.payload.model_dump()
    return json.dumps(context, indent=2)

# --- Nodes ---

def orchestrator_node(state: WorkflowState):
    print("Running Orchestrator...")
    result = call_agent_with_degradation(
        ORCHESTRATOR_PROMPT,
        state.brief,
        OrchestratorOutput
    )
    return {"orchestrator": result}

def a01_node(state: WorkflowState):
    if _should_skip(state, "a01_brief_framing"):
        return {"a01_brief_framing": AgentResult(status="skipped")}
    print("Running A01...")
    ctx = _get_upstream_context(state, ["orchestrator"]) + f"\nRaw Brief: {state.brief}"
    result = call_agent_with_degradation(A01_PROMPT, ctx, A01BriefFramingOutput, FALLBACKS["a01"])
    return {"a01_brief_framing": result}

def a02_node(state: WorkflowState):
    if _should_skip(state, "a02_business_goals"):
        return {"a02_business_goals": AgentResult(status="skipped")}
    print("Running A02...")
    ctx = _get_upstream_context(state, ["a01_brief_framing"])
    result = call_agent_with_degradation(A02_PROMPT, ctx, A02BusinessGoalsOutput, FALLBACKS["a02"])
    return {"a02_business_goals": result}

def a03_node(state: WorkflowState):
    if _should_skip(state, "a03_domain_market"):
        return {"a03_domain_market": AgentResult(status="skipped")}
    print("Running A03...")
    ctx = _get_upstream_context(state, ["orchestrator"])
    result = call_agent_with_degradation(A03_PROMPT, ctx, A03DomainMarketResearchOutput, FALLBACKS["a03"])
    return {"a03_domain_market": result}

def a04_node(state: WorkflowState):
    if _should_skip(state, "a04_competitive"):
        return {"a04_competitive": AgentResult(status="skipped")}
    print("Running A04...")
    ctx = _get_upstream_context(state, ["a01_brief_framing", "a03_domain_market"])
    result = call_agent_with_degradation(A04_PROMPT, ctx, A04CompetitiveAnalysisOutput, FALLBACKS["a04"])
    return {"a04_competitive": result}

def a05_node(state: WorkflowState):
    if _should_skip(state, "a05_secondary_research"):
        return {"a05_secondary_research": AgentResult(status="skipped")}
    print("Running A05...")
    ctx = _get_upstream_context(state, ["a03_domain_market", "a04_competitive"])
    result = call_agent_with_degradation(A05_PROMPT, ctx, A05SecondaryUserResearchOutput, FALLBACKS["a05"])
    return {"a05_secondary_research": result}

def a06_node(state: WorkflowState):
    if _should_skip(state, "a06_ux_audit"):
        return {"a06_ux_audit": AgentResult(status="skipped")}
    print("Running A06...")
    ctx = _get_upstream_context(state, ["a03_domain_market", "a04_competitive"])
    result = call_agent_with_degradation(A06_PROMPT, ctx, A06UxAuditOutput, FALLBACKS["a06"])
    return {"a06_ux_audit": result}

def a07_node(state: WorkflowState):
    if _should_skip(state, "a07_persona"):
        return {"a07_persona": AgentResult(status="skipped")}
    print("Running A07...")
    ctx = _get_upstream_context(state, ["a03_domain_market", "a05_secondary_research", "a06_ux_audit"])
    result = call_agent_with_degradation(A07_PROMPT, ctx, A07PersonaBuildingOutput, FALLBACKS["a07"])
    return {"a07_persona": result}

def a08_node(state: WorkflowState):
    if _should_skip(state, "a08_jtbd"):
        return {"a08_jtbd": AgentResult(status="skipped")}
    print("Running A08...")
    ctx = _get_upstream_context(state, ["a04_competitive", "a05_secondary_research", "a07_persona"])
    result = call_agent_with_degradation(A08_PROMPT, ctx, A08JTBDOutput, FALLBACKS["a08"])
    return {"a08_jtbd": result}

def a09_node(state: WorkflowState):
    if _should_skip(state, "a09_journey"):
        return {"a09_journey": AgentResult(status="skipped")}
    print("Running A09...")
    ctx = _get_upstream_context(state, ["a05_secondary_research", "a06_ux_audit", "a07_persona", "a08_jtbd"])
    result = call_agent_with_degradation(A09_PROMPT, ctx, A09JourneyMappingOutput, FALLBACKS["a09"])
    return {"a09_journey": result}

def a10_node(state: WorkflowState):
    if _should_skip(state, "a10_task_flows"):
        return {"a10_task_flows": AgentResult(status="skipped")}
    print("Running A10...")
    ctx = _get_upstream_context(state, ["a04_competitive", "a08_jtbd", "a09_journey"])
    result = call_agent_with_degradation(A10_PROMPT, ctx, A10KeyTaskFlowsOutput, FALLBACKS["a10"])
    return {"a10_task_flows": result}

def a11_node(state: WorkflowState):
    if _should_skip(state, "a11_ia"):
        return {"a11_ia": AgentResult(status="skipped")}
    print("Running A11...")
    ctx = _get_upstream_context(state, ["a04_competitive", "a06_ux_audit", "a08_jtbd", "a10_task_flows"])
    result = call_agent_with_degradation(A11_PROMPT, ctx, A11IAOutput, FALLBACKS["a11"])
    return {"a11_ia": result}

def a12_node(state: WorkflowState):
    if _should_skip(state, "a12_prioritization"):
        return {"a12_prioritization": AgentResult(status="skipped")}
    print("Running A12...")
    ctx = _get_upstream_context(state, ["a02_business_goals", "a04_competitive", "a05_secondary_research", "a08_jtbd"])
    result = call_agent_with_degradation(A12_PROMPT, ctx, A12FeaturePrioritizationOutput, FALLBACKS["a12"])
    return {"a12_prioritization": result}

def a13_node(state: WorkflowState):
    if _should_skip(state, "a13_success_matrix"):
        return {"a13_success_matrix": AgentResult(status="skipped")}
    print("Running A13...")
    ctx = _get_upstream_context(state, ["a02_business_goals", "a08_jtbd", "a12_prioritization"])
    result = call_agent_with_degradation(A13_PROMPT, ctx, A13SuccessMatrixOutput, FALLBACKS["a13"])
    return {"a13_success_matrix": result}

def a14_node(state: WorkflowState):
    # A14 always runs to compile whatever is available.
    print("Running A14 (Report Compiler)...")
    ctx = _get_upstream_context(state, [
        "a01_brief_framing", "a02_business_goals", "a03_domain_market",
        "a04_competitive", "a05_secondary_research", "a06_ux_audit",
        "a07_persona", "a08_jtbd", "a09_journey", "a10_task_flows",
        "a11_ia", "a12_prioritization", "a13_success_matrix"
    ])
    result = call_agent_with_degradation(A14_PROMPT, ctx, A14ReportCompilerOutput, "Unable to compile final report. Please review agent outputs manually.")
    return {"a14_compiler": result}

# --- Build Graph ---
builder = StateGraph(WorkflowState)
builder.add_node("orchestrator", orchestrator_node)
builder.add_node("a01", a01_node)
builder.add_node("a02", a02_node)
builder.add_node("a03", a03_node)
builder.add_node("a04", a04_node)
builder.add_node("a05", a05_node)
builder.add_node("a06", a06_node)
builder.add_node("a07", a07_node)
builder.add_node("a08", a08_node)
builder.add_node("a09", a09_node)
builder.add_node("a10", a10_node)
builder.add_node("a11", a11_node)
builder.add_node("a12", a12_node)
builder.add_node("a13", a13_node)
builder.add_node("a14", a14_node)

builder.add_edge(START, "orchestrator")
builder.add_edge("orchestrator", "a01")
builder.add_edge("a01", "a02")
builder.add_edge("a02", "a03")
builder.add_edge("a03", "a04")
builder.add_edge("a04", "a05")
builder.add_edge("a05", "a06")
builder.add_edge("a06", "a07")
builder.add_edge("a07", "a08")
builder.add_edge("a08", "a09")
builder.add_edge("a09", "a10")
builder.add_edge("a10", "a11")
builder.add_edge("a11", "a12")
builder.add_edge("a12", "a13")
builder.add_edge("a13", "a14")
builder.add_edge("a14", END)

workflow_app = builder.compile()
