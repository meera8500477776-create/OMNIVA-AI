"""Offline-first tutor contract with bounded, validated board operations."""
from __future__ import annotations

import asyncio

from dataclasses import asdict, dataclass, field
from typing import Protocol

from .common import AdapterError, Mode, RuntimeConfig, new_id, utc_now, run_bounded


@dataclass(frozen=True, slots=True)
class BoardEvent:
    kind: str
    x: int
    y: int
    text: str = ""
    x2: int | None = None
    y2: int | None = None


@dataclass(frozen=True, slots=True)
class TutorTurn:
    answer: str
    board_events: tuple[BoardEvent, ...] = ()


class LessonProvider(Protocol):
    async def respond(self, topic: str, text: str, history: list[dict[str, str]]) -> TutorTurn: ...


@dataclass(slots=True)
class TutorSession:
    session_id: str
    user_id: str
    topic: str
    duration_minutes: int
    mode: Mode
    course_id: str | None = None
    state: str = "active"
    history: list[dict[str, str]] = field(default_factory=list)
    progress: int = 0
    in_flight: asyncio.Task[object] | None = None


_DEMO_LESSONS = {
    "fractions": (
        "A fraction names equal parts of a whole. In 3/4, the 4 counts equal parts and the 3 counts selected parts.",
        "A fraction has a numerator and denominator. What does the denominator count?",
        "The denominator counts the equal parts making up one whole.",
    ),
    "linear equations": (
        "A linear equation stays balanced when we do the same operation to both sides. For x + 3 = 8, subtract 3 from each side.",
        "Solve x + 3 = 8. What value balances both sides?",
        "x = 5, because 5 + 3 = 8.",
    ),
}


