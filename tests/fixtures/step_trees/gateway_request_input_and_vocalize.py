from ivr_gateway.exit_paths import HangUpExitPath
from ivr_gateway.steps.api.v1 import PlayMessageStep, InputStep
from ivr_gateway.steps.config import StepTree, StepBranch, Step

step_tree = StepTree(
    branches=[
        StepBranch(
            name="root",
            steps=[
                Step(
                    name="step-1",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "gateway_request_message_step_1"
                    }
                ),
                Step(
                    name="step-2",
                    step_type=InputStep.get_type_string(),
                    step_kwargs={
                        "name": "enter_number",
                        "input_key": "number",
                        "input_prompt": "Please enter a number and then press pound",
                    },
                ),
                Step(
                    name="step-3",
                    step_type=PlayMessageStep.get_type_string(),
                    step_kwargs={
                        "message_key": "gateway_request_message_step_3",
                        "fieldset": [
                            ("step[root:step-2].input.value", "step_2_input")
                        ]
                    },
                    exit_path={
                        "exit_path_type": HangUpExitPath.get_type_string(),
                    },
                ),
            ]
        )

    ]
)