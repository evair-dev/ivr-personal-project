from ivr_gateway.exit_paths import CurrentQueueExitPath, HangUpExitPath
from ivr_gateway.steps.api.v1 import UpdateCurrentQueueStep, PlayMessageStep, BooleanLogicStep, \
    AddFieldToWorkflowSessionStep, BranchMapWorkflowStep, NoopStep, InputActionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

loan_origination_step_tree = StepTree(
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
                    }
                ),
                Step(
                    name="set-should-continue-true",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.customer_id", "session.customer_id"
                        ],
                        "result_field": "should_continue",
                        "op": "=="
                    }
                ),
                Step(
                    name="branch-on-should-continue",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.should_continue",
                        "branches": {
                            "True": "root",
                            "False": "hangup"
                        }
                    },
                ),
                Step(
                    name="set-should-continue-false",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.customer_id", "session.customer_id"
                        ],
                        "result_field": "should_continue",
                        "op": "!="
                    }
                ),
                Step(
                    name="play-originations-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "loan_origininations_message"
                    }
                ),
                Step(
                    name="gather-customer-wants-to-talk-to-agent",
                    step_type=InputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "action",
                        "input_prompt": " ",
                        "on_error_reset_to_step": "branch-on-should-continue",
                        "actions": [
                            {
                                "name": "agent", "display_name": "To talk to agent"
                            },
                        ]
                    }
                ),
                Step(
                    name="set-origination-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.ORIG"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                )
            ]
        ),
        StepBranch(
            name="hangup",
            steps=[
                Step(
                    name="noop-hangup",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": HangUpExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        )
    ]
)
