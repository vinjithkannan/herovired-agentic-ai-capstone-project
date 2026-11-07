from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    app_name: str = "ReqFlow AI"
    app_env: str = "development"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://reqflow:reqflow_dev_only_change_me@localhost:5432/reqflow"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "development-only-change-this-secret"
    openai_api_key: str = ""
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: int = 300
    cors_origins: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
