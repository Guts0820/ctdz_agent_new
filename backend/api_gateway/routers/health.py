from fastapi import APIRouter

from backend.api_gateway.services.health_service import get_gateway_health


router = APIRouter(tags=["health"])


@router.get("/health")
def health_check() -> dict:
    return get_gateway_health()
