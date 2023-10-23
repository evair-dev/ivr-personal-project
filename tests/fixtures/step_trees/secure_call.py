from ivr_gateway.steps.api.v1 import InputStep, AddFieldToWorkflowSessionStep, BranchMapWorkflowStep, \
    NoopStep, PlayMessageStep
from ivr_gateway.steps.api.v1.Iivr_basic_workflow import InitializeAvantBasicWorkflowStep, RunAvantBasicWorkflowStep
from ivr_gateway.steps.api.v1.input import ConfirmationStep
from ivr_gateway.steps.api.v1.update_call import SecureCallStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import BirthdayInput, Last4SSNInput
from ivr_gateway.exit_paths import WorkflowExitPath

secure_call_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="play-intro",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "secure_call_play_intro_message"
                    }
                ),
                Step(
                    name="enter-dob",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "dob",
                        "input_prompt": "Please enter your full 8-digit date of birth.",
                        "input_type": BirthdayInput.get_type_string()
                    },
                ),
                Step(
                    name="confirm-dob",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_dob",
                        "confirm_key": "dob",
                        "confirm_type": "date"
                    },
                ),
                Step(
                    name="reset-if-incorrect-dob",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_dob",
                        "branches": {
                            "correct": "root"
                        },
                        "on_error_reset_to_step": "enter-dob",
                    },
                ),
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
                    name="initiate-secure-call-workflow",
                    step_type=InitializeAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "workflow_name": "secure_call"
                    }
                ),
                Step(
                    name="run-dob-workflow-step",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "dob",
                        "step_action": "next"
                    }
                ),
                Step(
                    name="one-more-step",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "secure_call_one_more_step_message"
                    }
                ),
                Step(
                    name="enter-ssn",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "ssn",
                        "input_prompt": "Please enter the last four digits of your social security number.",
                        "input_type": Last4SSNInput.get_type_string()
                    },
                ),
                Step(
                    name="confirm-ssn",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_ssn",
                        "confirm_key": "ssn",
                        "confirm_type": "individual"
                    },
                ),
                Step(
                    name="reset-if-ssn-incorrect",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_ssn",
                        "branches": {
                            "correct": "root"
                        },
                        "on_error_reset_to_step": "enter-ssn"
                    },
                ),
                Step(
                    name="run-ssn-workflow-step",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "ssn",
                        "step_action": "next"
                    }
                ),
                Step(
                    name="secure-the-call",
                    step_type=SecureCallStep.get_type_string(),
                    step_kwargs={
                    }
                ),
                Step(
                    name="branch-on-call-being-secured",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.state.action_to_take",
                        "branches": {
                            "NOT_SECURED": "not_secured"
                        },
                        "default_branch": "root"
                    }
                ),
                Step(
                    name="transfer-to-self-service",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.self_service_menu",

                        }
                    }
                )
            ]
        ),
        StepBranch(
            name="not_secured",
            steps=[
                Step(
                    name="transfer-to-main-menu",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.main_menu",
                        }
                    }
                )
            ]
        )
    ]
)
