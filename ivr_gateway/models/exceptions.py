class UninitializedWorkflowActionException(Exception):
    pass


class MissingWorkflowStepConfigurationException(Exception):
    """Exception thrown if a step configuration can not be found, this is a sever exception"""


class MissingTransferRoutingException(Exception):
    pass
