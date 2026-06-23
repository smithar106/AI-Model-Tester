"""MCP server exposing model regression-testing tools.

Tools:
    - run_regression_test: run a suite of prompts against both models + score
    - compare_models: single-prompt head-to-head comparison
    - get_cost_projection: project cost at scale for both models
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

from .evaluator import evaluate_pair
from .models import run_claude, run_deepseek
from .prompts import load_prompts
from .report import (
    DEFAULT_TARGETS,
    build_projection_report,
    build_report,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")
DEEPSEEK_MODEL = os.getenv("DEEPSEEK_MODEL", "deepseek-chat")
EVAL_MODEL = os.getenv("EVAL_MODEL", "claude-sonnet-4-6")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

mcp = FastMCP("model-regression-tester")

_anthropic = None
_deepseek = None


def _anthropic_client():
    global _anthropic
    if _anthropic is None:
        from anthropic import AsyncAnthropic

        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Add it to your environment or .env file.")
        _anthropic = AsyncAnthropic(api_key=key)
    return _anthropic


def _deepseek_client():
    global _deepseek
    if _deepseek is None:
        from openai import AsyncOpenAI

        key = os.getenv("DEEPSEEK_API_KEY")
        if not key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set. Add it to your environment or .env file.")
        _deepseek = AsyncOpenAI(api_key=key, base_url=DEEPSEEK_BASE_URL)
    return _deepseek


async def _run_single(anthropic, deepseek, prompt: str) -> dict:
    """Run one prompt against both models simultaneously, then score the pair."""
    claude_result, deepseek_result = await asyncio.gather(
        run_claude(anthropic, CLAUDE_MODEL, prompt),
        run_deepseek(deepseek, DEEPSEEK_MODEL, prompt),
    )
    evaluation = await evaluate_pair(anthropic, EVAL_MODEL, prompt, claude_result, deepseek_result)
    return {
        "prompt": prompt,
        "claude": claude_result,
        "deepseek": deepseek_result,
        "evaluation": evaluation,
    }


@mcp.tool()
async def run_regression_test(
    prompts_file: str | None = None,
    prompts: list[str] | None = None,
) -> str:
    """Run a regression suite across both models and return a comparison report.

    Args:
        prompts_file: Optional path to a text file (one prompt per line; blank
            lines and lines starting with '#' are ignored).
        prompts: Optional explicit list of prompts. Takes priority over the file.

    If neither is provided, a built-in set of sample prompts is used. Each prompt
    is run against Claude and DeepSeek simultaneously; outputs are scored by a
    Claude meta-evaluator on accuracy, clarity, and completeness. The report
    includes side-by-side outputs, per-prompt metrics, scores, run cost, and cost
    projections at 1M and 10M tokens/day.
    """
    try:
        prompt_list = load_prompts(prompts_file=prompts_file, prompts=prompts)
    except (FileNotFoundError, ValueError) as exc:
        return f"Error loading prompts: {exc}"

    try:
        anthropic = _anthropic_client()
        deepseek = _deepseek_client()
    except RuntimeError as exc:
        return f"Configuration error: {exc}"

    results: list[dict] = []
    for prompt in prompt_list:
        results.append(await _run_single(anthropic, deepseek, prompt))

    return build_report(results, CLAUDE_MODEL, DEEPSEEK_MODEL, DEFAULT_TARGETS)


@mcp.tool()
async def compare_models(prompt: str) -> str:
    """Compare both models on a single prompt with full metrics and scores.

    Args:
        prompt: The prompt to send to both Claude and DeepSeek.

    Returns a report with side-by-side outputs, latency, token usage, cost, and
    a Claude-judged score (accuracy, clarity, completeness) plus a winner.
    """
    if not prompt or not prompt.strip():
        return "Error: prompt is empty."

    try:
        anthropic = _anthropic_client()
        deepseek = _deepseek_client()
    except RuntimeError as exc:
        return f"Configuration error: {exc}"

    result = await _run_single(anthropic, deepseek, prompt.strip())
    return build_report([result], CLAUDE_MODEL, DEEPSEEK_MODEL, DEFAULT_TARGETS)


@mcp.tool()
def get_cost_projection(
    input_tokens: int,
    output_tokens: int,
    tokens_per_day: list[int] | None = None,
) -> str:
    """Project daily and monthly cost for both models at target token volumes.

    Args:
        input_tokens: Representative input tokens per request.
        output_tokens: Representative output tokens per request.
        tokens_per_day: Target daily token volumes to project. Defaults to
            [1,000,000, 10,000,000].

    The input/output ratio is used to split each target volume before pricing
    with each model's public rate card.
    """
    targets = tokens_per_day or list(DEFAULT_TARGETS)
    return build_projection_report(
        CLAUDE_MODEL, DEEPSEEK_MODEL, int(input_tokens), int(output_tokens), targets
    )


def main() -> None:
    """Run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
