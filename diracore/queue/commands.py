from diracore.main import app, cli
from diracore.queue import AscWorker

from redis import Redis

from tortoise import Tortoise
import asyncio

@cli.command("queue.work")
def package_test():
    worker = AscWorker(['default'], connection=app.make(Redis))
    asyncio.run(Tortoise.close_connections())
    worker.work(with_scheduler=True)
