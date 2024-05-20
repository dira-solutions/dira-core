from dira.support.service_provider import ServiceProvider

from redis import Redis
from redis.asyncio import Redis as ARedis

from dira.main import config

class RedisServiceProvider(ServiceProvider):
    def register(self):
        host = config('database.redis.default.host')
        port = config('database.redis.default.port')
        db = config('database.redis.default.db')
        username = config('database.redis.default.username')
        password = config('database.redis.default.password')
        self.app.bind(Redis, lambda: Redis(host, port, db, password, username=username))
        self.app.bind(ARedis, lambda: ARedis(host=host, port=port, db=db, password=password, username=username))

    def boot(self):
        pass