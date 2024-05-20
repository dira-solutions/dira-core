from abc import ABC, abstractmethod

class Application(ABC):
    @abstractmethod
    def get_version()-> str:
        """
        Get the version number of the application.
        """
        pass


