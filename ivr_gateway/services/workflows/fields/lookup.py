from abc import ABC, abstractmethod
from datetime import datetime as dt
from typing import Set

import dateparser
from sqlalchemy import orm

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.steps.inputs import Numeric


class FieldLookupServiceABC(ABC):
    field_registry: Set[str]

    def __init__(self, workflow_run: WorkflowRun, db_session: orm.Session):
        self.db_session = db_session
        self.workflow_run = workflow_run
        if self.field_registry is None:
            raise RuntimeError(
                f"Field Lookup service {self.__class__.__name__} does not have entry for required field, field_registry"
            )

    @abstractmethod
    def get_field_by_lookup_key(self, lookup_key: str, use_cache: bool = True, service_overrides: dict = None) -> str:
        pass

    def get_date_field_by_lookup_key(self, lookup_key: str) -> dt:
        return dateparser.parse(self.get_field_by_lookup_key(lookup_key))

    def get_numeric_field_by_lookup_key(self, lookup_key: str, int_cast=False) -> Numeric:
        if int_cast:
            return int(self.get_field_by_lookup_key(lookup_key))
        else:
            return float(self.get_field_by_lookup_key(lookup_key))

    def get_bool_field_by_lookup_key(self, lookup_key: str) -> bool:
        return bool(self.get_field_by_lookup_key(lookup_key))

    def get_dict_field_by_lookup_key(self, lookup_key: str) -> dict:
        pass
