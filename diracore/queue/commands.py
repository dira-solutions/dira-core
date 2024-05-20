from diracore.main import app, cli
from diracore.queue import AscWorker

from redis import Redis

from diracore.contracts.kernel import Kernel
from diracore.main import app
from app.entity.channels import Post

@cli.command("queue.work")
def package_test():
    worker = AscWorker(['default'], connection=app.make(Redis))
    worker.work(with_scheduler=True)
