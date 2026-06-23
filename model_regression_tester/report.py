"""Markdown report rendering for comparison runs and cost projections."""

from __future__ import annotations

from .models import ModelResult
from .pricing import project_cost

DEFAULT_TARGETS = [1_000_000, 10_000_000]
OUTPUT_DISPLAY_LIMIT = 800


def _money(value: float) -> str:
    if abs(value) >= 1:
        return f"${value:,.2f}"
    return f"${value:,.6f}"


def _truncate(text: str, limit: int = OUTPUT_DISPLAY_LIMIT) -> str:
    text = text or "(no output)"
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + " …[truncated]"


def _scores_table(label_a: str, label_b: str, ev: dict) -> list[str]:
    c = ev.get("claude", {})
    d = ev.get("deepseek", {})
    rows = [
        f"| Score (1–10) | {label_a} | {label_b} |",
        "| --- | ---: | ---: |",
        f"| Accuracy | {c.get('accuracy', 0)} | {d.get('accuracy', 0)} |",
        f"| Clarity | {c.get('clarity', 0)} | {d.get('clarity', 0)} |",
        f"| Completeness | {c.get('completeness', 0)} | {d.get('completeness', 0)} |",
        f"| **Average** | **{c.get('average', 0)}** | **{d.get('average', 0)}** |",
    ]
    return rows


def _metrics_table(label_a: str, label_b: str, a: ModelResult, b: ModelResult) -> list[str]:
    return [
        f"| Metric | {label_a} | {label_b} |",
        "| --- | ---: | ---: |",
        f"| Latency (ms) | {a.latency_ms:,.0f} | {b.latency_ms:,.0f} |",
        f"| Input tokens | {a.input_tokens:,} | {b.input_tokens:,} |",
        f"| Output tokens | {a.output_tokens:,} | {b.output_tokens:,} |",
        f"| Cost | {_money(a.cost_usd)} | {_money(b.cost_usd)} |",
    ]


