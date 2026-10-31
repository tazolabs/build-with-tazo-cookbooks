# Build with Tazo cookbooks

Runnable backend scripts for the cookbooks in the **Build with Tazo** section of the Tazo
docs. Each cookbook is built on the [Tazo Python SDK](https://github.com/tazolabs/tazo-sdk).

| Cookbook | Folder |
| --- | --- |
| Speculative tool calling | [`speculative-tool-calling`](speculative-tool-calling) |
| Graph agents | [`graph-agents`](graph-agents) |
| User profiling | [`user-profiling`](user-profiling) |

## Setup

Requires Python 3.11 or newer (the scripts use `asyncio.TaskGroup`).

```bash
python -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
export TAZO_API_KEY='your-key'
```

## Run a cookbook

```bash
python speculative-tool-calling/speculative_tool_calling.py speculative-tool-calling/examples/caller_says_yes.wav
```

Each cookbook folder has its own README with the example recordings and their expected output.
