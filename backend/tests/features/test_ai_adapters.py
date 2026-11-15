from __future__ import annotations

import asyncio
import unittest

from features.ai_adapters.career import CareerProfile, CareerRecommendationAdapter
from features.ai_adapters.common import AdapterError, Mode, RuntimeConfig, run_bounded
from features.ai_adapters.desktop import DesktopAdapter
from features.ai_adapters.tutor import BoardEvent, TutorAdapter, TutorTurn
from features.ai_adapters.voice import VoiceAdapter


class FakeExecutor:
    def __init__(self):
        self.calls = 0

    async def __call__(self, plan):
        self.calls += 1
        return {"fake": True}


class FakeDialogue:
    async def respond(self, text, locale, history):
        return "A helpful test response"


class FakeSTT:
    async def transcribe(self, audio, locale):
        return "What is a fraction?"


class StaticTutorProvider:
    async def respond(self, topic, text, history):
        return TutorTurn("A clear explanation.", (BoardEvent("text", 10, 20, "Step one"),))


class FakeTTS:
    async def synthesize(self, text, locale):
        return "test-audio-ref"


class FakeVoiceIssuer:
    async def create_session(self, session_id, user_id, locale):
        return {
            "transport": "fake-live",
            "token": "short-lived-test-token",
            "expires_at": "2099-01-01T00:00:00Z",
        }

    async def end_session(self, session_id):
        return None

    async def cancel_session(self, session_id):
        return None


class SlowDialogue:
    def __init__(self):
        self.cancelled = False
        self.started = asyncio.Event()

    async def respond(self, text, locale, history):
        self.started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class ErrorDialogue:
    async def respond(self, text, locale, history):
        raise RuntimeError("secret provider detail")


class SlowTutorProvider:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def respond(self, topic, text, history):
        self.started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class BlockingExecutor:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = False

    async def __call__(self, plan):
        self.started.set()
        try:
            await asyncio.sleep(5)
        except asyncio.CancelledError:
            self.cancelled = True
            raise


class InvalidBoardProvider:
    async def respond(self, topic, text, history):
        return TutorTurn("A response", (BoardEvent("script", 9999, 9999),))


