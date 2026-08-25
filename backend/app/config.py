from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql://aquawatch:aquawatch_dev@localhost:5432/aquawatch"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = True

    # CORS
    cors_origins: str = "*"

    # App
    app_name: str = "AquaWatch"
    app_version: str = "0.1.0"

    # CV Analysis
    max_image_size_mb: int = 10
    image_max_dimension: int = 800  # Resize to this max width/height

    # Roboflow
    roboflow_api_key: str = ""
    roboflow_model_id: str = "drone-water-quality-monitor/1"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
