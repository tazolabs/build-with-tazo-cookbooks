# Call Coach

A sales-coaching backend that listens to a representative's reply and answers three
questions: what to do next, how the rep sounds, and what the customer wants. It sends the
same audio to three **persistent Tazo Large streaming sessions**, one per question, and
prints feedback as decisions arrive. Earlier conversation is supplied as text; the current
reply is judged from the original waveform. See the cookbook in the Tazo docs for the
step-by-step walkthrough.

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python call-coach-ai/call_coach_ai.py call-coach-ai/examples/rep_solution.wav --history call-coach-ai/examples/sales_history.json
```

To try an opening question with no previous conversation, or silence:

```bash
python call-coach-ai/call_coach_ai.py call-coach-ai/examples/rep_discovery.wav
python call-coach-ai/call_coach_ai.py call-coach-ai/examples/silence.wav
```

With no arguments, the script uses `rep_discovery.wav`. It replays recordings at microphone
speed; total runtime also includes connection setup, inference and session closure. Use
Python 3.11+ and `tazo-sdk>=0.1.2`; no web server, voice-partner service or other API key is
needed.

## How it works

- **One question per session.** `next`, `delivery` and `customer` each open one session
  with `model="tazo-large"`, `audio_scope="turn"` and a 1,000 ms evaluation interval. Each
  session receives the same reply in paced PCM16 frames and stays open for the whole reply.
  The interval requests evaluations; it does not guarantee a result every second.
- **Audio and history have different jobs.** Only the rep's microphone belongs in the
  waveform. `--history` accepts a JSON list of `{"speaker": "rep" | "customer", "text": "..."}`
  turns that precede that reply. Customer needs come from earlier customer text, not the
  rep's tone. Without earlier customer text, customer feedback is always flagged for review,
  even if the model selects a confident label.
- **Uncertain feedback stays visible.** Each JSON line includes the question, event type,
  choice, confidence, all probabilities and `needs_review`. A choice is trusted only at
  65% confidence with a 12-point lead over the runner-up. `NO_TOOL` becomes `null` and
  always needs review. Confidence is not a performance score.
- **Finish explicitly.** At the end of the WAV, each sender commits its turn. Each receiver
  waits for a final answer covering the recording, calls `finish()`, and consumes normal
  closure. A failed question cancels its siblings; the script does not reconnect or replay.

Recordings must be nonempty mono 16 kHz PCM16 WAVs of at most 30 seconds. Frames also obey
the negotiated per-message and turn limits. The script rejects history that makes any
question exceed its 1,000-character text budget; it never silently drops earlier turns.

## Examples

The speech clips were synthesized with macOS `say`, voice Samantha, in the source project.
The silence clip is two seconds of PCM silence. These are evaluation fixtures, not recorded
customers.

| File | Spoken / context | Expected behavior |
| --- | --- | --- |
| `rep_discovery.wav` | "Thanks for taking the call. What is your team trying to improve?" No history. | Coaching and delivery feedback; customer feedback always needs review. |
| `rep_solution.wav` with `sales_history.json` | Customer previously described manual reporting. Rep: "We can help automate those reports. Is there a particular deadline you are working toward?" | All three questions can use the reply and the customer's stated problem. |
| `silence.wav` | No speech and no history. | Abstain or flag uncertain answers for review. |

Outputs are probabilistic; choices and confidence can vary between runs. `decision.updated`
is provisional, while `decision.finalized` is the turn's final result. Feedback is advisory:
the script never executes a tool or generates a spoken reply.

In a live SDK 0.1.2 check, the solution clip returned `connect_value` at 0.36 (review),
`confident_clear` at 0.67 (trusted), and a close customer-needs result at 0.46 (review).
All three silence answers were `NO_TOOL`. The discovery clip's customer answer guessed
`solve_problem` at 0.58 despite absent customer history: the application flags it rather
than treating that guess as evidence about the customer.

## Adapt it

Replace the WAV sender with frames from the rep's live microphone, gated while the partner
is speaking. Start fresh sessions with refreshed history for each new rep reply. Add another
scenario by replacing the three question specifications. Sending more questions or using
shorter evaluation intervals consumes more inference capacity.

This is the Tazo coaching core adapted from
[`tazo-cookbooks/projects/call-coach-ai`](https://github.com/tazolabs/tazo-cookbooks/tree/main/projects/call-coach-ai).
The full app adds a voice partner, transcription, web UI and other scenarios. Those services
are outside this recipe. Call Coach's upstream MIT notice is retained in [LICENSE](LICENSE).
