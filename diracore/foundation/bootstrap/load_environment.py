from dotenv import load_dotenv
import os
from diracore.contracts.foundation.application import Application
from pathlib import PosixPath

class LoadEnvironment:
    def bootstrap(self, app: Application):
        load_dotenv(dotenv_path=self.get_full_path(app), override=True)

    def get_full_path(self, app) -> str:
        directory = app.get_env_path()
        file = app.get_env_file()
        
        return f"{directory}/{file}"