class AdapterContractTests(unittest.TestCase):
    def test_desktop_requires_local_user_start_and_preview_is_allowlisted(self):
        adapter = DesktopAdapter()
        with self.assertRaises(AdapterError) as denied:
            adapter.create_session("u1", ["preview"], "v1", False)
        self.assertEqual(denied.exception.code, "user_action_required")
        created = adapter.create_session("u1", ["preview"], "v1", True)
        preview = adapter.preview(created["session_id"], "open calculator")
        self.assertTrue(preview["approval_required"])
        self.assertTrue(preview["simulation"])
        with self.assertRaises(AdapterError):
            adapter.preview(created["session_id"], "run powershell")

    def test_desktop_approval_hash_cancel_and_demo_never_execute_os(self):
        adapter = DesktopAdapter()
        sid = adapter.create_session("u1", ["preview"], "v1", True)["session_id"]
        preview = adapter.preview(sid, "open calculator")
        plan = preview["actions"][0]
        with self.assertRaises(AdapterError):
            adapter.approve(sid, plan["plan_id"], plan["plan_hash"], False)
        with self.assertRaises(AdapterError):
            adapter.approve(sid, plan["plan_id"], "wrong", True)
        adapter.approve(sid, plan["plan_id"], plan["plan_hash"], True)
        result = asyncio.run(adapter.execute(sid, plan["plan_id"], Mode.DEMO))
        self.assertTrue(result["simulation"])
        self.assertEqual(result["state"], "completed")
        self.assertFalse(adapter.config.real_desktop_approved)

    def test_real_desktop_is_disabled_without_approved_executor(self):
        adapter = DesktopAdapter(RuntimeConfig(Mode.LIVE, 0.2, False))
        sid = adapter.create_session("u1", ["preview"], "v1", True)["session_id"]
        plan = adapter.preview(sid, "open calculator")["actions"][0]
        adapter.approve(sid, plan["plan_id"], plan["plan_hash"], True)
        with self.assertRaises(AdapterError) as unavailable:
            asyncio.run(adapter.execute(sid, plan["plan_id"], Mode.LIVE))
        self.assertEqual(unavailable.exception.code, "desktop_executor_unavailable")

    def test_desktop_executor_requires_both_configuration_and_approval(self):
        executor = FakeExecutor()
        adapter = DesktopAdapter(RuntimeConfig(Mode.LIVE, 0.2, True), executor)
        sid = adapter.create_session("u1", ["preview", "execute"], "v1", True)["session_id"]
        plan = adapter.preview(sid, "open calculator")["actions"][0]
        with self.assertRaises(AdapterError):
            asyncio.run(adapter.execute(sid, plan["plan_id"], Mode.LIVE))
        adapter.approve(sid, plan["plan_id"], plan["plan_hash"], True)
        result = asyncio.run(adapter.execute(sid, plan["plan_id"], Mode.LIVE))
        self.assertFalse(result["simulation"])
        self.assertEqual(executor.calls, 1)

    def test_career_output_is_original_illustrative_and_deterministic_except_id(self):
        adapter = CareerRecommendationAdapter()
        profile = CareerProfile("secondary", ("building", "technology"), ("python",))
        first = adapter.recommend(profile)
        second = adapter.recommend(profile)
        self.assertEqual(first["recommendations"], second["recommendations"])
        top = first["recommendations"][0]
        self.assertEqual(top["role"], "Software Developer")
        self.assertEqual(top["score_kind"], "illustrative_rule_based_fit")
        self.assertIn("not probabilities", " ".join(first["limitations"]))
        self.assertTrue(top["skill_gaps"])

    def test_career_rejects_empty_profile(self):
        with self.assertRaises(AdapterError):
            CareerRecommendationAdapter().recommend(CareerProfile("secondary", (), ()))

    def test_tutor_demo_lesson_board_quiz_and_end_state(self):
        adapter = TutorAdapter()
        sid = adapter.start_session("u1", "fractions")["session_id"]
        turn = asyncio.run(adapter.send_turn(sid, "Explain the denominator"))
        self.assertTrue(turn["simulation"])
        self.assertEqual(len(turn["board_events"]), 3)
        self.assertEqual(turn["board_events"][0]["kind"], "text")
        quiz = adapter.quiz(sid)
        self.assertEqual(quiz["question_id"], "q1")
        answer = adapter.submit_quiz_answer(sid, "equal parts in one whole")
        self.assertTrue(answer["correct"])
        adapter.end_session(sid)
        with self.assertRaises(AdapterError):
            asyncio.run(adapter.send_turn(sid, "again"))

    def test_voice_demo_transcript_and_conversation_state(self):
        voice = VoiceAdapter()

        async def check():
            created = await voice.create_session("u1")
            self.assertEqual(created["transport"], "simulation")
            self.assertIsNone(created["token"])
            result = await voice.submit_audio(created["session_id"], b"sample-only")
            self.assertTrue(result["simulation"])
            self.assertEqual(result["transcript_source"], "simulated")
            self.assertEqual(result["answer"], "Demo heard: offline sample greeting")
            self.assertEqual(len(result["events"]), 2)
            self.assertEqual(voice.status(created["session_id"])["turn_count"], 1)
            ended = await voice.end_session(created["session_id"])
            self.assertEqual(ended["state"], "ended")

        asyncio.run(check())

    def test_missing_live_providers_are_clear(self):
        voice = VoiceAdapter(RuntimeConfig(Mode.LIVE))
        with self.assertRaises(AdapterError) as voice_error:
            asyncio.run(voice.create_session("u1"))
        self.assertEqual(voice_error.exception.code, "provider_unavailable")
        tutor = TutorAdapter(RuntimeConfig(Mode.LIVE))
        tsid = tutor.start_session("u1", "fractions")["session_id"]
        with self.assertRaises(AdapterError) as tutor_error:
            asyncio.run(tutor.send_turn(tsid, "Help"))
        self.assertEqual(tutor_error.exception.code, "provider_unavailable")

    def test_adapter_errors_do_not_leak_provider_details(self):
        voice = VoiceAdapter(
            RuntimeConfig(Mode.LIVE, 0.2),
            dialogue=ErrorDialogue(),
            tts=FakeTTS(),
            transport_issuer=FakeVoiceIssuer(),
        )
        sid = asyncio.run(voice.create_session("u1"))["session_id"]
        with self.assertRaises(AdapterError) as raised:
            asyncio.run(voice.submit_text(sid, "Hi"))
        self.assertEqual(raised.exception.code, "voice_provider_error")
        self.assertNotIn("secret", raised.exception.message)

    def test_live_voice_uses_injected_token_stt_dialogue_and_tts_providers(self):
        voice = VoiceAdapter(
            RuntimeConfig(Mode.LIVE, 0.5),
            stt=FakeSTT(),
            dialogue=FakeDialogue(),
            tts=FakeTTS(),
            transport_issuer=FakeVoiceIssuer(),
        )

        async def check():
            created = await voice.create_session("u1", locale="en")
            self.assertEqual(created["transport"], "fake-live")
            self.assertEqual(created["token"], "short-lived-test-token")
            result = await voice.submit_audio(created["session_id"], b"audio")
            self.assertFalse(result["simulation"])
            self.assertEqual(result["transcript_source"], "provider")
            self.assertEqual(result["answer"], "A helpful test response")
            self.assertEqual(result["audio_ref"], "test-audio-ref")
            await voice.end_session(created["session_id"])
            self.assertEqual(voice.status(created["session_id"])["state"], "ended")

        asyncio.run(check())

    def test_live_tutor_provider_success(self):
        tutor = TutorAdapter(RuntimeConfig(Mode.LIVE, 0.5), StaticTutorProvider())
        sid = tutor.start_session("u1", "fractions")["session_id"]
        result = asyncio.run(tutor.send_turn(sid, "Explain"))
        self.assertFalse(result["simulation"])
        self.assertEqual(result["answer"], "A clear explanation.")
        self.assertEqual(result["board_events"][0]["text"], "Step one")

    def test_voice_provider_timeout_is_typed(self):
        dialogue = SlowDialogue()
        voice = VoiceAdapter(
            RuntimeConfig(Mode.LIVE, 0.02),
            dialogue=dialogue,
            tts=FakeTTS(),
            transport_issuer=FakeVoiceIssuer(),
        )
        sid = asyncio.run(voice.create_session("u1"))["session_id"]
        with self.assertRaises(AdapterError) as raised:
            asyncio.run(voice.submit_text(sid, "Hello"))
        self.assertEqual(raised.exception.code, "voice_timeout")

    def test_tutor_rejects_unsafe_board_events(self):
        tutor = TutorAdapter(RuntimeConfig(Mode.LIVE, 0.2), InvalidBoardProvider())
        sid = tutor.start_session("u1", "fractions")["session_id"]
        with self.assertRaises(AdapterError) as raised:
            asyncio.run(tutor.send_turn(sid, "Explain"))
        self.assertEqual(raised.exception.code, "invalid_board_events")

    def test_tutor_provider_timeout_is_typed(self):
        tutor = TutorAdapter(RuntimeConfig(Mode.LIVE, 0.02), SlowTutorProvider())
        sid = tutor.start_session("u1", "fractions")["session_id"]
        with self.assertRaises(AdapterError) as raised:
            asyncio.run(tutor.send_turn(sid, "Help"))
        self.assertEqual(raised.exception.code, "tutor_timeout")

    def test_desktop_executor_timeout_is_typed(self):
        executor = BlockingExecutor()
        adapter = DesktopAdapter(RuntimeConfig(Mode.LIVE, 0.02, True), executor)
        sid = adapter.create_session("u1", ["preview", "execute"], "v1", True)["session_id"]
        plan = adapter.preview(sid, "open calculator")["actions"][0]
        adapter.approve(sid, plan["plan_id"], plan["plan_hash"], True)
        with self.assertRaises(AdapterError) as raised:
            asyncio.run(adapter.execute(sid, plan["plan_id"], Mode.LIVE))
        self.assertEqual(raised.exception.code, "desktop_timeout")
        self.assertEqual(adapter.status(sid)["state"], "failed")

    def test_provider_timeout_maps_to_typed_safe_error(self):
        async def slow():
            await asyncio.sleep(2)

        async def check():
            with self.assertRaises(AdapterError) as raised:
                await run_bounded(slow(), 0.02, "voice")
            self.assertEqual(raised.exception.code, "voice_timeout")
            self.assertEqual(raised.exception.http_status, 504)

        asyncio.run(check())

    def test_tutor_cancel_endpoint_cancels_in_flight_provider(self):
        provider = SlowTutorProvider()
        tutor = TutorAdapter(RuntimeConfig(Mode.LIVE, 10), provider)
        sid = tutor.start_session("u1", "fractions")["session_id"]

        async def check():
            task = asyncio.create_task(tutor.send_turn(sid, "Help"))
            await asyncio.wait_for(provider.started.wait(), 1)
            tutor.cancel_session(sid)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(provider.cancelled)

        asyncio.run(check())
        self.assertEqual(tutor._get(sid).state, "cancelled")

    def test_desktop_emergency_stop_cancels_in_flight_executor(self):
        executor = BlockingExecutor()
        adapter = DesktopAdapter(RuntimeConfig(Mode.LIVE, 10, True), executor)
        sid = adapter.create_session("u1", ["preview", "execute"], "v1", True)["session_id"]
        plan = adapter.preview(sid, "open calculator")["actions"][0]
        adapter.approve(sid, plan["plan_id"], plan["plan_hash"], True)

        async def check():
            task = asyncio.create_task(adapter.execute(sid, plan["plan_id"], Mode.LIVE))
            await asyncio.wait_for(executor.started.wait(), 1)
            adapter.cancel(sid)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(executor.cancelled)

        asyncio.run(check())
        self.assertEqual(adapter.status(sid)["state"], "cancelled")

    def test_provider_cancellation_propagates_and_session_cancel_is_explicit(self):
        dialogue = SlowDialogue()
        voice = VoiceAdapter(
            RuntimeConfig(Mode.LIVE, 10),
            dialogue=dialogue,
            tts=FakeTTS(),
            transport_issuer=FakeVoiceIssuer(),
        )
        sid = asyncio.run(voice.create_session("u1"))["session_id"]

        async def check():
            task = asyncio.create_task(voice.submit_text(sid, "Hello"))
            await asyncio.wait_for(dialogue.started.wait(), 1)
            await voice.cancel_session(sid)
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertTrue(dialogue.cancelled)

        asyncio.run(check())
        self.assertEqual(voice.status(sid)["state"], "cancelled")
        with self.assertRaises(AdapterError):
            asyncio.run(voice.submit_text(sid, "Again"))


if __name__ == "__main__":
    unittest.main()
