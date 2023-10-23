from ivr_gateway.exit_paths import HangUpExitPath, CurrentQueueExitPath
from ivr_gateway.steps.api.v1 import InputStep, AddFieldToWorkflowSessionStep, CallExternalServiceStep, PlayMessageStep, \
    BranchMapWorkflowStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step
from ivr_gateway.steps.inputs import Last4CreditCardInput, Last4SSNInput, PhoneNumberInput
from ivr_gateway.steps.api.v1.input import ConfirmationStep

activate_card_step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="get-card-id",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "field_name": "credit_card_account_id",
                        "service_name": "customer_lookup",
                        "lookup_key": "card_id",
                    }
                ),
                Step(
                    name="branch-on-lookup-error",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.credit_card_account_id",
                        "branches": {
                            "None": "get_customer_phone_number"
                        },
                        "default_branch": "get_customer_card_last_four"
                    }
                )
            ]
        ),
        StepBranch(
            name="get_customer_card_last_four",
            steps=[
                Step(
                    name="enter-card-last-4",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "card_last_4",
                        "input_prompt": "To activate your card, please enter the last 4 digits of your credit card "
                                        "number.",
                        "input_type": Last4CreditCardInput.get_type_string(),
                        "error_message": "I'm sorry, I didn't receive 4 digits.",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
                Step(
                    name="confirm-card-last-4",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_card_last_4",
                        "confirm_key": "card_last_4",
                        "confirm_type": "individual",
                    },
                ),
                Step(
                    name="reset-if-card-incorrect",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_card_last_4",
                        "branches": {
                            "correct": "get_customer_ssn_last_four",
                        },
                        "on_error_reset_to_step": "enter-card-last-4",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
            ]
        ),
        StepBranch(
            name="get_customer_ssn_last_four",
            steps=[
                Step(
                    name="enter-ssn",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "ssn_last_4",
                        "input_prompt": "Please enter the last four digits of your social security number.",
                        "input_type": Last4SSNInput.get_type_string(),
                        "error_message": "I'm sorry, I didn't receive 4 digits.",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
                Step(
                    name="confirm-ssn",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_ssn",
                        "confirm_key": "ssn_last_4",
                        "confirm_type": "individual",
                    },
                ),
                Step(
                    name="reset-if-ssn-incorrect",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_ssn",
                        "branches": {
                            "correct": "card_activation"
                        },
                        "on_error_reset_to_step": "enter-ssn",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
            ]
        ),
        StepBranch(
            name="get_customer_phone_number",
            steps=[
                Step(
                    name="enter-phone-number",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "input_key": "input_phone_number",
                        "input_prompt": "To activate your card, please enter your full ten digit phone number on file.",
                        "input_type": PhoneNumberInput.get_type_string(),
                        "error_message": "I'm sorry, I didn't receive 10 digits.",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
                Step(
                    name="confirm-phone-number",
                    step_type=ConfirmationStep.get_type_string(),
                    step_kwargs={
                        "input_key": "confirm_phone_number",
                        "confirm_key": "input_phone_number",
                        "confirm_type": "individual"
                    },
                ),
                Step(
                    name="reset-if-phone-number-incorrect",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.confirm_phone_number",
                        "branches": {
                            "correct": "customer_lookup_with_session"
                        },
                        "on_error_reset_to_step": "enter-phone-number",
                        "on_error_switch_to_branch": "customer_info_input_failed_transfer"
                    },
                ),
            ]
        ),
        StepBranch(
            name="customer_lookup_with_session",
            steps=[
                Step(
                    name="customer-lookup-with-session-phone-number",
                    step_type=AddFieldToWorkflowSessionStep.get_type_string(),
                    step_kwargs={
                        "field_name": "credit_card_account_id",
                        "service_name": "customer_lookup",
                        "service_overrides": {
                            "lookup_phone_number": "session.input_phone_number"
                        },
                        "lookup_key": "card_id",
                        "use_cache": False
                    }
                ),
                Step(
                    name="branch-on-lookup-error",
                    step_type=BranchMapWorkflowStep.get_type_string(),
                    step_kwargs={
                        "field": "session.credit_card_account_id",
                        "branches": {
                            "None": "customer_lookup_with_session_failed"
                        },
                        "default_branch": "get_customer_card_last_four"
                    }
                )
            ]
        ),
        StepBranch(
            name="card_activation",
            steps=[
                Step(
                    name="activate-card",
                    step_type=CallExternalServiceStep.get_type_string(),
                    step_kwargs={
                        "partner": "amount",
                        "service": "activate_card",
                        "on_error_switch_to_branch": "card_activation_failed"
                    }
                ),
                Step(
                    name="play-card-activation-succeeded-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": 'Congratulations, your <phoneme alphabet="ipa" ph="əˈvɑnt">Iivr</phoneme> Card is '
                                    'now active. Please remove the activation sticker and sign the back of the card '
                                    'in the designated area. Have a wonderful day. '
                    },
                    exit_path={
                        "exit_path_type": HangUpExitPath.get_type_string(),
                    }
                ),
            ]
        ),
        StepBranch(
            name="card_activation_failed",
            steps=[
                Step(
                    name="connect-to-customer-service-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": (
                            'Please hold while we connect you to a customer service specialist.'
                        )
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    },
                )
            ]
        ),
        StepBranch(
            name="customer_lookup_with_session_failed",
            steps=[
                Step(
                    name="connect-to-customer-service-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": (
                            "We're sorry, we were not able to locate your account. Please hold while we transfer your "
                            "call."
                        )
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    },
                )
            ]
        ),
        StepBranch(
            name="customer_info_input_failed_transfer",
            steps=[
                Step(
                    name="connect-to-customer-service-message",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "template": (
                            "Please hold while we transfer your call."
                        )
                    },
                    exit_path={
                        "exit_path_type": CurrentQueueExitPath.get_type_string(),
                    },
                )
            ]
        ),
    ]
)
