import os
from pathlib import Path

from pydantic_settings import BaseSettings

_PEDAGOGUE_DATA = Path(__file__).resolve().parent / "agents" / "pedagogue" / "data"


class Settings(BaseSettings):
    # Intake agent LLM (Google AI Studio / Gemini)
    gemini_api_key: str
    gemini_model: str = "gemini-2.5-flash"

    # Legacy — ignored by intake; kept so old .env files still load
    mistral_api_key: str | None = None
    mistral_model: str = "mistral/mistral-large-latest"

    frontend_origin: str = "http://localhost:3000"
    mongo_uri: str = "mongodb://localhost:27017"
    mongo_db_name: str = "ledgermind"
    freshness_max_days: int = 120

    # Pedagogue RAG (ChromaDB + embeddings) — used by /education, not guidance
    pedagogue_chroma_dir: str = str(_PEDAGOGUE_DATA / "chroma")
    pedagogue_chroma_collection: str = "corpus_fiscal_fr"
    pedagogue_embeddings_provider: str = "mistral"  # "mistral" | "local"
    pedagogue_local_embedding_model: str = "intfloat/multilingual-e5-large"
    pedagogue_mistral_model: str = "mistral-small-latest"

    # Légifrance MCP (optional — PISTE API keys)
    piste_client_id: str = ""
    piste_client_secret: str = ""

    # Auth (JWT) — change AUTH_SECRET in production (min 32 chars)
    auth_secret: str = "ledgermind-dev-secret-change-me-32b"
    auth_token_days: int = 14

    # Veille (pedagogue corpus) — manual /api/education/veille/run always available
    veille_enabled: bool = False
    veille_cron_hour: int = 3

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

os.environ.setdefault("GEMINI_API_KEY", settings.gemini_api_key)
if settings.mistral_api_key:
    os.environ.setdefault("MISTRAL_API_KEY", settings.mistral_api_key)
