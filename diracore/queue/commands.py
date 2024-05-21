from diracore.main import app, cli
from diracore.queue import AscWorker

from redis import Redis

@cli.command("queue.work")
def package_test():
    worker = AscWorker(['default'], connection=app.make(Redis))
    worker.work(with_scheduler=True)
