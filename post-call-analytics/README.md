# Post call analytics

A call-review backend for a bank that offers a credit card by phone. For each recorded call
it asks Tazo two questions about the **audio itself**: whether the audio is clear and noise
free (a filter for downstream analytics), and whether the customer accepted the offer
(sales understanding). See the cookbook in the Tazo docs for the full walkthrough.

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python post-call-analytics/post_call_analytics.py post-call-analytics/examples/*.wav
```

The script prints one JSON line per recording with the quality `outcome` and `title`, the
raw `quality` answer, and the `offer` answer.

## How it works

Tazo answers one `choice` question per request, so the script makes two calls on the same
recording and runs them in parallel. A quality verdict needs at least 80% confidence and a
20-point lead over the runner-up. If Tazo is not sure, the call is reported as clear.

## Examples

The recordings in [`examples/`](examples) are synthetic speech (macOS `say`, voices
Samantha and Daniel) saved as WAV. The noisy one has random noise added.

| File | The call | Quality | Offer |
| --- | --- | --- | --- |
| [`call_agreed.wav`](examples/call_agreed.wav) | Samantha offers a no-fee card; Daniel: "Yes, that sounds great. Please sign me up for the card." | usable 0.74, **clear** | agreed 1.00 |
| [`call_declined.wav`](examples/call_declined.wav) | Same offer; Daniel: "No thanks, I am not interested in a new credit card." | usable 0.71, **clear** | declined 1.00 |
| [`call_noisy.wav`](examples/call_noisy.wav) | The agreed call with heavy white noise | too_noisy 0.71, **clear** (below the 80% bar) | agreed 1.00 |

The offer answers are confident on every clip. The noisy clip is heard as `too_noisy`, but
at 71% it does not reach the 80% bar, so it is reported as clear. That is the simplification
in the cookbook: an unsure answer never flags a call. Lower the thresholds if you would
rather flag borderline calls. Outputs come from live runs against the Tazo API; confidences
vary between runs.
