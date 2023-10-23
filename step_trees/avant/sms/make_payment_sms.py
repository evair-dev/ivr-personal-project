from ivr_gateway.exit_paths import SMSExitPath
from ivr_gateway.steps.api.v1 import AddFieldsToWorkflowSessionStep, InitializeAvantBasicWorkflowStep, \
    RunAvantBasicWorkflowStep, PlayMessageStep, InputStep, JumpBranchStep, BranchMapWorkflowStep, BooleanLogicStep, \
    CopySessionVariable, NoopStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import ZipCodeInput, TextInput, CurrencyTextInput

make_payment_sms_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="gather-zip-code",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "entered_zip_code",
                        "input_prompt": "To set up a payment, please reply with your zip code to confirm your identity. Please note that messages will time out after 1 hour to protect your security.",
                        "input_type": ZipCodeInput.get_type_string()
                    },
                ),
                Step(
                    name="check-zip-code",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.entered_zip_code", "session.zip_code"
                        ],
                        "result_field": "confirmed_zip_code",
                        "op": "=="
                    }
                ),
                Step(
                    name="branch-on-zip-code-response",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirmed_zip_code",
                        "branches": {
                            "True": "get_customer_info",
                            "False": "root"
                        }
                    }
                ),
                Step(
                    name="regather-zip-code",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "entered_zip_code",
                        "input_prompt": "Sorry, invalid zip code. Try again please.",
                        "input_type": ZipCodeInput.get_type_string(),
                        "retry_count": 2
                    },
                ),
                Step(
                    name="recheck-zip-code",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.entered_zip_code", "session.zip_code"
                        ],
                        "result_field": "confirmed_zip_code",
                        "op": "=="
                    }
                ),
                Step(
                    name="branch-on-zip-code-retry",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirmed_zip_code",
                        "branches": {
                            "True": "get_customer_info"
                        },
                        "on_error_reset_to_step": "regather-zip-code",
                        "on_error_switch_to_branch": "payment_not_made"
                    }
                )
            ]),
        StepBranch(
            name="get_customer_info",
            steps=[
                Step(
                    name="set-upcoming-payment-false",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.zip_code", "session.zip_code"
                        ],
                        "result_field": "upcoming_payment",
                        "op": "!="
                    }
                ),
                Step(
                    name="get-product-info-for-customer",
                    step_type=AddFieldsToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "service_name": "customer",
                        "lookup_keys": ["loan_id", "loan_past_due_amount_cents"]
                    }
                ),
                Step(
                    name="branch-on-lookup-error",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_id",
                        "branches": {
                            "None": "payment_not_made"
                        },
                        "default_branch": "get_customer_info"
                    }
                ),
                Step(
                    name="set-play-confirmation-message-true",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "play_additional_confirmation_message",
                        "op": "=="
                    }
                ),
                Step(
                    name="play-zip-code-confirmed-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": "Zipcode confirmed."
                    }
                ),
                Step(
                    name="set-potential-cutoff-scenario-false",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "potential_cutoff_scenario",
                        "op": "!="
                    }
                ),
                Step(
                    name="branch-to-initialize-payment-if-no-past-due",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_past_due_amount_cents",
                        "branches": {
                            "0": "initialize_payment",
                            "None": "initialize_payment"
                        },
                        "default_branch": "get_customer_info"
                    }
                ),
                Step(
                    name="play_debt_collection_message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": "This is an attempt to collect a debt and any information obtained will be used for that purpose."
                    }
                ),
                Step(
                    name="jump_to_set_up_payment",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "initialize_payment"
                    },
                )
            ]),
        StepBranch(
            name="initialize_payment",
            steps=[
                Step(
                    name="initialize-make-payment",
                    step_type=InitializeAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "workflow_name": "make_payment",
                        "on_error_switch_to_branch": "error_processing"
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="Iivr-basic-workflow-branch-step",
            steps=[
                Step(
                    name="branch-on-Iivr-basic-workflow-step",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.Iivr_basic_step_name",
                        "branches": {
                            "pay_with_bank_account_on_file": "pay_with_bank_account_on_file",
                            "apply_to_future_installments": "apply_to_future_installments",
                            "pay_amount_due": "pay_amount_due",
                            "pay_on_earliest_date": "pay_on_earliest_date",
                            "select_amount": "select_amount",
                            "confirmation": "confirmation"
                        },
                        "on_error_switch_to_branch": "error_processing",
                        "default_branch": "error_processing"
                    },
                )
            ]),
        StepBranch(
            name="pay_with_bank_account_on_file",
            steps=[
                Step(
                    name="agree-to-use-bank-account-on-file-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes",
                        "on_error_switch_to_branch": "error_processing",
                        "retry_count": 0,
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="apply_to_future_installments",
            steps=[
                Step(
                    name="set-upcoming-payment-true",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "upcoming_payment",
                        "op": "=="
                    }
                ),
                Step(
                    name="agree-to-apply-to-future-installment",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes",
                        "on_error_switch_to_branch": "error_processing",
                        "retry_count": 0,
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="pay_on_earliest_date",
            steps=[
                Step(
                    name="agree-to-pay-on-earliest-date",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes",
                        "on_error_switch_to_branch": "error_processing",
                        "retry_count": 0,
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step-or-return-to-cutoff",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.potential_cutoff_scenario",
                        "branches": {
                            "True": "cutoff",
                            "False": "Iivr-basic-workflow-branch-step"
                        },
                        "default_branch": "error_processing"
                    },
                )
            ]),
        StepBranch(
            name="pay_amount_due",
            steps=[
                Step(
                    name="use-amount-due-in-workflow",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "yes",
                        "on_error_switch_to_branch": "error_processing",
                        "retry_count": 0,
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="select_amount",
            steps=[
                Step(
                    name="branch-to-use-past-due-if-past-due-is-nonzero",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_past_due_amount_cents",
                        "branches": {
                            "0": "select_amount",
                            "None": "select_amount"
                        },
                        "default_branch": "select_amount_use_past_due"
                    },
                ),
                Step(
                    name="play-additional-payment-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": "It looks like you recently made your monthly payment."
                    }
                ),
                Step(
                    name="get-payment-amount",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "amount",
                        "input_prompt": "Please reply with the additional payment you'd like to make as a number \"$XXX.XX\".",
                        "input_type": CurrencyTextInput.get_type_string()
                    },
                ),
                Step(
                    name="run-workflow-step-with-payment-amount",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "amount",
                        "field_type": "currency",
                        "step_action": "next",
                        "on_error_reset_to_step": "get-payment-amount",
                        "on_error_switch_to_branch": "cutoff"
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="select_amount_use_past_due",
            steps=[
                Step(
                    name="save-past-due-as-amount-in-workflow",
                    step_type=CopySessionVariable.get_type_string(),
                    step_kwargs={
                        "existing_field": "session.loan_past_due_amount_cents",
                        "new_field_name": "amount"
                    }
                ),
                Step(
                    name="run-workflow-step-with-payment-amount",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field_name": "amount",
                        "field_type": "currency",
                        "step_action": "next",
                        "on_error_switch_to_branch": "error_processing",
                        "retry_count": 0
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    },
                )
            ]),
        StepBranch(
            name="confirmation",
            steps=[
                Step(
                    name="play-additional-confirmation-message-if-required",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.play_additional_confirmation_message",
                        "branches": {
                            "True": "branch_to_additional_message",
                            "False": "confirmation"
                        }
                    }
                ),
                Step(
                    name="show-confirmation-of-payment-terms",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": "To authorize one e-payment of {{session.confirmation_currency | currency}} on loan ending in {{session.loan_id | last_characters(4)}} from your bank account ending in {{session.confirmation_digits}} for {{session.confirmation_date | date_mmddyy}}, reply PAY."
                    }
                ),
                Step(
                    name="get-confirmation-of-payment-terms",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirmation",
                        "input_prompt": "",
                        "input_type": TextInput.get_type_string()
                    },
                ),
                Step(
                    name="continue-on-confirmation",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirmation",
                        "branches": {
                            "pay": "confirmation"
                        },
                        "default_branch": "payment_not_made",
                    }
                ),
                Step(
                    name="run-workflow-step-with-agreement",
                    step_type=RunAvantBasicWorkflowStep.get_type_string(),
                    step_kwargs={
                        "step_action": "i_agree",
                        "on_error_switch_to_branch": "cutoff",
                        "retry_count": 0,
                    }
                ),
                Step(
                    name="play-confirmation-payment-submitted",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "sms_make_payment_submitted"
                    },
                    exit_path={
                        "exit_path_type": SMSExitPath.get_type_string()
                    }
                )
            ]),
        StepBranch(
            name="branch_to_additional_message",
            steps=[
                Step(
                    name="set-play-additional-confirmation-message-false",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "play_additional_confirmation_message",
                        "op": "!="
                    }
                ),
                Step(
                    name="branch-to-play-upcoming-payment-message",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.upcoming_payment",
                        "branches": {
                            "True": "play_upcoming_payment_message",
                        },
                        "default_branch": "branch_to_additional_message"
                    }
                ),
                Step(
                    name="branch-to-play-delinquent-message",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.loan_past_due_amount_cents",
                        "branches": {
                            "0": "confirmation",
                            "None": "confirmation"
                        },
                        "default_branch": "play_delinquent_message"
                    }
                )
            ]),
        StepBranch(
            name="play_delinquent_message",
            steps=[
                Step(
                    name="play_delinquent_message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "start_new_message": True,
                        "template": "Your current past due is {{session.confirmation_currency | currency}}."
                    }
                ),
                Step(
                    name="return-to-confirmation-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "confirmation"
                    },
                )
            ]),
        StepBranch(
            name="play_upcoming_payment_message",
            steps=[
                Step(
                    name="play_upcoming_payment_message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": "Your payment amount is {{session.confirmation_currency | currency}}."
                    }
                ),
                Step(
                    name="return-to-confirmation-branch",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "confirmation"
                    },
                )
            ]),
        StepBranch(
            name="cutoff",
            reset_on_switch=False,
            steps=[
                Step(
                    name="copy-date-of-failed-payment",
                    step_type=CopySessionVariable.get_type_string(),
                    step_kwargs={
                        "existing_field": "session.pay_on_earliest_date_date",
                        "new_field_name": "original_pay_on_earliest_date_date"
                    }
                ),
                Step(
                    name="set-potential-cutoff-scenario-true",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "potential_cutoff_scenario",
                        "op": "=="
                    }
                ),
                Step(
                    name="jump-to-initialize-payment",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "initialize_payment"
                    }
                ),
                Step(
                    name="evaluate-cutoff-possibility",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.original_pay_on_earliest_date_date", "session.pay_on_earliest_date_date"
                        ],
                        "result_field": "cutoff_occurred",
                        "op": "<",
                        "on_error_switch_to_branch": "error_processing"
                    }
                ),
                Step(
                    name="branch-on-cutoff-or-error",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.cutoff_occurred",
                        "branches": {
                            "True": "cutoff",
                            "False": "error_processing"
                        }
                    }
                ),
                Step(
                    name="play-cutoff-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "sms_make_payment_cutoff_message",
                        "end_break": True
                    }
                ),
                Step(
                    name="set-play-confirmation-message-true",
                    step_type=BooleanLogicStep.get_type_string(),
                    step_kwargs={
                        "fieldset": [
                            "session.loan_id", "session.loan_id"
                        ],
                        "result_field": "play_additional_confirmation_message",
                        "op": "=="
                    }
                ),
                Step(
                    name="jump-to-Iivr-basic-workflow-branch-step",
                    step_type=JumpBranchStep.get_type_string(),
                    step_kwargs={
                        "branch": "Iivr-basic-workflow-branch-step"
                    }
                )
            ]),
        StepBranch(
            name="payment_not_made",
            steps=[
                Step(
                    name="play-payment-not-made-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "sms_make_payment_payment_not_made_message",
                    },
                    exit_path={
                        "exit_path_type": SMSExitPath.get_type_string()
                    }
                )
            ]),
        StepBranch(
            name="error_processing",
            steps=[
                Step(
                    name="no-op-error-processing",
                    step_type=NoopStep.get_type_string(),
                    step_kwargs={
                    },
                    exit_path={
                        "exit_path_type": SMSExitPath.get_type_string(),
                        "exit_path_kwargs": {
                            "exit_msg": "Sorry! There was an issue processing your payment. Call 800-712-5407 "
                                        "to speak to an agent.",
                            "overwrite_response": True
                        }
                    }
                )
            ]),
    ]
)
