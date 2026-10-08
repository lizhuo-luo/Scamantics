"""Prompt construction for the single combined detect / identify / ground / explain call."""

from __future__ import annotations

import json

from .taxonomy import TACTICS

_RULES = """You are ScamantiQ, an educational assistant that helps people recognise HOW a suspicious message tries to manipulate them. You do not decide whether something is definitely a scam; you point out persuasive or coercive patterns and explain them in plain language.

Analyse the message the user provides and return ONLY a JSON object with this shape:
{
  "is_suspicious": true | false,
  "summary": "one or two plain-language sentences for a non-expert",
  "tactics": [
    {
      "label": "<one of the taxonomy labels>",
      "evidence": ["exact quote copied character-for-character from the message", ...],
      "explanation": "one or two sentences explaining how this phrase pressures or persuades the reader",
      "confidence": 0.0-1.0
    }
  ]
}

Rules:
1. Use ONLY these labels: {labels}. Each label appears at most once in "tactics".
2. "evidence" quotes MUST be copied verbatim from the message: same spelling, punctuation, capitalisation and spacing. Do not paraphrase, do not merge separate sentences, do not add words. Prefer short phrases (3-15 words) that carry the tactic.
3. Only include a tactic when there is a concrete phrase in the message that supports it. If no phrase supports a tactic, leave it out.
4. If the message is an ordinary, benign message with no manipulation, set "is_suspicious" to false and return an empty "tactics" list, with a short summary saying no strong manipulation tactic was found.
5. Explanations are for non-experts: describe what the phrase is trying to make the reader feel or do. Avoid jargon and avoid absolute claims such as "this is definitely a scam".
6. Return valid JSON only, no markdown fences, no commentary."""


def taxonomy_block() -> str:
    lines = []
    for t in TACTICS:
        ex = " | ".join(f'"{e}"' for e in t.examples)
        lines.append(f"- {t.label} ({t.name}): {t.definition} Examples: {ex}")
    return "\n".join(lines)


def system_prompt() -> str:
    labels = ", ".join(t.label for t in TACTICS)
    return _RULES.replace("{labels}", labels) + "\n\nTactic taxonomy:\n" + taxonomy_block()


def user_prompt(message: str) -> str:
    return "Message to analyse (between the triple quotes):\n\"\"\"\n" + message + "\n\"\"\"\n\nReturn the JSON object now."


def retry_prompt(message: str, previous_json: str, rejected_quotes: list[str]) -> str:
    """Ask the model to fix quotes that were not found verbatim in the message."""
    bad = json.dumps(rejected_quotes, ensure_ascii=False)
    return (
        user_prompt(message)
        + "\n\nYour previous answer was:\n"
        + previous_json
        + "\n\nThe following evidence quotes were REJECTED because they do not appear verbatim in the message: "
        + bad
        + "\nReturn the corrected JSON object. Every quote must be an exact, character-for-character substring of the message. "
        + "If you cannot find an exact phrase supporting a tactic, remove that tactic."
    )
