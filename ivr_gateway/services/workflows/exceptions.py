class WorkflowServiceException(Exception):
    pass


class CreateStepForWorkflowException(WorkflowServiceException):
    pass


class InvalidStepException(WorkflowServiceException):
    pass


class MissingStepInputError(WorkflowServiceException):
    pass


class MissingWorkflowService(WorkflowServiceException):
    pass


class NotInRegistryException(WorkflowServiceException):
    pass


class MissingDependentValueException(WorkflowServiceException):
    pass


class MissingWorkflowConfigException(WorkflowServiceException):
    pass


class InvalidWorkflowConfigTagException(WorkflowServiceException):
    pass
