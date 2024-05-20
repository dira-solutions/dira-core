from fastapi.responses import JSONResponse

class HttpRoute:
    middlewares: list = []
    _tags: list = []
    enpoint: callable
    path: str = ""
    prefix: str = ""
    methods: list
    response_class=None
    default_response_class=JSONResponse

    def __init__(
            self, 
            path: str, 
            endpoint, 
            methods: list, 
            prefix: str = "", 
            name = "", 
            tags: list = [],
            response_class=None, 
            default_response_class=JSONResponse
        ) -> None:
        self.path = prefix + path
        self.enpoint = endpoint
        self.methods = methods
        self._tags = []
        self._name = name
        self.response_class=response_class
        self.default_response_class=default_response_class

    def middleware(self, *middlewares):
        if isinstance(middlewares, tuple):
            self.middlewares.extend(middlewares)
        else:
            for middleware in middlewares:
                self.middlewares.append(middleware)
        return self

    def tags(self, *tags):
        self._tags.append(*tags)
        return self
    
    def name(self, name):
        self._name = name
        return self
    
class Route:
    @staticmethod
    def get(path: str, endpoint) -> HttpRoute:
        route = HttpRoute(path, endpoint, methods=["GET"])
        return route
    
    @staticmethod
    def post(path: str, endpoint) -> HttpRoute:
        route = HttpRoute(path, endpoint, methods=["POST"])
        return route

    @staticmethod
    def put(path: str, endpoint: callable) -> HttpRoute:
        route = HttpRoute(path, endpoint, methods=["PUT"])
        return route

    @staticmethod
    def delete(path: str, endpoint: callable) -> HttpRoute:
        route = HttpRoute(path, endpoint, methods=["DELETE"])
        return route
    
    @staticmethod
    def group(callback, prefix=""):
        route = RouteList()
        if isinstance(callback, str):
            route.routes = Route._handle_file(callback)
            return route
        if isinstance(callback, list):
            route.routes = callback
            route.prefix = prefix
            return route

    def _handle_file(file_path):
        context = {'route': RouteList}
        with open(file_path, 'r') as file:
            exec(file.read(), context)
        route = context['route']
        return route.routes
    
class RouteBuild:
    def __init__(self):
        self.prefix: str = ""
        self.routes: list = []
        self.middlewares: list = []
        self._tags: list = []
        self._response_class=None
        self.default_response_class=JSONResponse

    def route(self, name) -> None|HttpRoute:
        for route in self.build():
            if route._name == name:
                return route
        return None
    
    def url(self, name, domen=None, **params):
        from dira.main import config
        # Retrieve the base URL from the configuration.
        base_url: str = domen or self.make_full_url(config('app.url'))
        # Fetch the route object by name, assuming it exists.
        route = self.route(name)

        # Construct the full URL by combining the base URL and the route's path.
        # We assume that the path includes placeholders for parameters.
        try:
            # If parameters are provided, format the URL using these parameters.
            if params:
                full_url = base_url + route.path.format(**params)
            else:
                full_url = base_url + route.path
        except KeyError as e:
            raise ValueError(f"Missing parameter in the URL formatting: {e}")

        return full_url
    
    def make_full_url(self, host: str, scheme='http'):
        if not host.startswith(('http://', 'https://')):
            return f'{scheme}://{host}'
        return host

    def _handle_file_to_route(self, file_path):
        context = {"route": []}
        with open(file_path, 'r') as file:
            exec(file.read(), context)
        route = context['route']
        return route

    def build(self, group = None):
        http_routes = self.build_routes(self.routes, group)
        
        return http_routes
    
    def build_routes(self, routes, group = None, http_routes: list = []):
        for route in routes:
            self.build_prefix(route, group)
            self.build_middleware(route, group)
            self.build_tags(route, group)
            if isinstance(route, HttpRoute):
                self.build_config(route)

                route.prefix = self.prefix + route.prefix                
                http_routes.append(route)
            elif isinstance(route, RouteList):
                http_routes = self.build_routes(route.routes, group=route, http_routes=http_routes)
        return http_routes
    
    def build_config(self, route: HttpRoute):
        if not route.response_class:
            route.response_class = self._response_class
        if not route.default_response_class:
            route.default_response_class = self.default_response_class
        return route

    
    def build_prefix(self, route, group):
        if isinstance(group, RouteBuild):
            route.prefix = group.prefix + route.prefix
        return route
    
    def build_middleware(self, route: HttpRoute, group):
        unique_middlewares = set(route.middlewares) | set(self.middlewares)
        if isinstance(group, RouteBuild):
            unique_middlewares = unique_middlewares | set(group.middlewares)
        route.middlewares = list(unique_middlewares)
        return route

    def build_tags(self, route: HttpRoute, group):
        unique_tags = set(route._tags) | set(self._tags)
        if isinstance(group, RouteBuild):
            unique_tags = unique_tags | set(group._tags)
        route._tags = list(unique_tags)
        return route

class RouteList(RouteBuild):
    def get(self, path: str, endpoint):
        route = Route.get(path, endpoint)
        self.routes.append(route)
        return route
    
    def post(self, path: str, endpoint):
        route = Route.post(path, endpoint)
        self.routes.append(route)
        return route

    def put(self, path: str, endpoint: callable):
        route = Route.put(path, endpoint)
        self.routes.append(route)
        return route

    def delete(self, path: str, endpoint: callable):
        route = Route.delete(path, endpoint)
        self.routes.append(route)
        return route
    
    def group(self, callback, prefix=""):
        if isinstance(callback, str):
            route: RouteList = self._handle_file_to_route(callback)
            route.prefix = prefix
            self.routes.append(route)
            return route
        elif isinstance(callback, list):
            route = RouteList()
            route.routes = callback
            route.prefix = prefix
            self.routes.append(route)
            return route
        return self

    def response_class(self, response_class):
        self._response_class = response_class
        return self
    
    def middleware(self, *middlewares):
        middlewares = self.make_middlewares(middlewares)
        self.middlewares.extend(middlewares)
        return self
    
    def tags(self, *tags):
        self._tags.extend(tags)
        return self
    
    def make_middlewares(self, middlewares):
        from dira.main import app
        _middlewares = []
        for middleware in middlewares:
            if isinstance(middleware, str):
                middleware = app.make(f"middlewares.{middleware}")
            else:
                middleware = app.make(middleware, default=middleware)
                middleware = app.build(middleware.handle)
            _middlewares.append(middleware)
        return _middlewares

class Router(RouteList):
    pass
    