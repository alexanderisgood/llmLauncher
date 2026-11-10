"""Shared recognition of Pi's native conversation-summary requests."""
from __future__ import annotations

from typing import Any


PI_SUMMARIZATION_SYSTEM_PROMPT = (
    "You are a context summarization assistant. Your task is to read a conversation "
    "between a user and an AI assistant, then produce a structured summary following "
    "the exact format specified.\n\nDo NOT continue the conversation. Do NOT respond "
    "to any questions in the conversation. ONLY output the structured summary."
)


def is_pi_summary(messages: Any) -> bool:
    first = messages[0] if isinstance(messages, list) and messages else None
    return bool(isinstance(first, dict) and first.get("role") == "system"
                and first.get("content") == PI_SUMMARIZATION_SYSTEM_PROMPT)
