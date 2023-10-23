from datetime import datetime as dt
from typing import List, Tuple, Set

from ddtrace import tracer
from jinja2 import Environment

from ivr_gateway.steps.api.v1 import APIV1Step
from ivr_gateway.steps.inputs import StepInput
from ivr_gateway.steps.result import StepResult, StepSuccess
from ivr_gateway.steps.utils import parse_fields_from_fieldset
from ivr_gateway.services.message import SimpleMessageService

__all__ = [
    "PlayMessageStep"
]

environment = Environment(
    autoescape=True
)


def parse_str_to_date(value: str) -> dt:
    return dt.fromisoformat(value)


empty_set = frozenset()


def grouped(value, grouping: Set = empty_set, spacing_character: str = " "):
    # TODO: make sure it parses to a
    if grouping == empty_set or len(grouping) == 0:
        return f'{value}'
    else:
        group_sum = sum(grouping)
        if group_sum != len(value):
            raise Exception(f"Cannot block value {value} into {grouping}")
        acc = []
        slice_idx = 0
        for blk in grouping:
            digits = value[slice_idx:(slice_idx + blk)]
            acc.append(digits)
            slice_idx += blk
        return spacing_character.join(acc)


def individual(value: str):
    digits = list(value)
    return ' '.join(digits)


def date(value: str):
    d = parse_str_to_date(value)
    return d.strftime("%B %-d, %Y")


def date_with_day(value: str):
    d = parse_str_to_date(value)
    return d.strftime("%A, %B %-d, %Y")


def payment_date(value: str):
    d = parse_str_to_date(value)
    return d.strftime("%A, %B %-d, %Y at %I:%M %p")


def date_mmddyy(value: str):
    d = parse_str_to_date(value)
    return d.strftime("%m/%d/%y")


def currency(value, symbol="$"):
    """
    Currency is always treated as represented in cents
    :param value:
    :param symbol:
    :return:
    """
    value = int(value)
    return f'${(value / 100):.2f}'


def last_characters(value, num_chars):
    value = str(value)
    if len(value) <= num_chars:
        return value
    return value[-num_chars:]


environment.filters['grouped'] = grouped
environment.filters['individual'] = individual
environment.filters['date'] = date
environment.filters['date_with_day'] = date_with_day
environment.filters['payment_date'] = payment_date
environment.filters['date_mmddyy'] = date_mmddyy
environment.filters['currency'] = currency
environment.filters['last_characters'] = last_characters


class PlayMessageStep(APIV1Step):
    """
    Play Message Step Example Usage:
    {
        "name": "step-name",
        "step_type": PlayMessageStep.get_type_string(),
        "step_kwargs": {
            "fieldset": [
                ("step[branch:step-name].(result|initialization|input).field_name", "map_field_2"),
                "etc..."
                # NOTE: Workflow session is always available as "session" variable in template
            ],
            "template": '''Some string that you want rendered with the fieldset + workflow session using jinja2
            style templates. Here is me accessing a session variable {{ session.get("test", "default") }}''',
        }
    }
    """

    message_service = SimpleMessageService()

    def __init__(self, name: str, template: str = "", fieldset: List[Tuple[str, str]] = None, message_key: str = None,
                 start_new_message: bool = False, end_break: bool = False, *args, **kwargs):
        self.fieldset = fieldset or []
        self.field_extractors = parse_fields_from_fieldset(self.fieldset)
        if message_key is None:
            self._template = template
        else:
            self._template = self.message_service.get_message_by_key(message_key) or template
        self._message_template = environment.from_string(self._template)
        self.start_new_message = start_new_message
        self.end_break = end_break
        kwargs.update({
            "message_key": message_key,
            "template": self._template,  # Should we persist this here so we can see it as part of the initialization
                                         # since messages can change?
            "fieldset": fieldset,
            "start_new_message": start_new_message,
            "end_break": end_break
        })
        super().__init__(name, *args, **kwargs)

    @tracer.wrap()
    def run(self, step_input: StepInput = None) -> StepResult:
        return self.save_result(result=StepSuccess(result=self.message))

    @property
    def message(self) -> str:
        workflow_run_session = self.step_run.workflow_run.session
        render_context = {
            "session": workflow_run_session
        }
        for field_name, (extractor, extraction_tokens) in self.field_extractors.items():
            render_context[field_name] = extractor(self.step_run.workflow_run, extraction_tokens)
        return self._message_template.render(**render_context)
