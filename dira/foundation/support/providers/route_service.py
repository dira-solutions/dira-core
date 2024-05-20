from dira.contracts.foundation.application import Application
from dira.support.service_provider import ServiceProvider
from dira.routing.router import HttpRoute, RouteList
from dira.foundation.application import Application

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from fastapi.datastructures import Default

class RouteServiceProvider(ServiceProvider):
    http_routes = []
    build_routes:list = []
    
    def __init__(self, app: Application):
        super().__init__(app)

    def routers(self, routers, prefix=""):        
        for router in routers:
            if isinstance(router, RouteList): 
                http_routes = router.build()
            if isinstance(router, HttpRoute):
                http_routes = [router]
            self.register_routes(http_routes)

    def register_routes(self, routes) -> None:            
        api_router = APIRouter()
        for route in routes:
            if not isinstance(route, HttpRoute): continue
            full_path = route.prefix + route.path
            api_router.add_api_route(
                tags=route._tags,
                path=full_path, 
                endpoint=route.enpoint, 
                methods=route.methods,
                response_model_by_alias=True,
                dependencies=[Depends(middleware) for middleware in route.middlewares],
                name=route._name,
                response_class=route.response_class if route.response_class else Default(JSONResponse)
                )
        if self.server:
            self.server.include_router(api_router)
        if hasattr(self.kernel, '_router'):
            self.kernel._router = api_router
