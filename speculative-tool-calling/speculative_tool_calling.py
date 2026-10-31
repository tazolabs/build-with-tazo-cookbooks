import asyncio
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path

from tazo import AsyncTazo, wav_chunks
from tazo.types import ChoiceAnswer, DecisionEvent

THRESHOLD = 0.7  # minimum probability for an option to count
ACTION_STREAK = 2  # consecutive updates that must agree before a function runs
STOP_TO_ACTION_GAP_S = 2.0  # pause between stop_talking() and the function

CONTEXT = (
    "A bank agent is phoning a customer to offer an upgrade of their credit card to the "
    "Indus Platinum Rewards card. Only the caller's microphone audio is streamed to you; "
    "the agent's own voice is not included. Choose the one action the application should "
    "take, judged only from the caller's voice and words."
)

SPEAKING = {
    "speaking": {
        "type": "choice",
        "instructions": "Is the caller speaking in this audio right now?",
        "criteria": {
            "yes": "A person is clearly speaking: real words, a reply or a spoken interruption. Not coughs, clicks or background sounds.",
            "noise": "Non-speech sound such as background noise, music, a cough or typing, with no clear words from the caller.",
            "no": "Silence or near silence, with no speech and no notable noise.",
        },
    }
}

ACTION = {
    "action": {
        "type": "choice",
        "instructions": "Which action should the application take right now, based on what the caller has said so far?",
        "criteria": {
            "NO_TOOL": "Do nothing. No speech yet, only noise or silence, or the caller is mid-sentence or unclear.",
            "send_offer_details_to_mobile": "The caller has finished speaking and clearly agreed to the offer, for example yes, sure, okay or go ahead.",
            "end_call": "The caller has finished speaking and clearly declined, for example no, not interested or please do not call again.",
        },
    }
}


@dataclass
class Tools:
    """The functions the agent can call. Replace the bodies with your own telephony and CRM code."""

    stop_talking: Callable[[], Awaitable[None]]
    send_offer_details_to_mobile: Callable[[], Awaitable[None]]
    end_call: Callable[[str, str], Awaitable[None]]


@dataclass
class CallController:
    tools: Tools
    agent_speaking: bool = True
    done: asyncio.Event = field(default_factory=asyncio.Event)
    _last_pick: str | None = None
    _count: int = 0

    async def on_speaking(self, event: DecisionEvent) -> None:
        answer = event.answers["speaking"]
        assert isinstance(answer, ChoiceAnswer)
        if self.agent_speaking and answer.probabilities.get("yes", 0) >= THRESHOLD:
            await self._stop_talking()

    async def on_action(self, event: DecisionEvent) -> None:
        answer = event.answers["action"]
        assert isinstance(answer, ChoiceAnswer)
        pick = max(answer.probabilities, key=answer.probabilities.__getitem__)
        confident = answer.probabilities[pick] >= THRESHOLD and pick != "NO_TOOL"
        key = pick if confident else None
        self._count = self._count + 1 if key is not None and key == self._last_pick else (1 if key else 0)
        self._last_pick = key
        if key is None or self._count < ACTION_STREAK or self.done.is_set():
            return
        self.done.set()
        # Runs stop_talking() first when the agent is still mid-sentence, then the function.
        if self.agent_speaking:
            await self._stop_talking()
            await asyncio.sleep(STOP_TO_ACTION_GAP_S)
        if key == "send_offer_details_to_mobile":
            await self.tools.send_offer_details_to_mobile()
        else:
            await self.tools.end_call("neutral", "not_interested")

    async def _stop_talking(self) -> None:
        self.agent_speaking = False
        await self.tools.stop_talking()


async def run_call(frames: AsyncIterator[bytes], tools: Tools) -> None:
    """Fan one caller-audio stream out to two Tazo sessions and drive the tools from their answers."""
    controller = CallController(tools)
    async with AsyncTazo() as client:
        async with (
            client.decisions.stream(
                state=CONTEXT, questions=SPEAKING, audio_scope="chunk", evaluation_interval_ms=1000
            ) as speaking,
            client.decisions.stream(
                state=CONTEXT, questions=ACTION, audio_scope="turn", evaluation_interval_ms=500
            ) as action,
        ):
            finalized = {"speaking": asyncio.Event(), "action": asyncio.Event()}

            async def send() -> None:
                async for frame in frames:
                    await asyncio.gather(speaking.send_audio(frame), action.send_audio(frame))
                    if controller.done.is_set():
                        break
                else:
                    # The caller hung up without a decision: ask for the final answer.
                    await asyncio.gather(speaking.commit(), action.commit())
                    await asyncio.gather(*(event.wait() for event in finalized.values()))
                await asyncio.gather(speaking.finish(), action.finish())

            async def receive(name: str, session, handler) -> None:
                async for event in session:
                    if event.type in {"decision.updated", "decision.finalized"}:
                        await handler(event)
                    if event.type == "decision.finalized":
                        finalized[name].set()

            async with asyncio.TaskGroup() as group:
                group.create_task(send())
                group.create_task(receive("speaking", speaking, controller.on_speaking))
                group.create_task(receive("action", action, controller.on_action))


async def paced_wav(path: Path) -> AsyncIterator[bytes]:
    for chunk in wav_chunks(path):
        await asyncio.sleep(len(chunk) / 32000)  # 32,000 bytes of audio per second
        yield chunk


async def main() -> None:
    async def stop_talking() -> None:
        print("stop_talking()")

    async def send_offer_details_to_mobile() -> None:
        print("send_offer_details_to_mobile()")

    async def end_call(emotion: str, interest: str) -> None:
        print(f"end_call(emotion={emotion}, interest={interest})")

    tools = Tools(stop_talking, send_offer_details_to_mobile, end_call)
    await run_call(paced_wav(Path(sys.argv[1] if len(sys.argv) > 1 else "caller_says_yes.wav")), tools)


if __name__ == "__main__":
    asyncio.run(main())
