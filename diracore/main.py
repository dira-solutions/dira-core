from diracore.foundation.application import Application
from diracore.console.cli import AscernderCLI, coro
import click

app: Application = Application()

@click.group(cls=AscernderCLI, help="main CLI command for lazy example",)
def cli():
    pass

def config(path: str, default=None):
    config_dict: dict = app.make('config')
    keys = path.split('.')
    for key in keys:
        if config_dict is None:
            return default
        config_dict = config_dict.get(key)
    return config_dict