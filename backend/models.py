from typing import List, Optional, Literal, Union, Dict, Any, Generic, TypeVar
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
    thinking_process: str = Field(description="Step-by-step reasoning before generating the final output", default="")
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
# SUB-SCHEMAS
# -------------------------------------------------------------------
class GoalHierarchyItem(BaseModel):
    goal: str
    level: Literal["primary", "supporting"]
    assumption: bool

class StakeholderMapItem(BaseModel):
    role: str
    likely_interest: str
    assumption: bool

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

class PainThemeItem(BaseModel):
    theme: str
    frequency: str
    sources: List[str]
    representative_signal: str

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

class JobItem(BaseModel):
    job_statement: str
    needs: List[str]
    pains: List[str]
    gains: List[str]
    priority: Literal["high", "med", "low"]
    grounded_in: List[str]

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

class MetricItem(BaseModel):
    business_goal: str
    metric: str
    framework: Literal["HEART", "KPI"]
    measures_job: str
    target: str

# -------------------------------------------------------------------
# PHASE MODELS
# -------------------------------------------------------------------
class FramePhaseOutput(BaseModel):
    problem_statement: str
    assumptions: List[str]
    constraints: List[str]
    unknowns: List[str]
    open_questions: List[str]
    handoff_scenario: str
    handoff_sharpest_unknown: str
    goal_hierarchy: List[GoalHierarchyItem]
    success_definition: str
    stakeholder_map: List[StakeholderMapItem]
    interview_guide: List[str]
    handoff_top_business_goal: str

class ResearchPhaseOutput(BaseModel):
    market_overview: str
    trends: List[TrendItem]
    regulatory: List[RegulatoryItem]
    conventions: List[str]
    key_players: List[KeyPlayerItem]
    citations: List[str]
    feature_matrix: List[FeatureMatrixItem]
    pattern_inventory: List[PatternInventoryItem]
    teardown_notes: List[TeardownNotesItem]
    gaps: List[GapItem]
    handoff_top_3_gaps: List[str]
    pain_themes: List[PainThemeItem]
    competitor_issues: List[CompetitorIssueItem]
    client_audit: ClientAuditPlaceholder

class SynthesisPhaseOutput(BaseModel):
    personas: List[PersonaItem]
    persona_status: str
    persona_grounding: str
    persona_open_questions: List[str]
    jobs: List[JobItem]
    journeys: List[JourneyItem]
    journey_status: str
    handoff_highest_friction_stage: str

class StructurePhaseOutput(BaseModel):
    flows: List[FlowItem]
    handoff_implied_screens: List[str]
    sitemap: List[SitemapNode]
    nav_model: List[NavItem]
    content_groups: List[ContentGroup]
    handoff_uncertain_nav_items: List[str]
    backlog: List[BacklogItem]
    metrics_tree: List[MetricItem]

# -------------------------------------------------------------------
# WIREFRAME MODELS
# -------------------------------------------------------------------
class WireframeRegion(BaseModel):
    type: Literal['header','nav','sidebar','content','list','form','card','cta','footer']
    label: str
    items: List[str] = Field(default_factory=list)

class WireframeScreen(BaseModel):
    name: str
    route: str
    purpose: str
    regions: List[WireframeRegion]

class WireframeOutput(BaseModel):
    screens: List[WireframeScreen]

# -------------------------------------------------------------------
# GRAPH STATE
# -------------------------------------------------------------------
T = TypeVar('T')

class AgentResult(BaseModel, Generic[T]):
    status: Literal["success", "degraded", "skipped", "pending"] = "pending"
    payload: Optional[T] = None
    fallback_instruction: Optional[str] = None
    error_message: Optional[str] = None

class WorkflowState(BaseModel):
    brief: str = ""
    job_id: str = ""
    cancelled: bool = False
    
    orchestrator: AgentResult[OrchestratorOutput] = AgentResult()
    frame: AgentResult[FramePhaseOutput] = AgentResult()
    research: AgentResult[ResearchPhaseOutput] = AgentResult()
    synthesis: AgentResult[SynthesisPhaseOutput] = AgentResult()
    structure: AgentResult[StructurePhaseOutput] = AgentResult()
    wireframe: AgentResult[WireframeOutput] = AgentResult()
