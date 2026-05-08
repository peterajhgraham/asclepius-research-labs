from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Asclepius Research Labs"
    app_env: str = "development"

    # LLM providers
    openai_api_key: str = ""
    anthropic_api_key: str = ""
    llm_model: str = "gpt-4o"  # OpenAI fallback model

    # External data sources
    ncbi_api_key: str = ""

    # CORS
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    # Cost control
    daily_budget_usd: str = "10.00"

    # Async database
    database_url: str = "sqlite+aiosqlite:///./data/asclepius.db"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
