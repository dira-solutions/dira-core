from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

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
    app: AppConfig = Field(default_factory=AppConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)