from ivr_gateway.exit_paths import WorkflowExitPath
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

customer_lookup_self_service_wrapper_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="lookup-customer-id",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "field_name": "customer_id",
                        "service_name": "customer_lookup",
                        "lookup_key": "customer_id"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.self_service",
                        }
                    }
                ),
            ]
        )
    ]
)
