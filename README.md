# Mitos

Mitos is the smallest agent harness: ten core files, zero third-party
dependencies, and one understandable path from a model response to real work.
It is a five-day reference implementation for learning how coding agents handle
tools, policy, context, memory, durable sessions, delegation, and concurrency.
Mitos requires Python 3.10 or newer and currently speaks the Gemini API.

## Run it

Set the API key before running Mitos:

```bash
export MITOS_API_KEY="your-gemini-api-key"
```

In PowerShell, use `$env:MITOS_API_KEY = "your-gemini-api-key"`. You may use
`GEMINI_API_KEY` as a fallback, and `MITOS_MODEL` to override the default model.

Run one of the three CLI forms from the repository root:

```bash
# Interactive: safe mode asks before writes and shell commands.
python3 -m mitos --workdir ./project

# Headless: -p defaults to yolo mode, while the hard denylist still applies.
python3 -m mitos --workdir ./project -p "Create and test a small Python app"

# Resume the newest durable session after an interruption.
python3 -m mitos --workdir ./project --resume
```

Select a model with `--model`, cap execution with `--max-turns`, or explicitly
choose `--mode safe`, `--mode yolo`, or `--mode read-only`. All file tools are
jailed to the real working directory. Session logs live under
`.mitos/sessions/` inside that directory.

## Five-day anatomy

| Day | Files | What they teach |
| --- | --- | --- |
| 1 | `provider.py`, `loop.py` | Neutral messages, Gemini thought signatures, retries, and the model/tool loop |
| 2 | `tools.py`, `security.py` | Generated schemas, workspace confinement, bounded output, and execution policy |
| 3 | `context.py`, `memory.py`, `skills.py` | Compaction, durable project facts, and on-demand instructions |
| 4 | `session.py`, `subagent.py`, `harness.py` | JSONL recovery, isolated delegation, and full composition |
| 5 | `cli.py`, `fleet.py` | A terminal product surface and ordered concurrent jobs |

`mitos.Harness` is the composition root. `mitos.Tool` and `mitos.tool` are its
extension seam; `mitos.run_fleet` runs independent harness jobs concurrently.

## Register one extra tool

The decorator keeps every parameter string-typed at the model boundary. Pass
the resulting `Tool` to `extra_tools` when constructing a harness:

```python
from mitos import Harness, tool


@tool("Count words in some text", text="Text to count")
def count_words(text: str) -> str:
    """Return the number of whitespace-delimited words."""
    return str(len(text.split()))


agent = Harness(workdir=".", extra_tools=[count_words])
agent.run("Use count_words to count: small agents stay understandable")
```

The same composition works with a custom `Policy`, event callback, model,
context budget, or additional tools—all without changing the harness loop.
