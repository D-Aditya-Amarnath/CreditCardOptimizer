import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    lmstudio_base_url: str = "http://localhost:1234/v1"
    lmstudio_api_key: str = "lm-studio"
    database_url: str = "sqlite:///offers.db"
    secret_key: str = "dev-secret-change-in-production"
    session_expire_hours: int = 24

    @property
    def llm_base_url(self) -> str:
        return self.lmstudio_base_url
    
    @property
    def llm_api_key(self) -> str:
        return self.lmstudio_api_key

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
