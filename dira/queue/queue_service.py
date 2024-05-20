from typing import Any, Callable
from dira.support.service_provider import ServiceProvider
from dira.foundation.console.console_kernel import ConsoleKernel
from dira.foundation.http.http_kernel import HttpKernel
from dira.main import config

from redis import Redis
from rq import Queue
from rq_dashboard_fast import RedisQueueDashboard
from . import AscQueue

class QueueServiceProvider(ServiceProvider):
    def register(self):
        redis: Redis = self.app.make(Redis)
        self.register_queue(redis)
        self.register_console()

    def register_queue(self, redis: Redis):
        self.app.bind(Queue, lambda name="default": AscQueue(name, connection=redis))
        self.app.bind('queue:default', lambda: self.app.make(Queue))

    def register_console(self):
        if isinstance(self.kernel, ConsoleKernel):
            # Load the console module into the kernel
            self.kernel.load('diracore.queue.commands')

    def boot(self):
        if config('database.redis.dashboard.status', False):
            self.register_dashboard()

    def register_dashboard(self):
        if isinstance(self.kernel, HttpKernel):
            redis: Redis = self.app.make(Redis)

            connection_uri = self.create_redis_connection_string(redis)
            dashboard = RedisQueueDashboard(connection_uri, "/rq")
            
            server = self.kernel.server
            server.mount("/rq", dashboard)

    def create_redis_connection_string(self, redis: Redis):
        connection_kwargs = redis.get_connection_kwargs()
        host = connection_kwargs.get('host', 'localhost')
        port = connection_kwargs.get('port', '6379')
        db = connection_kwargs.get('db', 0)
        password = connection_kwargs.get('password', None)
        
        if password:
            connection_uri = f"redis://:{password}@{host}:{port}/{db}"
        else:
            connection_uri = f"redis://{host}:{port}/{db}"
        
        return connection_uri