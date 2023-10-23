from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.steps.api.v1 import NoopStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

hangup_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="noop-hangup",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": HangUpExitPath.get_type_string(),
                    },
                ),
            ]
        )
    ]
)
