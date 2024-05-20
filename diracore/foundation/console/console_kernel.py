from diracore.contracts.foundation.application import Application
from diracore.foundation.bootstrap import (
    load_configuration, 
    load_environment, 
    register_providers, 
    boot_providers, 
    connection_database
)
from diracore.console.cli_ascender import AscernderCLI
from diracore.main import cli

import asyncio
import importlib.util
import click

class ConsoleKernel():
    _app: any
    _router: any
    server: any
    _routes: list = []
    routes: list = []
    cli: any
    _commands: dict = {}

    __bootstrappers: dict = [
        load_environment.LoadEnvironment,
        load_configuration.LoadConfiguration,
        connection_database.ConnectionDatabase,
        register_providers.RegisterProviders,
        boot_providers.BootProviders
    ]

    def __init__(self, app: Application) -> None:
        self._app: Application = app
        self.routes: list = []
        self._router = None
        self.loop = asyncio.get_event_loop()

    async def bootstrap(self):
        await self._app.bootstrap_with(self.get_bootstrappers())
        self.load_base_commands()
        self.commands()

    def handle(self):
        self.loop.run_until_complete(self.bootstrap())
        cli()

    def get_bootstrappers(self):
        return self.__bootstrappers
    
    def commands(self) -> None:
        pass

    def load_base_commands(self) -> None:
        self.load('diracore.foundation.console.commands.*')


    def getCLI(self) -> AscernderCLI:
        if not hasattr(self, 'cli'):
            self.cli = AscernderCLI()
            self.cli.commands |= self._commands
            # self.cli.resolve_commands(self._commands)
            # self.cli.refresh_comand_loader()
        return self.cli
    
    def load(self, cmd:str, cmd_object_name="cli"):
        if isinstance(cmd, str):
            cmd_object = self.load_str(cmd, cmd_object_name)
        else:
            mod = cmd
            cmd_object = getattr(mod, cmd_object_name, None)
            if cmd_object is None:
                for attr_name in dir(mod):
                    cmd_object = getattr(mod, attr_name)
                    if not isinstance(cmd_object, click.BaseCommand):
                        raise ValueError(
                            f"Lazy loading of {cmd} failed by returning "
                            "a non-command object"
                        )
        return cmd_object
        
    
    def load_str(self, cmd_name:str, cmd_object_name: str):
        split_method = cmd_name.split(":", 1)
        if len(split_method) == 2:
            cmd_object_name = split_method[1]
            cmd_name = split_method[0]

        directory = cmd_name.split(".*", 1)
        if len(directory) == 2:

            dir_path = directory[0]
            modules = self.get_modules(dir_path)
            for module in modules:
                if "__init__" in module: continue
                self.load(module, cmd_object_name)
            return
        mod = importlib.import_module(cmd_name)
        cmd_object = getattr(mod, cmd_object_name)
        if not isinstance(cmd_object, click.BaseCommand):
            raise ValueError(
                f"Lazy loading of {cmd_name} failed by returning "
                "a non-command object"
            )
        return cmd_object
    
    def get_modules(self, module_dir: str):
        import pkgutil
        packages = importlib.import_module(module_dir)
        modules_path = [module_name for _, module_name, _ in pkgutil.iter_modules(packages.__path__, packages.__name__ + ".")]

        return modules_path