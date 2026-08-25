"""Pydantic schemas for water body endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class WaterBodyResponse(BaseModel):
    """Single water body in list view."""
    id: str
    name: str
    latitude: float
    longitude: float
    type: str
    city: Optional[str]
    risk_level: str
    risk_score: float
    total_reports: int
    reports_last_7_days: int = 0
    last_report_at: Optional[datetime]


class ContaminationBreakdown(BaseModel):
    industrial_discharge: int = 0
    sewage: int = 0
    algal_bloom: int = 0
    solid_waste: int = 0
    agricultural_runoff: int = 0
    fish_kill: int = 0
    foam: int = 0
    oil_spill: int = 0
    others: int = 0


class LatestAnalysis(BaseModel):
    forel_ule_index: Optional[int]
    algae_percentage: Optional[float]
    foam_detected: Optional[bool]
    foam_coverage_percentage: Optional[float]
    turbidity_score: Optional[float]
    oil_sheen_detected: Optional[bool]
    color_abnormality_score: Optional[float]
    debris_detected: Optional[bool]


class WaterBodyDetailResponse(BaseModel):
    """Detailed water body view."""
    id: str
    name: str
    latitude: float
    longitude: float
    type: str
    city: Optional[str]
    state: Optional[str]
    risk_level: str
    risk_score: float
    total_reports: int
    reports_last_7_days: int = 0
    latest_analysis: Optional[LatestAnalysis]
    contamination_breakdown: ContaminationBreakdown
    last_report_at: Optional[datetime]
    created_at: datetime


class WaterBodyListResponse(BaseModel):
    """Response for GET /water-bodies."""
    count: int
    water_bodies: list[WaterBodyResponse]


class RiskHistoryEntry(BaseModel):
    date: str
    risk_score: float
    risk_level: str
    report_count: Optional[int]
    avg_algae: Optional[float]
    avg_turbidity: Optional[float]


class RiskHistoryResponse(BaseModel):
    water_body_id: str
    water_body_name: str
    history: list[RiskHistoryEntry]
