# Personal Assistant for Mac

A desktop-assistant backend that turns a spoken command into a bounded action plan.
Tazo Large hears the **same original recording at every stage**: command structure, app,
operation, exact target, and a final completeness check. The application translates the
chosen IDs into local plan steps. See the cookbook in the Tazo docs for the full walkthrough.

The script prints plans and decision traces. Connect its output to your own desktop
adapters to run actions; the sample itself does not open apps, move windows or start timers.

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python tazo-assistant/tazo_assistant.py tazo-assistant/examples/open-finder-downloads.wav
```

Pass several WAVs to route them independently:

```bash
python tazo-assistant/tazo_assistant.py tazo-assistant/examples/open-notes.wav tazo-assistant/examples/open-safari-and-notes.wav
```

With no arguments, the script uses `open-notes.wav`. It needs only Python 3.11+, the Tazo
Python SDK and `TAZO_API_KEY`; it runs without macOS or a microphone.

## Supported commands

| Structure | Supported scope |
| --- | --- |
| Open one app | Safari, Notes or Finder. |
| Open one app, then one action | Safari: open YouTube/Tazo Labs or position its window. Notes: position its window. Finder: show Desktop/Documents/Downloads or position its window. Positions: left, right, fill. |
| Open two apps | Two different apps from Safari, Notes and Finder, in spoken order, without further operations. |
| Standalone timer | Exactly 30, 60 or 120 minutes. |
| Coding mode | Fixed plan opening Cursor, Linear, Codex and Slack, in that order. These four apps are available only through this preset. |

This is a deliberately small subset of the source app. Free-form URLs, shell commands,
dictation, arbitrary apps and other multi-step combinations are unsupported.

## How it works

`Router.ask` submits one `choice` question per request with `model="tazo-large"`. It includes
earlier selections as context and adds `NO_TOOL` at every stage. Every selected option must
have at least 65% confidence and a 12-point lead over the runner-up. Choices that fail that
gate stop routing and discard the partial plan.

For app commands, a final question checks that **all and only** the spoken effects are in
the plan. A confident `missing` answer also discards it. This catches some omitted clauses;
it does not guarantee that the command was understood correctly. Timers and Coding mode
resolve directly from their bounded choices, as in the source app.

| Command | Decisions when each stage passes |
| --- | --- |
| Open Notes | structure → app → completeness (3) |
| Open Safari and Notes | structure → first app → second app → completeness (4) |
| Open Finder and show Downloads | structure → app → operation → target → completeness (5) |
| Set a thirty-minute timer | structure → duration (2) |
| Enter Coding mode | structure → fixed local plan (1) |

Each recording has a ten-decision ceiling. Each stage checks a 1,000-character text budget.
Recordings must be nonempty mono 16 kHz PCM16 WAVs of at most 30 seconds. API errors propagate
rather than releasing a plan; the script does not automatically resubmit failed routes.

## Examples

All clips are original scripted commands synthesized with macOS `say`, voice Samantha,
in the source project. Expected plans describe the intended routing; model choices and
confidence can vary.

| File | Spoken | Expected plan / outcome |
| --- | --- | --- |
| `open-notes.wav` | "Open Notes." | Open Notes. |
| `open-safari-and-notes.wav` | "Open Safari and Notes." | Open Safari, then Notes. |
| `open-finder-downloads.wav` | "Open Finder and show my Downloads folder." | Open Finder, then show Downloads. |
| `open-notes-left.wav` | "Open Notes and put its window on the left." | Open Notes, then position its window left. |
| `set-timer-thirty.wav` | "Set a timer for thirty minutes." | Plan a 30-minute timer. |
| `enter-coding-mode.wav` | "Enter Coding mode." | Open Cursor, Linear, Codex and Slack. |
| `chatter.wav` | "That was such a lovely weekend. I really enjoyed the sunshine." | No plan; `needs_clarification`. |
| `dictation.wav` | "Type this sentence: let's meet tomorrow at noon." | Unsupported; no plan. |

A live SDK 0.1.2 check produced the intended plans for all six supported recordings.
Chatter and dictation stopped at `NO_TOOL` with 0.98 and 0.99 confidence respectively.
The Finder command's operation passed at 0.68; the remaining stages also passed their gates.

A successful JSON line has `status: "planned"`, a `plan` list and a `trace` containing the
choice and confidence for each stage. An uncertain or unsupported command has
`status: "needs_clarification"`, a reason, the trace and an empty `plan`.

## Adapt it

Add apps to `APPS`, their operations to `OPERATIONS`, and exact targets to `TARGETS` and
`VALUES`. Keep IDs mapped to local, typed actions. Before connecting real effects, filter
choices by installed apps and permissions, preflight the entire plan, show it for review,
and record completed steps if a later adapter fails.

Adapted from
[`tazo-cookbooks/projects/tazo-assistant`](https://github.com/tazolabs/tazo-cookbooks/tree/main/projects/tazo-assistant).
The source is a native macOS app with a larger command tree, device adapters, review UI,
timers and a hotkey recorder. This recipe keeps its hierarchical audio-routing pattern.
