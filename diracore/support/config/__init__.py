from pydantic_settings import BaseSettings, SettingsConfigDict

from .app import AppConfig
from .database import DatabaseConfig
from .auth import AuthConfig

class Config(BaseSettings):
    model_config = SettingsConfigDict(
        env_file='.env', 
        env_file_encoding='utf-8', 
        validate_default=False,
        extra='allow'
    )
    app: AppConfig = AppConfig()
    database: DatabaseConfig = DatabaseConfig()
    auth: AuthConfig = AuthConfig()