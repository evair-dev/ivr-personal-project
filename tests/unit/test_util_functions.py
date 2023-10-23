import pytest
from ivr_gateway.utils import format_as_sentence, trailing_digits


@pytest.mark.parametrize("msg, expected", [
    ("please enter a better value", "Please enter a better value."),
    ("today is July 11", "Today is July 11."),
    ("$11.00 is the payment amount", "$11.00 is the payment amount."),
    ("This sentence is already fine.", "This sentence is already fine."),
    ("i", "I."),
    (".", "."),
    ("", "")
])
def test_format_as_sentence(msg, expected):
    assert format_as_sentence(msg) == expected


@pytest.mark.parametrize("s, expected", [
    ("hello12345", "12345"),
    ("hello9876543210", "9876543210"),
    ("12345hello", "")
])
def test_trailing_digits(s, expected):
    assert trailing_digits(s) == expected
