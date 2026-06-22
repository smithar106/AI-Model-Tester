"""Model Regression Tester — an MCP server for comparing LLM outputs.

Runs prompts against two models side-by-side, scores them with a Claude
meta-evaluator, and reports latency, token usage, cost, and cost projections.
"""

__version__ = "0.1.0"
