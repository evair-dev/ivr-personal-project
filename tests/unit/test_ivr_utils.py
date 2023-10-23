import pytest

from ivr_gateway.models.enums import Partner
from ivr_gateway.utils import get_partner_namespaced_environment_variable


class TestUtils:
    @pytest.mark.parametrize("service, partner, field, environment_variable_name, expected_value", [
        ("testservice", Partner.IVR, "api_key", "TESTSERVICE_IVR_API_KEY", "abc123"),
        (None, Partner.IVR, "api_key", "IVR_API_KEY", "abc123"),
        (None, Partner.IVR, "amount_base_url", "IVR_AMOUNT_BASE_URL", "abc123"),
        ("testservice", None, "api_key", "TESTSERVICE_API_KEY", "abc123")
    ])
    def test_get_partner_namespaced_environment_variable(self, service, partner, field, environment_variable_name,
                                                         expected_value, monkeypatch):
        monkeypatch.setenv(environment_variable_name, expected_value)
        var = get_partner_namespaced_environment_variable(field=field, service=service, partner=partner)
        assert var == expected_value

    def test_get_partner_namespaced_environment_variable_bad_inputs(self):
        with pytest.raises(TypeError):
            get_partner_namespaced_environment_variable(service="testservice", partner=Partner.IVR, field=None)

        with pytest.raises(ValueError, match="Either partner or service must be specified."):
            get_partner_namespaced_environment_variable(service=None, partner=None, field="api_key")

    def test_get_partner_namespaced_environment_variable_variable_does_not_exist_1(self):
        with pytest.raises(TypeError, match="Environment variable TEST_SERVICE_IVR_API_KEY not found."):
            get_partner_namespaced_environment_variable(service="test_service", partner=Partner.IVR, field="api_key")

    def test_get_partner_namespaced_environment_variable_variable_does_not_exist_2(self):
        var = get_partner_namespaced_environment_variable(service="test_service", partner=Partner.IVR,
                                                          field="api_key", raise_if_none=False)
        assert var is None
