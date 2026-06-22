"""Model invocation and per-call metric capture."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass

from .pricing import cost_usd

MAX_TOKENS = 1024


@dataclass
class ModelResult:
    """Captured metrics for a single model call."""

    model: str
    output: str
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    error: str | None = None

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


async def run_claude(client, model: str, prompt: str) -> ModelResult:
    """Call an Anthropic model and capture metrics."""
    start = time.perf_counter()
    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        latency = (time.perf_counter() - start) * 1000
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        in_tok = resp.usage.input_tokens
        out_tok = resp.usage.output_tokens
        return ModelResult(
            model=model,
            output=text.strip(),
            latency_ms=round(latency, 1),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(cost_usd(model, in_tok, out_tok), 6),
        )
    except Exception as exc:  # noqa: BLE001 - surface provider errors in the report
        latency = (time.perf_counter() - start) * 1000
        return ModelResult(
            model=model,
            output="",
            latency_ms=round(latency, 1),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            error=str(exc),
        )


async def run_openai(client, model: str, prompt: str) -> ModelResult:
    """Call an OpenAI chat model and capture metrics."""
    start = time.perf_counter()
    try:
        resp = await client.chat.completions.create(
            model=model,
            max_tokens=MAX_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        latency = (time.perf_counter() - start) * 1000
        text = resp.choices[0].message.content or ""
        in_tok = resp.usage.prompt_tokens
        out_tok = resp.usage.completion_tokens
        return ModelResult(
            model=model,
            output=text.strip(),
            latency_ms=round(latency, 1),
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=round(cost_usd(model, in_tok, out_tok), 6),
        )
    except Exception as exc:  # noqa: BLE001 - surface provider errors in the report
        latency = (time.perf_counter() - start) * 1000
        return ModelResult(
            model=model,
            output="",
            latency_ms=round(latency, 1),
            input_tokens=0,
            output_tokens=0,
            cost_usd=0.0,
            error=str(exc),
        )
