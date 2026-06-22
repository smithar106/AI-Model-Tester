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


def _with_average(scores: dict[str, object]) -> dict[str, object]:
    vals = [scores.get("accuracy", 0), scores.get("clarity", 0), scores.get("completeness", 0)]
    nums = [float(v) for v in vals if isinstance(v, (int, float))]
    avg = round(sum(nums) / len(nums), 2) if nums else 0.0
    return {
        "accuracy": scores.get("accuracy", 0),
        "clarity": scores.get("clarity", 0),
        "completeness": scores.get("completeness", 0),
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
    gpt_result: ModelResult,
) -> dict[str, object]:
    """Score the two outputs. Responses are anonymized (A/B) to reduce bias."""
    user_msg = (
        f"PROMPT:\n{prompt}\n\n"
        f"RESPONSE A:\n{claude_result.output or '(no output)'}\n\n"
        f"RESPONSE B:\n{gpt_result.output or '(no output)'}\n"
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
            "gpt": _empty_scores("evaluator error"),
            "winner": "tie",
            "rationale": f"Evaluation failed: {exc}",
            "error": str(exc),
        }

    data = _extract_json(raw)
    if not data:
        return {
            "claude": _empty_scores("could not parse evaluator output"),
            "gpt": _empty_scores("could not parse evaluator output"),
            "winner": "tie",
            "rationale": raw.strip()[:500],
            "error": "parse_error",
        }

    winner_letter = str(data.get("winner", "tie")).strip().upper()
    winner = {"A": "claude", "B": "gpt"}.get(winner_letter, "tie")

    return {
        "claude": _with_average(data.get("A", {})),
        "gpt": _with_average(data.get("B", {})),
        "winner": winner,
        "rationale": data.get("rationale", ""),
        "error": None,
    }
