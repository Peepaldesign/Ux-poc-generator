from typing import List, Optional, Literal, Union, Dict, Any
from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# ORCHESTRATOR
# -------------------------------------------------------------------
class Signals(BaseModel):
    named_product: Optional[str] = None
    named_market_domain: Optional[str] = None
    product_count: Literal["0", "1", "2+"] = "0"
    current_platforms: List[str] = Field(default_factory=list)
    target_platforms: List[str] = Field(default_factory=list)
    problem_signals: List[str] = Field(default_factory=list)
    metric_signals: List[str] = Field(default_factory=list)
    change_scope: Literal["none", "cosmetic", "structural", "full_overhaul"] = "none"
    action_verbs: List[str] = Field(default_factory=list)

class OrchestratorOutput(BaseModel):
    signals: Signals
    existence: Literal["greenfield", "brownfield"]
    objective: Literal["create", "extend", "transform", "improve", "grow", "foundation"]
    primary_scenario: str
    secondary_scenario: Optional[str] = None
    confidence: float
    needs_disambiguation: bool
    clarifying_question: Optional[str] = None
    rationale: str

# -------------------------------------------------------------------
# AGENT 01: Brief Framing
# -------------------------------------------------------------------
class A01BriefFramingOutput(BaseModel):
    problem_statement: str
    assumptions: List[str]
    constraints: List[str]
    unknowns: List[str]
    open_questions: List[str]
    handoff_scenario: str
    handoff_sharpest_unknown: str

# -------------------------------------------------------------------
# AGENT 02: Business Goals
# -------------------------------------------------------------------
class GoalHierarchyItem(BaseModel):
    goal: str
    level: Literal["primary", "supporting"]
    assumption: bool

class StakeholderMapItem(BaseModel):
    role: str
    likely_interest: str
    assumption: bool

class A02BusinessGoalsOutput(BaseModel):
    goal_hierarchy: List[GoalHierarchyItem]
    success_definition: str
    stakeholder_map: List[StakeholderMapItem]
    interview_guide: List[str]
    handoff_top_business_goal: str

# -------------------------------------------------------------------
# AGENT 03: Domain/Market Research
# -------------------------------------------------------------------
class TrendItem(BaseModel):
    trend: str
    source: str

class RegulatoryItem(BaseModel):
    constraint: str
    implication_for_ux: str
    source: str

class KeyPlayerItem(BaseModel):
    name: str
    url: str
    why_relevant: str

class A03DomainMarketResearchOutput(BaseModel):
    market_overview: str
    trends: List[TrendItem]
    regulatory: List[RegulatoryItem]
    conventions: List[str]
    key_players: List[KeyPlayerItem]
    citations: List[str]

# -------------------------------------------------------------------
# AGENT 04: Competitive Analysis
# -------------------------------------------------------------------
class FeatureMatrixItem(BaseModel):
    feature: str
    by_competitor: Dict[str, Literal["yes", "no", "partial"]]

class PatternInventoryItem(BaseModel):
    pattern: str
    where_seen: List[str]
    assessment: str

class TeardownNotesItem(BaseModel):
    competitor: str
    observation: str
    source: str

class GapItem(BaseModel):
    gap: str
    evidence: str
    opportunity_size: Literal["high", "med", "low"]

class A04CompetitiveAnalysisOutput(BaseModel):
    feature_matrix: List[FeatureMatrixItem]
    pattern_inventory: List[PatternInventoryItem]
    teardown_notes: List[TeardownNotesItem]
    gaps: List[GapItem]
    handoff_top_3_gaps: List[str]

# -------------------------------------------------------------------
# AGENT 05: Secondary User Research
# -------------------------------------------------------------------
class PainThemeItem(BaseModel):
    theme: str
    frequency: str
    sources: List[str]
    representative_signal: str

class A05SecondaryUserResearchOutput(BaseModel):
    pain_themes: List[PainThemeItem]

# -------------------------------------------------------------------
# AGENT 06: UX Audit on Competitor Products
# -------------------------------------------------------------------
class CompetitorIssueItem(BaseModel):
    competitor: str
    issue: str
    heuristic: str
    wcag: str
    severity: int
    source: str

class ClientAuditPlaceholder(BaseModel):
    status: Literal["placeholder", "complete"]
    instruction: str

class A06UxAuditOutput(BaseModel):
    competitor_issues: List[CompetitorIssueItem]
    client_audit: ClientAuditPlaceholder

# -------------------------------------------------------------------
# AGENT 07: Persona Building
# -------------------------------------------------------------------
class GroundedGoal(BaseModel):
    goal: str
    grounded_in: str

class GroundedPain(BaseModel):
    pain: str
    grounded_in: str

class PersonaItem(BaseModel):
    name: str
    role: str
    context: str
    goals: List[GroundedGoal]
    pains: List[GroundedPain]
    provisional: bool

