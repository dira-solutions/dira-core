from dira.contracts.foundation.application import Application
from dira.contracts.kernel import Kernel as KernelContract

from fastapi import FastAPI
from abc import ABC

class ServiceProvider(ABC):
    app: Application

    _booting_callbacks: list = []
    _booted_callbacks: list = []

    publish_groups = {}
    publishes = {}

    def __init__(self, app: Application):
        self.app = app
        self.kernel: KernelContract = self.app.make(KernelContract)
        if hasattr(self.kernel, 'server'):
            self.server: FastAPI = self.kernel.server
        else:
            self.server = None

    def register(self) -> None:
        pass

    def add_booting(self, callback: callable):
        self._booting_callbacks.append(callback)

    def add_booted(self, callback: callable):
        self._booted_callbacks.append(callback)

    def call_booting_callbacks(self):
        for callback in self._booting_callbacks:
            self.app.call(callback)

    def call_booted_callbacks(self):
        for callback in self._booted_callbacks:
            self.app.call(callback)

    def publish(self, paths, groups=None):
        self.ensure_publish_array_initialized(self.__class__.__name__)
        self.publishes[self.__class__.__name__] = self.publishes.get(self.__class__.__name__, {}) | paths
        if groups is not None:
            for group in groups if isinstance(groups, list) else [groups]:
                self.add_publish_group(group, paths)

    def ensure_publish_array_initialized(self, class_name):
        if class_name not in self.publishes:
            self.publishes[class_name] = {}

    def add_publish_group(self, group, paths):
        if group not in self.publish_groups:
            self.publish_groups[group] = []

        self.publish_groups[group] += paths

    @classmethod
    def paths_to_publish(cls, provider=None, group=None):
        if provider and hasattr(provider, '__class__'):
            provider = provider.__name__

        paths = cls.paths_for_provider_or_group(provider, group)
        if paths:
            return paths
        return []

    @classmethod
    def paths_for_provider_or_group(cls, provider=None, group=None):
        if provider and group:
            result = cls.paths_for_provider_and_group(provider, group)
            if result: 
                return result
            elif group and group in cls.publish_groups:
                return cls.publish_groups[group]
            elif provider and provider in cls.publishes:
                return cls.publishes[provider]

    @classmethod
    def paths_for_provider_and_group(cls, provider, group):
        if provider in cls.publishes and group in cls.publish_groups:
            return {
                key: cls.publishes[provider][key] 
                for key in cls.publishes[provider] 
                if key in cls.publish_groups[group]
            }
        return []

    @staticmethod
    def default_list() -> list:
        return DefaultServiceProviders().get_providers()
class DefaultServiceProviders():
    _providers: []

    def __init__(self) -> None:
        from dira.database.providers.db_service import DatabaseServiceProvider
        from dira.database.providers.redis_service import RedisServiceProvider
        from dira.queue.queue_service import QueueServiceProvider
        
        self._providers = [
            DatabaseServiceProvider,
            RedisServiceProvider,
            QueueServiceProvider,
        ]

    def get_providers(self) -> list:
        return self._providers
    

