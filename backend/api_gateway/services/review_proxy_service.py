import requests
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from backend.api_gateway.services.service_urls import SERVICE_URLS


def proxy_review_request(method: str, prefix: str, path: str, body: bytes | None) -> JSONResponse:
    target_path = f"/{prefix}" + (f"/{path}" if path else "")
    try:
        response = requests.request(method=method, url=f"{SERVICE_URLS['review']}{target_path}", headers={"Content-Type": "application/json"}, data=body, timeout=60)
    except requests.RequestException as error:
        raise HTTPException(status_code=503, detail="Review Service 不可用") from error
    try:
        content = response.json() if response.text else {}
    except ValueError:
        content = {"detail": response.text[:500]}
    return JSONResponse(content=content, status_code=response.status_code)
