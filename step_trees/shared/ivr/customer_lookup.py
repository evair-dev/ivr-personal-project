from ivr_gateway.exit_paths import CurrentQueueExitPath
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

ivr_customer_lookup = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="get-customer-id",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "field_name": "customer_id",
                        "service_name": "customer_lookup",
                        "lookup_key": "customer_id"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    }
                )
            ]
        )
    ]
)