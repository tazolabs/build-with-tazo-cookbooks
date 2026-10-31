# Speculative tool calling

A voice-agent backend that takes a stream of caller audio and calls any of three functions
while the caller is still finishing their sentence. See the cookbook in the Tazo docs for
the full walkthrough.

| Function | Called when |
| --- | --- |
| `stop_talking()` | The caller starts speaking over the agent. |
| `send_offer_details_to_mobile()` | The caller finished and clearly agreed. |
| `end_call(emotion, interest)` | The caller finished and clearly declined. |

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python speculative-tool-calling/speculative_tool_calling.py speculative-tool-calling/examples/caller_says_yes.wav
```

The script replays the WAV in real time as if it were a live call, so a run takes about as
long as the recording. The functions are stubs that print their name; replace the bodies
of `stop_talking`, `send_offer_details_to_mobile` and `end_call` in `main()` with your own
telephony and CRM code.

## How it works

Two Tazo streaming sessions receive the same audio:

- **Speaking** (chunk scope, evaluated every 1000 ms): is the caller speaking right now?
  At 70% or more, and while the agent is talking, the controller calls `stop_talking()`.
- **Action** (turn scope, evaluated every 500 ms): which function should run? An option
  must reach 70% and win on 2 updates in a row. If the agent is still speaking, the
  controller calls `stop_talking()` first and waits 2 seconds before the function.

If the audio ends without a decision, the script commits both sessions and waits for the
final answers.

## Examples

The recordings in [`examples/`](examples) are synthetic speech (macOS `say`, voice
Samantha) saved as 16 kHz mono PCM WAV. The agent is assumed to be speaking when the call
starts, so `stop_talking()` fires first in each run.

| File | The caller says | Output |
| --- | --- | --- |
| [`caller_says_yes.wav`](examples/caller_says_yes.wav) | "Yes, sure. Please go ahead and send me the details." | `stop_talking()`<br>`send_offer_details_to_mobile()` |
| [`caller_says_no.wav`](examples/caller_says_no.wav) | "No, I am not interested. Please do not call again." | `stop_talking()`<br>`end_call(emotion=neutral, interest=not_interested)` |
| [`caller_unclear.wav`](examples/caller_unclear.wav) | "Hmm, let me think about it for a moment." | `stop_talking()` only |

- **Yes:** the caller is detected speaking, so the agent is stopped. The Action session
  then picks `send_offer_details_to_mobile` twice in a row above 70%, and the function runs
  after the 2-second gap.
- **No:** the same flow, ending in `end_call`. The emotion is always `neutral` in this
  example, and the interest is `not_interested`.
- **Unclear:** the caller is speaking, so the agent is stopped, but the answer is never a
  clear yes or no. `NO_TOOL` wins and no function is called. This is the missing re-ask
  step described in the cookbook's Limitations section.

Outputs come from live runs against the Tazo API and can vary slightly between runs.
