from typing import Optional


class StepAction:

    def __init__(self, name: str, display_name: str, is_finish: bool = False, is_replay: bool = False,
                 emphasized: bool = False, secondary: Optional["StepAction"] = None, opts: dict = None,):
        self.name = name
        self.display_name = display_name
        self.is_finish = is_finish
        self.is_replay = is_replay
        self.emphasized = emphasized
        self.secondary = secondary
        self.opts = opts or {}

class NumberedStepAction(StepAction):
    def __init__(self, name: str, display_name: str, number: str, is_finish: bool = False, is_replay: bool = False,
                 emphasized: bool = False, secondary: Optional["NumberedStepAction"] = None, opts: dict = None):
        self.number = number
        super().__init__(name, display_name, is_finish, is_replay, emphasized, secondary, opts)
