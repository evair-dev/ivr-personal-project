from enum import Enum

__all__ = [
    "StringEnum",
    "WorkflowState",
    "Partner",
    "ProductCode",
    "Department",
    "TransferType",
    "AdminRole",
    "OperatingMode",
    "ContactType",
    "ProductType"
]


class StringEnum(str, Enum):
    """Enum where members are also (and must be) strings"""

    @classmethod
    def list_keys(cls):
        return list(map(lambda c: c.value, cls))


class WorkflowState(StringEnum):
    uninitialized = "uninitialized"
    initialized = "initialized"
    step_in_progress = "step_in_progress"
    requesting_user_input = "requesting_user_input"
    processing_input = "processing_input"
    error = "error"
    terminated = "terminated"
    finished = "finished"


class CompanyCodeMap(StringEnum):
    AFC = 'Iivr'
    CC = 'Iivr'
    ELN = 'eloan'
    HSB = 'hsbc'
    PNC = 'pnc'
    REG = 'regions'
    TDB = 'td'
    US = 'Iivr'


class Partner(StringEnum):
    IVR = "Iivr"
    ELOAN = "eloan"
    TD = "td"
    REGIONS = "regions"
    HSBC = "hsbc"
    PNC = "pnc"
    BBVA = "bbva"


class ProductCode(StringEnum):
    CREDIT_CARD = "CC"
    LOAN = 'LN'


class Department(StringEnum):
    CUSTOMERS = "CUS"
    ORIGINATIONS = "ORIG"
    PAYMENTS = "PAY"
    ANY = "ANY"


class TransferType(StringEnum):
    SIP = "SIP"
    PSTN = "PSTN"
    QUEUE = "QUEUE"
    INTERNAL = "INTERNAL"


class AdminRole(StringEnum):
    admin = "admin"
    user = "user"


class OperatingMode(StringEnum):
    NORMAL = "normal"
    CLOSED = "closed"
    HOLIDAY = "holiday"
    EMERGENCY = "emergency"


class ContactType(StringEnum):
    IVR = "ivr"
    SMS = "sms"
    CHAT = "chat"


class ProductType(StringEnum):
    Loan = "Loan"
    CreditCardAccount = "CreditCardAccount"

