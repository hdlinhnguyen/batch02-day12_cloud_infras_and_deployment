from __future__ import annotations

import re
from typing import Any


_PROFANITY_RE = re.compile(
    r"\b("
    r"dm|dit|địt|djt|d\*t|lon|lồn|cặc|cac|cc|vcl|vl|đm|đmm|đkm|đcm|"
    r"fuck|shit|bitch|asshole|cunt|retard|kys"
    r")\b",
    re.IGNORECASE,
)

_SPAM_RE = re.compile(r"(https?://\S+){3,}|\b(?:free\s+money|click\s+here|subscribe)\b", re.IGNORECASE)
_GIBBERISH_RE = re.compile(r"^[^A-Za-zÀ-ỹ0-9]{0,3}([A-Za-zÀ-ỹ0-9]{1,2}[^A-Za-zÀ-ỹ0-9]{0,3}){0,5}$")
_ALL_CAPS_RE = re.compile(r"^[^a-zà-ỹ]*[A-ZÀ-Ỹ]{12,}[^a-zà-ỹ]*$")


def _norm(text: str) -> str:
    return " ".join((text or "").strip().split())


def _signals(text: str) -> dict[str, bool]:
    t = text or ""
    return {
        "profanity_or_hate": bool(_PROFANITY_RE.search(t)),
        "spam": bool(_SPAM_RE.search(t)),
        "gibberish_or_too_short": len(_norm(t)) < 3 or bool(_GIBBERISH_RE.match(_norm(t))),
        "shouting": bool(_ALL_CAPS_RE.match(_norm(t))),
        "impossible_request": any(
            phrase in (t.lower())
            for phrase in [
                "hack",
                "bẻ khóa",
                "crack",
                "ddos",
                "spam tin nhắn",
                "lừa đảo",
                "chiếm tài khoản",
            ]
        ),
    }


def _severity(sig: dict[str, bool]) -> str:
    if sig["impossible_request"]:
        return "high"
    if sig["profanity_or_hate"] or sig["spam"]:
        return "medium"
    if sig["gibberish_or_too_short"] or sig["shouting"]:
        return "low"
    return "none"


def troll_guard(text: str = "", *, mode: str = "polite") -> dict[str, Any]:
    """
    Detect low-quality / troll-ish prompts and suggest a safe, helpful response.

    mode:
      - polite: short, calm redirection
      - firm: set boundaries
      - playful: light tone without escalating
    """
    text = _norm(text)
    sig = _signals(text)
    severity = _severity(sig)
    is_trollish = severity != "none"

    if not is_trollish:
        return {
            "tool": "troll_guard",
            "is_trollish": False,
            "severity": "none",
            "signals": sig,
            "suggested_response": "",
        }

    if sig["impossible_request"]:
        suggested = "Mình không thể giúp với yêu cầu này. Nếu bạn muốn, hãy mô tả mục tiêu hợp pháp (ví dụ bảo mật, phòng thủ, học tập) để mình hỗ trợ theo hướng an toàn."
    elif sig["spam"]:
        suggested = "Mình không hỗ trợ spam. Nếu bạn cần viết nội dung hợp lệ (thông báo, email, post), nói rõ mục tiêu và đối tượng nhận để mình giúp soạn thảo."
    elif sig["profanity_or_hate"]:
        suggested = "Mình có thể giúp nếu bạn giữ trao đổi lịch sự. Bạn muốn mình hỗ trợ vấn đề gì cụ thể?"
    elif sig["gibberish_or_too_short"]:
        suggested = "Mình chưa hiểu yêu cầu. Bạn mô tả rõ hơn (bạn muốn tìm gì, liên quan ai/chủ đề nào, và cần kết quả dạng nào)?"
    else:
        suggested = "Mình sẵn sàng giúp, nhưng bạn cho mình biết bạn đang muốn làm gì cụ thể nhé."

    if mode == "firm":
        suggested = suggested.replace("Mình", "Tôi")
    elif mode == "playful" and severity in {"low", "medium"}:
        suggested = "Ok, mình bắt được vibe rồi — nhưng để mình giúp đúng ý, bạn nói rõ yêu cầu hơn nhé."

    return {
        "tool": "troll_guard",
        "is_trollish": True,
        "severity": severity,
        "signals": sig,
        "suggested_response": suggested,
    }

