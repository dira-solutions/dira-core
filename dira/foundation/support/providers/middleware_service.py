from dira.support.service_provider import ServiceProvider

from dira.main import config

class MiddlewareServiceProvider(ServiceProvider):
    http_middlewares: dict = {}
    
    async def register(self) -> None:
        self.build_middlewares()

    def build_middlewares(self):
        self.http_middlewares = config('app.middlewares', {})


    async def boot(self) -> None:
        self.register_middlewares()

    def register_middlewares(self):
        for key, middleware in self.http_middlewares.items():
            self.add_middleware(key, middleware)
    
    def add_middleware(self, key, middleware):
        if type(middleware) is not type:
            middleware = getattr(middleware, 'handle')
        else:
            if middleware in self.app.bindings:
                middleware = self.app.make(middleware)
            else:
                middleware = middleware()
            return self.add_middleware(key, middleware)
        self.app.bind(f"middlewares.{key}", middleware)