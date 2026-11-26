"""Application settings. Every Google integration is optional and degrades gracefully."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(".env", "../.env"), extra="ignore")

    env: str = "dev"  # dev | test | prod
    # Database: pooled URL for the app, direct URL for Alembic (Neon). Plain postgres URLs.
    database_url: str = "postgresql://raktsetu:raktsetu@localhost:55432/raktsetu"
    database_url_direct: str | None = None
    db_pool_size: int = 5

    # Auth
    auth_mode: str = "both"  # firebase | demo | both
    demo_auth_secret: str = "dev-only-change-me"  # noqa: S105 - refused at startup when ENV=prod (see main.py)
    firebase_project_id: str | None = None

    # Gemini: AI Studio key (no card needed) OR Vertex AI (ADC on Cloud Run).
    gemini_api_key: str | None = None
    google_genai_use_vertexai: bool = False
    google_cloud_project: str | None = None
    google_cloud_location: str = "global"
    gemini_model: str = "gemini-3.7-flash"
    gemini_model_lite: str = "gemini-3.5-flash-lite"
    # Tried in order when the primary model is overloaded (503) or rate-limited (429).
    gemini_model_fallbacks: str = "gemini-3.8-flash,gemini-3.5-flash,gemini-2.5-flash"
    # Groq: second provider used when every Gemini model is unavailable (free tier, no card).
    groq_api_key: str | None = None
    groq_model: str = "llama-3.3-70b-versatile"
    groq_base_url: str = "https://api.groq.com/openai/v1"

    # Maps / Routes / Calendar
    maps_server_key: str | None = None
    google_calendar_api_key: str | None = None
    holiday_calendar_id: str = "en.indian#holiday@group.v.calendar.google.com"

    # Firestore mirror + FCM (uses ADC or GOOGLE_APPLICATION_CREDENTIALS)
    firestore_enabled: bool = False
    fcm_enabled: bool = False

    # BigQuery analytics export (sandbox works without billing)
    bigquery_dataset: str | None = None

    # Internal jobs (Cloud Scheduler OIDC, or shared token for non-GCP schedulers)
    internal_audience: str | None = None
    internal_token: str | None = None
    scheduler_sa_email: str | None = None

    # Simulation
    risk_paths: int = 2000
    risk_horizon_hours: int = 168
    random_seed: int = 42

    # Brevo transactional email (optional, for critical alerts when FCM is not available)
    brevo_api_key: str | None = None
    alert_email_to: str | None = None
    alert_email_from: str = "alerts@raktsetu.local"

    cors_origins: str = "http://localhost:5173"

    @property
    def async_database_url(self) -> str:
        return _to_async(self.database_url)

    @property
    def sync_database_url_direct(self) -> str:
        url = (self.database_url_direct or self.database_url).replace("postgresql+asyncpg://", "postgresql://")
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://"):]
        # SQLAlchemy 2.1 maps bare postgresql:// to psycopg3; we ship psycopg2 for migrations.
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)

    @property
    def gemini_enabled(self) -> bool:
        return bool(self.gemini_api_key) or self.google_genai_use_vertexai


def _to_async(url: str) -> str:
    """Convert a libpq URL to asyncpg; asyncpg wants ssl=require, not sslmode/channel_binding."""
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        url = "postgresql+asyncpg://" + url[len("postgresql://") :]
    if "?" in url:
        base, query = url.split("?", 1)
        parts = [p for p in query.split("&") if not p.startswith(("sslmode=", "channel_binding="))]
        need_ssl = "sslmode=require" in query or "sslmode=verify" in query
        if need_ssl and not any(p.startswith("ssl=") for p in parts):
            parts.append("ssl=require")
        url = base + ("?" + "&".join(parts) if parts else "")
    return url


@lru_cache
def get_settings() -> Settings:
    return Settings()
