from ivr_gateway.exit_paths import CurrentQueueExitPath, PSTNExitPath
from ivr_gateway.steps.api.v1 import BranchMapWorkflowStep, UpdateCurrentQueueStep, NoopStep, NumberedInputActionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from commands.configs.constants import LOST_CARD

main_menu_step_tree = StepTree(
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
                                "name": "application", "display_name": "For questions about an application",
                                "number": "1",
                            },
                            {
                                "name": "existing", "display_name": "For questions about an existing product",
                                "number": "2",
                            },
                            {
                                "name": "lost", "display_name": "If you are calling about a lost or stolen card",
                                "number": "3",
                            },
                            {
                                "name": "general", "display_name": "For general questions",
                                "number": "0"
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
                            "application": "application",
                            "existing": "existing",
                            "lost": "lost"
                        },
                        "default_branch": "root"
                    },
                ),
                Step(
                    name="transfer-to-current-queue",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="application",
            steps=[
                Step(
                    name="ask-about-application-type",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "product",
                        "actions": [
                            {
                                "name": "card", "display_name": "For credit cards",
                                "number": "1",
                            },
                            {
                                "name": "unsecured", "display_name": "For personal loans",
                                "number": "2",
                            },
                            {
                                "name": "deposits", "display_name": "For deposit accounts",
                                "number": "3",
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
                    name="branch-on-application-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.product",
                        "branches": {
                            "card": "application_card",
                            "unsecured": "application_unsecured",
                            "deposits": "transfer_to_banking_queue"
                        },
                        "default_branch": "application"
                    },
                ),
                Step(
                    name="set-loan-customer-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="application_card",
            steps=[
                Step(
                    name="set-card-origination-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.ORIG"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="application_unsecured",
            steps=[
                Step(
                    name="set-loan-origination-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.ORIG"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="existing",
            steps=[
                Step(
                    name="ask-about-product-type",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "product",
                        "actions": [
                            {
                                "name": "card", "display_name": "For credit cards",
                                "number": "1",
                            },
                            {
                                "name": "unsecured", "display_name": "For personal loans",
                                "number": "2",
                            },
                            {
                                "name": "deposits", "display_name": "For deposit accounts",
                                "number": "3",
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
                    name="branch-on-product-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.product",
                        "branches": {
                            "card": "existing_card",
                            "unsecured": "existing_unsecured",
                            "deposits": "transfer_to_banking_queue"
                        },
                        "default_branch": "existing"
                    },
                ),
                Step(
                    name="set-loan-customer-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="existing_card",
            steps=[
                Step(
                    name="set-card-customer-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.CUS"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="existing_unsecured",
            steps=[
                Step(
                    name="set-loan-customer-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="lost",
            steps=[
                Step(
                    name="transfer-to-lost-card",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": PSTNExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "phone_number": LOST_CARD
                        }
                    }
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
    ]
)
