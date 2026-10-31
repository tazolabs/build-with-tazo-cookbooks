import asyncio
import sys
from dataclasses import dataclass, field
from itertools import combinations
from pathlib import Path

from tazo import AsyncTazo
from tazo.types import ChoiceAnswer

THRESHOLD = 0.8  # every answer must reach this confidence before a light changes
TARGET_MODEL = "tazo-large"
ACTION_MODEL = "tazo-small"
NO_TOOL = "NO_TOOL"
NO_TOOL_DESCRIPTION = "No usable request."

ROOMS = ["Bedroom", "Kitchen", "Study"]


@dataclass
class Home:
    """Replace this with your real device API."""

    lights: dict[str, bool] = field(default_factory=lambda: {room: False for room in ROOMS})

    def describe(self, speaker: str, room: str) -> str:
        state = ", ".join(f"{name} light {'on' if on else 'off'}" for name, on in self.lights.items())
        return (
            f"Home with 3 rooms. {state}. "
            f"The speaker is {speaker}, currently in the {room}. "
        )

def target_choices() -> tuple[dict[str, str], dict[str, list[str]]]:
    """The target options, and the rooms each one stands for."""
    criteria, rooms_for = {}, {}
    for name in ROOMS:
        criteria[name.lower()] = f"The {name} light, named or as 'here' when the speaker is in the {name}."
        rooms_for[name.lower()] = [name]
    for a, b in combinations(ROOMS, 2):
        criteria[f"{a.lower()}_{b.lower()}"] = f"Both the {a} and {b} lights, both spoken."
        rooms_for[f"{a.lower()}_{b.lower()}"] = [a, b]
    criteria["whole_home"] = "Every light in the home, no room named."
    criteria["unspecified"] = "No identifiable room. A generic 'the lights' is not whole-home."
    criteria["unknown_target"] = "A room that is not in this home."
    return criteria, rooms_for


TARGET_INSTRUCTIONS = "Which room's light does the AUDIO target? Use the speaker's room only for 'here' or 'this room'."

ACTION_CHOICES = {
    "turn_on": "Switch the light on.",
    "turn_off": "Switch the light off.",
    "other": "Unclear, compound or unsupported action.",
}
ACTION_INSTRUCTIONS = "Choose the tool that best matches the user's spoken request for light control."

async def ask(client, audio, model, state, instructions, criteria) -> ChoiceAnswer:
    result = await client.decisions.create(
        audio=audio,
        model=model,
        state=state,
        questions={
            "action": {
                "type": "choice",
                "instructions": instructions,
                "criteria": {**criteria, NO_TOOL: NO_TOOL_DESCRIPTION},
            }
        },
    )
    answer = result.answers["action"]
    assert isinstance(answer, ChoiceAnswer)
    return answer

def decide(target: ChoiceAnswer, action: ChoiceAnswer) -> tuple[list[str], str] | str:
    """Rooms and operation to apply, or a clarifying question."""
    _, rooms_for = target_choices()
    if target.confidence < THRESHOLD or target.choice not in rooms_for:
        return "Which room do you mean?"
    if action.confidence < THRESHOLD or action.choice not in {"turn_on", "turn_off"}:
        return "Do you want the light on or off?"
    return rooms_for[target.choice], action.choice


async def handle_command(home: Home, audio: Path, speaker: str, room: str) -> str:
    """One spoken command: two questions on the same audio, asked in parallel."""
    state = home.describe(speaker, room)
    criteria, _ = target_choices()
    async with AsyncTazo() as client:
        target, action = await asyncio.gather(
            ask(client, audio, TARGET_MODEL, state, TARGET_INSTRUCTIONS, criteria),
            ask(client, audio, ACTION_MODEL, state, ACTION_INSTRUCTIONS, ACTION_CHOICES),
        )
        if action.choice == "set_temperature" and action.confidence >= THRESHOLD:
            return await set_thermostat(client, audio, state)
    outcome = decide(target, action)
    if isinstance(outcome, str):
        return outcome
    rooms, operation = outcome
    for name in rooms:
        home.lights[name] = operation == "turn_on"
    return f"{operation} -> {', '.join(rooms)}"

ACTION_CHOICES["set_temperature"] = "Set the thermostat to a temperature."

TEMPERATURE_CHOICES = {f"t{c}": f"Set to {c} degrees Celsius." for c in range(16, 29)}
TEMPERATURE_INSTRUCTIONS = "Which temperature does the AUDIO ask the thermostat to be set to?"


async def set_thermostat(client, audio, state) -> str:
    answer = await ask(client, audio, TARGET_MODEL, state, TEMPERATURE_INSTRUCTIONS, TEMPERATURE_CHOICES)
    if answer.confidence < THRESHOLD or answer.choice == NO_TOOL:
        return "What temperature do you want?"
    return f"thermostat -> {answer.choice[1:]} °C"

async def main() -> None:
    home = Home()
    for wav in sys.argv[1:]:
        print(f"{Path(wav).name}: {await handle_command(home, Path(wav), speaker='Maya', room='Kitchen')}")
    print(home.lights)


if __name__ == "__main__":
    asyncio.run(main())
