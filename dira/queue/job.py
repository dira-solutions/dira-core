from enum import Enum
from abc import ABC, abstractmethod
from dira.main import app, Application
from dira.container.container import ABSTRACT
from rq import Queue
from dira.queue import AscCallback, AscQueue
import asyncio

from dira.database.manager import DatabaseManager
from tortoise.backends.asyncpg.client import AsyncpgDBClient

from dira.contracts.kernel import Kernel as KernelContract

class Priority(Enum):
    IMPORTANT: 1
    MID: 2
    LOW: 3


class JobBase(ABC):
    job='default'

    name=''

    description=''

    meta:dict={}

    group=None

    """указывает максимальное время выполнения задания до его прерывания и отмечен как failed. 
    Его единицей измерения по умолчанию является секунда, и она может быть целым числом или строкой, 
    представляющей целое число (например, 2, '2'). Кроме того, это может быть строка с указанием 
    единиц измерения, включая час, минуту, секунду (например, '1h', '3m', '5s'). """
    job_timeout: int|str = 100
    """указывает, как долго (в секундах) выполняются успешные задания и их результаты сохраняются. 
    Просроченные задания будут автоматически удалены. По умолчанию 500 секунд. """
    result_ttl = 500
    """указывает максимальное время нахождения задания в очереди (в секундах) до его отклонения. 
    Этот аргумент по умолчанию имеет значение None(бесконечный ТТЛ). """
    ttl=None
    """указывает, как долго сохраняются неудачные задания (по умолчанию 1 год) """
    failure_ttl="365d"

    @abstractmethod
    def handle(self):
        pass

    def get_meta(self):
        return self.meta or {}

    def get_name(self):
        return self.name or __class__

    def get_description(self):
        return self.description or ''
    
    def get_job_name(self):
        return f"{self.get_name()} - {self.get_description()}"
    
    def get_job_timeout(self):
        return self.job_timeout
    
    def get_ttl(self):
        return self.ttl
    
    def get_result_ttl(self):
        return self.result_ttl
    
    def get_failure_ttl(self):
        return self.failure_ttl
    
    def enqueue_in(self, time_delta, job_timeout=None, result_ttl=None, ttl=None, failure_ttl=None):
        job_timeout = job_timeout or self.get_job_timeout()
        result_ttl = result_ttl or self.get_result_ttl()
        failure_ttl = failure_ttl or self.get_failure_ttl()
        ttl = ttl or self.get_ttl()
        handle = self.lifespan, self.handle if asyncio.iscoroutinefunction(self.handle) else self.handle
        self.get_queue().enqueue_in(time_delta, *handle, 
            description=self.get_job_name(), meta=self.get_meta(),
            job_timeout=job_timeout, result_ttl=result_ttl, failure_ttl=failure_ttl, ttl=ttl,
            on_success=AscCallback(self._on_success, (self)), 
            # on_failure=AscCallback(self._on_failure, (self)), 
            # on_stopped=AscCallback(self._on_stopped, (self))
        )

    def enqueue_at(self, datetime, job_timeout=None, result_ttl=None, ttl=None, failure_ttl=None):
        job_timeout = job_timeout or self.get_job_timeout()
        result_ttl = result_ttl or self.get_result_ttl()
        failure_ttl = failure_ttl or self.get_failure_ttl()
        ttl = ttl or self.get_ttl()
        handle = self.lifespan, self.handle if asyncio.iscoroutinefunction(self.handle) else self.handle
        self.get_queue().enqueue_at(datetime, *handle, 
            description=self.get_job_name(), meta=self.get_meta(),
            job_timeout=job_timeout, result_ttl=result_ttl, failure_ttl=failure_ttl, ttl=ttl,
            on_success=AscCallback(self._on_success, (self)), 
            # on_failure=AscCallback(self._on_failure, (self)), 
            # on_stopped=AscCallback(self._on_stopped, (self))
        )

    def enqueue(self, job_timeout=None, result_ttl=None, ttl=None, failure_ttl=None):
        job_timeout = job_timeout or self.get_job_timeout()
        result_ttl = result_ttl or self.get_result_ttl()
        failure_ttl = failure_ttl or self.get_failure_ttl()
        ttl = ttl or self.get_ttl()
        handle = self.lifespan, self.handle if asyncio.iscoroutinefunction(self.handle) else self.handle
        self.get_queue().enqueue(*handle, 
            description=self.get_job_name(), meta=self.get_meta(),
            job_timeout=job_timeout, result_ttl=result_ttl, failure_ttl=failure_ttl, ttl=ttl,
            on_success=AscCallback(self._on_success, (self)), 
            on_failure=AscCallback(self._on_failure, (self)), 
            # on_stopped=AscCallback(self._on_stopped, (self))
        )

    def get_queue(self, job:str='default')-> Queue|AscQueue:
        job = job or self.job
        if isinstance(job, str):
            return app.make(f"queue:{job}")
        else:
            return job
        
    async def lifespan(self, func, *args, **kwargs):
        await self.on_startup()
        try:
            result = await func(*args, **kwargs)
        finally:
            await self.on_shutdown()
        
        return result

    async def on_startup(self):
        pass

    async def on_shutdown(self):
        pass
    
    def run_sync_or_async(self, func, *args, **kwargs):
        if asyncio.iscoroutinefunction(func):
            lifespan = self.lifespan(func, *args, **kwargs)
            loop: asyncio.AbstractEventLoop = asyncio.new_event_loop()
            try:
                _func = loop.run_until_complete(lifespan)
            finally:
                loop.close()
            
            return _func
        return func(*args, **kwargs)
    
    def _on_success(self, job, connection, result):
        func = self.success
        return self.run_sync_or_async(func, job, connection, result)

    def _on_failure(self, job, connection, result, *args, **kwargs):
        func = self.failure
        return self.run_sync_or_async(func, job, connection, result, *args, **kwargs)

    def _on_stopped(self, job, connection):
        func = self.stopped
        return self.run_sync_or_async(func, job, connection)
    
    def success(self, job, connection, result):
        pass

    def failure(self, job, connection, result, *args, **kwargs):
        pass

    def stopped(self, job, connection):
        pass


class Job(JobBase):
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