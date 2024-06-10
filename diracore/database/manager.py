from diracore.contracts.foundation.application import Application
from tortoise import Tortoise
from tortoise.contrib.fastapi import register_tortoise
from diracore.contracts.kernel import Kernel
from diracore.foundation.http.http_kernel import HttpKernel

class InvalidArgumentException(Exception):
    pass

class DatabaseManager():
    _app: Application
    _connections: dict = {}
    _reconnector: callable
    _extensions: list = []
    _models: list = []

    def __init__(self, app: Application) -> None:
        self._app = app
        self._reconnector = lambda connection: self.reconnect(connection.get_name_with_read_write_type())

    def reconnect(self, name: str = None):
        # TODO: disconnect
        if not name in self._connections:
            return self.connection(name)
        return self.refresh_connections(name)
    
    def refresh_connections(self, name: str = None):
        database, type = self._parse_connection_name(name)
        self._connections[name] = self.configure(
            self.make_connection(database), self.get_db_name(name))
        return self._connections[name]
    
    @staticmethod
    def get_db_name(name):
        match name:
            case 'pgsql': return 'postgres'
        return name
    
    def make_connection(self, name):
        config = self.configuration(name)
        if name in self._extensions:
            return self._extensions[name](config, name)
        return config
        
    def configuration(self, name):
        name = name or self.get_default_connection()
        config: dict = self._app.make('config')
        connections = config.get('database', {}).get('connections')
        db_config = connections.get(name, None)
        if db_config is None:
            raise InvalidArgumentException(f"Database connection [{name}] not configured.")
        return db_config

    async def connection(self, name: str = None):
        database, type = self._parse_connection_name(name)
        name = name or database
        if not name in self._connections:
            self._connections[name] = await self.configure(
                self.make_connection(database), self.get_db_name(name))
        return self._connections[name]
    
    async def configure(self, connecton: dict, db_type: str):
        if (db_type == "sqlite"):
            db_url=db_type+'://{url}'.format(**connecton),
            modules={'models': self._models},
        else:
            db_url=db_type+'://{username}:{password}@{host}:{port}/{database}'.format(**connecton),
            modules={'models': self._models},
        
        obj = await Tortoise.init(
            db_url=db_url[0],
            modules=modules[0]
        )
        kernel = self._app.make(Kernel)
        if isinstance(kernel, HttpKernel):
            register_tortoise(kernel.server, db_url=db_url, modules=modules)
        
        # await Tortoise.generate_schemas()
        return Tortoise.get_connection('default')
    
    def transaction(self, name: str = None):
        name = name or "default"
        return Tortoise.get_connection(name)._in_transaction()

    def _parse_connection_name(self, name: str):
        name = name or self.get_default_connection()
        return name.split('::', 1) if any(name.endswith(ending) for ending in ['::read', '::write']) else [name, None]
    
    def get_default_connection(self) -> str:
        config: dict = self._app.make('config')
        return config.get('database', {}).get('default', '')
