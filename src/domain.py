"""Typed domain contracts shared by ParkSense services and API handlers."""
from datetime import datetime
from typing import Any, Literal, Optional
from pydantic import BaseModel, Field


class DataLineage(BaseModel):
    dataset: str
    dataset_max_timestamp: datetime
    computed_at: datetime
    formula_version: str
    model_version: Optional[str] = None
    measured: bool
    caveat: Optional[str] = None


class HotspotRecord(BaseModel):
    hotspot_id: str
    locality_name: str
    police_station: Optional[str]
    centroid_lat: float
    centroid_lon: float
    violation_count: int
    peak_hour: int
    trend_direction: Literal["increasing", "stable", "decreasing", "insufficient_data"]
    density_score: float = Field(ge=0, le=100)
    recency_score: float = Field(ge=0, le=100)
    frequency_score: float = Field(ge=0, le=100)
    recurrence_score: float = Field(ge=0, le=100)
    severity_score: float = Field(ge=0, le=100)
    risk_score: float = Field(ge=0, le=100)
    risk_level: Literal["Low", "Moderate", "High", "Critical"]
    confidence_score: float = Field(ge=0, le=1, default=1.0)
    risk_breakdown: dict[str, float] = Field(default_factory=lambda: {})
    lineage: DataLineage


class ForecastPoint(BaseModel):
    horizon_hours: Literal[1, 6, 24, 168]
    expected_violations: float
    lower_bound: float
    upper_bound: float
    confidence: float = Field(ge=0, le=1)


class ForecastResponse(BaseModel):
    locality_name: str
    forecast_origin: datetime
    status: Literal["modelled", "insufficient_data"]
    points: list[ForecastPoint]
    evaluation: dict[str, Any]
    lineage: DataLineage


class ImpactEstimate(BaseModel):
    hotspot_id: str
    label: Literal["Estimated Economic Impact"] = "Estimated Economic Impact"
    amount_inr: float
    lower_bound_inr: float
    upper_bound_inr: float
    fuel_waste_inr: float = 0.0
    co2_emissions_kg: float = 0.0
    pedestrian_safety_index: float = 0.0
    impact_breakdown: dict[str, float] = Field(default_factory=lambda: {})
    confidence_score: float = Field(ge=0, le=1, default=1.0)
    inputs: dict[str, float]
    formula: str
    lineage: DataLineage


class DispatchRecommendation(BaseModel):
    hotspot_id: str
    enforcement_level: Literal["Low Enforcement", "Moderate Enforcement", "High Enforcement", "Critical Enforcement"]
    actions: list[str]
    reasons: list[str]
    rule_version: str
    is_unit_assignment: bool = False
    caveat: str = "This is a resource-level recommendation, not a patrol-unit assignment. Live unit availability is unavailable."
    recommended_officers: int = 1
    recommended_barricades: int = 0
    recommended_tow_trucks: int = 0
    suggested_response: Literal["Immediate", "Priority", "Routine"] = "Routine"


class CopilotRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    language: Literal["en", "kn", "hi"] = "en"
    context: dict[str, Any] = Field(default_factory=dict)


class CopilotResponse(BaseModel):
    answer: str
    confidence: float = Field(ge=0, le=1)
    status: Literal["answered", "insufficient_data", "unsupported_intent"]
    facts: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    as_of: Optional[datetime] = None


class AlertRecord(BaseModel):
    alert_id: str
    hotspot_id: str
    severity: str
    message: str
    timestamp: datetime


class HotspotResponseItem(BaseModel):
    id: str
    name: str
    lat: float
    lng: float
    riskScore: float
    violations: int
    congestionLevel: str
    status: str
    trend: str
    cluster_id: str
    economicImpact: Optional[float] = None
    confidence: Optional[float] = 1.0


class StatsResponse(BaseModel):
    totalViolations: int
    avgRiskScore: float
    criticalZones: int
    activeOfficers: int
    timestamp: str
    city: str
    revenueLeakagePrevented: float = 0.0
    avgResponseTimeMins: float = 0.0
    congestionReductionPct: float = 0.0
    hotspotsMitigated: int = 0


class ForecastResponseItem(BaseModel):
    hotspot_id: str
    hotspot_name: str
    hour_offset: int
    predictedRisk: float
    predictedViolations: float
    confidence: float


class HistoricalBucket(BaseModel):
    label: str
    violations: int


class HistoricalJunction(BaseModel):
    name: str
    violations: int
    risk: float


class HistoricalResponse(BaseModel):
    range: str
    bucketLabel: str
    buckets: list[HistoricalBucket]
    topJunctions: list[HistoricalJunction]
    totalViolations: int = 0
    avgRisk: float = 0.0
    peakHour: int = 0
    peakDay: str = "N/A"
    hotspotCount: int = 0


class AlertItem(BaseModel):
    id: str
    type: str  # 'Critical' | 'Warning' | 'Info'
    junction_id: str
    junction_name: str
    message: str
    timestamp: str
    resolved: bool
    current_risk: float = 0.0
    predicted_risk: float = 0.0
    eta_minutes: float = 0.0
    recommended_officers: int = 0
    state: str = "New"


class IncidentInjection(BaseModel):
    locality_name: str
    incident_type: Literal["Accident", "Road Closure", "Festival"]
    severity: Literal["Low", "Medium", "High", "Critical"]
    duration_minutes: int


class AnalyticsResponse(BaseModel):
    violations_by_hour: list[int]
    risk_distribution: dict[str, int]
    top_junctions: list[dict[str, Any]]
    weekly_trend: list[dict[str, Any]]


class ViolationIngest(BaseModel):
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    violation_type: str = "WRONG PARKING"
    vehicle_type: str = "UNKNOWN"
    severity: float = Field(default=2.0, ge=0, le=5)
    junction_name: str = ""
    police_station: str = ""
    occurred_at: Optional[str] = None


class AuditEntry(BaseModel):
    id: int
    timestamp: str
    username: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    details: Optional[str] = None


class DispatchSendRequest(BaseModel):
    hotspot_id: str
    channel: Literal["webhook", "whatsapp", "sms"] = "webhook"
    language: str = "en"


class FeedbackRequest(BaseModel):
    hotspot_id: str
    hotspot_name: str = ""
    feedback_text: str = Field(min_length=1, max_length=1000)

