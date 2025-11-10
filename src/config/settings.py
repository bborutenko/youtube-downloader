from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    RELOAD: bool = True
    YOUTUBE_COOKIES_DIR: str = "storage/cookies"

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
