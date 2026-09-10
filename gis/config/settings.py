from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path
import os

class Layer5Settings(BaseSettings):
    """SubSense Layer 5: Spatial & GIS Rendering Stack Configuration"""
    model_config = SettingsConfigDict(env_prefix="SUBSENSE_", extra="ignore")

    APP_NAME: str = "SubSense GIS & Visualization Layer (L5)"
    VERSION: str = "2.1.0"
    ENVIRONMENT: str = "development"
    
    # Storage Paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    TILE_STORAGE_PATH: Path = BASE_DIR / "data" / "tiles"
    CACHE_DIR: Path = BASE_DIR / "data" / "cache"
    SITES_REGISTRY_PATH: Path = BASE_DIR / "config" / "sites_crs_registry.json"
    
    # SLA & Geotechnical Parameters
    INGESTION_SLA_SECONDS: float = 30.0
    DATA_CURRENCY_STALENESS_SECONDS: float = 30.0
    DEFAULT_VERTICAL_EXAGGERATION: float = 25.0
    MIN_VERTICAL_EXAGGERATION: float = 10.0
    MAX_VERTICAL_EXAGGERATION: float = 50.0
    
    # Risk-Zone Engine Thresholds
    ALERT_THRESHOLD_ADVISORY: float = 0.65
    ALERT_THRESHOLD_WARNING: float = 0.75
    ALERT_THRESHOLD_CRITICAL: float = 0.85
    MIN_POLYGON_AREA_SQ_METERS: float = 250.0
    ZONE_JACCARD_MATCH_THRESHOLD: float = 0.40
    
    # Tiling Parameters
    TILE_SIZE: int = 256
    MIN_ZOOM: int = 12
    MAX_ZOOM: int = 18
    
    # Database & Cache (Optional Fallback)
    POSTGIS_URL: str = "postgresql://postgres:postgres@localhost:5432/subsense_gis"
    REDIS_URL: str = "redis://localhost:6379/0"
    USE_LOCAL_CACHE_FALLBACK: bool = True

settings = Layer5Settings()

# Ensure directories exist
os.makedirs(settings.TILE_STORAGE_PATH, exist_ok=True)
os.makedirs(settings.CACHE_DIR, exist_ok=True)
