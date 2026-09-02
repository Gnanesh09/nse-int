from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # =========================================================
    # APPLICATION
    # =========================================================

    app_name: str = "South Decan Capital — NSE Intelligence"
    app_version: str = "1.0.0"

    # =========================================================
    # MONGODB
    # =========================================================

    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db: str = "nse_alerts"

    # =========================================================
    # NSE
    # =========================================================

    nse_poll_seconds: int = 60

    # NSE API is date-based, therefore the worker fetches a
    # recent date window and MongoDB performs deduplication.
    nse_lookback_minutes: int = 180

    nse_timeout_seconds: int = 30

    nse_max_retries: int = 4

    # =========================================================
    # GROQ
    # =========================================================

    groq_api_key: str | None = None

    # Strict structured-output supported model.
    groq_model: str = "openai/gpt-oss-20b"

    # Maximum generated tokens per LLM request.
    groq_max_output_tokens: int = 1800

    # Character safety limit for a single LLM document.
    groq_max_input_chars: int = 100000

    # Chunk size for long PDFs.
    groq_chunk_chars: int = 24000

    # Number of chunk analyses allowed.
    groq_max_chunks: int = 12

    # =========================================================
    # SMTP
    # =========================================================

    smtp_host: str | None = None
    smtp_port: int = 587

    smtp_user: str | None = None
    smtp_password: str | None = None

    smtp_from: str | None = None

    smtp_starttls: bool = True

    # =========================================================
    # SCHEDULER
    # =========================================================

    scheduler_enabled: bool = True

    # =========================================================
    # CORS
    # =========================================================

    cors_origins: str = (
        "http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "http://localhost:3000,"
        "http://127.0.0.1:3000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()