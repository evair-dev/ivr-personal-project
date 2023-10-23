from dataclasses import dataclass
from typing import NamedTuple, List, Dict, Optional

from ivr_gateway.steps.action import NumberedStepAction, StepAction


@dataclass
class Step:
    name: str
    step_type: str
    step_kwargs: Dict
    exit_path: Optional[Dict] = None

    def get_actions_if_exists(self) -> List[StepAction]:
        step_actions = self.step_kwargs.get("actions", [])
        # Check if the arguments attached were dict rather than
        if len(step_actions) > 0 and not isinstance(step_actions[0], StepAction):
            return [StepAction(**a) for a in step_actions]
        else:
            return step_actions

    def get_numbered_actions_if_exists(self) -> List[NumberedStepAction]:
        step_actions = self.step_kwargs.get("actions", [])
        # Check if the arguments attached were dict rather than
        if len(step_actions) > 0 and not isinstance(step_actions[0], NumberedStepAction):
            return [NumberedStepAction(**a) for a in step_actions]
        else:
            return step_actions

class StepBranch(NamedTuple):
    name: str
    steps: List[Step]
    reset_on_switch: bool = True


@dataclass
class StepTree:
    branches: List[StepBranch]
