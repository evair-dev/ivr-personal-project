import pytest
import time_machine
from sqlalchemy.orm import Session as SQLAlchemySession

from ivr_gateway.models.contacts import Greeting, InboundRouting
from ivr_gateway.models.queues import Queue
from ivr_gateway.models.workflows import Workflow
from ivr_gateway.services.sms import SmsService

from tests.factories import queues as qf
from tests.factories import workflow as wcf
from tests.fixtures.step_trees.main_menu import main_menu_step_tree


class TestMainMenuLiveVox:

    @pytest.fixture
    def workflow(self, db_session: SQLAlchemySession) -> Workflow:
        workflow_factory = wcf.workflow_factory(db_session, "main_menu", step_tree=main_menu_step_tree)
        return workflow_factory.create()

    @pytest.fixture
    def greeting(self, db_session) -> Greeting:
        greeting = Greeting(message='hello from Avant.')
        db_session.add(greeting)
        db_session.commit()
        return greeting

    @pytest.fixture
    def queue(self, db_session) -> Queue:
        queue = qf.queue_factory(db_session).create(
            name="test"
        )
        return queue

    @pytest.fixture
    def inbound_routing(self, db_session, workflow: Workflow, greeting: Greeting, queue: Queue) -> InboundRouting:
        call_routing = InboundRouting(
            inbound_target="main_menu",
            workflow=workflow,
            active=True,
            greeting=greeting,
            operating_mode="normal",
            initial_queue=queue
        )
        db_session.add(call_routing)
        db_session.commit()
        return call_routing

    def test_loan_origination_sms(self, db_session, workflow, greeting, inbound_routing,
                                  test_client):
        init_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": [155555555556],
            "input": "",
            "initial_settings": {
                "zip_code": "60601"
            }
        }

        initial_response = test_client.post("/api/v1/livevox/new", json=init_form)
        assert initial_response.json == {"error": None,
                                         "text_array":
                                             ['For questions about an application, press 1. For questions '
                                              'about an existing product, press 2. If you are calling about '
                                              'a lost or stolen card, press 3. For gene',
                                              'ral questions, press 0. To'
                                              ' hear this again, press 9.'],
                                         "finished": False}

        second_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "1",
        }

        second_response = test_client.post("/api/v1/livevox/continue", json=second_form)
        assert second_response.json == {"error": None,
                                        "text_array":
                                            ['For credit cards, press 1. For personal loans, press 2. For '
                                             'deposit accounts, press 3. To hear this again, press 9.'],
                                        "finished": False}

        sms_service = SmsService(db_session)
        sms = sms_service.get_active_contact_leg_for_sms_system_and_id("livevox", "test")
        assert sms.contact.session.get("zip_code") == "60601"
        assert sms.workflow_run.session.get("zip_code") == "60601"
        assert sms.contact.device_identifier == "155555555556"

    @time_machine.travel("2020-12-29 19:00")
    def test_loan_origination_sms_one_endpoint(self, db_session, workflow, greeting, inbound_routing,
                                               test_client):
        init_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "",
            "initial_settings": {
                "zip_code": ["60601"]
            }
        }

        initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
        assert initial_response.json == {"error": None,
                                         "text_array":
                                             ['For questions about an application, press 1. For questions '
                                              'about an existing product, press 2. If you are calling about '
                                              'a lost or stolen card, press 3. For gene',
                                              'ral questions, press 0. To'
                                              ' hear this again, press 9.'],
                                         "finished": False}

        second_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "1",
        }

        second_response = test_client.post("/api/v1/livevox/sms", json=second_form)
        assert second_response.json == {"error": None,
                                        "text_array":
                                            ['For credit cards, press 1. For personal loans, press 2. For '
                                             'deposit accounts, press 3. To hear this again, press 9.'],
                                        "finished": False}

        sms_service = SmsService(db_session)
        sms = sms_service.get_active_contact_leg_for_sms_system_and_id("livevox", "test")
        assert sms.contact.session.get("zip_code") == "60601"
        assert sms.workflow_run.session.get("zip_code") == "60601"

    @time_machine.travel("2020-12-29 19:00")
    def test_multiple_sms(self, db_session, workflow, greeting, inbound_routing,
                          test_client):
        init_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "",
            "initial_settings": {
                "zip_code": "60601"
            }
        }

        initial_response = test_client.post("/api/v1/livevox/sms", json=init_form)
        assert initial_response.json == {"error": None,
                                         "text_array":
                                             ['For questions about an application, press 1. For questions '
                                              'about an existing product, press 2. If you are calling about '
                                              'a lost or stolen card, press 3. For gene',
                                              'ral questions, press 0. To'
                                              ' hear this again, press 9.'],
                                         "finished": False}

        init_form2 = {
            "thread_id": "test2",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "",
            "initial_settings": {
                "zip_code": "60602"
            }
        }

        initial_response = test_client.post("/api/v1/livevox/sms", json=init_form2)
        assert initial_response.json == {"error": None,
                                         "text_array":
                                             ['For questions about an application, press 1. For questions '
                                              'about an existing product, press 2. If you are calling about '
                                              'a lost or stolen card, press 3. For gene',
                                              'ral questions, press 0. To'
                                              ' hear this again, press 9.'],
                                         "finished": False}

        second_form = {
            "thread_id": "test",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "1",
        }

        second_response = test_client.post("/api/v1/livevox/sms", json=second_form)
        assert second_response.json == {"error": None,
                                        "text_array":
                                            ['For credit cards, press 1. For personal loans, press 2. For '
                                             'deposit accounts, press 3. To hear this again, press 9.'],
                                        "finished": False}

        sms_service = SmsService(db_session)
        sms = sms_service.get_active_contact_leg_for_sms_system_and_id("livevox", "test")
        assert sms.contact.session.get("zip_code") == "60601"
        assert sms.workflow_run.session.get("zip_code") == "60601"

        second_form = {
            "thread_id": "test2",
            "workflow": "main_menu",
            "phone_number": "+155555555556",
            "input": "9",
        }

        second_response = test_client.post("/api/v1/livevox/sms", json=second_form)
        assert second_response.json == {"error": None,
                                        "text_array":
                                            ['For questions about an application, press 1. For questions '
                                              'about an existing product, press 2. If you are calling about '
                                              'a lost or stolen card, press 3. For gene',
                                              'ral questions, press 0. To'
                                              ' hear this again, press 9.'],
                                        "finished": False}

        sms_service = SmsService(db_session)
        sms = sms_service.get_active_contact_leg_for_sms_system_and_id("livevox", "test2")
        assert sms.contact.session.get("zip_code") == "60602"
        assert sms.workflow_run.session.get("zip_code") == "60602"
