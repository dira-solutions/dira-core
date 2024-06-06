import os

from diracore.contracts.foundation.application import Application
from pathlib import Path, PosixPath

from pydantic_settings import BaseSettings

class LoadConfiguration:
    def __init__(self, config_class: BaseSettings = None) -> None:
        self.config_class = config_class
    
    def bootstrap(self, app: Application):
        _config: dict = {}
        if self.config_class:
            self.load_config_settings_files(app, _config)
        else:
            self.load_config_files(app, _config)
        
        app.singleton("config", _config)
        app.instance("config", _config)
        
    def load_config_settings_files(self, app: Application, _config: dict):
        config = self.config_class.model_dump()
        
        for key, value in config.items():
            _config[key] = value


    def load_config_files(self, app: Application, _config: dict):
        files: [PosixPath] = self.get_config_files(app)
        if 'app' not in files:
            raise Exception('Unable to load the "app" configuration file.')
        
        for key, path in files.items():
            config_data = {}
            exec(path.read_bytes(), {}, config_data)
            _config[key] = config_data.get("config")

    def get_config_files(self, app: Application) -> [PosixPath]:
        files = {}
        config_path = os.path.realpath(app.get_config_path())

        for file_path in Path(config_path).rglob('*.py'):
            file_name = os.path.splitext(file_path.name)[0]
            files[f"{file_name}"] = file_path.resolve()

        sorted_files = dict(sorted(files.items(), key=lambda item: item[0], reverse=False))
        return sorted_files
    
    def get_nested_directory(self, relative_path):
        nested = str(relative_path).replace(os.path.sep, '.')
        if nested:
            nested += '.'
        return nested

