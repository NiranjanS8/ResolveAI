from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings

# Load the repository-root .env regardless of the process working directory, so
# the backend picks up API keys whether it is started from backend/ or the root.
ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    # API
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "ResolveAI"
    
    # Database
    DATABASE_URL: str = "postgresql+psycopg://resolveai:resolveai@localhost:5433/resolveai"
    
    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"

    # SQL statement logging (very noisy; enable only when debugging)
    SQL_ECHO: bool = False
    
    # LLM API Keys
    ANTHROPIC_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    # The Google SDK also accepts GOOGLE_API_KEY; treated as an alias for Gemini.
    GOOGLE_API_KEY: Optional[str] = None

    # Provider preference (comma-separated). When unset, providers are selected
    # automatically from whichever API keys are configured.
    LLM_PROVIDER_ORDER: Optional[str] = None
    EMBEDDING_PROVIDER: Optional[str] = None
    
    # CORS
    BACKEND_CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]
    
    class Config:
        env_file = str(ROOT_ENV_FILE)
        case_sensitive = True
        extra = "ignore"


settings = Settings()