def build_projection_table(
    claude_model: str,
    deepseek_model: str,
    claude_in: int,
    claude_out: int,
    deepseek_in: int,
    deepseek_out: int,
    targets: list[int],
) -> list[str]:
    rows = [
        f"| Tokens/day | {claude_model} (daily) | {claude_model} (monthly) | "
        f"{deepseek_model} (daily) | {deepseek_model} (monthly) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for target in targets:
        cp = project_cost(claude_model, claude_in, claude_out, target)
        dp = project_cost(deepseek_model, deepseek_in, deepseek_out, target)
        rows.append(
            f"| {target:,} | {_money(cp['daily_cost'])} | {_money(cp['monthly_cost'])} | "
            f"{_money(dp['daily_cost'])} | {_money(dp['monthly_cost'])} |"
        )
    return rows


def build_report(
    run_results: list[dict],
    claude_model: str,
    deepseek_model: str,
    projection_targets: list[int] | None = None,
) -> str:
    targets = projection_targets or DEFAULT_TARGETS
    label_a = f"Claude ({claude_model})"
    label_b = f"DeepSeek ({deepseek_model})"

    lines: list[str] = []
    lines.append("# Model Regression Test Report")
    lines.append("")
    lines.append(f"- **Model A:** {claude_model}")
    lines.append(f"- **Model B:** {deepseek_model}")
    lines.append(f"- **Prompts tested:** {len(run_results)}")
    lines.append("- **Judge:** Claude meta-evaluator (anonymized A/B scoring)")
    lines.append("")

    totals = {
        "claude": {"cost": 0.0, "in": 0, "out": 0, "latency": 0.0, "avg": 0.0},
        "deepseek": {"cost": 0.0, "in": 0, "out": 0, "latency": 0.0, "avg": 0.0},
    }
    wins = {"claude": 0, "deepseek": 0, "tie": 0}

    for idx, item in enumerate(run_results, start=1):
        prompt = item["prompt"]
        claude: ModelResult = item["claude"]
        deepseek: ModelResult = item["deepseek"]
        ev: dict = item["evaluation"]

        lines.append("---")
        lines.append(f"## Prompt {idx}")
        lines.append("")
        lines.append(f"> {prompt}")
        lines.append("")
        lines.append(f"### {label_a}")
        if claude.error:
            lines.append(f"`ERROR: {claude.error}`")
        lines.append("")
        lines.append(_truncate(claude.output))
        lines.append("")
        lines.append(f"### {label_b}")
        if deepseek.error:
            lines.append(f"`ERROR: {deepseek.error}`")
        lines.append("")
        lines.append(_truncate(deepseek.output))
        lines.append("")
        lines.append("### Metrics")
        lines.extend(_metrics_table(label_a, label_b, claude, deepseek))
        lines.append("")
        lines.append("### Scores")
        lines.extend(_scores_table(label_a, label_b, ev))
        lines.append("")
        winner = ev.get("winner", "tie")
        winner_label = {"claude": label_a, "deepseek": label_b, "tie": "Tie"}.get(winner, "Tie")
        lines.append(f"**Winner:** {winner_label}")
        rationale = ev.get("rationale")
        if rationale:
            lines.append("")
            lines.append(f"_Rationale:_ {rationale}")
        lines.append("")

        totals["claude"]["cost"] += claude.cost_usd
        totals["claude"]["in"] += claude.input_tokens
        totals["claude"]["out"] += claude.output_tokens
        totals["claude"]["latency"] += claude.latency_ms
        totals["claude"]["avg"] += ev.get("claude", {}).get("average", 0.0)
        totals["deepseek"]["cost"] += deepseek.cost_usd
        totals["deepseek"]["in"] += deepseek.input_tokens
        totals["deepseek"]["out"] += deepseek.output_tokens
        totals["deepseek"]["latency"] += deepseek.latency_ms
        totals["deepseek"]["avg"] += ev.get("deepseek", {}).get("average", 0.0)
        wins[winner] = wins.get(winner, 0) + 1

    n = max(len(run_results), 1)
    lines.append("---")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Aggregate | {label_a} | {label_b} |")
    lines.append("| --- | ---: | ---: |")
    lines.append(
        f"| Total cost (run) | {_money(totals['claude']['cost'])} | "
        f"{_money(totals['deepseek']['cost'])} |"
    )
    lines.append(
        f"| Avg latency (ms) | {totals['claude']['latency'] / n:,.0f} | "
        f"{totals['deepseek']['latency'] / n:,.0f} |"
    )
    lines.append(
        f"| Avg score | {totals['claude']['avg'] / n:.2f} | "
        f"{totals['deepseek']['avg'] / n:.2f} |"
    )
    lines.append(
        f"| Total tokens | {totals['claude']['in'] + totals['claude']['out']:,} | "
        f"{totals['deepseek']['in'] + totals['deepseek']['out']:,} |"
    )
    lines.append("")
    lines.append(
        f"**Win tally:** {label_a}: {wins['claude']} · "
        f"{label_b}: {wins['deepseek']} · Tie: {wins['tie']}"
    )
    lines.append("")
    lines.append("## Projected Cost at Scale")
    lines.append("")
    lines.append(
        "_Projection splits the target daily token volume using each model's "
        "observed input/output ratio from this run; monthly = daily × 30._"
    )
    lines.append("")
    lines.extend(
        build_projection_table(
            claude_model,
            deepseek_model,
            totals["claude"]["in"],
            totals["claude"]["out"],
            totals["deepseek"]["in"],
            totals["deepseek"]["out"],
            targets,
        )
    )
    lines.append("")
    return "\n".join(lines)


def build_projection_report(
    claude_model: str,
    deepseek_model: str,
    input_tokens: int,
    output_tokens: int,
    targets: list[int],
) -> str:
    lines = ["# Cost Projection", ""]
    lines.append(
        f"Representative usage per request: **{input_tokens:,}** input tokens, "
        f"**{output_tokens:,}** output tokens."
    )
    lines.append("")
    lines.extend(
        build_projection_table(
            claude_model,
            deepseek_model,
            input_tokens,
            output_tokens,
            input_tokens,
            output_tokens,
            targets,
        )
    )
    lines.append("")
    return "\n".join(lines)
