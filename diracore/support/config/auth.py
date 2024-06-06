from pydantic import Field
from pydantic_settings import BaseSettings

class AuthConfig(BaseSettings):
    secret_key: str = Field(alias='auth_secret_key', default='your-secret-key')
    algorithm: str = Field(alias='auth_algorithm', default='HS256')
    token_expire_minutes: int = Field(alias='auth_token_expire_minutes', default=2*60)