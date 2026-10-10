from typing import List
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "AI-Based Agricultural Price Prediction and Smart Transport Optimization System"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    DEBUG: bool = True
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # CORS Configuration
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:5500,http://localhost:8000,http://127.0.0.1:8000"

    # Database Configuration (Phase 3)
    DATABASE_URL: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/agri_mini_db"

    # External Data Services - data.gov.in (Phase 2A)
    DATA_GOV_IN_API_KEY: str = ""
    DATA_GOV_IN_BASE_URL: str = "https://api.data.gov.in/resource"
    DATA_GOV_IN_RESOURCE_ID: str = "9ef84268-d588-465a-a308-a864a43d0070"

    # External Data Services - Open-Meteo (Phase 2B)
    OPEN_METEO_BASE_URL: str = "https://api.open-meteo.com/v1/forecast"

    # External Data Services - FAOSTAT (Phase 2C)
    FAOSTAT_BASE_URL: str = "https://fenixservices.fao.org/faostat/api/v1/en/data"
    FAOSTAT_DEFAULT_DOMAIN: str = "QCL"
    FAOSTAT_DEFAULT_AREA_CODE: str = "100"  # India

    # External Data Services - OSRM (Phase 2D)
    OSRM_BASE_URL: str = "http://router.project-osrm.org"

    model_config = SettingsConfigDict(
        env_file=[
            str(Path(__file__).resolve().parent.parent / ".env"),
            str(Path(__file__).resolve().parent.parent.parent / ".env"),
            ".env",
        ],
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )

    @property
    def cors_origins(self) -> List[str]:
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]

    @property
    def sync_database_url(self) -> str:
        """Ensures PostgreSQL URL uses the psycopg2 dialect driver."""
        url = self.DATABASE_URL.strip()
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)
        return url


settings = Settings()
