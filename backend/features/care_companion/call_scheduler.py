from dataclasses import dataclass
from datetime import datetime, time


@dataclass(frozen=True)
class CheckIn:
    user_id: str
    at: datetime
    persona: str
    opted_in: bool
    window_start: time
    window_end: time

    def due(self, now: datetime) -> bool:
        local = now.timetz().replace(tzinfo=None)
        in_window = (
            (self.window_start <= local < self.window_end)
            if self.window_start <= self.window_end
            else (local >= self.window_start or local < self.window_end)
        )
        return self.opted_in and now >= self.at and in_window


class Scheduler:
    def __init__(self):
        self.items = []
        self.stopped = False

    def schedule(self, item):
        if not item.opted_in:
            raise PermissionError("Check-in requires explicit opt-in")
        self.items.append(item)

    def due(self, now):
        return [] if self.stopped else [x for x in self.items if x.due(now)]

    def emergency_stop(self):
        self.stopped = True
        self.items.clear()
