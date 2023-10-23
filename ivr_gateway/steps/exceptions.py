class StepInitializationException(Exception):
    """
    Subset of error classes to be raised during step instantiation, can be used to test/catch invalid step configurations
    """


class FieldParsingException(StepInitializationException):
    """Used to denote that there has been an exception parsing the field definition supplied to the step"""
