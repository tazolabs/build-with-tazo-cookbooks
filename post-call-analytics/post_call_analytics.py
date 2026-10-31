import asyncio
import json
import sys
from pathlib import Path

from tazo import AsyncTazo
from tazo.types import ChoiceAnswer

MODEL = "tazo-large"
QUALITY_MIN_CONFIDENCE = 0.8  # a quality verdict needs a clear winner...
QUALITY_MIN_MARGIN = 0.2  # ...and a wide lead over the runner-up

QUALITY = {
    "context": "Judge the main audible issue in this recorded customer service call: speech quality only, not words, identity or equipment.",
    "instructions": "Overall quality: listen for noise or distortion behind the speech. Which issue is audible?",
    "criteria": {
        "usable": "Clean, clear speech with no audible hiss, noise or distortion.",
        "too_noisy": "Audible background noise or hiss behind the speech.",
        "clipping": "Harsh, crackly distortion like clipping.",
        "reverberant": "Echo or room reverb that blurs the speech.",
    },
}
OFFER = {
    "context": "Recorded sales call where an agent offers a credit card to a customer. Judge whether the customer accepts the offer.",
    "instructions": "Did the customer like the offer and agree to it, for example by saying they are interested or asking for the details to be sent?",
    "criteria": {
        "agreed": "Customer says they like the offer, are interested, or asks for the details to be sent or to go ahead.",
        "declined": "Customer says they are not interested or declines the offer.",
    },
}

# What each quality answer means for the call.
VERDICTS = {
    "usable": ("clear", "Clear audio"),
    "too_noisy": ("low_quality", "Low quality · noisy"),
    "clipping": ("low_quality", "Low quality · distorted"),
    "reverberant": ("low_quality", "Low quality · echo"),
}

async def ask(client: AsyncTazo, audio: Path, spec: dict) -> ChoiceAnswer:
    result = await client.decisions.create(
        audio=audio,
        model=MODEL,
        state=spec["context"],
        questions={
            "answer": {"type": "choice", "instructions": spec["instructions"], "criteria": spec["criteria"]}
        },
    )
    answer = result.answers["answer"]
    assert isinstance(answer, ChoiceAnswer)
    return answer

def quality_verdict(answer: ChoiceAnswer) -> tuple[str, str]:
    ranked = sorted(answer.probabilities.values(), reverse=True)
    runner_up = ranked[1] if len(ranked) > 1 else 0.0
    sure = answer.confidence >= QUALITY_MIN_CONFIDENCE and answer.confidence - runner_up >= QUALITY_MIN_MARGIN
    # An unsure answer never flags a call; it is reported as clear.
    return VERDICTS[answer.choice] if sure else ("clear", "Clear audio")


async def analyze_call(audio: Path) -> dict:
    """Two independent questions about one recorded call, asked in parallel."""
    async with AsyncTazo() as client:
        quality, offer = await asyncio.gather(ask(client, audio, QUALITY), ask(client, audio, OFFER))
    outcome, title = quality_verdict(quality)
    return {
        "call": audio.name,
        "outcome": outcome,
        "title": title,
        "quality": {"choice": quality.choice, "confidence": round(quality.confidence, 2)},
        "offer": {"choice": offer.choice, "confidence": round(offer.confidence, 2)},
    }

async def main() -> None:
    for wav in sys.argv[1:]:
        print(json.dumps(await analyze_call(Path(wav))))


if __name__ == "__main__":
    asyncio.run(main())
