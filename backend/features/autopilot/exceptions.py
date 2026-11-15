class AutopilotError(Exception):
    code = "autopilot_error"
    status_code = 400

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class NotFound(AutopilotError):
    code = "not_found"
    status_code = 404


class Forbidden(AutopilotError):
    code = "forbidden"
    status_code = 403


class Conflict(AutopilotError):
    code = "conflict"
    status_code = 409


class CapabilityUnavailable(AutopilotError):
    code = "capability_unavailable"
    status_code = 503


class UnsafeAction(AutopilotError):
    code = "unsafe_action"
    status_code = 422


class ApprovalRequired(AutopilotError):
    code = "approval_required"
    status_code = 403


class ProviderTimeout(AutopilotError):
    code = "provider_timeout"
    status_code = 504
