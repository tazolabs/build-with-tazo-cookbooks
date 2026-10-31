# User profiling

An annotation backend that takes a WAV clip and asks Tazo three questions about the
**audio itself**: the speaker's age group, the speaker's gender, and what the speaker is
doing (the dialog act). Each label comes with a flag when a person should review it. See the
cookbook in the Tazo docs for the full walkthrough.

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python user-profiling/user_profiling.py user-profiling/examples/caller_greeting.wav
```

The script prints a JSON object with one entry per question (`choice`, `confidence`,
`needs_review`) and a clip-level `needs_review` that is true when any label is uncertain.
A `choice` of `null` means Tazo picked `NO_TOOL`: nothing fit.

## How it works

Tazo answers one `choice` question per request, so the script makes three calls on the same
clip and runs them in parallel. A label is trusted only when the winner is not `NO_TOOL`, has
at least 65% probability, and leads the runner-up by at least 12 points. Anything else is
flagged for review.

## Examples

The recordings in [`examples/`](examples) are synthetic speech (macOS `say`, voices
Samantha and Daniel) saved as 16 kHz mono PCM WAV, plus a clip of silence.

| File | The clip | Age | Gender | Dialog act | Clip needs review |
| --- | --- | --- | --- | --- | --- |
| [`caller_greeting.wav`](examples/caller_greeting.wav) | Samantha: "Hello, thank you for calling Northstar Bank. My name is Anna, how can I help you today?" | young 0.78 | female 0.99 | greeting 0.69 | no |
| [`caller_lost_card.wav`](examples/caller_lost_card.wav) | Daniel: "Hi, I lost my credit card yesterday and I need to get it blocked." | young 0.74 | male 0.75 | problem_description 1.00 | no |
| [`caller_thanks.wav`](examples/caller_thanks.wav) | Samantha: "Thank you so much for your help, that is all I needed. Goodbye." | young 0.69 | female 0.60 (review) | thanks 0.61 (review) | **yes** |
| [`silence.wav`](examples/silence.wav) | Two seconds of silence | young 0.33 (review) | none 0.43 (review) | none 0.17 (review) | **yes** |

- **Greeting and lost card:** every label clears the 65% threshold and the 12-point lead,
  so the labels stand.
- **Thanks:** the dialog act is correct, but gender and dialog act both fall under 65%, so
  the clip is flagged. This is what the review gate is for.
- **Silence:** with nothing to hear, every label is uncertain, and gender and dialog act
  come back as `NO_TOOL` (`null`). The clip is flagged.

Age is an estimate from the voice alone, and these clips are text-to-speech, so treat the
age labels here as illustrations of the output shape, not accuracy. Outputs come from live
runs against the Tazo API; confidences vary between runs.
