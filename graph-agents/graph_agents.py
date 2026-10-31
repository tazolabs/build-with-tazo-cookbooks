import asyncio
import sys
from dataclasses import dataclass, field
from pathlib import Path

from tazo import AsyncTazo
from tazo.types import ChoiceAnswer

MODEL = "tazo-large"
MIN_CONFIDENCE = 0.65
MIN_MARGIN = 0.12
TEXT_BUDGET = 1000  # Tazo limits state + instructions + criteria to roughly this many characters

TITLE = "Customer support"
NODES = {
    "TRIAGE": {
        "label": "Welcome & triage",
        "description": "Find out whether the caller needs payment help or a person.",
        "instructions": "Identify the main reason for this support call. Choose Billing for charges or payments. For an explicit request for a person, choose the human destination. Do not route from a greeting alone.",
    },
    "BILLING": {
        "label": "Billing",
        "description": "The caller needs help with a charge, payment, invoice or billing issue.",
        "instructions": "The caller is already in the billing workflow. Keep payment details and answers to the billing question at CURRENT_STEP. Use the human path only for an explicit request for personal help.",
    },
    "HUMAN": {
        "label": "Human specialist",
        "description": "The caller explicitly asks to speak with a person or specialist.",
        "instructions": "This is the end of the route. Only continuing here or asking for clarity can be selected.",
    },
}
START = "TRIAGE"
EDGES = [("TRIAGE", "BILLING"), ("TRIAGE", "HUMAN"), ("BILLING", "HUMAN")]


def clip(text: str, limit: int) -> str:
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def build_question(current: str) -> tuple[str, dict[str, str]]:
    """The state text and the choices for one node: its reachable next nodes plus three built-ins."""
    node = NODES[current]
    state = (
        f"Voice call: {TITLE}. Now at {node['label']} ({current}). "
        f"{clip(node['instructions'], 170)}"
    )
    criteria = {to: clip(NODES[to]["description"], 80) for src, to in EDGES if src == current}
    criteria["CURRENT_STEP"] = "The caller answers the current question."
    criteria["UNCERTAIN"] = "Unclear reply, or matches no listed step."
    criteria["NO_TOOL"] = "None of the options fits: the clip is silent, unclear or unrelated to the question."
    size = len(state) + sum(len(k) + len(v) for k, v in criteria.items())
    if size > TEXT_BUDGET:
        raise ValueError(f"Node {current} needs {size} characters; shorten descriptions or remove edges.")
    return state, criteria


def is_confident(answer: ChoiceAnswer) -> bool:
    ranked = sorted(answer.probabilities.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0
    return answer.confidence >= MIN_CONFIDENCE and answer.confidence - runner_up >= MIN_MARGIN


def next_node(current: str, answer: ChoiceAnswer) -> str:
    """The application, not the model, moves the call: only reachable nodes are allowed."""
    reachable = {to for src, to in EDGES if src == current}
    if not is_confident(answer) or answer.choice in {"UNCERTAIN", "CURRENT_STEP", "NO_TOOL"}:
        return current
    return answer.choice if answer.choice in reachable else current


@dataclass
class Call:
    node: str = START
    path: list[str] = field(default_factory=lambda: [START])

    async def turn(self, client: AsyncTazo, audio: Path) -> ChoiceAnswer:
        state, criteria = build_question(self.node)
        result = await client.decisions.create(
            audio=audio,
            model=MODEL,
            state=state,
            questions={"action": {"type": "choice", "instructions": "Which next step does the caller want?", "criteria": criteria}},
        )
        answer = result.answers["action"]
        assert isinstance(answer, ChoiceAnswer)
        new = next_node(self.node, answer)
        if new != self.node:
            self.node = new
            self.path.append(new)
        return answer


async def main() -> None:
    call = Call()
    async with AsyncTazo() as client:
        for wav in sys.argv[1:] or ["examples/caller_billing.wav", "examples/caller_wants_person.wav"]:
            answer = await call.turn(client, Path(wav))
            print(f"{wav}: {answer.choice} ({answer.confidence:.2f}) -> now at {call.node}")
    print(" → ".join(call.path))


if __name__ == "__main__":
    asyncio.run(main())
