# TODO: Dynamically load these
from .add_field_to_workflow_session import *  # noqa: F401,F403
from .add_session_variable import *  # noqa: F403
from .Iivr_basic_workflow import *  # noqa: F401,F403
from .base import APIV1Step  # noqa: F401,F403
from .branch_workflow import *  # noqa: F401,F403
from .call_external_service import *  # noqa: F401,F403
from .input import *  # noqa: F401,F403
from .logic import *  # noqa: F401,F403
from .noop import *  # noqa: F401,F403
from .play_message import *  # noqa: F401,F403
from .update_call import *  # noqa: F401,F403

REGISTRY = [
    AddFieldToWorkflowSessionStep,  # noqa: F405
    BranchWorkflowStep,  # noqa: F405
    JumpBranchStep,  # noqa: F405
    InputStep,  # noqa: F405
    InputActionStep,  # noqa: F405
    NumberedInputActionStep,  # noqa: F405
    BooleanLogicStep,  # noqa: F405
    NoopStep,  # noqa: F405
    PlayMessageStep,  # noqa: F405
    AvantBasicWorkflowStep,  # noqa: F405
    InitializeAvantBasicWorkflowStep,  # noqa: F405
    RunAvantBasicWorkflowStep,  # noqa: F405
    UpdateCallStep,  # noqa: F405
    CopySessionVariable,  # noqa: F405
    CallExternalServiceStep  # noqa: F405
]
