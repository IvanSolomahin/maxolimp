from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gazprompt:gazprompt@localhost:5432/gazprompt"
    embedding_model: str = "qwen/qwen3-embedding-4b"
    embedding_dimension: int = 2560
    openrouter_api_key: str | None = None
    rrf_k: int = 60


settings = Settings()
