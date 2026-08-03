from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Asclepius Research Labs"
    app_env: str = "development"

    # LLM providers
    anthropic_api_key: str = ""

    # External data sources
    ncbi_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # Cost control
    daily_budget_usd: float = 10.0

    # Async database
    database_url: str = "sqlite+aiosqlite:///./data/asclepius.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.anthropic_api_key:
            import logging
            logging.getLogger(__name__).warning(
                "ANTHROPIC_API_KEY is not set — LLM features will be unavailable"
            )


settings = Settings()
