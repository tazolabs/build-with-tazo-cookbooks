# Graph agents

A call router over a small three-state graph. After each caller reply, Tazo reads the
**audio itself** and picks the next step from the nodes the call can reach from where it is
now. See the cookbook in the Tazo docs for the full walkthrough.

```
TRIAGE ──► BILLING ──► HUMAN
   └──────────────────► HUMAN
```

## Run it

From the repository root, after the [setup](../README.md#setup), pass the caller's turns in
order. With no arguments the script plays `caller_billing.wav` then `caller_wants_person.wav`.

```bash
python graph-agents/graph_agents.py graph-agents/examples/caller_billing.wav graph-agents/examples/caller_wants_person.wav
```

Each turn prints the option Tazo chose, its confidence, and where the call is now. The last
line is the path the call took.

## How it works

For every turn, `build_question` rebuilds one `choice` question for the current node. Its
options are the nodes reachable from there, plus `CURRENT_STEP`, `UNCERTAIN` and `NO_TOOL`.
The call moves only when the answer is confident (at least 65%, with a 12-point lead over
the runner-up), is not one of the built-ins, and is reachable from the current node. The
application moves the call, not the model.

## Examples

The recordings in [`examples/`](examples) are synthetic speech (macOS `say`, voice
Samantha) saved as 16 kHz mono PCM WAV. Every run starts at `TRIAGE`.

| Turns | The caller says | Output |
| --- | --- | --- |
| `caller_billing.wav`<br>`caller_wants_person.wav` | "Hi, I have a question about a charge on my last invoice."<br>"Actually, can I just talk to a real person please?" | `BILLING (0.99) -> now at BILLING`<br>`HUMAN (0.97) -> now at HUMAN`<br>`TRIAGE → BILLING → HUMAN` |
| `caller_billing.wav`<br>`caller_answers_billing_question.wav` | "Hi, I have a question about a charge on my last invoice."<br>"It's a payment I'm trying to make on my credit card." | `BILLING (0.99) -> now at BILLING`<br>`CURRENT_STEP (0.48) -> now at BILLING`<br>`TRIAGE → BILLING` |
| `caller_unclear.wav` | "Um, well, I am not really sure." | `UNCERTAIN (0.64) -> now at TRIAGE`<br>`TRIAGE` |
| `caller_wants_person.wav` | "Actually, can I just talk to a real person please?" | `HUMAN (0.95) -> now at HUMAN`<br>`TRIAGE → HUMAN` |

- **Billing, then a person:** the first reply routes `TRIAGE → BILLING`. At `BILLING` the
  only reachable node is `HUMAN`, which the second reply asks for.
- **Billing, then an answer:** the second reply answers the billing question rather than
  asking to move, so the call stays at `BILLING`. Here the answer was `CURRENT_STEP` at only
  0.48, which would not have moved the call either way.
- **Unclear:** `UNCERTAIN` is a built-in answer, so the call stays at `TRIAGE`.
- **A person straight away:** `TRIAGE` also connects to `HUMAN` directly, so one reply is
  enough.

Outputs come from live runs against the Tazo API; confidences vary between runs.
