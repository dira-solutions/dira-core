from pydantic import Field, BaseModel
from pydantic_settings import BaseSettings
from typing import Any

import os
import itertools


class ConnectionDBConfig(BaseSettings):
    url: str = Field(alias='db_url', default=None)
    host: str = Field(alias='db_host', default='127.0.0.1')
    port: str|int = Field(alias='db_port', default='5432')
    database: str = Field(alias='db_database', default='forge')
    username: str = Field(alias='db_username', default='forge')
    password: str = Field(alias='db_password', default='')
    charset: str = Field(alias='db_charset', default='utf8')
    prefix: str = Field(alias='db_prefix', default=None)
    prefix_indexes: bool = Field(default=True)
    search_path: str = Field(default='public')
    sslmode: str = Field(default='prefer')
    file_path: str = Field(alias='db_path', default=None)


class ModelsDBConfig(BaseModel):
    path: list[str] = ["app/entity/"]


class DatabaseConfig(BaseSettings):
    default: str = Field(alias='db_connection', default=None)
    connections: Any = Field(default={
        "pgsql": Field(default_factory=ConnectionDBConfig)
    })
    models: ModelsDBConfig = ModelsDBConfig()
    
    def get_engine(self, name=None):
        match name:
            case "pgsql":
                return "tortoise.backends.asyncpg"
            case "mysql":
                return "tortoise.backends.mysql"
            case "sqlite":
                return "tortoise.backends.sqlite"
            case _:
                if self.default:
                    return self.get_engine(self.default)
                return None
            
    def get_models(self):
        model_directory = self.models.path
        
        models = []
        for directory in model_directory:
            models.append(self.get_filenames(directory))
        models = list(itertools.chain(*models))
        return models
    
    def get_filenames(self, directory) -> list:
        try:
            filenames = os.listdir(directory)
            if "__pycache__" in filenames:
                filenames.remove("__pycache__")
            if not directory.endswith('/'):
                directory += "/"
            directory = directory.replace("/", ".")
            listmodules = [directory + filename.rstrip('.py') for filename in filenames]
            return listmodules
        except FileNotFoundError:
            print(f"Directory {directory} not found for models")
            return []
        
    
    def get_connection_config(self):
        connection_configs = {}
        for name, config in self.connections.items():
            if name == "sqlite":
                file_path = config.get("file_path")
                connection_configs[name] = f"sqlite://{file_path}"
            else:
                connection_configs[name] = {
                    "engine": self.get_engine(name),
                    "credentials": {
                        "host": config.get("host"),
                        "port": config.get("port"),
                        "user": config.get("username"),
                        "password": config.get("password"),
                        "database": config.get("database"),
                        "ssl": config.get("sslmode") if config.get("sslmode") else None,
                    }
                }
        return connection_configs
    
    def tortoise_config(self):
        connection_configs = self.get_connection_config()
        
        config = {
            "connections": connection_configs,
            "apps": {
                "models": {
                    "models": self.get_models() + ["aerich.models"],
                    "default_connection": self.default,
                }
            }
        }
        return config