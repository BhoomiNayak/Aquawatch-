"""Pydantic schemas for CV analysis results."""

from pydantic import BaseModel


class ForelUleResult(BaseModel):
    fu_index: int
    fu_color_name: str
    fu_quality_score: float
    dominant_rgb: list[int]


class AlgaeResult(BaseModel):
    algae_percentage: float
    severity: str


class FoamResult(BaseModel):
    foam_detected: bool
    foam_coverage_percentage: float
    foam_patch_count: int


class TurbidityResult(BaseModel):
    turbidity_score: float
    laplacian_variance: float
    clarity_description: str


class OilSheenResult(BaseModel):
    oil_sheen_detected: bool
    oil_coverage_percentage: float
    confidence: str


class ColorAbnormalityResult(BaseModel):
    color_abnormality_score: float
    color_uniformity: float
    unnatural_color_percentage: float
    description: str


class DebrisResult(BaseModel):
    debris_detected: bool
    contour_density: float
    significant_objects: int
    description: str


class RiskBreakdown(BaseModel):
    algae_component: float
    foam_component: float
    turbidity_component: float
    forel_ule_component: float
    oil_sheen_component: float
    color_abnormality_component: float
    debris_component: float


class RiskResult(BaseModel):
    composite_score: float
    risk_level: str
    breakdown: RiskBreakdown


class CVAnalysisResult(BaseModel):
    forel_ule: ForelUleResult
    algae: AlgaeResult
    foam: FoamResult
    turbidity: TurbidityResult
    oil_sheen: OilSheenResult
    color_abnormality: ColorAbnormalityResult
    surface_debris: DebrisResult
