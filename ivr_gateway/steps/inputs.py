from abc import abstractmethod, ABC
from datetime import datetime, date, timedelta
from typing import List, Optional, Type, Union, Generic, TypeVar

import dateparser

from ivr_gateway.steps.action import NumberedStepAction, StepAction

class StepInputBindingException(Exception):
    pass


class StepInputArgumentsException(Exception):
    pass


InputType = TypeVar("InputType")
SerializableType = Union[None, bool, int, float, str, list, set, dict]
OutputType = TypeVar("OutputType", bound=SerializableType)


class StepInput(Generic[InputType, OutputType], ABC):
    _bound_input: Optional[InputType] = None
    _bound_output: Optional[OutputType] = None
    expected_input_length = -1

    def __init__(self, input_key: str, input_value: Optional[str], auto_bind=False, *args, **kwargs):
        self.input_key = input_key
        self.input_value = input_value
        # constructable value types should preserve arguments
        self.args = args
        self.kwargs = kwargs
        if auto_bind:
            self.bind()

    @classmethod
    def get_type_string(cls) -> str:
        return f"ivr_gateway.steps.inputs.{cls.__name__}"

    @abstractmethod
    def bind(self):  # pragma: no cover
        pass

    @property
    def is_bound(self):
        return self._bound_output is not None

    @property
    def format(self) -> Optional[bool]:
        return False

    def check_max_stars(self, count: int):
        if self.input_value.count("*") > count or self.input_value.count("*") == len(self.input_value):
            raise StepInputBindingException(f"Input should include at most {count} *s and at least one digit")

    def check_max_periods(self, count: int):
        if self.input_value.count(".") > count or self.input_value.count(".") == len(self.input_value):
            raise StepInputBindingException(f"Input should include at most {count} .s and at least one digit")

    @staticmethod
    def check_isnumeric(value: str):
        if not value.isnumeric():
            raise StepInputBindingException("Input is not a valid numeric entry.")

    def check_length(self):
        if self.expected_input_length == -1:
            return
        input_length = len(self.input_value)
        if input_length != self.expected_input_length:
            raise StepInputBindingException(
                f"Input invalid with length {input_length}, acceptable length is {self.expected_input_length}"
            )

    @staticmethod
    def format_string(string: str) -> str:
        return string.strip().lower()

    def get(self) -> OutputType:
        if not self.is_bound or self._bound_output is None:
            try:
                self.bind()
            except StepInputBindingException as e:
                raise e

        return self._bound_output


# Base Input Value Types


class StringInput(StepInput[str, str]):

    def bind(self):
        self._bound_input = self.input_value
        if self.format:
            self._bound_output = self.format_string(self.input_value)
        else:
            self._bound_output = self._bound_input


class TextInput(StringInput):

    def bind(self):
        super(TextInput, self).bind()

    @property
    def format(self) -> Optional[bool]:
        return True


Numeric = Union[int, float]


class IntegerInput(StepInput[int, int]):

    def bind(self):
        try:
            self._bound_input = int(self.input_value)
            self._bound_output = self._bound_input
        except ValueError:
            raise StepInputBindingException()


# Concrete Implementations


class DateInput(StepInput[datetime, str]):
    expected_input_length = len("mmddyyyy")
    _bound_date_obj: Optional[datetime] = None
    """
    input format "mmddyyyy"
    """

    def bind(self):
        self.check_length()
        self.check_max_stars(0)
        try:
            self._bound_input = dateparser.parse(self.input_value, date_formats=["%m%d%Y"])
            if not self._bound_input:
                raise ValueError("Date out of bounds")
            if self.min_date is not None:
                if self.min_date > self._bound_input.date():
                    raise ValueError(f"Date too small, min date is {self.min_date.isoformat()}")
            if self.max_date is not None:
                if self.max_date < self._bound_input.date():
                    raise ValueError(f"Date too large, max date is {self.max_date.isoformat()}")
            self._bound_output = self._bound_input.date().isoformat()
        except ValueError as e:
            raise StepInputBindingException(str(e))

    @property
    def max_date(self) -> Optional[date]:
        return None

    @property
    def min_date(self) -> Optional[date]:
        return None


