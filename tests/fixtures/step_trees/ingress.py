from ivr_gateway.exit_paths import WorkflowExitPath, CurrentQueueExitPath
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep, NoopStep, BranchMapWorkflowStep, \
    BooleanLogicStep, UpdateCurrentQueueStep, AddFieldsToWorkflowSessionStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

ingress_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="get-customer-info",
                    step_type=AddFieldsToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer_lookup",
                        "lookup_keys": ["customer_id", "applications_count", "application_type", "product_type",
                                        "loan_operationally_charged_off?", "loan_past_due_amount_cents",
                                        "card_past_due_amount_cents", "loan_days_late",
                                        "card_days_late", "customer_state_of_residence", "loan_in_grace_period?"]
                    }
                ),
                Step(
                    name="branch-on-customer-id",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.customer_id",
                        "branches": {
                            "None": "check_if_incoming_from_banking"
                        },
                        "default_branch": "known_customer"
                    }
                ),
            ]
        ),
        StepBranch(
            name="known_customer",
            steps=[
                Step(
                    name="branch-on-application-count",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.applications_count",
                        "branches": {
                            "0": "no_application"
                        },
                        "default_branch": "application"
                    },
                )
            ]
        ),
        StepBranch(
            name="application",
            steps=[
                Step(
                    name="branch-on-application-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.application_type",
                        "branches": {
                            "installment": "loan_application",
                            "credit_card": "card_application"
                        },
                        "default_branch": "loan_application"
                    },
                )
            ]
        ),
        StepBranch(
            name="loan_application",
            steps=[
                Step(
                    name="set-loan-application-queue",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.ORIG"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.secure_call",
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="card_application",
            steps=[
                Step(
                    name="set-card-application-queue",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.ORIG"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.secure_call",
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="no_application",
            steps=[
                Step(
                    name="branch-on-product-type",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.product_type",
                        "branches": {
                            "Loan": "loan",
                            "CreditCardAccount": "card"
                        },
                        "default_branch": "no_product"
                    },
                )
            ]
        ),
        StepBranch(
            name="loan",
            steps=[
                Step(
                    name="set-loan-customer-queue",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
                    }
                ),
                Step(
                    name="branch-if-charged-off",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_operationally_charged_off?",
                        "branches": {
                            "True": "loan_state_of_residence"
                        },
                        "default_branch": "loan"
                    },
                ),
                Step(
                    name="get-max-past-due-amount",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "queue",
                        "lookup_key": "past_due_cents_amount",
                        "field_name": "max_past_due_cents"
                    }
                ),
                Step(
                    name="check-past-due-amount",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_past_due_amount_cents", "session.max_past_due_cents"
                        ],
                        "result_field": "past_due_too_large",
                        "op": ">"
                    }
                ),
                Step(
                    name="branch-on-past-due-amount",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.past_due_too_large",
                        "branches": {
                            "True": "loan_check_grace_period"
                        },
                        "default_branch": "loan"
                    },
                ),
                Step(
                    name="check-days-late",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_days_late",
                        "branches": {
                            "0": "loan"
                        },
                        "default_branch": "loan_check_grace_period"
                    },
                ),

                Step(
                    name="noop-exit-to-secure-call",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={},
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.secure_call"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="card",
            steps=[
                Step(
                    name="set-card-customer-queue",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.CUS"
                    }
                ),
                Step(
                    name="get-max-past-due-amount",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "queue",
                        "lookup_key": "past_due_cents_amount",
                        "field_name": "max_past_due_cents"
                    }
                ),
                Step(
                    name="check-past-due-amount",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.card_past_due_amount_cents", "session.max_past_due_cents"
                        ],
                        "result_field": "past_due_too_large",
                        "op": ">"
                    }
                ),
                Step(
                    name="branch-on-past-due-amount",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.past_due_too_large",
                        "branches": {
                            "True": "card_state_of_residence"
                        },
                        "default_branch": "card"
                    },
                ),
                Step(
                    name="branch-on-days-late",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.card_days_late",
                        "branches": {
                            "0": "card",
                            "None": "card"
                        },
                        "default_branch": "card_state_of_residence"
                    },
                ),
                Step(
                    name="noop-go-to-secure-call",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.secure_call"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="check_if_incoming_from_banking",
            steps=[
                Step(
                    name="check-for-banking-flag",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "call",
                        "lookup_key": "is_banking_call",
                        "field_name": "transferred_from_banking"
                    }
                ),
                Step(
                    name="branch-on-transferred-from-banking",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.transferred_from_banking",
                        "branches": {
                            "True": "transfer_to_queue",
                            "False": "unknown_customer"
                        },
                        "default_branch": "unknown_customer"
                    },
                )
            ]
        ),
        StepBranch(
            name="unknown_customer",
            steps=[
                Step(
                    name="get-if-current-queue-is-pay-queue",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "queue",
                        "lookup_key": "is_pay_queue"
                    }
                ),
                Step(
                    name="branch-on-current-queue",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.is_pay_queue",
                        "branches": {
                            "True": "transfer_to_queue",
                            "False": "unknown_customer"
                        },
                        "default_branch": "unknown_customer"
                    },
                ),
                Step(
                    name="noop-go-to-main-menu",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.main_menu"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="transfer_to_queue",
            steps=[
                Step(
                    name="noop-go-to-current-queue",
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
            name="no_product",
            steps=[
                Step(
                    name="noop-go-to-main-menu",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.main_menu"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="loan_check_grace_period",
            steps=[
                Step(
                    name="branch-on-grace-period",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_in_grace_period?",
                        "branches": {
                            "True": "loan_check_grace_period",
                            "False": "loan_state_of_residence"
                        },
                        "default_branch": "loan_state_of_residence"
                    },
                ),
                Step(
                    name="update-queue-go-to-secure-call",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.CUS"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.secure_call"
                        }
                    }
                ),
            ]
        ),
        StepBranch(
            name="loan_state_of_residence",
            steps=[
                Step(
                    name="branch-on-state",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.customer_state_of_residence",
                        "branches": {
                            "NV": "loan_int",
                            "CT": "loan_int"
                        },
                        "default_branch": "loan_ext"
                    },
                )
            ]
        ),
        StepBranch(
            name="loan_int",
            steps=[
                Step(
                    name="set-internal-loan-pay-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.PAY.INT"
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
            name="loan_ext",
            steps=[
                Step(
                    name="set-external-loan-pay-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.LN.PAY.EXT"
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
            name="card_state_of_residence",
            steps=[
                Step(
                    name="branch-on-state-of-residence",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.customer_state_of_residence",
                        "branches": {
                            "NV": "card_int",
                            "CT": "card_int"
                        },
                        "default_branch": "card_ext"
                    },
                )
            ]
        ),
        StepBranch(
            name="card_int",
            steps=[
                Step(
                    name="set-internal-card-pay-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.PAY.INT"
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
            name="card_ext",
            steps=[
                Step(
                    name="set-external-card-pay-queue-transfer",
                    step_type=UpdateCurrentQueueStep.get_type_string(),
                    step_kwargs={
                        "queue": "AFC.CC.PAY.EXT"
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                        "exit_path_kwargs": {
                        }
                    }
                ),
            ]
        ),
    ]
)
