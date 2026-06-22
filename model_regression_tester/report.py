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
    g = ev.get("gpt", {})
    rows = [
        f"| Score (1–10) | {label_a} | {label_b} |",
        "| --- | ---: | ---: |",
        f"| Accuracy | {c.get('accuracy', 0)} | {g.get('accuracy', 0)} |",
        f"| Clarity | {c.get('clarity', 0)} | {g.get('clarity', 0)} |",
        f"| Completeness | {c.get('completeness', 0)} | {g.get('completeness', 0)} |",
        f"| **Average** | **{c.get('average', 0)}** | **{g.get('average', 0)}** |",
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
    gpt_model: str,
    claude_in: int,
    claude_out: int,
    gpt_in: int,
    gpt_out: int,
    targets: list[int],
) -> list[str]:
    rows = [
        f"| Tokens/day | {claude_model} (daily) | {claude_model} (monthly) | "
        f"{gpt_model} (daily) | {gpt_model} (monthly) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for target in targets:
        cp = project_cost(claude_model, claude_in, claude_out, target)
        gp = project_cost(gpt_model, gpt_in, gpt_out, target)
        rows.append(
            f"| {target:,} | {_money(cp['daily_cost'])} | {_money(cp['monthly_cost'])} | "
            f"{_money(gp['daily_cost'])} | {_money(gp['monthly_cost'])} |"
        )
    return rows


def build_report(
    run_results: list[dict],
    claude_model: str,
    gpt_model: str,
    projection_targets: list[int] | None = None,
) -> str:
    targets = projection_targets or DEFAULT_TARGETS
    label_a = f"Claude ({claude_model})"
    label_b = f"GPT ({gpt_model})"

    lines: list[str] = []
    lines.append("# Model Regression Test Report")
    lines.append("")
    lines.append(f"- **Model A:** {claude_model}")
    lines.append(f"- **Model B:** {gpt_model}")
    lines.append(f"- **Prompts tested:** {len(run_results)}")
    lines.append(f"- **Judge:** Claude meta-evaluator (anonymized A/B scoring)")
    lines.append("")

    totals = {
        "claude": {"cost": 0.0, "in": 0, "out": 0, "latency": 0.0, "avg": 0.0},
        "gpt": {"cost": 0.0, "in": 0, "out": 0, "latency": 0.0, "avg": 0.0},
    }
    wins = {"claude": 0, "gpt": 0, "tie": 0}

    for idx, item in enumerate(run_results, start=1):
        prompt = item["prompt"]
        claude: ModelResult = item["claude"]
        gpt: ModelResult = item["gpt"]
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
        if gpt.error:
            lines.append(f"`ERROR: {gpt.error}`")
        lines.append("")
        lines.append(_truncate(gpt.output))
        lines.append("")
        lines.append("### Metrics")
        lines.extend(_metrics_table(label_a, label_b, claude, gpt))
        lines.append("")
        lines.append("### Scores")
        lines.extend(_scores_table(label_a, label_b, ev))
        lines.append("")
        winner = ev.get("winner", "tie")
        winner_label = {"claude": label_a, "gpt": label_b, "tie": "Tie"}.get(winner, "Tie")
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
        totals["gpt"]["cost"] += gpt.cost_usd
        totals["gpt"]["in"] += gpt.input_tokens
        totals["gpt"]["out"] += gpt.output_tokens
        totals["gpt"]["latency"] += gpt.latency_ms
        totals["gpt"]["avg"] += ev.get("gpt", {}).get("average", 0.0)
        wins[winner] = wins.get(winner, 0) + 1

    n = max(len(run_results), 1)
    lines.append("---")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Aggregate | {label_a} | {label_b} |")
    lines.append("| --- | ---: | ---: |")
    lines.append(
        f"| Total cost (run) | {_money(totals['claude']['cost'])} | "
        f"{_money(totals['gpt']['cost'])} |"
    )
    lines.append(
        f"| Avg latency (ms) | {totals['claude']['latency'] / n:,.0f} | "
        f"{totals['gpt']['latency'] / n:,.0f} |"
    )
    lines.append(
        f"| Avg score | {totals['claude']['avg'] / n:.2f} | "
        f"{totals['gpt']['avg'] / n:.2f} |"
    )
    lines.append(
        f"| Total tokens | {totals['claude']['in'] + totals['claude']['out']:,} | "
        f"{totals['gpt']['in'] + totals['gpt']['out']:,} |"
    )
    lines.append("")
    lines.append(
        f"**Win tally:** {label_a}: {wins['claude']} · "
        f"{label_b}: {wins['gpt']} · Tie: {wins['tie']}"
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
            gpt_model,
            totals["claude"]["in"],
            totals["claude"]["out"],
            totals["gpt"]["in"],
            totals["gpt"]["out"],
            targets,
        )
    )
    lines.append("")
    return "\n".join(lines)


def build_projection_report(
    claude_model: str,
    gpt_model: str,
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
            gpt_model,
            input_tokens,
            output_tokens,
            input_tokens,
            output_tokens,
            targets,
        )
    )
    lines.append("")
    return "\n".join(lines)
