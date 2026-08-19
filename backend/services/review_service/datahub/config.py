import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    REVIEW_PLAN_SERVICE_URL: str = os.getenv(
        "REVIEW_SERVICE_URL", "http://127.0.0.1:8087"
    )
    ERROR_ANALYSIS_SERVICE_URL: str = os.getenv(
        "ERROR_ANALYSIS_SERVICE_URL", "http://127.0.0.1:8082"
    )
    NEO4J_URI: str = os.getenv("NEO4J_URI", "bolt://127.0.0.1:7687")
    NEO4J_USERNAME: str = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD: str = os.getenv("NEO4J_PASSWORD", "")
    CACHE_TTL: int = int(os.getenv("DATAHUB_CACHE_TTL", "3600"))


settings = Settings()
