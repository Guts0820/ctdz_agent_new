from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    REVIEW_PLAN_SERVICE_URL: str = "http://localhost:8003"
    ERROR_ANALYSIS_SERVICE_URL: str = "http://localhost:8004"
    
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USERNAME: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    CACHE_TTL: int = 3600
    
    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()