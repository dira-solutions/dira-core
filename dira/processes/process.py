from multiprocessing import Process

from dira.main import app
import asyncio
import logging

from dira.main import app, Application
from dira.container.container import ABSTRACT
import asyncio

from dira.database.manager import DatabaseManager
from tortoise.backends.asyncpg.client import AsyncpgDBClient


class BaseProcess(Process):
    def run(self) -> None:
        self._target = self._target or self.handle            
        loop = asyncio.new_event_loop()
        loop.run_until_complete(self.lifespan(self._target, *self._args, **self._kwargs))
                
    async def lifespan(self, handle, *args, **kwargs):
        await self.on_startup()
        
        await self.on_handle(handle, *args, **kwargs)
                
        await self.on_shutdown()
        
    async def on_handle(self, handle=None, *args, **kwargs):
        handle = handle or self.handle
        try:
            result = handle(*args, **kwargs)
            if (asyncio.iscoroutine(result)):
                await result
        except Exception as e:
            on_failed = self.failed(e, *args, **kwargs)
            if (asyncio.iscoroutine(on_failed)):
                await on_failed
        else:
            om_success = self.success(result, *args, **kwargs)
            if (asyncio.iscoroutine(om_success)):
                await om_success
    
    def handle(self, *args, **kwargs):
        pass
    
    def failed(self, error, *args, **kwargs):
        logging.error(error)
        raise error
    
    def success(self, result, *args, **kwargs):
        pass
    
    def app(self, abstract=ABSTRACT|None)->ABSTRACT|Application|None:
        return app.make(abstract) if abstract else app

    def db(self) -> DatabaseManager:
        return self.app('db')
    
    def db_connection(self, connection_name=None):
        db = self.db()
        connection_name = connection_name or db.get_default_connection()
        return db._connections[connection_name]

    async def register_db(self):
        connect: AsyncpgDBClient = self.db_connection()
        connect.pool_maxsize = 10
        await connect.create_connection(True)
    
    async def on_startup(self):
        await self.register_db()

    async def on_shutdown(self):
        from tortoise import Tortoise
        await Tortoise.close_connections()