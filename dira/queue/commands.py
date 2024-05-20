from dira.main import app, cli
from dira.queue import AscWorker

from redis import Redis

from dira.contracts.kernel import Kernel
from dira.main import app
from app.entity.channels import Post

@cli.command("queue.work")
def package_test():
    worker = AscWorker(['default'], connection=app.make(Redis))
    worker.work(with_scheduler=True)
