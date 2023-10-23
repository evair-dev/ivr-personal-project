from abc import ABC, abstractmethod

from ivr_gateway.steps.base import Step


class APIStep(Step, ABC):
    @staticmethod
    @property
    @abstractmethod
    def version() -> str:
        pass

    @classmethod
    def get_type_string(cls) -> str:
        return f"ivr_gateway.steps.api.{cls.version}.{cls.__name__}"
