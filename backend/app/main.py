import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import time

from app.config import get_settings
from app.database import engine, Base
from app.api.reports import router as reports_router
from app.api.water_bodies import router as water_bodies_router

settings = get_settings()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("aquawatch")

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Citizen-science water body health monitoring API",
)

# CORS middleware — allow all for demo
origins = settings.cors_origins.split(",") if settings.cors_origins != "*" else ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(reports_router, prefix="/api/v1", tags=["Reports"])
app.include_router(water_bodies_router, prefix="/api/v1", tags=["Water Bodies"])


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    elapsed = time.time() - start
    logger.info(f"{request.method} {request.url.path} -> {response.status_code} ({elapsed:.2f}s)")
    return response


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled error on {request.method} {request.url.path}: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error. Please try again."},
    )


@app.on_event("startup")
async def startup():
    """Create database tables on startup."""
    from app.models import water_body, report, risk_score  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info(f"AquaWatch API v{settings.app_version} started")
    logger.info(f"Database: {settings.database_url.split('@')[-1] if '@' in settings.database_url else 'configured'}")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    import cv2
    return {
        "status": "healthy",
        "version": settings.app_version,
        "app": settings.app_name,
        "opencv_version": cv2.__version__,
    }
