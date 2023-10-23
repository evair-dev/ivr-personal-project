from ivr_gateway.exit_paths import CurrentQueueExitPath
from ivr_gateway.steps.api.v1 import NoopStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

noop_queue_transfer_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="transfer-to-current-queue",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    },
                ),
            ]
        )
    ]
)
