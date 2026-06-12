from __future__ import annotations

import re
from typing import Any


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.MULTILINE)


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    # Common env assignments
    ("env_assignment", _compile(r"(?P<key>[A-Z0-9_]{6,})\s*=\s*(?P<secret>[^\s#\"']{8,})")),
    # Provider keys from this lab
    ("openrouter_key", _compile(r"\b(sk-or-v1-[A-Za-z0-9]{20,})\b")),
    ("openai_key", _compile(r"\b(sk-(?:proj-)?[A-Za-z0-9]{20,})\b")),
    ("anthropic_key", _compile(r"\b(sk-ant-[A-Za-z0-9_-]{20,})\b")),
    ("gemini_key", _compile(r"\b(AIza[0-9A-Za-z_-]{20,})\b")),
    ("tavily_key", _compile(r"\b(tvly-[0-9A-Za-z_-]{10,})\b")),
    ("firecrawl_key", _compile(r"\b(fc-[0-9A-Za-z_-]{10,})\b")),
    ("rapidapi_key", _compile(r"\b([0-9a-f]{32,})\b")),
    # Telegram bot token: 123456789:AA...
    ("telegram_bot_token", _compile(r"\b(\d{6,}:[0-9A-Za-z_-]{20,})\b")),
    # Generic long tokens (avoid matching normal text too aggressively)
    ("generic_token", _compile(r"\b([A-Za-z0-9_-]{32,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,})\b")),  # JWT-ish
]


def _redact_value(value: str) -> str:
    value = value or ""
    if len(value) <= 8:
        return "[REDACTED]"
    return f"{value[:3]}…{value[-3:]}"


def _redact_match(kind: str, match: re.Match[str]) -> str:
    if kind == "env_assignment":
        key = match.group("key")
        secret = match.group("secret")
        return f"{key}={_redact_value(secret)}"
    # other patterns capture whole secret in group 1
    secret = match.group(1) if match.groups() else match.group(0)
    return _redact_value(secret)


def security_scan(text: str = "", *, redact: bool = True, max_findings: int = 25) -> dict[str, Any]:
    """
    Scan text for likely secrets (API keys/tokens) and optionally redact them.

    Returns:
      - contains_secrets: bool
      - redacted_text: str (if redact=True)
      - findings: list of {kind, preview, start, end}
    """
    raw = text or ""
    max_findings = max(1, min(int(max_findings or 25), 100))

    findings: list[dict[str, Any]] = []
    redacted = raw

    # Apply redaction progressively so multiple matches don't leak.
    for kind, pattern in _PATTERNS:
        for m in list(pattern.finditer(redacted)):
            if len(findings) >= max_findings:
                break
            start, end = m.span()
            replacement = _redact_match(kind, m)
            preview = replacement if replacement != "[REDACTED]" else _redact_value(m.group(0))
            findings.append({"kind": kind, "preview": preview, "start": start, "end": end})
        if redact:
            redacted = pattern.sub(lambda m: _redact_match(kind, m), redacted)

    return {
        "tool": "security_scan",
        "contains_secrets": len(findings) > 0,
        "findings": findings,
        "redacted_text": redacted if redact else "",
        "note": "Heuristic scanner; review findings before sharing logs/screenshots.",
    }

