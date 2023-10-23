import json
from typing import TYPE_CHECKING

from ddtrace import tracer

from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepError, StepSuccess

if TYPE_CHECKING:
    from ivr_gateway.services.workflows.fields import FieldSessionService

__all__ = [
    "AddFieldToWorkflowSessionStep",
    "AddFieldsToWorkflowSessionStep"
]


class AddFieldToWorkflowSessionStep(APIV1Step):
    """
    Step used for adding a field to the workflow_run session which can then later be used to in
    comparison or other branch logic steps
    """

    def __init__(self, name: str, service_name: str, lookup_key: str, field_name: str = None, use_cache: bool = True,
                 service_overrides: dict = None, *args, **kwargs):
        self.service_name = service_name
        self.lookup_key = lookup_key
        self.field_name = field_name if field_name is not None else self.lookup_key
        self.use_cache = use_cache
        self.service_overrides = service_overrides
        self._field_service_config = {
            "field_name": field_name,
            "service_name": service_name,
            "lookup_key": lookup_key,
            "use_cache": use_cache,
            "service_overrides": service_overrides
        }
        kwargs.update(self._field_service_config)
        self.value = None
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, service: "FieldSessionService" = None) -> StepResult:
        if service is None:
            error = StepError(msg=f"Error running AddFieldToWorkflowSessionStep name:{self.name}. "
                                  f"Service {service} not specified by engine."
                                  f"Field service config: {json.dumps(self._field_service_config)}")
            raise self.save_result(result=error)
        workflow_run = self.step_run.workflow_run
        self.value = service.get_field_for_step(workflow_run, self.service_name, self.lookup_key,
                                                use_cache=self.use_cache, service_overrides=self.service_overrides)
        workflow_run.store_session_variable(self.field_name, self.value)
        return self.save_result(result=StepSuccess(result=self.value))


class AddFieldsToWorkflowSessionStep(APIV1Step):
    """
    Step used for adding a field to the workflow_run session which can then later be used to in
    comparison or other branch logic steps
    """

    def __init__(self, name: str, service_name: str, lookup_keys: [str], use_cache: bool = True,
                 service_overrides: dict = None, *args, **kwargs):
        self.service_name = service_name
        self.lookup_keys = lookup_keys
        self.use_cache = use_cache
        self.service_overrides = service_overrides
        self._field_service_config = {
            "service_name": service_name,
            "lookup_keys": lookup_keys,
            "use_cache": use_cache,
            "service_overrides": service_overrides
        }
        kwargs.update(self._field_service_config)
        self.value = None
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, service: "FieldSessionService" = None) -> StepResult:
        if service is None:
            error = StepError(msg=f"Error running AddFieldsToWorkflowSessionStep name:{self.name}. "
                                  f"Service {service} not specified by engine."
                                  f"Field service config: {json.dumps(self._field_service_config)}")
            raise self.save_result(result=error)
        workflow_run = self.step_run.workflow_run
        use_cache = self.use_cache
        values = {}
        for lookup_key in self.lookup_keys:
            value = service.get_field_for_step(workflow_run, self.service_name, lookup_key, use_cache=use_cache,
                                               service_overrides=self.service_overrides)
            values.update({lookup_key: value})
            use_cache = True
        workflow_run.store_session_variables(values)
        self.value = values
        return self.save_result(result=StepSuccess(result=self.value))