class A07PersonaBuildingOutput(BaseModel):
    personas: List[PersonaItem]
    status: str
    grounding: str
    open_questions: List[str]

# -------------------------------------------------------------------
# AGENT 08: JTBD Framework / User Need
# -------------------------------------------------------------------
class JobItem(BaseModel):
    job_statement: str
    needs: List[str]
    pains: List[str]
    gains: List[str]
    priority: Literal["high", "med", "low"]
    grounded_in: List[str]

class A08JTBDOutput(BaseModel):
    jobs: List[JobItem]

# -------------------------------------------------------------------
# AGENT 09: Journey Mapping
# -------------------------------------------------------------------
class StageItem(BaseModel):
    stage: str
    action: str
    touchpoint: str
    emotion: str
    pain: str
    opportunity: str
    grounded_in: str

class JourneyItem(BaseModel):
    persona: str
    type: Literal["current", "future"]
    stages: List[StageItem]

class A09JourneyMappingOutput(BaseModel):
    journeys: List[JourneyItem]
    status: str
    handoff_highest_friction_stage: str

# -------------------------------------------------------------------
# AGENT 10: Key Task Flows
# -------------------------------------------------------------------
class FlowNode(BaseModel):
    id: str
    label: str
    type: Literal["screen", "action", "system"]

class FlowDecision(BaseModel):
    at_node: str
    condition: str
    branches: List[str]

class FlowItem(BaseModel):
    name: str
    serves_job: str
    nodes: List[FlowNode]
    decisions: List[FlowDecision]
    states: List[str]

class A10KeyTaskFlowsOutput(BaseModel):
    flows: List[FlowItem]
    handoff_implied_screens: List[str]

# -------------------------------------------------------------------
# AGENT 11: Information Architecture
# -------------------------------------------------------------------
class SitemapNode(BaseModel):
    node: str
    children: List[str]

class NavItem(BaseModel):
    nav_item: str
    is_destination: bool
    screens: List[str]

class ContentGroup(BaseModel):
    group: str
    rationale: str

class A11IAOutput(BaseModel):
    sitemap: List[SitemapNode]
    nav_model: List[NavItem]
    content_groups: List[ContentGroup]
    handoff_uncertain_nav_items: List[str]

# -------------------------------------------------------------------
# AGENT 12: Feature Prioritization
# -------------------------------------------------------------------
class RICECalc(BaseModel):
    reach: str
    impact: str
    confidence: str
    effort: str
    score: str

class BacklogItem(BaseModel):
    item: str
    moscow: Literal["must", "should", "could", "wont"]
    rice: RICECalc
    serves_goal: str
    grounded_in: List[str]

class A12FeaturePrioritizationOutput(BaseModel):
    backlog: List[BacklogItem]

# -------------------------------------------------------------------
# AGENT 13: Success Matrix
# -------------------------------------------------------------------
class MetricItem(BaseModel):
    business_goal: str
    metric: str
    framework: Literal["HEART", "KPI"]
    measures_job: str
    target: str

class A13SuccessMatrixOutput(BaseModel):
    metrics_tree: List[MetricItem]

# -------------------------------------------------------------------
# GRAPH STATE
# -------------------------------------------------------------------
from typing import Generic, TypeVar

T = TypeVar('T')

class AgentResult(BaseModel, Generic[T]):
    status: Literal["success", "degraded", "skipped", "pending"] = "pending"
    payload: Optional[T] = None
    fallback_instruction: Optional[str] = None
    error_message: Optional[str] = None

class WorkflowState(BaseModel):
    brief: str = ""
    job_id: str = ""
    
    orchestrator: AgentResult[OrchestratorOutput] = AgentResult()
    a01_brief_framing: AgentResult[A01BriefFramingOutput] = AgentResult()
    a02_business_goals: AgentResult[A02BusinessGoalsOutput] = AgentResult()
    a03_domain_market: AgentResult[A03DomainMarketResearchOutput] = AgentResult()
    a04_competitive: AgentResult[A04CompetitiveAnalysisOutput] = AgentResult()
    a05_secondary_research: AgentResult[A05SecondaryUserResearchOutput] = AgentResult()
    a06_ux_audit: AgentResult[A06UxAuditOutput] = AgentResult()
    a07_persona: AgentResult[A07PersonaBuildingOutput] = AgentResult()
    a08_jtbd: AgentResult[A08JTBDOutput] = AgentResult()
    a09_journey: AgentResult[A09JourneyMappingOutput] = AgentResult()
    a10_task_flows: AgentResult[A10KeyTaskFlowsOutput] = AgentResult()
    a11_ia: AgentResult[A11IAOutput] = AgentResult()
    a12_prioritization: AgentResult[A12FeaturePrioritizationOutput] = AgentResult()
    a13_success_matrix: AgentResult[A13SuccessMatrixOutput] = AgentResult()
