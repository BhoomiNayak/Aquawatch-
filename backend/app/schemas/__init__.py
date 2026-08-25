from app.schemas.report import ReportCreate, AnalysisResponse, ReportSummary, ReportListResponse
from app.schemas.water_body import (
    WaterBodyResponse,
    WaterBodyDetailResponse,
    WaterBodyListResponse,
    RiskHistoryEntry,
    RiskHistoryResponse,
)
from app.schemas.analysis import (
    ForelUleResult,
    AlgaeResult,
    FoamResult,
    TurbidityResult,
    OilSheenResult,
    ColorAbnormalityResult,
    DebrisResult,
    RiskResult,
    CVAnalysisResult,
)

__all__ = [
    "ReportCreate",
    "AnalysisResponse",
    "ReportSummary",
    "ReportListResponse",
    "WaterBodyResponse",
    "WaterBodyDetailResponse",
    "WaterBodyListResponse",
    "RiskHistoryEntry",
    "RiskHistoryResponse",
    "ForelUleResult",
    "AlgaeResult",
    "FoamResult",
    "TurbidityResult",
    "OilSheenResult",
    "ColorAbnormalityResult",
    "DebrisResult",
    "RiskResult",
    "CVAnalysisResult",
]
