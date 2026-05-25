from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ATRI API"
    environment: str = "development"
    log_level: str = "INFO"
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    review_store_path: str = "data/processed/reviews.json"

    model_config = SettingsConfigDict(env_file=".env", env_prefix="ATRI_")


settings = Settings()
