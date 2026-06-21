import uuid
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, ForeignKey, Table, Enum, Numeric, LargeBinary
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

class PoliceStation(Base):
    __tablename__ = 'police_station'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    external_code = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    location = Column(String)  # Stored as string represent of geography or coordinates
    jurisdiction = Column(String)
    officer_capacity = Column(Integer)
    towing_capacity = Column(Integer)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

class Location(Base):
    __tablename__ = 'location'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    locality_name = Column(String, nullable=False)
    normalized_address = Column(String)
    point = Column(String)
    boundary = Column(String)
    h3_cell = Column(Integer)
    police_station_id = Column(UUID(as_uuid=True), ForeignKey('police_station.id'))
    source = Column(String, nullable=False)
    source_confidence = Column(Float)

class Violation(Base):
    __tablename__ = 'violation'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id = Column(String, nullable=False)
    source_system = Column(String, nullable=False)
    occurred_at = Column(DateTime, nullable=False)
    received_at = Column(DateTime, default=datetime.utcnow)
    location_id = Column(UUID(as_uuid=True), ForeignKey('location.id'))
    position = Column(String, nullable=False)
    violation_type = Column(String, nullable=False)
    vehicle_type = Column(String)
    vehicle_token = Column(String)
    severity = Column(Integer, nullable=False)
    validation_status = Column(String, nullable=False)
    evidence_uri = Column(String)
    evidence_hash = Column(String)
    quality_score = Column(Float)
    attributes = Column(JSONB, default=dict)

class Hotspot(Base):
    __tablename__ = 'hotspot'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), nullable=False)
    algorithm = Column(String, nullable=False)
    algorithm_version = Column(String, nullable=False)
    parameters = Column(JSONB, nullable=False)
    locality_id = Column(UUID(as_uuid=True), ForeignKey('location.id'))
    police_station_id = Column(UUID(as_uuid=True), ForeignKey('police_station.id'))
    centroid = Column(String, nullable=False)
    hull = Column(String)
    window_start = Column(DateTime, nullable=False)
    window_end = Column(DateTime, nullable=False)
    violation_count = Column(Integer, nullable=False)
    peak_hour = Column(Integer)
    trend_direction = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

class RiskAssessment(Base):
    __tablename__ = 'risk_assessment'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotspot_id = Column(UUID(as_uuid=True), ForeignKey('hotspot.id'), nullable=False)
    assessed_at = Column(DateTime, nullable=False)
    density_score = Column(Float, nullable=False)
    recency_score = Column(Float, nullable=False)
    frequency_score = Column(Float, nullable=False)
    recurrence_score = Column(Float, nullable=False)
    severity_score = Column(Float, nullable=False)
    risk_score = Column(Float, nullable=False)
    risk_level = Column(String, nullable=False)
    formula_version = Column(String, nullable=False)
    inputs = Column(JSONB, nullable=False)

class Forecast(Base):
    __tablename__ = 'forecast'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    locality_id = Column(UUID(as_uuid=True), ForeignKey('location.id'), nullable=False)
    generated_at = Column(DateTime, nullable=False)
    forecast_origin = Column(DateTime, nullable=False)
    horizon_hours = Column(Integer, nullable=False)
    expected_violations = Column(Float)
    lower_bound = Column(Float)
    upper_bound = Column(Float)
    confidence = Column(Float)
    model_name = Column(String, nullable=False)
    model_version = Column(String, nullable=False)
    status = Column(String, nullable=False)
    evaluation = Column(JSONB, nullable=False)
    features_snapshot = Column(JSONB, nullable=False)

class DispatchRecommendation(Base):
    __tablename__ = 'dispatch_recommendation'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotspot_id = Column(UUID(as_uuid=True), ForeignKey('hotspot.id'), nullable=False)
    forecast_id = Column(UUID(as_uuid=True), ForeignKey('forecast.id'))
    created_at = Column(DateTime, nullable=False)
    level = Column(String, nullable=False)
    actions = Column(JSONB, nullable=False)
    reasons = Column(JSONB, nullable=False)
    rule_version = Column(String, nullable=False)
    expires_at = Column(DateTime)
    accepted_at = Column(DateTime)
    accepted_by = Column(UUID(as_uuid=True))
    override_reason = Column(String)

class UserQuery(Base):
    __tablename__ = 'user_query'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), nullable=False)
    jurisdiction_station_id = Column(UUID(as_uuid=True), ForeignKey('police_station.id'))
    question = Column(String, nullable=False)
    language = Column(String, nullable=False)
    parsed_intent = Column(String)
    entities = Column(JSONB, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)

class AIReport(Base):
    __tablename__ = 'ai_report'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_id = Column(UUID(as_uuid=True), ForeignKey('user_query.id'), nullable=False)
    answer = Column(String, nullable=False)
    status = Column(String, nullable=False)
    confidence = Column(Float, nullable=False)
    facts = Column(JSONB, nullable=False)
    source_refs = Column(JSONB, nullable=False)
    model_name = Column(String)
    model_version = Column(String)
    prompt_version = Column(String, nullable=False)
    generated_at = Column(DateTime, default=datetime.utcnow)

class AnalyticsAudit(Base):
    __tablename__ = 'analytics_audit'
    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_type = Column(String, nullable=False)
    entity_id = Column(UUID(as_uuid=True))
    operation = Column(String, nullable=False)
    dataset_version = Column(String, nullable=False)
    code_version = Column(String, nullable=False)
    parameters = Column(JSONB, nullable=False)
    result_hash = Column(String, nullable=False)
    computed_at = Column(DateTime, default=datetime.utcnow)
