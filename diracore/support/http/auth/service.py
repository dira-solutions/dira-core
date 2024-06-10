from diracore.contracts.foundation.application import Application
from diracore.support.service_provider import ServiceProvider
from diracore.main import config
from .middleware import JWTAuthentication
from .model import User

class AuthServiceProvider(ServiceProvider):
    async def register(self):
        self.app.bind(JWTAuthentication, self.jwt_middleware())
        self.app.bind('auth', lambda: self.app.make(JWTAuthentication))

    def jwt_middleware(self, user_model=User):
        return JWTAuthentication(
            secret_key=config('auth.secret_key'),
            algorithm=config('auth.algorithm'),
            token_expire_minutes=config('auth.token_expire_minutes'),
            user_model=user_model
        )