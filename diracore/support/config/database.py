from pydantic import BaseModel, Field


class ConnectionDBConfig(BaseModel):
    url: str = Field(alias='db_url', default=None)
    host: str = Field(alias='db_host', default='127.0.0.1')
    port: str|int = Field(alias='db_port', default='5432')
    database: str = Field(alias='db_database', default='forge')
    username: str = Field(alias='db_username', default='forge')
    password: str = Field(alias='db_password', default='')
    charset: str = Field(alias='utf8', default=None)
    prefix: str = Field(alias='', default=None)
    prefix_indexes: bool = Field(default=True)
    search_path: str = Field(default='public')
    sslmode: str = Field(default='prefer')


class ModelsDBConfig(BaseModel):
    path: list[str] = ["app/entity/"]


class DatabaseConfig(BaseModel):
    default: str = Field(alias='db_connection', default=None)
    connections: dict[str, ConnectionDBConfig] = Field(default={
        "pgsql": ConnectionDBConfig()
    })
    models: ModelsDBConfig = ModelsDBConfig()