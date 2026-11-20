from fastapi import APIRouter

from app import config
from app.schemas.models import Health

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health", response_model=Health, summary="서비스별 키 설정 여부 (boolean만)")
def health():
    return {"status": "ok", "services": config.service_status()}
