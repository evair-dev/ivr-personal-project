from ivr_gateway.exit_paths import CurrentQueueExitPath, WorkflowExitPath
from ivr_gateway.steps.api.v1 import NumberedInputActionStep, BranchMapWorkflowStep, UpdateCurrentQueueStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

banking_menu_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="ask-about-call-subject",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "inquiry",
                        "actions": [
                            {
                                "name": "banking", "display_name": "For questions about your Deposits Account",
                                "number": "1"
                            },
                            {
                                "name": "credit_card", "display_name": "For questions about your <phoneme alphabet='ipa' ph='əˈvɑnt'>Iivr</phoneme> Card",
                                "number": "2"
                            },
                            {
                                "name": "loan", "display_name": "For questions about your Loan",
                                "number": "3"
                            },
                            {
                                "name": "repeat", "display_name": "To hear this again",
                                "number": "9",
                                "is_replay": True
                            }
                        ]
                    }
                ),
                Step(
                    name="branch-on-subject",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.inquiry",
                        "branches": {
                            "banking": "transfer_to_banking_queue",
                            "credit_card": "transfer_to_ingress_card",
                            "loan": "transfer_to_ingress_loan"
                        },
                        "default_branch": "root"
                    },
                ),
            ]
        ),
        StepBranch(
            name="transfer_to_banking_queue",
            steps=[
                Step(
                    name="set-bank-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.BANK.CUS"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    }
                ),
            ]
        ),
        StepBranch(
            name="transfer_to_ingress_card",
            steps=[
                Step(
                    name="go-to-ingress-card",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.ORIG"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.ingress"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="transfer_to_ingress_loan",
            steps=[
                Step(
                    name="go-to-ingress-loan",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.ORIG"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.ingress"
                        }
                    }
                )
            ]
        )
    ]
)
