from typing import Dict

import dateparser
from ddtrace import tracer

from ivr_gateway.services.amount.workflow_runner import WorkflowRunnerService, AvantBasicError
from ivr_gateway.steps.api.v1.base import APIV1Step
from ivr_gateway.steps.result import StepResult, StepSuccess, UserStepError, StepError

__all__ = [
    "AvantBasicWorkflowStep",
    "InitializeAvantBasicWorkflowStep",
    "RunAvantBasicWorkflowStep"
]

field_types = (
    'digits',
    'date',
    'currency'
)


class AvantBasicWorkflowStep(APIV1Step):
    """
    Base step used for running a workflow with Iivr basic.
    """

    def __init__(self, name: str, *args, **kwargs):
        super().__init__(name, *args, **kwargs)

    def run(self, workflow_runner_service: WorkflowRunnerService = None) -> StepResult:  # pragma: no cover
        workflow_run = self.step_run.workflow_run

        try:
            json = workflow_runner_service.run_step(workflow_run)
        except AvantBasicError:
            error = AvantBasicStepError("There was a problem with Avant Basic")
            raise self.save_result(result=error)

        response_state = json.get("state")
        if response_state is None:
            raise self.save_result(result=AvantBasicStepError("No state in the response"))

        workflow_run.store_session_variable("state", response_state)
        step_info = self.parse_step(json)

        if step_info.get("Iivr_basic_step_name") == workflow_run.session.get("Iivr_basic_step_name"):
            error = json.get("state").get("error", "")
            # errors = json.get("state").get("errors")
            # if len(errors) != 0:
            #     error = errors[0]
            error_message = self.parse_error(error)
            error = AvantBasicUserStepError("Error in Avant Basic Workflow", retryable=True,
                                            user_msg=error_message)

            raise self.save_result(result=error)

        workflow_run.store_session_variables(step_info)

        return self.save_result(result=StepSuccess(result=step_info.get("Iivr_basic_step_name")))

    @staticmethod
    def parse_error(script: str) -> str:
        script_parts = script.split(",")
        final_parts = []
        for part in script_parts:
            final_parts.append(AvantBasicWorkflowStep.parser_error_part(part))

        return " ".join(final_parts)

    @staticmethod
    def parser_error_part(part: str) -> str:
        script_dict = {
            "_enter_amount": "please enter an amount that is",
            "_or_less": "or less",
            "_enter_date": "please enter a date that is",
            "_or_later": "or later",
            "_or_earlier": "or earlier",
            "_is_not_a_business_day": "is not a business day",
            "_a_business_day": "a business day"
        }
        if part.count(':') == 0:
            return script_dict.get(part, "")
        item_type, item_value = part.split(":", 1)
        if item_type == "currency":
            return f"${item_value}"
        elif item_type == "date":
            date = dateparser.parse(item_value, date_formats=["%m%d%Y"])
            return f'{date.strftime("%B %-d, %Y")}'
        else:
            return item_value

    @staticmethod
    def parse_step(json: Dict) -> Dict:
        json_output = json.get("json_output")
        step = json_output.get("step")
        script = step.get("script")
        step_name = step.get("name")
        values = {"Iivr_basic_step_name": step_name}
        return AvantBasicWorkflowStep.parse_script(script, step_name, values)

    @staticmethod
    def parse_script(script: str, step_name: str, values: Dict) -> Dict:
        if script is None:
            return values
        script_parts = script.split(",")
        for part in script_parts:
            item_type, item_value = part.split(":", 1)
            if item_type == "currency":
                dollars, cents = item_value.split(".", 1)
                total_cents = int(dollars) * 100 + int(cents)
                values[step_name + "_currency"] = total_cents
            elif item_type == "date":
                date = dateparser.parse(item_value, date_formats=["%m%d%Y"])
                values[step_name + "_date"] = date.date().isoformat()
            elif item_type == "digits":
                values[step_name + "_digits"] = item_value
            elif item_type == "phone":
                values[step_name + "_phone_number"] = item_value
        return values


class AvantBasicUserStepError(UserStepError):
    pass


class AvantBasicStepError(StepError):
    def __init__(self, msg: str, *args, **kwargs):
        super().__init__(msg, *args, **kwargs)


class InitializeAvantBasicWorkflowStep(AvantBasicWorkflowStep):
    """
    Step used for initializing a workflow with Iivr basic.
    """

    def __init__(self, name: str, workflow_name: str, *args, **kwargs):
        self.workflow_name = workflow_name
        kwargs.update({
            "workflow_name": workflow_name,
        })
        AvantBasicWorkflowStep.__init__(self, name, *args, **kwargs)

    @tracer.wrap()
    def run(self, workflow_runner_service: WorkflowRunnerService = None) -> StepResult:
        workflow_run = self.step_run.workflow_run
        workflow_run.store_session_variable("Iivr_basic_workflow_name", self.workflow_name)

        workflow_session_state = workflow_runner_service.get_initial_state(workflow_run)
        workflow_url = workflow_runner_service.get_url(workflow_run, self.workflow_name)
        workflow_run.store_session_variable("Iivr_basic_workflow_url", workflow_url)
        workflow_run.store_session_variable("state", workflow_session_state)

        return super().run(workflow_runner_service=workflow_runner_service)


class RunAvantBasicWorkflowStep(AvantBasicWorkflowStep):
    """
    Step used for running a workflow step with Avant Basic.
    """

    def __init__(self, name: str, step_action: str, field_name: str = None, field_type: str = None, *args, **kwargs):
        self.step_action = step_action
        self.field_name = field_name
        self.field_type = field_type
        kwargs.update({
            "step_action": step_action,
            "field_name": field_name,
            "field_type": field_type
        })
        self.value = None

        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, workflow_runner_service: WorkflowRunnerService = None) -> StepResult:
        workflow_run = self.step_run.workflow_run
        workflow_state = workflow_run.session.get("state")
        workflow_state.update({"step_action": self.step_action})

        if self.field_name is not None:
            local_field = workflow_run.session.get(self.field_name)
            if self.field_type == "currency":
                local_field = f'{(local_field / 100):.2f}'

            workflow_state.update({self.field_name: local_field})

        workflow_run.store_session_variable("state", workflow_state)

        return super().run(workflow_runner_service=workflow_runner_service)
