"""Claude-as-judge meta-evaluation of two model outputs."""

from __future__ import annotations

import json
import re

from .models import ModelResult

EVAL_MAX_TOKENS = 700

RUBRIC = (
    "You are an impartial evaluator comparing two AI assistant responses to the "
    "same prompt. Score each response from 1 (poor) to 10 (excellent) on three "
    "criteria:\n"
    "- accuracy: factual / logical correctness\n"
    "- clarity: how clear, well-structured, and easy to follow it is\n"
    "- completeness: how fully it addresses the prompt\n\n"
    "Respond with ONLY a JSON object, no prose, in exactly this shape:\n"
    "{\n"
    '  "A": {"accuracy": int, "clarity": int, "completeness": int, "notes": str},\n'
    '  "B": {"accuracy": int, "clarity": int, "completeness": int, "notes": str},\n'
    '  "winner": "A" | "B" | "tie",\n'
    '  "rationale": str\n'
    "}\n"
)


def _empty_scores(notes: str) -> dict[str, object]:
    return {"accuracy": 0, "clarity": 0, "completeness": 0, "average": 0.0, "notes": notes}


def _coerce_score(value: object) -> int:
    try:
        return int(round(float(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 0


def _with_average(scores: dict[str, object]) -> dict[str, object]:
    accuracy = _coerce_score(scores.get("accuracy"))
    clarity = _coerce_score(scores.get("clarity"))
    completeness = _coerce_score(scores.get("completeness"))
    avg = round((accuracy + clarity + completeness) / 3, 2)
    return {
        "accuracy": accuracy,
        "clarity": clarity,
        "completeness": completeness,
        "average": avg,
        "notes": scores.get("notes", ""),
    }


def _extract_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return None


async def evaluate_pair(
    client,
    model: str,
    prompt: str,
    claude_result: ModelResult,
    deepseek_result: ModelResult,
) -> dict[str, object]:
    """Score the two outputs. Responses are anonymized (A/B) to reduce bias."""
    if not claude_result.output and not deepseek_result.output:
        return {
            "claude": _empty_scores("no output to evaluate"),
            "deepseek": _empty_scores("no output to evaluate"),
            "winner": "tie",
            "rationale": "Both models returned no output; skipped evaluation.",
            "error": None,
        }

    user_msg = (
        f"PROMPT:\n{prompt}\n\n"
        f"RESPONSE A:\n{claude_result.output or '(no output)'}\n\n"
        f"RESPONSE B:\n{deepseek_result.output or '(no output)'}\n"
    )

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=EVAL_MAX_TOKENS,
            system=RUBRIC,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
    except Exception as exc:  # noqa: BLE001
        return {
            "claude": _empty_scores("evaluator error"),
            "deepseek": _empty_scores("evaluator error"),
            "winner": "tie",
            "rationale": f"Evaluation failed: {exc}",
            "error": str(exc),
        }

    data = _extract_json(raw)
    if not data:
        return {
            "claude": _empty_scores("could not parse evaluator output"),
            "deepseek": _empty_scores("could not parse evaluator output"),
            "winner": "tie",
            "rationale": raw.strip()[:500],
            "error": "parse_error",
        }

    raw_winner = str(data.get("winner", "tie")).strip().lower()
    if raw_winner in ("a", "model a", "response a", "claude"):
        winner = "claude"
    elif raw_winner in ("b", "model b", "response b", "deepseek"):
        winner = "deepseek"
    else:
        winner = "tie"

    return {
        "claude": _with_average(data.get("A", {})),
        "deepseek": _with_average(data.get("B", {})),
        "winner": winner,
        "rationale": data.get("rationale", ""),
        "error": None,
    }
