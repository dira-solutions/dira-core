
import os
from enum import Enum
from diracore.container.container import Container
from diracore.contracts.foundation.application import Application as ApplicationContract
from diracore.support.service_provider import ServiceProvider
from diracore.routing.routing_service import RoutingServiceProvider
import inspect

class ApplicationEnum(Enum):
    VERSION = "0.0.1"

class Application(Container, ApplicationContract):
    _config_path: str = "config"
    _env_path: str = ""
    _env_file: str = ".env"
    
    _booted: bool = False

    _service_providers: list = []
    _loaded_providers: dict = {}

    _booting_callbacks: list = []
    _booted_callbacks: list = []

    def get_env_path(self):
        """Get the path to the environment file directory."""
        return self._env_path or os.path.realpath("")
    
    def get_env_file(self):
        return self._env_file

    def set_env_path(self, path: str):
        self._env_path = path
        return self

    def get_config_path(self):
        return self._config_path

    def __init__(self) -> None:
        super().__init__()
        """
        Create a new Illuminate application instance.
        """
    
    async def base_register(self):
        await self._register_base_bindings()
        self._register_base_service_provider()
        self._register_base_core_container_aliases()

    async def boot(self):
        await self.base_register()

        if self.is_booted():
            return

        self.fire_app_callbacks(self._booting_callbacks)
        for provider in self._service_providers:
            await self.boot_provider(provider)

        self._booted = True
        self.fire_app_callbacks(self._booted_callbacks)

    async def boot_provider(self, provider: ServiceProvider):
        provider.call_booting_callbacks()

        if hasattr(provider, 'boot'):
            await self.call([provider, 'boot'])
        provider.call_booted_callbacks()
    
    def fire_app_callbacks(self, callbacks: [callable]):
        for callback in callbacks:
            callback(self)

    def is_booted(self) -> bool:
        return self._booted
    
    def get_version(self) -> str:
        """
        Get the version number of the application.
        """
        return ApplicationEnum.VERSION.value

    async def _register_base_bindings(self) -> None:
        """
        Register the basic bindings into the container.
        """
        await self.register(RoutingServiceProvider)

    def _register_base_service_provider(self) -> None:
        """
        Register all of the base service providers.
        """
        pass

    def _register_base_core_container_aliases(self) -> None:
        """
        Register the core class aliases in the container.
        """
        pass

    async def register_configured_providers(self):
        providers = self.make("config").get("app", {}).get("providers", [])
        if isinstance(providers, tuple):
            providers = providers[0]
        for provider in providers:
            if inspect.iscoroutinefunction(self.register):
                await self.register(provider)
            else:
                self.register(provider)
    
    async def register(self, provider):
        if isinstance(provider, object):
            provider = self.resolve_provider(provider)

        if inspect.iscoroutinefunction(provider.register):
            await provider.register() 
        else:
            provider.register()

        if hasattr(provider, 'bindings'):
            for key, value in provider.bindings:
                self.bind(key, value)
        if hasattr(provider, 'singletons'):
            for key, value in provider.singletons:
                if isinstance(key, int):
                    key = value
                self.singleton(key, value)
        self.mark_as_registered(provider)

        if self.is_booted():
            await self.boot_provider(provider)

        return provider

    def mark_as_registered(self, provider: ServiceProvider) -> None:
        self._service_providers.append(provider)
        self._loaded_providers[type(provider).__name__] = True

    def resolve_provider(self, provider):
        return provider(self)

    async def bootstrap_with(self, bootstrappers):
        for bootstrapper in bootstrappers:
            bootstrap = self.make(bootstrapper).bootstrap
            if (inspect.iscoroutinefunction(bootstrap)):
                await bootstrap(self)
            else:
                bootstrap(self)