class MenuActionInput(StepInput[int, str]):

    def __init__(self, input_key: str, input_value: str, menu_actions: List[StepAction] = None, *args, **kwargs):
        menu_actions = menu_actions or []
        if len(menu_actions) == 0:
            raise StepInputArgumentsException("Missing menu_actions for step_input")
        self.menu_actions = menu_actions
        super().__init__(input_key, input_value, *args, **kwargs)

    def get_menu_action_list(self):
        return [f"{i}. {ma.display_name}" for i, ma in enumerate(self.menu_actions)]

    def bind(self):
        try:
            if self.input_value is None:
                raise StepInputBindingException("No input")
            self._bound_input = int(self.input_value)
            if self._bound_input > len(self.menu_actions) or self._bound_input < 0:
                actions_text = "\n".join(self.get_menu_action_list())
                raise StepInputBindingException(
                    f"Invalid menu choice {self.input_value}, acceptable choices:\n{actions_text}"
                )
            self._bound_output = self.menu_actions[self._bound_input - 1].name
        except ValueError as e:
            raise StepInputBindingException(str(e))

    def get_action(self) -> StepAction:
        if self.input_value == "0" or self.input_value == 0:
            self._bound_output = "0"
            return None
        if not self.is_bound:
            self.bind()
        return self.menu_actions[self._bound_input-1]

class NumberedMenuActionInput(StepInput[int, str]):

    def __init__(self, input_key: str, input_value: str, menu_actions: dict = None, *args, **kwargs):
        menu_actions = menu_actions or {}
        if len(menu_actions.keys()) == 0:
            raise StepInputArgumentsException("Missing menu_actions for step_input")
        self.menu_actions = menu_actions
        super().__init__(input_key, input_value, *args, **kwargs)

    def bind(self):
        try:
            if self.input_value is None:
                raise StepInputBindingException("No input")
            self._bound_input = int(self.input_value)
            if self._bound_input not in self.menu_actions.keys() or \
                self._bound_input < 0:
                actions_text = "\n".join(self.get_numbered_menu_action_list())
                raise StepInputBindingException(
                    f"Invalid menu choice {self.input_value}, acceptable choices:\n{actions_text}"
                )
            else:
                self._bound_output = self.menu_actions[self._bound_input].name
        except ValueError as e:
            raise StepInputBindingException(str(e))
    
    def get_action(self) -> NumberedStepAction:
        if self.input_value == "0":
            self._bound_output = "0"
            return None
        if not self.is_bound:
            self.bind()
        return self.menu_actions[self._bound_input]

    def get_numbered_menu_action_list(self):
        return [f"{key}. {self.menu_actions[key].display_name}" for key in self.menu_actions]

class BirthdayInput(DateInput):

    def bind(self):
        # Todo: validate it's an acceptable date
        super(BirthdayInput, self).bind()

    @property
    def max_date(self) -> Optional[date]:
        return date.today()

    @property
    def min_date(self) -> Optional[date]:
        return date(1900, 1, 1)


class CardPaymentDateInput(DateInput):
    def bind(self):
        super(CardPaymentDateInput, self).bind()

    @property
    def max_date(self) -> Optional[date]:
        return date.today() + timedelta(days=180)

    @property
    def min_date(self) -> Optional[date]:
        return date.today()


class SSNInputABC(StringInput, ABC):

    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("SSNInput missing input_value, received None")
        if not isinstance(self.input_value, str):
            raise TypeError(f"SSNInput requires string input got {self.input_value.__class__.__name__}")
        self.check_max_stars(0)
        self.check_length()
        super().bind()


class SSNInput(SSNInputABC):
    expected_input_length = 9


class Last4SSNInput(SSNInputABC):
    expected_input_length = 4


