"""Pydantic schemas for report endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.analysis import CVAnalysisResult, RiskResult


class ReportCreate(BaseModel):
    """Metadata sent alongside the uploaded image (form fields)."""
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    contamination_type: str = Field(
        ...,
        description="Type of contamination observed",
        examples=["industrial_discharge", "sewage", "algal_bloom", "solid_waste", "others"],
    )
    reporter_name: Optional[str] = Field(None, max_length=100)
    notes: Optional[str] = Field(None, max_length=500)


class WaterBodyMatch(BaseModel):
    id: str
    name: str
    distance_meters: float


class AnalysisResponse(BaseModel):
    """Full response from POST /analyze-water."""
    report_id: str
    water_body: WaterBodyMatch
    analysis: CVAnalysisResult
    risk: RiskResult
    created_at: datetime


class ReportSummary(BaseModel):
    """Short report summary for listing."""
    id: str
    contamination_type: str
    reporter_name: Optional[str]
    notes: Optional[str]
    composite_score: float
    risk_level: str
    forel_ule_index: Optional[int]
    algae_percentage: Optional[float]
    foam_detected: bool
    turbidity_score: Optional[float]
    latitude: float
    longitude: float
    created_at: datetime


class ReportListResponse(BaseModel):
    water_body_id: str
    total: int
    reports: list[ReportSummary]
