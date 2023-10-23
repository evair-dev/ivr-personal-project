from ivr_gateway.exit_paths import CurrentQueueExitPath, WorkflowExitPath
from ivr_gateway.steps.api.v1 import AddFieldToWorkflowSessionStep, InitializeAvantBasicWorkflowStep, \
    ConfirmationStep, RunAvantBasicWorkflowStep, PlayMessageStep, NoopStep, InputStep, \
    JumpBranchStep, BranchMapWorkflowStep
from ivr_gateway.steps.api.v1.input import AgreementStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import DateInput, CurrencyInput

make_payment_step_tree = StepTree(
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
                    name="get-loan-id",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "field_name": "loan_id",
                        "service_name": "customer_lookup",
                        "lookup_key": "loan_id"
                    }
                ),
                Step(
                    name="initialize-make-payment",
                    step_type=InitializeAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "workflow_name": "make_payment"
                    }
                ),
                Step(
                    name="branch-on-workflow-step",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.Iivr_basic_step_name",
                        "branches": {
                            "pay_with_bank_account_on_file": "use_bank_account",
                            "apply_to_future_installments": "apply_to_future"
                        }
                    },
                ),
            ]),
        StepBranch(
            name="use_bank_account",
            steps=[
                Step(
                    name="ask-to-use-bank-account-on-file",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "name": "use_bank_account",
                        "input_key": "use_bank_account",
                        "template": "Would you like to make this payment with your bank account on file?"
                    },
                ),
                Step(
                    name="branch-on-bank-account",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.use_bank_account",
                        "branches": {
                            "yes": "use_bank_account",
                            "no": "current_queue"
                        }
                    },
                ),
                Step(
                    name="use-bank-account-on-file-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="branch-on-workflow-step",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.Iivr_basic_step_name",
                        "branches": {
                            "pay_amount_due": "late",
                            "pay_on_earliest_date": "pay_on_earliest_date"
                        }
                    },
                ),
            ]),
        StepBranch(
            name="pay_on_earliest_date",
            steps=[
                Step(
                    name="ask-if-paying-on-earliest-date",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "name": "pay_on_earliest_date",
                        "input_key": "pay_on_earliest_date",
                        "template": "Would you like to schedule this payment for {{ session.pay_on_earliest_date_date | date }}?"
                    },
                ),
                Step(
                    name="branch-on-earliest-date",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.pay_on_earliest_date",
                        "branches": {
                            "yes": "pay_on_earliest_date",
                            "no": "pay_on_earliest_date_no"
                        }
                    },
                ),
                Step(
                    name="use-earliest-date-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="branch-on-workflow-step",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.Iivr_basic_step_name",
                        "branches": {
                            "pay_amount_due": "pay_amount_due",
                            "end_queue": "current_queue",
                            "select_amount": "select_amount"
                        }

                    },
                ),
            ]),
        StepBranch(
            name="pay_on_earliest_date_no",
            steps=[
                Step(
                    name="do-not-use-earliest-date-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "no"
                    }
                ),
                Step(
                    name="ask-for-date",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "make_payment_ask_for_date_message"
                    }
                ),
                Step(
                    name="gather-date",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "date",
                        "input_prompt": "For january 2nd, 2016. Enter 0-1-0-2-2-0-1-6.",
                        "input_type": DateInput.get_type_string()
                    },
                ),
                Step(
                    name="confirm-date",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_payment_date",
                        "confirm_key": "date",
                        "confirm_type": "date"
                    },
                ),
                Step(
                    name="reset-if-date-incorrect",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_payment_date",
                        "branches": {
                            "correct": "pay_on_earliest_date_no"
                        },
                        "on_error_reset_to_step": "gather-date",
                    },
                ),
                Step(
                    name="run-workflow-step-with-date",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "date",
                        "step_action": "next",
                        "on_error_reset_to_step": "gather-date"
                    }
                ),
                Step(
                    name="branch-on-workflow-step",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.Iivr_basic_step_name",
                        "branches": {
                            "pay_amount_due": "pay_amount_due",
                            "select_amount": "select_amount",
                            "end_queue": "current_queue",
                        },
                        "default_branch": "current_queue"

                    },
                ),
            ]),
        StepBranch(
            name="pay_amount_due",
            steps=[
                Step(
                    name="ask-if-paying-amount-due",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "name": "pay_amount_due",
                        "input_key": "pay_amount_due",
                        "template": "Your next payment amount is {{session.pay_amount_due_currency | currency}}. Would you like to pay that amount?"
                    },
                ),
                Step(
                    name="branch-on-using-amount-due",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.pay_amount_due",
                        "branches": {
                            "yes": "pay_amount_due",
                            "no": "pay_amount_due_no"
                        }
                    },
                ),
                Step(
                    name="use-amount-due-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="go-to-confirmation-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "confirmation"
                    },
                ),
            ]),
        StepBranch(
            name="pay_amount_due_no",
            steps=[
                Step(
                    name="do-not-use-amount-due-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "no"
                    }
                ),
                Step(
                    name="go-to-select-amount-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "select_amount"
                    },
                ),
            ]),
        StepBranch(
            name="select_amount",
            steps=[
                Step(
                    name="ask-how-much-to-pay",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "make_payment_ask_how_much_to_pay_message"
                    }
                ),
                Step(
                    name="gather-payment-amount",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "amount",
                        "input_prompt": "Please enter the amount using the numbers on your telephone key pad. Press star for the decimal point.",
                        "input_type": CurrencyInput.get_type_string()
                    },
                ),
                Step(
                    name="confirm-payment-amount",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_payment_amount",
                        "confirm_key": "amount",
                        "confirm_type": "currency"
                    },
                ),
                Step(
                    name="reset-if-incorrect-payment-amount",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_payment_amount",
                        "branches": {
                            "correct": "select_amount"
                        },
                        "on_error_reset_to_step": "gather-payment-amount",
                    },
                ),

                Step(
                    name="run-workflow-step-with-payment-amount",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "amount",
                        "field_type": "currency",
                        "step_action": "next",
                        "on_error_reset_to_step": "gather-payment-amount"
                    }
                ),
                Step(
                    name="go-to-confirmation-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "confirmation"
                    },
                ),
            ]),
        StepBranch(
            name="late",
            steps=[
                Step(
                    name="ask-if-paying-amount-due",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "input_key": "pay_amount_due",
                        "template": "You have a past due amount of {{ session.pay_amount_due_currency | currency}}. Would you like to pay that amount?"
                    },
                ),
                Step(
                    name="branch-on-paying-amount-due",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.pay_amount_due",
                        "branches": {
                            "yes": "late",
                            "no": "current_queue"
                        }
                    },
                ),
                Step(
                    name="run-workflow-step-with-amount-due",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="ask-if-paying-on-earliest-date",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "input_key": "pay_on_earliest_date",
                        "template": "Would you like to schedule this payment for {{session.pay_on_earliest_date_date|date}}?"
                    },
                ),
                Step(
                    name="branch-on-using-earliest-date",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.pay_on_earliest_date",
                        "branches": {
                            "yes": "late",
                            "no": "current_queue"
                        }
                    },
                ),
                Step(
                    name="run-workflow-step-with-earliest-date",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="go-to-confirmation",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "confirmation"
                    },
                ),
            ]),
        StepBranch(
            name="confirmation",
            steps=[
                Step(
                    name="get-confirmation-of-payment-terms",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirmation",
                        "template": "You are authorizing <phoneme alphabet='ipa' ph='əˈvɑnt'>Avant</phoneme>, as the servicer for your account. To initiate a one time A C H debit from your account ending in {{session.confirmation_digits | individual}} for {{session.confirmation_currency | currency}} on {{session.confirmation_date | date}}. You are also authorizing <phoneme alphabet='ipa' ph='əˈvɑnt'>Avant</phoneme> as the servicer for your account to send you confirmation of this transaction via email.",
                        "input_prompt": "To authorize this transaction, press 1, to cancel, press 2, to hear this again, press 9."
                    },
                ),
                Step(
                    name="branch-on-confirmation",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirmation",
                        "branches": {
                            "yes": "confirmation",
                            "no": "payment_cancel"
                        }
                    },
                ),
                Step(
                    name="run-workflow-step-with-agreement",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "i_agree"
                    }
                ),
                Step(
                    name="play-confirmation-transfer-to-self-service",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "make_payment_play_confirmation_transfer_to_self_service_message"
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.self_service_menu",
                        }
                    }

                )
            ]),
        StepBranch(
            name="apply_to_future",
            steps=[
                Step(
                    name="ask-if-applying-to-future-installment",
                    step_type=AgreementStep.get_type_string(),
                    step_kwargs={
                        "input_key": "apply_to_future_installment",
                        "template": "Is this payment for your upcoming installment due on: {{session.apply_to_future_installments_date | date}}?"
                    },
                ),
                Step(
                    name="branch-on-applying-future-installment",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.apply_to_future_installment",
                        "branches": {
                            "yes": "apply_to_future",
                            "no": "apply_to_future_no"
                        }
                    },
                ),
                Step(
                    name="run-workflow-step-with-future-installment",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes"
                    }
                ),
                Step(
                    name="go-to-use-bank-account-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "use_bank_account"
                    },
                ),
            ]
        ),
        StepBranch(
            name="apply_to_future_no",
            steps=[
                Step(
                    name="run-workflow-step-with-not-future-installment",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "no"
                    }
                ),
                Step(
                    name="go-to-use-bank-account-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "use_bank_account"
                    },
                ),
            ]
        ),
        StepBranch(
            name="payment_cancel",
            steps=[
                Step(
                    name="play-canceled-payment-message-go-to-self-service",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={

                        "message_key": "make_payment_payment_cancel_message",
                    },
                    exit_path={
                        "exit_path_type": WorkflowExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "workflow": "Iivr.self_service_menu",
                        }
                    }
                )
            ]),
        StepBranch(
            name="current_queue",
            steps=[
                Step(
                    name="go-to-current-queue",
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
