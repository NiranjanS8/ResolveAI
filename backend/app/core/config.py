from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ResolveAI"
    
    # Database
    DATABASE_URL: str = "postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()