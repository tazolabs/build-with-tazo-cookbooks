# Home assistant

A small home-assistant backend for a home with three rooms (Bedroom, Kitchen, Study), each
with one light. For every spoken command it asks Tazo which room is meant and what should
happen there, straight from the **audio**, and changes a light only when every answer is
confident. It also includes the thermostat bonus from the cookbook: setting a temperature.
See the cookbook in the Tazo docs for the full walkthrough.

## Run it

From the repository root, after the [setup](../README.md#setup):

```bash
python home-assistant/home_assistant.py home-assistant/examples/lights_here_on.wav
```

Pass several WAV files to run them as consecutive commands against the same home. The
speaker is Maya, standing in the kitchen, so "here" means the kitchen. The script prints one
result per command and the final light states.

## How it works

Tazo answers one `choice` question per request, so each command makes two calls on the same
audio (target and action) and runs them in parallel. A light changes only when the target is
a real room, or a pair of rooms, with at least 80% confidence and the action is on or off
with at least 80% confidence. Anything else, including whole-home, becomes a clarifying
question. When the action is `set_temperature`, a third question picks the temperature, one
option per degree from 16 to 28 °C.

## Examples

The recordings in [`examples/`](examples) are synthetic speech (macOS `say`, voices Samantha
and Daniel) saved as WAV. Results are from live runs against the Tazo API; probabilities
vary between runs.

| File | Spoken | Result |
| --- | --- | --- |
| [`lights_here_on.wav`](examples/lights_here_on.wav) | "Lights on here." | Kitchen on |
| [`bedroom_and_study_on.wav`](examples/bedroom_and_study_on.wav) | "Turn on the bedroom and the study." | Bedroom and Study on |
| [`all_lights_off.wav`](examples/all_lights_off.wav) | "Turn off all the lights." | "Which room do you mean?" (whole-home is recognised and deliberately not acted on) |
| [`thermostat_22.wav`](examples/thermostat_22.wav) | "Set the thermostat to twenty two degrees." | `thermostat -> 22 °C` |
| [`thermostat_no_value.wav`](examples/thermostat_no_value.wav) | "Set the thermostat." | "What temperature do you want?" |
