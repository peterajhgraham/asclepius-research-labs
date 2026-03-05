from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Asclepius Research Labs"
    app_env: str = "development"
    openai_api_key: str = ""
    ncbi_api_key: str = ""
    llm_model: str = "gpt-4o"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
