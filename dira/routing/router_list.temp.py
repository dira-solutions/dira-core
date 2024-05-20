from abc import ABC
from .router import Router
from pathlib import Path
import os
from dira.contracts.routing.http_router import HttpRouter
from fastapi import APIRouter

class AbstractRouteList(ABC):
    pass

class RouteList(AbstractRouteList):
    routes: list = []
    current: APIRouter
    all_routes: list = []

    def __init__(self, route: HttpRouter) -> None:
        self.current = route
        super().__init__()

    def add(self, route: HttpRouter):
        return route
    
    def add_to_list(self, route: Router):
        pass

    def group(self, callback):
        if isinstance(callback, str):
            route_file_path = os.path.realpath(callback)
            config_data = {}
            exec(Path(route_file_path).read_bytes(), {}, config_data)
            route = config_data.get("route")
            self.routes.append(route)
        return self
    
    def build_all(self) -> None:
        for router in self.routes:
            self.build(router)
    
    def build(self, router) -> None:
        if isinstance(router, RouteList):
            pass
        else:
            if (not hasattr(router, 'routes')): return
            self.current.include_router(router)


