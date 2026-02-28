from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Autoimmune Intelligence"
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"
    cors_origins: list[str] = ["*"]
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
