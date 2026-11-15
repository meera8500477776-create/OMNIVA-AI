from .contracts import CallState
class InAppCall:
 def __init__(self, name: str): self.name=name; self.state=CallState.INCOMING; self.started_at=None; self.muted=False
 def accept(self, now: float):
  if self.state != CallState.INCOMING: raise ValueError("Call is not incoming")
  self.state=CallState.ACTIVE; self.started_at=now
 def decline(self):
  if self.state != CallState.INCOMING: raise ValueError("Call is not incoming")
  self.state=CallState.DECLINED
 def miss(self):
  if self.state != CallState.INCOMING: raise ValueError("Call is not incoming")
  self.state=CallState.MISSED
 def end(self):
  if self.state != CallState.ACTIVE: raise ValueError("Call is not active")
  self.state=CallState.ENDED
 def duration(self, now: float) -> int: return int(max(0, now-(self.started_at or now)))
 def toggle_mute(self): self.muted=not self.muted
