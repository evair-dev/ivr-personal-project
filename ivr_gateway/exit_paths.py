class ExitPath:

    def __init__(self, **kwargs):
        self.kwargs = kwargs or {}

    @classmethod
    def get_type_string(cls):
        return f"ivr_gateway.exit_paths.{cls.__name__}"


class HangUpExitPath(ExitPath):
    pass


class QueueExitPath(ExitPath):
    def __init__(self, queue_name: str):
        self.queue_name = queue_name
        super().__init__(**{"queue_name": queue_name})


class PSTNExitPath(ExitPath):
    def __init__(self, phone_number: str):
        self.phone_number = phone_number
        super().__init__(**{"phone_number": phone_number})


class CurrentQueueExitPath(ExitPath):
    pass


class WorkflowExitPath(ExitPath):
    def __init__(self, workflow: str):
        self.workflow = workflow
        super().__init__(**{"workflow": workflow})


class ErrorTransferToCurrentQueueExitPath(ExitPath):
    def __init__(self, error: str):
        super().__init__(**{"error": error})


class AdapterStatusCallBackExitPath(ExitPath):
    def __init__(self, call_status: str):
        super().__init__(**{"call_status": call_status})


class SMSExitPath(ExitPath):
    def __init__(self, exit_msg: str = None, overwrite_response: bool = False):
        if exit_msg:
            super().__init__(**{"exit_msg": exit_msg, "overwrite_response": overwrite_response})
        else:
            super().__init__()