
import pytest

from ivr_gateway.services.message import SimpleMessageService


class TestSimpleMessageService:

    @pytest.fixture
    def message_service(self) -> SimpleMessageService:
        return SimpleMessageService()

    def test_get_message_by_name_key_exists(self, monkeypatch, message_service: SimpleMessageService):
        monkeypatch.setenv("IVR_APP_ENV", "test")
        assert message_service.get_message_by_key("test") == "This is a test"

    def test_get_message_by_name_key_nonexistent(self, monkeypatch, message_service: SimpleMessageService):
        monkeypatch.setenv("IVR_APP_ENV", "test")
        assert not message_service.get_message_by_key("nonexistent_key")

