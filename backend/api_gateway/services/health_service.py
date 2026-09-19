import requests

from backend.api_gateway.services.service_urls import SERVICE_URLS
from backend.shared.internal_auth import internal_headers


def get_gateway_health() -> dict:
    results = {}
    for service, url in SERVICE_URLS.items():
        try:
            results[service] = requests.get(f"{url}/health", timeout=3, headers=internal_headers()).json()
        except requests.RequestException:
            results[service] = {"status": "unhealthy"}
    return {"api_gateway": "healthy", "services": results}