class TutorAdapter:
    def __init__(self, config: RuntimeConfig | None = None, provider: LessonProvider | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.provider = provider
        self.sessions: dict[str, TutorSession] = {}

    def start_session(
        self, user_id: str, topic: str, duration_minutes: int = 10,
        course_id: str | None = None, mode: Mode | None = None,
    ) -> dict[str, object]:
        if not topic.strip() or len(topic) > 160:
            raise AdapterError("invalid_topic", "Topic must contain 1 to 160 characters", 422)
        if not 1 <= duration_minutes <= 60:
            raise AdapterError("invalid_duration", "duration_minutes must be between 1 and 60", 422)
        selected = mode or self.config.default_mode
        session = TutorSession(new_id(), user_id, topic.strip(), duration_minutes, selected, course_id)
        self.sessions[session.session_id] = session
        return {"session_id": session.session_id, "state": session.state, "mode": selected.value,
                "simulation": selected == Mode.DEMO}

    async def send_turn(self, session_id: str, text: str, audio_ref: str | None = None) -> dict[str, object]:
        session = self._active(session_id)
        if audio_ref is not None:
            raise AdapterError("audio_provider_unavailable", "Tutor audio transcription is not configured", 503)
        clean = text.strip()
        if not clean or len(clean) > 4000:
            raise AdapterError("invalid_message", "Text must contain 1 to 4000 characters", 422)
        if session.mode == Mode.DEMO:
            lesson = _DEMO_LESSONS.get(session.topic.casefold())
            if lesson is None:
                lesson = (f"Let us break {session.topic} into small steps. First, tell me what you already know.",
                          f"What is one thing you already know about {session.topic}?",
                          f"Great. We can build from that starting point about {session.topic}.")
            answer = lesson[0] if not session.history else lesson[2]
            events = (
                BoardEvent("text", 80, 90, session.topic[:80]),
                BoardEvent("text", 80, 170, answer[:220]),
                BoardEvent("arrow", 120, 200, "next", 360, 200),
            )
            result = TutorTurn(answer, events)
        else:
            if self.provider is None:
                raise AdapterError("provider_unavailable", "Live tutor provider is not configured", 503)
            task = asyncio.current_task()
            session.in_flight = task
            try:
                result = await run_bounded(
                    self.provider.respond(session.topic, clean, list(session.history)),
                    self.config.provider_timeout_seconds, "tutor")
            finally:
                if session.in_flight is task:
                    session.in_flight = None
        self._validate_turn(result)
        session.history.extend(({"role": "user", "text": clean}, {"role": "assistant", "text": result.answer}))
        session.progress += 1
        return {"session_id": session_id, "answer": result.answer, "speech_ref": None,
                "board_events": [asdict(event) for event in result.board_events],
                "progress": session.progress, "mode": session.mode.value,
                "simulation": session.mode == Mode.DEMO}

    def quiz(self, session_id: str) -> dict[str, object]:
        session = self._active(session_id)
        topic = session.topic.casefold()
        if topic == "fractions":
            q = "In 3/4, what does 4 represent?"
        elif topic == "linear equations":
            q = "Solve x + 3 = 8."
        else:
            q = f"Name one idea you learned about {session.topic}."
        return {"session_id": session_id, "question_id": "q1", "question": q, "state": session.state}

    def submit_quiz_answer(self, session_id: str, answer: str) -> dict[str, object]:
        session = self._active(session_id)
        if not answer.strip() or len(answer) > 1000:
            raise AdapterError("invalid_quiz_answer", "Quiz answer must contain 1 to 1000 characters", 422)
        question = self.quiz(session_id)["question"]
        topic = session.topic.casefold()
        if topic == "fractions":
            correct = "equal parts" in answer.casefold()
            feedback = "Correct: the denominator counts equal parts." if correct else "Try again: look at the bottom number."
        elif topic == "linear equations":
            correct = answer.strip() == "5"
            feedback = "Correct: x = 5." if correct else "Try subtracting 3 from both sides."
        else:
            correct = bool(answer.strip())
            feedback = "Thanks for sharing an idea." if correct else "Enter an idea to continue."
        session.progress += int(correct)
        return {"session_id": session_id, "question": question, "correct": correct,
                "feedback": feedback, "progress": session.progress, "simulation": session.mode == Mode.DEMO}

    def context(self, session_id: str) -> dict[str, object]:
        session = self._active(session_id)
        return {"session_id": session_id, "topic": session.topic, "course_id": session.course_id,
                "recent_turns": list(session.history[-6:]), "progress": session.progress}

    def cancel_session(self, session_id: str) -> dict[str, object]:
        session = self._get(session_id)
        session.state = "cancelled"
        if session.in_flight is not None and session.in_flight is not asyncio.current_task():
            session.in_flight.cancel()
        return {"session_id": session_id, "state": session.state}
    def end_session(self, session_id: str) -> dict[str, object]:
        session = self._get(session_id)
        session.state = "ended"
        return {"session_id": session_id, "state": session.state, "ended_at": utc_now()}

    def _validate_turn(self, turn: TutorTurn) -> None:
        if not isinstance(turn, TutorTurn):
            raise AdapterError("invalid_provider_output", "Tutor provider returned an invalid turn", 502)
        if not isinstance(turn.answer, str) or not turn.answer.strip() or len(turn.answer) > 8000:
            raise AdapterError("invalid_provider_output", "Tutor provider returned an invalid explanation", 502)
        if len(turn.board_events) > 40:
            raise AdapterError("invalid_board_events", "Tutor returned too many board operations", 502)
        allowed = {"text", "line", "arrow", "clear"}
        for event in turn.board_events:
            if event.kind not in allowed or not (0 <= event.x <= 1000 and 0 <= event.y <= 1000):
                raise AdapterError("invalid_board_events", "Tutor returned an invalid board operation", 502)
            if event.x2 is not None and not 0 <= event.x2 <= 1000:
                raise AdapterError("invalid_board_events", "Board coordinate is out of bounds", 502)
            if event.y2 is not None and not 0 <= event.y2 <= 1000:
                raise AdapterError("invalid_board_events", "Board coordinate is out of bounds", 502)
            if len(event.text) > 300:
                raise AdapterError("invalid_board_events", "Board text is too long", 502)

    def _get(self, session_id: str) -> TutorSession:
        session = self.sessions.get(session_id)
        if session is None:
            raise AdapterError("session_not_found", "Tutor session was not found", 404)
        return session

    def _active(self, session_id: str) -> TutorSession:
        session = self._get(session_id)
        if session.state != "active":
            raise AdapterError("session_state_conflict", "Tutor session is not active", 409)
        return session
