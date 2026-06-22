"""Prompt loading: hardcoded samples or a user-provided text file."""

from __future__ import annotations

from pathlib import Path

SAMPLE_PROMPTS: list[str] = [
    "Explain the difference between a process and a thread to a junior developer.",
    "Write a Python function that returns the nth Fibonacci number using memoization.",
    "Summarize the plot of Romeo and Juliet in exactly three sentences.",
    "A train leaves Chicago at 60 mph and another leaves NYC at 80 mph. "
    "If the cities are 790 miles apart and they travel toward each other, "
    "how long until they meet? Show your work.",
    "Rewrite this sentence to be more concise: "
    "'Due to the fact that the meeting was cancelled, we were not able to "
    "discuss the items that were on the agenda.'",
    "List three trade-offs of using microservices instead of a monolith.",
]


def load_prompts(
    prompts_file: str | None = None,
    prompts: list[str] | None = None,
) -> list[str]:
    """Resolve the prompt set.

    Priority: explicit ``prompts`` list > ``prompts_file`` > built-in samples.
    In a prompt file, blank lines and lines starting with ``#`` are ignored.
    """
    if prompts:
        cleaned = [p.strip() for p in prompts if p and p.strip()]
        if cleaned:
            return cleaned

    if prompts_file:
        path = Path(prompts_file).expanduser()
        if not path.is_file():
            raise FileNotFoundError(f"Prompt file not found: {path}")
        lines = path.read_text(encoding="utf-8").splitlines()
        cleaned = [
            line.strip()
            for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        if not cleaned:
            raise ValueError(f"No usable prompts found in {path}")
        return cleaned

    return list(SAMPLE_PROMPTS)
