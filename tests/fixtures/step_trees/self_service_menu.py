from ivr_gateway.exit_paths import WorkflowExitPath, CurrentQueueExitPath, PSTNExitPath
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep, BranchMapWorkflowStep, NoopStep, \
    UpdateCurrentQueueStep, InputActionStep, AddFieldsToWorkflowSessionStep, BooleanLogicStep, NumberedInputActionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from commands.configs.constants import LOST_CARD

self_service_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="get-products-count-no-cache",
                    step_type=AddFieldsToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_keys": ["products_count", "product_type"],
                        "use_cache": False,
                    }
                ),
                Step(
                    name="set-multiple-product",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.products_count", 1
                        ],
                        "result_field": "has_multiple_products",
                        "op": ">"
                    }
                ),
                Step(
                    name="branch-on-has-multiple-products",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.has_multiple_products",
                        "branches": {
                            "True": "multiple_products",
                        },
                        "default_branch": "root"
                    },
                ),
                Step(
                    name="branch-on-product-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.product_type",
                        "branches": {
                            "Loan": "loan",
                            "CreditCardAccount": "card"
                        },
                        "default_branch": "root"
                    },
                ),
                Step(
                    name="get-application-type",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_key": "application_type"
                    }
                ),
                Step(
                    name="branch-on-application-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.application_type",
                        "branches": {
                            "installment": "loan_origination"
                        },
                        "default_branch": "other"
                    },
                )
            ]
        ),
        StepBranch(
            name="multiple_products",
            steps=[
                Step(
                    name="list-product-options",
                    step_type=InputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "product_choice",
                        "actions": [
                            {
                                "name": "card_questions",
                                "display_name": "For questions about your Credit Card"
                            },
                            {
                                "name": "loan_questions",
                                "display_name": "For questions about your Loan"
                            }
                        ],
                    }
                ),
                Step(
                    name="branch-on-product-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.product_choice",
                        "branches": {
                            "card_questions": "card",
                            "loan_questions": "loan",
                        },
                        "on_error_reset_to_step": "list-product-options",
                        "on_error_switch_to_branch": "other",
                    },
                )
            ]
        ),
        StepBranch(
            name="loan",
            steps=[
                Step(
                    name="get-application-type",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_key": "application_type"
                    }
                ),
                Step(
                    name="branch-on-application-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.application_type",
                        "branches": {
                            "installment": "loan"
                        },
                        "default_branch": "loan_balance_make_payment"
                    },
                ),
                Step(
                    name="get-loan-can-make-ach-payment",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_key": "loan_can_make_ach_payment"
                    }
                ),
                Step(
                    name="branch-on-loan-can-make-ach-payment",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_can_make_ach_payment",
                        "branches": {
                            "True": "loan",
                            "False": "loan_balance_origination"
                        },
                        "default_branch": "loan"
                    },
                ),
                Step(
                    name="list-menu-options",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "menu_choice",
                        "actions": [
                            {
                                "name": "loan_balance",
                                "display_name": "To hear your current loan balance and summary of recent payments",
                                "number": "1",
                            },
                            {
                                "name": "loan_make_payment",
                                "display_name": "To make a payment on your personal unsecured loan",
                                "number": "2",
                            },
                            {
                                "name": "loan_origination", "display_name": "If you’re calling about a loan application",
                                "number": "3",
                            },
                            {
                                "name": "other", "display_name": "For all other questions",
                                "number":"0"
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
                    name="branch-on-menu-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.menu_choice",
                        "branches": {
                            "loan_make_payment": "loan_make_payment",
                            "loan_balance": "loan_balance",
                            "loan_origination": "loan_origination"
                        },
                        "default_branch": "other"
                    },
                ),
            ]
        ),
        StepBranch(
            name="loan_balance_make_payment",
            steps=[
                Step(
                    name="get-loan-can-make-ach-payment",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_key": "loan_can_make_ach_payment"
                    }
                ),
                Step(
                    name="branch-on-loan-can-make-ach-payment",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_can_make_ach_payment",
                        "branches": {
                            "True": "loan_balance_make_payment",
                            "False": "loan_balance_only"
                        },
                        "default_branch": "loan_balance_only"
                    },
                ),
                Step(
                    name="list-menu-options",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "menu_choice",
                        "actions": [
                            {
                                "name": "loan_balance",
                                "display_name": "To hear your current loan balance and summary of recent payments",
                                "number": "1",
                            },
                            {
                                "name": "loan_make_payment",
                                "display_name": "To make a payment on your personal unsecured loan",
                                "number": "2",
                            },
                            {
                                "name": "other", "display_name": "For all other questions",
                                "number":"0"
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
                    name="branch-on-menu-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.menu_choice",
                        "branches": {
                            "loan_make_payment": "loan_make_payment",
                            "loan_balance": "loan_balance",
                            
                        },
                        "default_branch": "other"
                    },
                ),
            ]
        ),
        StepBranch(
            name="loan_balance_origination",
            steps=[
                Step(
                    name="branch-on-loan-can-make-ach-payment",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_can_make_ach_payment",
                        "branches": {
                            "True": "loan",
                            "False": "loan_balance_origination"
                        },
                        "default_branch": "loan"
                    },
                ),
                Step(
                    name="list-menu-options",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "menu_choice",
                        "input_prompt": "To hear your current loan balance and summary of recent payments, press 1. If you’re calling about a loan application, press 2. For all other questions, press 0. To hear this again, press 9.",
                        "actions": [
                            {
                                "name": "loan_balance",
                                "display_name": "To hear your current loan balance and summary of recent payments",
                                "number": "1",
                            },
                            {
                                "name": "loan_origination", "display_name": "If you’re calling about a loan application",
                                "number": "2",
                            },
                            {
                                "name": "other", "display_name": "For all other questions",
                                "number":"0"
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
                    name="branch-on-menu-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.menu_choice",
                        "branches": {
                            "loan_make_payment": "loan_make_payment",
                            "loan_balance": "loan_balance",
                            "loan_origination": "loan_origination",
                            
                        },
                        "default_branch": "other"
                    },
                ),
            ]
        ),
        StepBranch(
            name="loan_balance_only",
            steps=[
                Step(
                    name="list-menu-options",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "menu_choice",
                        "actions": [
                            {
                                "name": "loan_balance",
                                "display_name": "To hear your current loan balance and summary of recent payments",
                                "number": "1",
                            },
                            {
                                "name": "other", "display_name": "For all other questions",
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
                    name="branch-on-menu-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.menu_choice",
                        "branches": {
                            "loan_balance": "loan_balance",
                        },
                        "default_branch": "other"
                    },
                ),
            ]
        ),
        StepBranch(
            name="card",
            steps=[
                Step(
                    name="list-menu-options",
                    step_type=NumberedInputActionStep.get_type_string(),
                    step_kwargs={
                        "input_key": "menu_choice",
                        "actions": [
                            {
                                "name": "card_balance",
                                "display_name": "To hear your card balance and statement information",
                                "number": "1",
                            },
                            {
                                "name": "card_make_payment",
                                "display_name": "To make a payment on your credit card balance",
                                "number": "2",
                            },
                            {
                                "name": "card_lost", "display_name": "If you’re calling about a lost or stolen card",
                                "number": "3",
                            },
                            {
                                "name": "other", "display_name": "For all other questions",
                                "number" : "0"

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
                    name="branch-on-menu-choice",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.menu_choice",
                        "branches": {
                            "card_balance": "card_balance",
                            "card_make_payment": "card_make_payment",
                            "card_lost": "card_lost",
                        },
                        "default_branch": "other"
                    },
                ),
            ]
        ),
        StepBranch(
            name="loan_origination",
            steps=[
                Step(
                    name="go-to-loan-origination-workflow",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.loan_origination",
                        }
                    }
                )
            ]
        ),
        StepBranch(
            name="loan_make_payment",
            steps=[
                Step(
                    name="get-loan-count",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_key": "loan_count"
                    }
                ),
                Step(
                    name="branch-on-loan-count",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_count",
                        "branches": {
                            "1": "loan_make_payment"
                        },
                        "default_branch": "other"
                    },
                ),
                Step(
                    name="transfer-to-make-payment",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.make_payment",
                        }
                    }
                )
            ]
        ),
        StepBranch(
            name="loan_balance",
            steps=[
                Step(
                    name="set-queue-loan-customer-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
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
            name="card_make_payment",
            steps=[
                Step(
                    name="set-queue-card-customer-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.CUS"
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
            name="card_balance",
            steps=[
                Step(
                    name="set-queue-card-customer-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.CUS"
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
            name="card_lost",
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
                )
            ]
        ),
        StepBranch(
            name="other",
            steps=[
                Step(
                    name="transfer-to-current-queue",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={},
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                )
            ]
        )

    ]
)
