from __future__ import annotations

from typing import Any, Protocol

from .exceptions import CapabilityUnavailable


class ExistingDesktopAgent(Protocol):
    def preview(self, session_id: str, command: str) -> dict[str, Any]: ...
    def approve(
        self, session_id: str, plan_id: str, plan_hash: str, confirmed: bool
    ) -> dict[str, Any]: ...
    async def execute(self, session_id: str, plan_id: str, mode=None) -> dict[str, Any]: ...
    def cancel(self, session_id: str) -> dict[str, Any]: ...


class DesktopIntegrationAdapter:
    """Delegates to the existing OMNIVA Desktop Agent. No independent executor exists here."""

    def __init__(self, delegate: ExistingDesktopAgent | None = None):
        self.delegate = delegate

    def _require(self):
        if self.delegate is None:
            raise CapabilityUnavailable("Existing OMNIVA Desktop Agent is not connected")
        return self.delegate

    def preview(self, session_id, command):
        return self._require().preview(session_id, command)

    def approve(self, session_id, plan_id, plan_hash, confirmed):
        return self._require().approve(session_id, plan_id, plan_hash, confirmed)

    async def execute(self, session_id, plan_id, *, demo=True):
        delegate = self._require()
        return await delegate.execute(session_id, plan_id, mode="demo" if demo else "live")

    def emergency_stop(self, session_id):
        return self._require().cancel(session_id)
