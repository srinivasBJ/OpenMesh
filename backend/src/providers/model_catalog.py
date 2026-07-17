"""
Model catalog ranking — turns raw provider model lists (OpenRouter returns
hundreds) into a curated, categorized view so users aren't overwhelmed.

Ranking is heuristic, ordered by: family capability/popularity, provider
reputation, then context length. Categories: coding | reasoning | fast |
general. The raw list is always available ("Show all models"); curation
only changes the default view, never what can be selected.
"""

from __future__ import annotations

import re
from typing import Any

# (regex on model id, category, base score) — first match wins.
# Scores encode popularity + capability + provider reputation.
_RULES: tuple[tuple[str, str, int], ...] = (
    (r"claude.*opus", "reasoning", 96),
    (r"claude.*(fable|mythos)", "reasoning", 95),
    (r"claude.*sonnet", "coding", 94),
    (r"claude.*haiku", "fast", 86),
    (r"gpt-5.*(mini|nano)", "fast", 85),
    (r"gpt-5", "reasoning", 93),
    (r"\bo[134](-|$|\b)", "reasoning", 90),
    (r"gpt-4\.1", "coding", 88),
    (r"gpt-4o-mini", "fast", 84),
    (r"gpt-4o", "coding", 86),
    (r"deepseek.*(r1|reason)", "reasoning", 88),
    (r"deepseek.*(coder|chat|v3)", "coding", 86),
    (r"qwen.*coder", "coding", 85),
    (r"gemini.*(think|pro)", "reasoning", 87),
    (r"gemini.*flash", "fast", 84),
    (r"grok", "reasoning", 80),
    (r"mistral.*(large|medium)", "coding", 78),
    (r"llama.*(70b|405b)", "general", 76),
    (r"qwen", "general", 74),
    (r"mistral|mixtral", "general", 72),
    (r"llama", "general", 70),
)

_EXCLUDE = re.compile(r"embed|whisper|tts|audio|vision-only|moderation|guard")


def classify_model(model_id: str) -> tuple[str, int]:
    """Return (category, score) for a model id."""
    lowered = model_id.lower()
    for pattern, category, score in _RULES:
        if re.search(pattern, lowered):
            return category, score
    return "general", 40


def rank_models(models: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Annotate models with category/score and sort best-first."""
    ranked = []
    for entry in models:
        model_id = str(entry.get("model") or "")
        if not model_id or _EXCLUDE.search(model_id.lower()):
            continue
        category, score = classify_model(model_id)
        metadata = entry.get("metadata") or {}
        context_length = metadata.get("context_length") or 0
        try:
            context_length = int(context_length)
        except (TypeError, ValueError):
            context_length = 0
        ranked.append(
            {
                **entry,
                "category": category,
                "score": score,
                "context_length": context_length,
            }
        )
    ranked.sort(key=lambda m: (-m["score"], -m["context_length"], m["model"]))
    return ranked


def curate_models(
    models: list[dict[str, Any]], limit: int = 25
) -> list[dict[str, Any]]:
    """Top recommended models across categories (default view)."""
    ranked = rank_models(models)
    # Guarantee category diversity: take the best of each category first.
    curated: list[dict[str, Any]] = []
    seen: set[str] = set()
    for category in ("coding", "reasoning", "fast"):
        for entry in ranked:
            if entry["category"] == category and entry["model"] not in seen:
                curated.append(entry)
                seen.add(entry["model"])
                break
    for entry in ranked:
        if len(curated) >= limit:
            break
        if entry["model"] not in seen:
            curated.append(entry)
            seen.add(entry["model"])
    curated.sort(key=lambda m: (-m["score"], -m["context_length"], m["model"]))
    return curated[:limit]
