import datetime
from typing import List, Type

import pytest

from ivr_gateway.steps.action import NumberedStepAction, StepAction
from ivr_gateway.steps.inputs import StepInput, MenuActionInput, BirthdayInput, SSNInput, NumberedMenuActionInput, \
    StepInputBindingException, CompoundStepInput, Last4SSNInput, StepInputArgumentsException, CurrencyInput, \
    CurrencyTextInput, CardPaymentDateInput, PhoneNumberInput, TextInput, ZipCodeInput


class TestStepInputs:

    def test_initialize_main_menu_workflow(self):
        with pytest.raises(TypeError):
            StepInput("key", "value")

    def test_numbered_menu_action_input_creation(self):
        menu_actions = {
            1:NumberedStepAction(name="option-1", display_name="Some options",number=1),
            2:NumberedStepAction(name="option-2", display_name="Another options",number=2)
        }
        _input = NumberedMenuActionInput("menu_action", "1", menu_actions=menu_actions)
        assert _input.get() == menu_actions[1].name
        assert _input.bind() is None
        assert _input.get() == "option-1"
    
    def test_numbered_menu_action_rejects_invalid_menu_choices(self):
        menu_actions = {
            1:NumberedStepAction(name="option-1", display_name="Some options",number=1),
            2:NumberedStepAction(name="option-2", display_name="Another options",number=2)
        }
        with pytest.raises(StepInputBindingException):
            NumberedMenuActionInput("menu_action", "-1", menu_actions=menu_actions, auto_bind=True)
        with pytest.raises(StepInputBindingException):
            NumberedMenuActionInput("menu_action", "3", menu_actions=menu_actions, auto_bind=True)
       
    def test_menu_action_input_creation(self):
        menu_actions = [
            StepAction(name="option-1", display_name="Some options"),
            StepAction(name="option-2", display_name="Another options")
        ]
        _input = MenuActionInput("menu_action", "1", menu_actions=menu_actions, auto_bind=True)
        assert _input.is_bound
        assert _input.get() == menu_actions[0].name
        assert _input.bind() is None
        assert _input.get() == "option-1"

    def test_menu_action_rejects_invalid_menu_choices(self):
        menu_actions = [
            StepAction(name="option-1", display_name="Some options"),
            StepAction(name="option-2", display_name="Another options")
        ]
        with pytest.raises(StepInputBindingException):
            MenuActionInput("menu_action", "-1", menu_actions=menu_actions, auto_bind=True)
        with pytest.raises(StepInputBindingException):
            MenuActionInput("menu_action", "3", menu_actions=menu_actions, auto_bind=True)

    def test_birthday_input_creation(self):
        _input = BirthdayInput("birthday", "10101987", auto_bind=True)
        assert _input.is_bound
        assert _input.input_key == "birthday"
        assert _input.get() == "1987-10-10"
        assert _input.bind() is None

    def test_birthday_input_rejects_invalid_lengths(self):
        with pytest.raises(StepInputBindingException):
            # Missing 19 in 1987
            BirthdayInput("birthday", "121087", auto_bind=True)

    def test_birthday_input_rejects_invalid_types(self):
        with pytest.raises(TypeError):
            # Numeric input should fail
            BirthdayInput("birthday", 12101987, auto_bind=True)

    def test_birthdate_input_rejects_too_early(self):
        with pytest.raises(StepInputBindingException):
            BirthdayInput("birthday", "12311899", auto_bind=True)

    def test_birthdate_input_rejects_too_late(self):
        with pytest.raises(StepInputBindingException):
            BirthdayInput("birthday", "10103030", auto_bind=True)

    def test_ssn_input_creation(self):
        _input = SSNInput("ssn", "123456789", auto_bind=True)
        assert _input.is_bound
        assert _input.get() == "123456789"
        assert _input.bind() is None

    def test_ssn_input_rejects_invalid_types(self):
        with pytest.raises(TypeError):
            # Numeric input should fail
            SSNInput("ssn", 123456789).bind()
        with pytest.raises(StepInputBindingException):
            # Incorrect lengths should fails
            SSNInput("ssn", "12345").bind()
        with pytest.raises(StepInputBindingException):
            # Incorrect lengths should fails
            SSNInput("ssn", "").bind()
        with pytest.raises(StepInputBindingException):
            # None types should fail
            SSNInput("ssn", None).bind()

    def test_last_4_ssn_input_creation(self):
        _input = Last4SSNInput("ssn", "1234", auto_bind=True)
        assert _input.is_bound
        assert _input.get() == "1234"
        assert _input.bind() is None

    def test_last_4_ssn_input_rejects_invalid_types(self):
        with pytest.raises(TypeError):
            # Numeric input should fail
            Last4SSNInput("ssn", 1234).bind()
        with pytest.raises(StepInputBindingException):
            # Incorrect lengths should fails
            Last4SSNInput("ssn", "12345").bind()
        with pytest.raises(StepInputBindingException):
            # Incorrect lengths should fails
            Last4SSNInput("ssn", "").bind()
        with pytest.raises(StepInputBindingException):
            # None types should fail
            Last4SSNInput("ssn", None).bind()

    def test_compound_step_input_creation(self):
        type_list: List[Type[StepInput]] = [BirthdayInput, SSNInput, Last4SSNInput]
        _input = CompoundStepInput("test", "10102020", compound_types=type_list, auto_bind=True)
        assert _input.get() == datetime.datetime(2020, 10, 10).date().isoformat()
        assert _input.get_bound_input_type() == BirthdayInput
        _input = CompoundStepInput("test", "123456789", compound_types=type_list)
        assert _input.get() == "123456789"
        assert _input.get_bound_input_type() == SSNInput
        _input = CompoundStepInput("test", "1234", compound_types=type_list)
        assert _input.get() == "1234"
        assert _input.get_bound_input_type() == Last4SSNInput
        with pytest.raises(StepInputArgumentsException):
            CompoundStepInput("test", "1234", compound_types=[]).bind()
        with pytest.raises(StepInputBindingException):
            CompoundStepInput("test", "", compound_types=type_list).bind()

    def test_currency_input_creation(self):
        input_with_cents = CurrencyInput("dollars", "123*45", auto_bind=True)
        assert input_with_cents.is_bound
        assert input_with_cents.get() == 12345
        assert input_with_cents.bind() is None
        input_without_cents = CurrencyInput("dollars", "123", auto_bind=True)
        assert input_without_cents.get() == 12300
        input_without_cents_and_star = CurrencyInput("dollars", "123*", auto_bind=True)
        assert input_without_cents_and_star.get() == 12300
        input_with_ten_cents = CurrencyInput("dollars", "123*5", auto_bind=True)
        assert input_with_ten_cents.get() == 12350
        input_with_just_cents = CurrencyInput("dollars", "*23", auto_bind=True)
        assert input_with_just_cents.get() == 23

    def test_currency_input_invalid_values(self):
        with pytest.raises(StepInputBindingException):
            # More than one *
            CurrencyInput("dollars", "12*34*5").bind()
        with pytest.raises(StepInputBindingException):
            # More than one *
            CurrencyInput("dollars", "12**5").bind()
        with pytest.raises(StepInputBindingException):
            # More than one *
            CurrencyInput("dollars", "*12345*").bind()
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            CurrencyInput("dollars", "12*345").bind()

    def test_currency_input_text_creation(self):
        input_with_cents = CurrencyTextInput("dollars", "123.45", auto_bind=True)
        assert input_with_cents.is_bound
        assert input_with_cents.get() == 12345
        assert input_with_cents.bind() is None
        input_without_cents = CurrencyTextInput("dollars", "123", auto_bind=True)
        assert input_without_cents.get() == 12300
        input_without_cents_and_decimal = CurrencyTextInput("dollars", "123.", auto_bind=True)
        assert input_without_cents_and_decimal.get() == 12300
        input_with_ten_cents = CurrencyTextInput("dollars", "123.5", auto_bind=True)
        assert input_with_ten_cents.get() == 12350
        input_with_just_cents = CurrencyTextInput("dollars", ".23", auto_bind=True)
        assert input_with_just_cents.get() == 23
        input_with_dollar_sign = CurrencyTextInput("dollars", "$1.23", auto_bind=True)
        assert input_with_dollar_sign.get() == 123
        input_with_commas = CurrencyTextInput("dollars", "1,000,000.23", auto_bind=True)
        assert input_with_commas.get() == 100000023
        input_with_spaces = CurrencyTextInput("dollars", " 1.23  ", auto_bind=True)
        assert input_with_spaces.get() == 123

    def test_currency_input_text_invalid_values(self):
        with pytest.raises(StepInputBindingException):
            # More than one .
            CurrencyTextInput("dollars", "12.34.5").bind()
        with pytest.raises(StepInputBindingException):
            # More than one .
            CurrencyTextInput("dollars", "12..5").bind()
        with pytest.raises(StepInputBindingException):
            # More than one .
            CurrencyTextInput("dollars", ".12345.").bind()
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            CurrencyTextInput("dollars", "12.345").bind()
        with pytest.raises(StepInputBindingException):
            # Non-numeric input
            CurrencyTextInput("dollars", "not a numeric entry").bind()

    def test_card_payment_input_creation(self):
        today = datetime.date.today()
        today_string = today.strftime("%m%d%Y")
        _input = CardPaymentDateInput("card_payment", today_string, auto_bind=True)
        assert _input.is_bound
        assert _input.input_key == "card_payment"
        assert _input.get() == today.isoformat()
        assert _input.bind() is None
        last_day = today + datetime.timedelta(days=180)
        last_day_string = last_day.strftime("%m%d%Y")
        _last_day_input = CardPaymentDateInput("card_payment", last_day_string, auto_bind=True)
        assert _last_day_input.get() == last_day.isoformat()

    def test_invalid_card_payment_input_creation(self):
        today = datetime.date.today()
        yesterday = today - datetime.timedelta(days=1)
        yesterday_string = yesterday.strftime("%m%d%Y")
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            CardPaymentDateInput("dollars", yesterday_string).bind()
        future_date = today + datetime.timedelta(days=181)
        future_date_string = future_date.strftime("%m%d%Y")
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            CardPaymentDateInput("dollars", future_date_string).bind()

    def test_phone_number_input_creation(self):
        _input = PhoneNumberInput("phone_number", "2234567890", auto_bind=True)
        assert _input.is_bound
        assert _input.input_key == "phone_number"
        assert _input.get() == "2234567890"
        assert _input.bind() is None

    def test_invalid_phone_number_input_creation(self):
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            PhoneNumberInput("phone_number", "1234567890").bind()
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            PhoneNumberInput("phone_number", "0234567890").bind()
        with pytest.raises(StepInputBindingException):
            # More than two digits after decimal
            PhoneNumberInput("phone_number", "223456789").bind()

    def test_text_input_creation(self):
        _input = TextInput("generic_text", " soMe StrING  ", auto_bind=True)
        assert _input.is_bound
        assert _input.input_key == "generic_text"
        assert _input.get() == "some string"
        assert _input.bind() is None

    def test_zipcode_input_creation(self):
        input_zipcode = ZipCodeInput("zip_code", "12345", auto_bind=True)
        assert input_zipcode.is_bound
        assert input_zipcode.get() == "12345"
        assert input_zipcode.bind() is None

    def test_zipcode_input_invalid_values(self):
        with pytest.raises(StepInputBindingException):
            ZipCodeInput("zip_code", "1234").bind()
        with pytest.raises(StepInputBindingException):
            ZipCodeInput("zip_code", "123456").bind()
        with pytest.raises(StepInputBindingException):
            ZipCodeInput("zip_code", "12345.").bind()
        with pytest.raises(StepInputBindingException):
            ZipCodeInput("zip_code", "12 345").bind()
        with pytest.raises(StepInputBindingException):
            ZipCodeInput("zip_code", "abcde").bind()
