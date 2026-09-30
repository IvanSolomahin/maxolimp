from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://olymp:olymp@localhost:5433/olymp"
    task_find_service_url: str = "http://task-app:8000"


settings = Settings()
