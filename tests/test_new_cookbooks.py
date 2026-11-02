"""Offline checks for routing boundaries and streaming completion.

Run with: python -m unittest discover -s tests -v
"""

import asyncio
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from tazo.types import ChoiceAnswer, DecisionEvent, SessionClosed

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


coach = load("call_coach", "call-coach-ai/call_coach_ai.py")
assistant = load("tazo_assistant", "tazo-assistant/tazo_assistant.py")


def answer(choice, confidence=0.95, runner_up=0.05):
    return ChoiceAnswer(type="choice", choice=choice, confidence=confidence,
                        probabilities={choice: confidence, "alternative": runner_up})


class Decisions:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.requests = []

    async def create(self, **request):
        self.requests.append(request)
        return SimpleNamespace(answers={"route": next(self.answers)})


class Client:
    def __init__(self, answers):
        self.decisions = Decisions(answers)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass


class RoutingTests(unittest.IsolatedAsyncioTestCase):
    async def route(self, answers):
        client = Client(answers)
        with patch.object(assistant, "AsyncTazo", return_value=client):
            result = await assistant.route_command(assistant.EXAMPLES / "open-notes.wav")
        self.assertTrue(all(request["model"] == "tazo-large" for request in client.decisions.requests))
        return result, client

    async def test_final_check_discards_a_partial_plan(self):
        result, _ = await self.route([answer("open_app"), answer("notes"), answer("missing")])
        self.assertEqual(result["plan"], [])
        self.assertEqual(result["status"], "needs_clarification")

    async def test_close_runner_up_stops_when_confidence_threshold_is_lowered(self):
        with patch.object(assistant, "MIN_CONFIDENCE", 0.5):
            result, client = await self.route([answer("two_apps", 0.53, 0.47)])
        self.assertEqual(result["plan"], [])
        self.assertEqual(len(client.decisions.requests), 1)

    async def test_unknown_option_never_becomes_an_action(self):
        result, _ = await self.route([answer("run_shell")])
        self.assertEqual(result["plan"], [])

    async def test_no_tool_discards_earlier_selections(self):
        result, _ = await self.route([answer("app_action"), answer("finder"), answer("NO_TOOL")])
        self.assertEqual(result["plan"], [])
        self.assertEqual(len(result["trace"]), 3)

    async def test_second_app_menu_excludes_first_app(self):
        result, client = await self.route([
            answer("two_apps"), answer("safari"), answer("notes"), answer("complete")
        ])
        options = client.decisions.requests[2]["questions"]["route"]["criteria"]
        self.assertNotIn("safari", options)
        self.assertEqual([step["app"] for step in result["plan"]], ["safari", "notes"])

    async def test_exact_target_resolves_to_local_value(self):
        result, _ = await self.route([
            answer("app_action"), answer("safari"), answer("open_site"), answer("youtube"), answer("complete")
        ])
        self.assertEqual(result["plan"][-1]["target"], "https://www.youtube.com")

    async def test_decision_ceiling_prevents_an_extra_request(self):
        router = assistant.Router(assistant.EXAMPLES / "open-notes.wav", trace=[{}] * assistant.MAX_DECISIONS)
        client = Client([])
        with self.assertRaises(assistant.UnresolvedCommand):
            await router.ask(client, "shape", "Choose.", assistant.SHAPES, [])
        self.assertEqual(client.decisions.requests, [])


class Session:
    def __init__(self, *, start=0, end=100, normal_close=True):
        self.ready = SimpleNamespace(max_turn_audio_ms=None, max_audio_message_bytes=1000)
        self.start, self.end, self.normal_close = start, end, normal_close
        self.committed, self.finished = asyncio.Event(), asyncio.Event()
        self.sent = []
        self.exited = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        self.exited = True

    async def send_audio(self, frame):
        self.sent.append(frame)

    async def commit(self):
        self.committed.set()

    async def finish(self):
        self.finished.set()

    async def __aiter__(self):
        await self.committed.wait()
        yield DecisionEvent.model_construct(
            type="decision.finalized", answers={"customer": answer("solve_problem")},
            audio_start_ms=self.start, audio_end_ms=self.end,
        )
        await self.finished.wait()
        if self.normal_close:
            yield SessionClosed.model_construct(type="session.closed")


class CoachingTests(unittest.IsolatedAsyncioTestCase):
    async def stream(self, session, customer_context=True):
        stream = lambda **kwargs: session
        client = SimpleNamespace(decisions=SimpleNamespace(stream=stream))
        output = io.StringIO()
        with (patch.object(coach, "wav_chunks", return_value=[b"\x00" * 3200]),
              patch.object(coach.asyncio, "sleep", new=AsyncMock()), contextlib.redirect_stdout(output)):
            await coach.coach_question(client, Path("example.wav"), "history", "customer", customer_context)
        return [json.loads(line) for line in output.getvalue().splitlines()]

    async def test_negotiated_message_limit_and_normal_closure(self):
        session = Session()
        await self.stream(session)
        self.assertEqual(sum(map(len, session.sent)), 3200)
        self.assertTrue(all(len(frame) <= 1000 and len(frame) % 2 == 0 for frame in session.sent))
        self.assertTrue(session.finished.is_set() and session.exited)

    async def test_missing_customer_history_forces_review_even_at_high_confidence(self):
        events = await self.stream(Session(), customer_context=False)
        self.assertEqual(events[0]["choice"], "solve_problem")
        self.assertTrue(events[0]["needs_review"])

    async def test_partial_final_audio_is_rejected(self):
        for session in (Session(end=50), Session(start=10)):
            with self.assertRaises(ExceptionGroup):
                await self.stream(session)
            self.assertTrue(session.exited)

    async def test_final_answer_without_normal_closure_is_rejected(self):
        with self.assertRaises(ExceptionGroup):
            await self.stream(Session(normal_close=False))

    def test_history_budget_is_checked_before_opening_streams(self):
        with self.assertRaises(ValueError):
            coach.build_state([{"speaker": "customer", "text": "x" * 2000}])

    def test_abstention_always_needs_review(self):
        result = coach.feedback(answer("NO_TOOL"))
        self.assertIsNone(result["choice"])
        self.assertTrue(result["needs_review"])


if __name__ == "__main__":
    unittest.main()
