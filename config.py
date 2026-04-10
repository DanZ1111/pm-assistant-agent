from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str
    database_url: str
    openai_model: str = "gpt-4o"
    max_history_messages: int = 40
    secret_key: str = "change-me-in-prod"          # override with SECRET_KEY env var
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    class Config:
        env_file = ".env"


settings = Settings()
