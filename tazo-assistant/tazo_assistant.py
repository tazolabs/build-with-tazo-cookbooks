import argparse
import asyncio
import json
from dataclasses import dataclass, field
from pathlib import Path

from tazo import AsyncTazo, wav_chunks
from tazo.types import ChoiceAnswer

MODEL = "tazo-large"
MIN_CONFIDENCE = 0.65
MIN_MARGIN = 0.12
MAX_DECISIONS = 10
TEXT_BUDGET = 1000
EXAMPLES = Path(__file__).resolve().parent / "examples"

SHAPES = {
    "open_app": "Open or switch to one app; no further action.",
    "app_action": "Open one app, then do one action such as show a folder or move its window.",
    "two_apps": "Open two distinct apps in spoken order, with no other actions.",
    "timer": "Start a standalone timer for 30, 60 or 120 minutes.",
    "coding_mode": "Explicitly enter Coding mode: open Cursor, Linear, Codex and Slack.",
}
APPS = {"safari": "Safari browser.", "notes": "Notes app.", "finder": "Finder file browser."}
OPERATIONS = {
    "safari": {"open_site": "Open a saved website.", "layout": "Move or resize its window."},
    "notes": {"layout": "Move or resize its window."},
    "finder": {"open_folder": "Show a standard folder.", "layout": "Move or resize its window."},
}
TARGETS = {
    "open_site": {"youtube": "YouTube.", "tazo": "Tazo Labs website."},
    "open_folder": {"desktop": "Desktop.", "documents": "Documents.", "downloads": "Downloads."},
    "layout": {"left": "Left half.", "right": "Right half.", "fill": "Fill the usable screen."},
}
# The model chooses IDs. Only local code supplies concrete URLs and native targets.
VALUES = {
    "open_site": {"youtube": "https://www.youtube.com", "tazo": "https://tazolabs.com"},
    "open_folder": {"desktop": "Desktop", "documents": "Documents", "downloads": "Downloads"},
    "layout": {"left": "left", "right": "right", "fill": "fill"},
}
CODING_PLAN = [{"tool": "open_app", "app": app} for app in ("cursor", "linear", "codex", "slack")]


class UnresolvedCommand(Exception):
    pass


@dataclass
class Router:
    audio: Path
    trace: list[dict] = field(default_factory=list)

    async def ask(self, client: AsyncTazo, stage: str, instructions: str, options: dict, prior: list) -> str:
        if len(self.trace) >= MAX_DECISIONS:
            raise UnresolvedCommand("Decision limit reached; no plan was released.")
        state = (
            "Desktop voice command. Listen to the whole recording at every stage. "
            "Only listed commands are supported. Earlier selections: "
            + json.dumps(prior, separators=(",", ":"))
        )
        criteria = {**options, "NO_TOOL": "Unsupported, unclear, silent, or no exact offered match."}
        size = len(state) + len(stage) + len(instructions) + sum(len(k) + len(v) for k, v in criteria.items())
        if size > TEXT_BUDGET:
            raise ValueError("Shorten this stage's state, instructions or choices before sending it.")
        result = await client.decisions.create(
            audio=self.audio,
            model=MODEL,
            state=state,
            questions={"route": {"type": "choice", "instructions": instructions, "criteria": criteria}},
        )
        answer = result.answers["route"]
        assert isinstance(answer, ChoiceAnswer)
        ranked = sorted(answer.probabilities.values(), reverse=True)
        runner_up = ranked[1] if len(ranked) > 1 else 0.0
        trusted = (
            answer.choice in options
            and answer.confidence >= MIN_CONFIDENCE
            and answer.confidence - runner_up >= MIN_MARGIN
        )
        self.trace.append({"stage": stage, "choice": answer.choice, "confidence": round(answer.confidence, 2)})
        if not trusted:
            raise UnresolvedCommand(f"Unresolved {stage}; ask the speaker to clarify.")
        return answer.choice

    async def build_plan(self, client: AsyncTazo) -> list[dict]:
        shape = await self.ask(
            client, "shape", "Which structure matches ALL spoken effects? Unsupported combinations use NO_TOOL.", SHAPES, []
        )
        if shape == "coding_mode":
            return [step.copy() for step in CODING_PLAN]
        if shape == "timer":
            duration = await self.ask(
                client, "duration", "Which exact timer duration was spoken?",
                {str(m): f"Exactly {m} minutes." for m in (30, 60, 120)}, [shape]
            )
            return [{"tool": "start_timer", "minutes": int(duration)}]

        plan, chosen = [], []
        for slot in range(2 if shape == "two_apps" else 1):
            app = await self.ask(
                client, f"app_{slot + 1}", f"Choose requested app {slot + 1} in spoken order; do not repeat earlier apps.",
                {k: v for k, v in APPS.items() if k not in chosen}, [shape, *plan]
            )
            chosen.append(app)
            plan.append({"tool": "open_app", "app": app})
        if shape == "app_action":
            app = chosen[0]
            operation = await self.ask(
                client, "operation", f"Which additional operation is requested for {app}?", OPERATIONS[app], plan
            )
            target = await self.ask(
                client, "target", f"Which exact target is requested for {operation}?", TARGETS[operation], [*plan, operation]
            )
            plan.append({"tool": operation, "app": app, "target": VALUES[operation][target]})
        await self.ask(
            client, "complete", "Does this plan cover EVERY requested effect, with no unspoken effects? Opening an app does not fulfill another action.",
            {"complete": "All and only the requested effects are present.", "missing": "The plan omits a spoken effect or adds an unrequested one."}, plan
        )
        if self.trace[-1]["choice"] != "complete":
            raise UnresolvedCommand("The plan does not match the whole command; no plan was released.")
        return plan


async def route_command(audio: Path) -> dict:
    frames = list(wav_chunks(audio))
    if not frames or sum(map(len, frames)) > 30 * 32000:
        raise ValueError("Provide a nonempty mono 16 kHz PCM16 WAV of at most 30 seconds.")
    router = Router(audio)
    async with AsyncTazo() as client:
        try:
            plan = await router.build_plan(client)
        except UnresolvedCommand as error:
            return {"status": "needs_clarification", "reason": str(error), "plan": [], "trace": router.trace}
    # Connect a reviewed plan to your own device adapters here.
    return {"status": "planned", "plan": plan, "trace": router.trace}


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a bounded desktop action plan from a spoken command.")
    parser.add_argument("audio", type=Path, nargs="*", help="Commands to route independently.")
    args = parser.parse_args()

    async def run() -> None:
        for audio in args.audio or [EXAMPLES / "open-notes.wav"]:
            print(json.dumps({"clip": audio.name, **await route_command(audio)}))

    asyncio.run(run())


if __name__ == "__main__":
    main()