class Last4CreditCardInput(StringInput):
    expected_input_length = 4

    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("Last4CreditCardInput missing input_value, received None")
        if not isinstance(self.input_value, str):
            raise TypeError(f"Last4CreditCardInput requires string input, got {self.input_value.__class__.__name__}")
        self.check_max_stars(0)
        self.check_length()
        self.check_isnumeric(self.input_value)
        super().bind()


class CurrencyInput(StepInput[int, int]):
    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("CurrencyInput missing input_value, received None")
        self.check_max_stars(1)
        parts = self.input_value.split("*")

        if len(parts) == 1:
            value = int(self.input_value) * 100
        elif self.input_value[0] == "*":  # Leading decimal point is just cents
            value = int(parts[1])
        else:
            value = int(parts[0]) * 100
            if len(parts[1]) == 2:
                value += int(parts[1])
            elif len(parts[1]) == 1:  # tenths should be treated as ten cents
                value += int(parts[1]) * 10
            elif len(parts[1]) > 2:  # ignore if more than two digits after *
                raise StepInputBindingException("CurrencyInput should have at most 2 digits after the *")

        self._bound_input = value
        self._bound_output = value


class CurrencyTextInput(StepInput[str, str]):
    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("CurrencyInput missing input_value, received None")
        self.check_max_periods(1)
        self.input_value = self.input_value.strip().replace("$", "").replace(",", "")
        parts = self.input_value.split(".")
        for part in parts:
            if part != "":
                self.check_isnumeric(part)

        if len(parts) == 1:
            value = int(self.input_value) * 100
        elif self.input_value[0] == ".":  # Leading decimal point is just cents
            value = int(parts[1])
        else:
            value = int(parts[0]) * 100
            if len(parts[1]) == 2:
                value += int(parts[1])
            elif len(parts[1]) == 1:  # tenths should be treated as ten cents
                value += int(parts[1]) * 10
            elif len(parts[1]) > 2:  # ignore if more than two digits after .
                raise StepInputBindingException("CurrencyInput should have at most 2 digits after the .")

        self._bound_input = value
        self._bound_output = value


class PhoneNumberInput(StepInput[str, str]):
    expected_input_length = 10

    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("PhoneNumberInput missing input_value, received None")
        self.check_max_stars(0)
        self.check_length()
        if self.input_value[0] == '0' or self.input_value[0] == '1':
            raise StepInputBindingException("Phone numbers cannot start with 0 or 1")
        self._bound_input = self.input_value
        self._bound_output = self.input_value


class ZipCodeInput(StepInput[str, str]):
    expected_input_length = 5

    def bind(self):
        if self.input_value is None:
            raise StepInputBindingException("ZipCodeInput missing input_value, received None")
        self.check_length()
        self.check_isnumeric(self.input_value)
        self._bound_input = self.input_value
        self._bound_output = self.input_value


class CompoundStepInput(StepInput):
    _bound_compound_input_type: Type[StepInput]

    def __init__(self, input_key: str, input_value: str,
                 compound_types: List[Type[StepInput]] = None, *args, **kwargs):
        compound_types = compound_types or []
        if len(compound_types) == 0:
            raise StepInputArgumentsException("Compound Steps require compound_type arguments")
        self.compound_types: List[Type[StepInput]] = compound_types
        super(CompoundStepInput, self).__init__(input_key, input_value, *args, **kwargs)

    def get_bound_input_type(self) -> Type[StepInput]:
        if self._bound_compound_input_type is not None:
            return self._bound_compound_input_type
        else:
            raise StepInputBindingException("Can't bind class")

    def bind(self):
        for cls in self.compound_types:
            try:
                _input = cls(self.input_key, self.input_value, *self.args, **self.kwargs)
                _input.bind()
                self._bound_compound_input_type = cls
                self._bound_input = _input._bound_input
                self._bound_output = _input._bound_output
                return
            except StepInputBindingException:
                pass

        raise StepInputBindingException(
            f"Could not bind input_value {self.input_value}, to compound types: {self.compound_types}"
        )
