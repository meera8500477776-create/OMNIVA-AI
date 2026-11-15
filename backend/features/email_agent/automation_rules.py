from dataclasses import dataclass


@dataclass(frozen=True)
class AutomationRule:
    sender: str
    allowed_action: str = "label"
    enabled: bool = False
    auto_send: bool = False

    def permits(self, sender: str, action: str, *, emergency_disabled: bool) -> bool:
        return (
            not emergency_disabled
            and self.enabled
            and not self.auto_send
            and self.sender.casefold() == sender.casefold()
            and action == self.allowed_action
            and action in {"label", "remind"}
        )
