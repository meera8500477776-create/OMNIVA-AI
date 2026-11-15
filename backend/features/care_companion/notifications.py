"""In-app only. No Web Push or closed-tab delivery is implemented here."""


class NotificationPreferences:
    def __init__(self):
        self.enabled = False
        self.quiet_start = None
        self.quiet_end = None

    def allow_in_app(self, opted_in: bool):
        return opted_in and self.enabled
