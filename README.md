# model-regression-tester

An **MCP server** for LLM regression testing. It runs your prompts against two
models side-by-side (`claude-sonnet-4-6` and `gpt-4o`), uses **Claude as a
meta-evaluator** to score the outputs, and reports latency, token usage, cost,
and **cost projections at 1M / 10M tokens per day**.

Use it to catch regressions when you switch models or providers, and to decide
which model gives you the best quality-per-dollar.

## Demo

![Demo of model-regression-tester](docs/demo.gif)

> _Placeholder — record a short run and drop the GIF at `docs/demo.gif`._

## Features

- Run a suite of prompts (built-in samples, an inline list, or a text file)
- Call both models **simultaneously** per prompt (`asyncio.gather`)
- Capture per call: **output text, latency (ms), input/output tokens, cost**
- **Claude-as-judge** scoring on a 1–10 rubric: accuracy, clarity, completeness
  (responses are anonymized A/B to the judge to reduce bias)
- Structured comparison report: side-by-side outputs, scores, run cost, and
  **projected cost at 1M and 10M tokens/day**
- Three MCP tools: `run_regression_test`, `compare_models`, `get_cost_projection`

## How it works

```
prompt ─┬─▶ claude-sonnet-4-6 ─┐
        └─▶ gpt-4o ────────────┤
                               ▼
                    Claude meta-evaluator (A/B scoring)
                               ▼
        side-by-side report + metrics + cost + projections
```

## Requirements

- **Python 3.10+** (required by the MCP SDK)
- API keys for Anthropic and OpenAI

## Setup

```bash
git clone https://github.com/smithar106/AI-Model-Tester.git
cd AI-Model-Tester

python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt    # or: pip install -e .

cp .env.example .env               # then fill in your keys
```

Set your keys in `.env`:

```env
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

## Running the server

```bash
python -m model_regression_tester.server
# or, if installed with `pip install -e .`:
model-regression-tester
```

The server speaks MCP over stdio and is meant to be launched by an MCP client.

### Connecting an MCP client (e.g. Claude Desktop)

Add this to your client's MCP server config (adjust the path):

```json
{
  "mcpServers": {
    "model-regression-tester": {
      "command": "python",
      "args": ["-m", "model_regression_tester.server"],
      "cwd": "/absolute/path/to/AI-Model-Tester",
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-...",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

## Tools

### `run_regression_test`
Run a full suite and return a comparison report.

| Arg | Type | Description |
| --- | --- | --- |
| `prompts_file` | `str?` | Path to a prompt file (one per line; `#` comments and blanks ignored). |
| `prompts` | `list[str]?` | Inline prompts. Takes priority over the file. |

If neither is given, the built-in sample prompts are used.

### `compare_models`
Head-to-head comparison on a single prompt.

| Arg | Type | Description |
| --- | --- | --- |
| `prompt` | `str` | The prompt to send to both models. |

### `get_cost_projection`
Project daily/monthly cost for both models at target volumes.

| Arg | Type | Description |
| --- | --- | --- |
| `input_tokens` | `int` | Representative input tokens per request. |
| `output_tokens` | `int` | Representative output tokens per request. |
| `tokens_per_day` | `list[int]?` | Target daily volumes. Default `[1_000_000, 10_000_000]`. |

## Prompt file format

```text
# Lines starting with '#' are ignored, as are blank lines.
Explain the CAP theorem to a backend engineer in under 120 words.
Write a SQL query to find the second-highest salary in an employees table.
```

See [`sample_prompts.txt`](sample_prompts.txt).

## Example output

```markdown
# Model Regression Test Report

- **Model A:** claude-sonnet-4-6
- **Model B:** gpt-4o
- **Prompts tested:** 1
- **Judge:** Claude meta-evaluator (anonymized A/B scoring)

---
## Prompt 1

> Summarize the plot of Romeo and Juliet in exactly three sentences.

### Claude (claude-sonnet-4-6)
Two young lovers from feuding families in Verona fall in love at first sight...

### GPT (gpt-4o)
Romeo and Juliet, from rival families, fall in love and secretly marry...

### Metrics
| Metric | Claude (claude-sonnet-4-6) | GPT (gpt-4o) |
| --- | ---: | ---: |
| Latency (ms) | 1,420 | 980 |
| Input tokens | 24 | 24 |
| Output tokens | 96 | 88 |
| Cost | $0.001512 | $0.000940 |

### Scores
| Score (1–10) | Claude (claude-sonnet-4-6) | GPT (gpt-4o) |
| --- | ---: | ---: |
| Accuracy | 9 | 9 |
| Clarity | 9 | 8 |
| Completeness | 9 | 8 |
| **Average** | **9.0** | **8.33** |

**Winner:** Claude (claude-sonnet-4-6)

---
## Summary

| Aggregate | Claude (claude-sonnet-4-6) | GPT (gpt-4o) |
| --- | ---: | ---: |
| Total cost (run) | $0.001512 | $0.000940 |
| Avg latency (ms) | 1,420 | 980 |
| Avg score | 9.00 | 8.33 |
| Total tokens | 120 | 112 |

**Win tally:** Claude: 1 · GPT: 0 · Tie: 0

## Projected Cost at Scale

| Tokens/day | claude-sonnet-4-6 (daily) | claude-sonnet-4-6 (monthly) | gpt-4o (daily) | gpt-4o (monthly) |
| --- | ---: | ---: | ---: | ---: |
| 1,000,000 | $12.60 | $378.00 | $8.39 | $251.79 |
| 10,000,000 | $126.00 | $3,780.00 | $83.93 | $2,517.86 |
```

## Pricing

Costs are computed from public list pricing (USD per 1M tokens), defined in
[`model_regression_tester/pricing.py`](model_regression_tester/pricing.py):

| Model | Input | Output |
| --- | ---: | ---: |
| `claude-sonnet-4-6` | $3.00 | $15.00 |
| `gpt-4o` | $2.50 | $10.00 |

Update the `PRICING` table if vendor pricing changes.

## Configuration

| Env var | Default | Purpose |
| --- | --- | --- |
| `ANTHROPIC_API_KEY` | — | Required. Claude model + evaluator. |
| `OPENAI_API_KEY` | — | Required. GPT model. |
| `CLAUDE_MODEL` | `claude-sonnet-4-6` | Model A under test. |
| `GPT_MODEL` | `gpt-4o` | Model B under test. |
| `EVAL_MODEL` | `claude-sonnet-4-6` | Meta-evaluator model. |

## Project structure

```
model_regression_tester/
  __init__.py
  server.py       # MCP server + tools
  models.py       # model calls + metric capture
  evaluator.py    # Claude-as-judge scoring
  pricing.py      # pricing tables, cost + projection math
  prompts.py      # sample prompts + file loader
  report.py       # markdown report rendering
requirements.txt
pyproject.toml
.env.example
sample_prompts.txt
```

## License

MIT
