from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    status: str
    service: str
    environment: str
    timestamp: str
    version: str


@router.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
        version="0.1.0",
    )
