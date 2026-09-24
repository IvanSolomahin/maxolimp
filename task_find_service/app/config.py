from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://gazprompt:gazprompt@localhost:5432/gazprompt"
    embedding_model: str = "intfloat/multilingual-e5-large"
    embedding_model_version: str = "1.0"
    embedding_dimension: int = 1024
    rrf_k: int = 60


settings = Settings()
