from fastapi import FastAPI
from diracore.contracts.foundation.application import Application
from diracore.foundation.bootstrap import load_configuration, load_environment, register_providers, boot_providers, connection_database
from contextlib import asynccontextmanager
import os
from fastapi.responses import ORJSONResponse

class HttpKernel:
    _app: any
    _router: any
    server: any
    _routes: list = []

    __bootstrappers: dict = [
        load_environment.LoadEnvironment,
        load_configuration.LoadConfiguration,
        connection_database.ConnectionDatabase,
        register_providers.RegisterProviders,
        boot_providers.BootProviders
    ]

    def __init__(self, app: Application, router = None) -> None:
        self._app = app
        self._router = router
        self._routes: list = []
        self.sync_middleware_to_router()

    def get_bootstrappers(self):
        return self.__bootstrappers
    
    async def bootstrap(self):        
        await self._app.bootstrap_with(self.get_bootstrappers())

    @asynccontextmanager
    async def lifespan(self, app: FastAPI):
        await self.bootstrap()
        yield

    def sync_middleware_to_router(self):
        return

    def handle(self):
        dependencies = [
            # ....
        ]
        title = os.getenv("APP_NAME", "DIRA Framework")
        self.server = FastAPI(
            lifespan=self.lifespan, 
            title=title, 
            dependencies=dependencies,
            default_response_class=ORJSONResponse
        )
        
    def send(self):
        return self.server