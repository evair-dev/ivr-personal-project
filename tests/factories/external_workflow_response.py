import json
from unittest.mock import Mock


class AmountWorkflowResponseFactory:

    @classmethod
    def get_response_for_workflow_step(cls, workflow_name, step_name):
        with open(f"tests/fixtures/external_workflows/{workflow_name}/step_{step_name}.json", "r") as f:
            return json.load(f)

    @classmethod
    def create_mock_responses_for_workflow(cls, workflow_response_sequence_path) -> list:
        with open(workflow_response_sequence_path, "r") as f:
            full_response_sequence = json.load(f)

        mocks = []
        for response in full_response_sequence:
            mock = Mock()
            mock.status_code = 200
            mock.json.return_value = response
            mocks.append(mock)

        return mocks

    @classmethod
    def create_mock_response_for_customer_lookup(cls, customer_lookup_path) -> Mock:
        with open(customer_lookup_path, "r") as f:
            mock_lookup = Mock()
            mock_lookup.status_code = 200
            mock_lookup.json.return_value = json.load(f)
            return mock_lookup
