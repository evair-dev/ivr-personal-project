from abc import ABC, abstractmethod
from requests import Response


class GenericExternalService(ABC):

    @abstractmethod
    def run_service(self, **kwargs):
        pass

    @abstractmethod
    def log_response(self, request_name, response: Response):
        pass
