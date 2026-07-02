"""OpsBrief — LLM service using Anthropic Claude."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from anthropic import AsyncAnthropic

from ..config import settings

logger = logging.getLogger(__name__)

client = AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY) if settings.ANTHROPIC_API_KEY else None

_MAX_PROMPT_INPUT_LEN = 4000


def _sanitize_for_llm(text: str) -> str:
    """Sanitize external text before interpolation into LLM prompts."""
    if not isinstance(text, str):
        text = str(text)
    # Remove null bytes to avoid truncation/termination issues
    text = text.replace("\x00", "")
    # Hard length cap to prevent prompt injection via extremely long strings
    if len(text) > _MAX_PROMPT_INPUT_LEN:
        text = text[:_MAX_PROMPT_INPUT_LEN]
    return text


async def query_with_context(message: str, user_id: str, system_prompt: str | None = None) -> str:
    """Send a message to Claude and return the response."""
    if not client:
        return "AI is not configured. Please set ANTHROPIC_API_KEY in your environment."

    if not system_prompt:
        system_prompt = (
            "You are OpsBrief, a helpful IT infrastructure and security assistant. "
            "You provide concise, accurate answers to technical questions about "
            "networking, cybersecurity, cloud infrastructure, and system administration. "
            "When discussing vulnerabilities, cite the CVE ID if known. "
            "Keep answers under 3 paragraphs unless the user asks for detail."
        )

    safe_message = _sanitize_for_llm(message)
    delimited_message = f"<<<USER_INPUT>>>{safe_message}<<<END_USER_INPUT>>>"

    try:
        resp = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            temperature=0.7,
            system=system_prompt,
            messages=[
                {"role": "user", "content": delimited_message},
            ],
        )
        content = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                content += block.text
        return content.strip()
    except Exception as e:
        logger.error(f"Claude call failed: {e}")
        return "Sorry, the AI service is temporarily unavailable. Please try again later."


async def summarize_intel_items(items: list[dict]) -> list[dict]:
    """Summarize a batch of raw intel items into briefing headlines.

    Returns a list of dicts with 'headline' and 'summary' keys.
    """
    if not client or not items:
        return [{"headline": i["title"], "summary": i["summary"][:200]} for i in items]

    # Batch items into a single prompt for efficiency
    batch_text = "\n\n".join(
        f"ITEM {idx+1}:\nTitle: {_sanitize_for_llm(i['title'])}\nSummary: {_sanitize_for_llm(i['summary'])[:500]}\nSeverity: {_sanitize_for_llm(i.get('severity','unknown'))}"
        for idx, i in enumerate(items)
    )

    prompt = (
        "You are an editor for a cybersecurity briefing. For each item below, "
        "write a punchy headline (max 10 words) and a 2-sentence summary. "
        "Return ONLY a JSON array of objects with 'headline' and 'summary' fields. "
        "No markdown, no commentary, just the JSON array.\n\n"
        f"{batch_text}\n\n"
        "Output:"
    )

    try:
        resp = await client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}],
        )
        content = ""
        for block in resp.content:
            if getattr(block, "type", None) == "text":
                content += block.text
        # Clean up markdown fences if present
        content = content.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        summaries = json.loads(content)
        if not isinstance(summaries, list) or len(summaries) != len(items):
            raise ValueError("Summaries count mismatch")
        return [
            {
                "headline": s.get("headline", items[i]["title"]),
                "summary": s.get("summary", items[i]["summary"][:200]),
            }
            for i, s in enumerate(summaries)
        ]
    except Exception as e:
        logger.error(f"Summarization failed: {e}")
        # Fallback: return truncated originals
        return [{"headline": i["title"], "summary": i["summary"][:200]} for i in items]
