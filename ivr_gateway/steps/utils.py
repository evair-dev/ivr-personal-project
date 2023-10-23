import copy
import re
from typing import List, Tuple, Dict, Callable, Any

from ivr_gateway.models.workflows import WorkflowRun
from ivr_gateway.steps.exceptions import FieldParsingException
from ivr_gateway.utils import recursive_dict_fetch

VALID_STEP_RUN_ACCESS_TYPES = ("initialization",)
VALID_STEP_STATE_ACCESS_TYPES = ("result", "input")
VALID_STEP_ACCESS_TYPES = VALID_STEP_RUN_ACCESS_TYPES + VALID_STEP_STATE_ACCESS_TYPES


def parse_fields_from_fieldset(fieldset: List[Tuple]) \
        -> Dict[str, Tuple[Callable[[WorkflowRun, List[str]], str], List[str]]]:
    """
    Produces a mapping of field_name => (Extractor, ExtractorTokens)
    Each extractor is of the form Callable[["WorkflowRun", List[str]], str], taking a workflow_run and list of
    extraction tokens. By calling the function w/ a workflow run, it can extract either from a workflow session
    or previous step run session
    :param fieldset:
    :return: {
        field_name => (Callable[workflow_run, extraction_tokens], extraction_tokens),
        ...
    }
    """
    field_extraction_and_token_mappings = {}
    for f in fieldset:
        if len(f) != 2:
            raise FieldParsingException("Fieldsets need to have 2 mappings field_extractor -> field_name")
        field_key = f[0]
        field_name_destination = f[1]
        field_extraction_and_token_mappings[field_name_destination] = parse_field(field_key)

    return field_extraction_and_token_mappings


def parse_field(field_key: str) -> Tuple[Callable[[WorkflowRun, List[str]], str], List[str]]:

    # Split the field extractor on "."
    field_key_tokens = field_key.split(".")
    if field_key_tokens[0].startswith("session"):
        extraction_tokens = copy.deepcopy(field_key_tokens[1:])

        # Session extractor
        def extractor(wr: WorkflowRun, _extraction_tokens: List[str]) -> str:
            return recursive_dict_fetch(wr.session, _extraction_tokens)

        return (extractor, extraction_tokens)
    elif field_key_tokens[0].startswith("step["):
        if len(field_key_tokens) < 2:
            raise FieldParsingException(
                f"Field extraction {field_key} for step requires format "
                f"step[branch:step-name].(result|initialization|input)"
            )
        step_extractor = field_key_tokens[0]
        step_component_extractor = field_key_tokens[1]
        if step_component_extractor not in VALID_STEP_ACCESS_TYPES:
            raise FieldParsingException(
                f"Invalid step_component_extractor {step_component_extractor}, "
                f"valid types are {VALID_STEP_ACCESS_TYPES}"
            )
        extraction_tokens = copy.deepcopy(field_key_tokens[2:])
        m = re.search(r"step\[([A-Za-z0-9_:-]+)]", step_extractor)
        branch_name, step_name = m.group(1).split(":")

        # Step Run extractor
        def extractor(wr: WorkflowRun, _extraction_tokens: List[str]) -> str:
            if step_component_extractor in VALID_STEP_RUN_ACCESS_TYPES:
                scope_object = wr.get_branch_step_run(branch_name, step_name)
            elif step_component_extractor in VALID_STEP_STATE_ACCESS_TYPES:
                scope_object = wr.get_step_run_state(branch_name, step_name)
            else:
                raise FieldParsingException(
                    f"Invalid step_component_extractor {step_component_extractor}, "
                    f"valid types are {VALID_STEP_STATE_ACCESS_TYPES}"
                )
            return recursive_dict_fetch(
                scope_object.__getattribute__(step_component_extractor), _extraction_tokens
            )

        return (extractor, extraction_tokens)
    else:
        raise Exception("Cannot parse step extractor fieldset")


def get_field(field_name: Any, workflow_run: WorkflowRun) -> Any:
    if type(field_name) == str:
        if field_name[:len("session.")] == "session." or field_name[:len("step[")] == "step[":
            extractor, extractor_tokens = parse_field(field_name)
            return extractor(workflow_run, extractor_tokens)
    return field_name
