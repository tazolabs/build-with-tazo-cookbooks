# Build with Tazo cookbooks

Runnable backend scripts for the cookbooks in the **Build with Tazo** section of the Tazo
docs. Each cookbook is built on the [Tazo Python SDK](https://github.com/tazolabs/tazo-sdk).

| Cookbook | Folder |
| --- | --- |
| Speculative tool calling | [`speculative-tool-calling`](speculative-tool-calling) |

## Setup

Requires Python 3.11 or newer (the scripts use `asyncio.TaskGroup`).

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
export TAZO_API_KEY='your-key'
```

## Run a cookbook

```bash
python speculative-tool-calling/speculative_tool_calling.py path/to/caller_recording.wav
```
