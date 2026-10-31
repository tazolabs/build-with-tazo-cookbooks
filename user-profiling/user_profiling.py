import asyncio
import json
import sys
from pathlib import Path

from tazo import AsyncTazo
from tazo.types import ChoiceAnswer

MODEL = "tazo-large"
MIN_CONFIDENCE = 0.65  # the winner must reach this probability...
MIN_MARGIN = 0.12  # ...and lead the runner-up by this much, or the clip needs review
NO_TOOL = "NO_TOOL"
NO_TOOL_DESCRIPTION = "None of the options fits: the clip is silent, unclear or unrelated to the question."

CONTEXT = (
    "You are annotating a short recording of a person speaking. Listen to the audio itself "
    "and answer only from what you hear."
)

QUESTIONS = {
    "age": {
        "name": "Speaker age group",
        "instructions": "Which age group does the speaker in this audio clip most likely belong to?",
        "options": {
            "young": "The voice of a young adult under 30 years old.",
            "middle": "The voice of a middle-aged adult between 30 and 49 years old.",
            "older": "The voice of an older adult who is 50 years old or older.",
        },
    },
    "gender": {
        "name": "Speaker gender",
        "instructions": "Which gender does the speaker in this audio clip most likely have?",
        "options": {
            "male": "The voice of a male speaker.",
            "female": "The voice of a female speaker.",
        },
    },
    "act": {
        "name": "Dialog act",
        "instructions": "What is the speaker doing in this audio clip?",
        "options": {
            "greeting": "Saying hello or introducing oneself or the company at the start of the call.",
            "problem_description": "The caller explaining what they need or what went wrong, such as a lost card or a request.",
            "open_question": "Asking a broad question such as how can I help you or is there anything else I can help with.",
            "data_question": "Asking for a specific piece of information such as an address, a name or an account.",
            "data_response": "Answering with a specific piece of information such as a number, an address or a name.",
            "data_communication": "Reading out or stating information such as numbers or figures to the other person.",
            "confirm_data": "Repeating or confirming a piece of information to check it is right.",
            "procedure_explanation": "Explaining what was done or what will happen next, such as a card being ordered and when it will arrive.",
            "bear_with_me": "Asking the other person to hold on or wait a moment.",
            "yes_response": "Answering a question with yes or an agreement.",
            "response": "Answering a question in general.",
            "acknowledgement": "A short acknowledgement such as okay, alright or I see.",
            "thanks": "Thanking the other person.",
            "closing": "Saying goodbye or ending the call.",
            "filler_disfluency": "Only filler sounds such as um, uh or hmm.",
            "other": "Anything else that does not fit another option.",
        },
    },
}


def is_confident(answer: ChoiceAnswer) -> bool:
    ranked = sorted(answer.probabilities.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0
    return (
        answer.choice != NO_TOOL
        and answer.confidence >= MIN_CONFIDENCE
        and answer.confidence - runner_up >= MIN_MARGIN
    )


async def annotate(client: AsyncTazo, audio: Path, question_id: str) -> dict:
    """One Tazo decision: a single question about the clip."""
    question = QUESTIONS[question_id]
    result = await client.decisions.create(
        audio=audio,
        model=MODEL,
        state=CONTEXT,
        questions={
            "answer": {
                "type": "choice",
                "instructions": question["instructions"],
                "criteria": {**question["options"], NO_TOOL: NO_TOOL_DESCRIPTION},
            }
        },
    )
    answer = result.answers["answer"]
    assert isinstance(answer, ChoiceAnswer)
    return {
        "question": question["name"],
        "choice": None if answer.choice == NO_TOOL else answer.choice,
        "confidence": round(answer.confidence, 2),
        "needs_review": not is_confident(answer),
    }


async def profile_clip(audio: Path) -> dict:
    """Ask every question about the same clip, in parallel, and flag the clip for review if needed."""
    async with AsyncTazo() as client:
        labels = await asyncio.gather(*(annotate(client, audio, q) for q in QUESTIONS))
    return {
        "clip": audio.name,
        "labels": dict(zip(QUESTIONS, labels)),
        "needs_review": any(label["needs_review"] for label in labels),
    }


async def main() -> None:
    print(json.dumps(await profile_clip(Path(sys.argv[1])), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
