import importlib
import click
import asyncio
from tortoise import Tortoise
from functools import wraps

def coro(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.get_event_loop()

        # Close db connections at the end of all but the cli group function
        try:
            loop.run_until_complete(f(*args, **kwargs))
        finally:
            if f.__name__ not in ["cli", "init"]:
                loop.run_until_complete(Tortoise.close_connections())

    return wrapper

class AscernderCLI(click.Group):
    def __init__(self, *args, load_subcommands=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.load_subcommands = load_subcommands or {}

    def list_commands(self, ctx):
        base = super().list_commands(ctx)
        lazy = sorted(self.load_subcommands.keys())
        return base + lazy

    def get_command(self, ctx, cmd_name):
        if cmd_name in self.load_subcommands:
            return self.load(cmd_name)
        return super().get_command(ctx, cmd_name)

    def load(self, cmd_name):
        # lazily loading a command, first get the module name and attribute name
        import_path = self.load_subcommands[cmd_name]
        modname, cmd_object_name = import_path.rsplit(".", 1)
        # do the import
        mod = importlib.import_module(modname)
        # get the Command object from that module
        cmd_object = getattr(mod, cmd_object_name)
        # check the result to make debugging easier
        if not isinstance(cmd_object, click.BaseCommand):
            raise ValueError(
                f"Lazy loading of {import_path} failed by returning "
                "a non-command object"
            )
        return cmd_object
