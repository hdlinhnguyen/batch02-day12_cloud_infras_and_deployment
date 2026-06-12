from __future__ import annotations

from typing import Any


def karpathy_guidelines(query: str = "") -> dict[str, Any]:
    """Return Karpathy-inspired coding guidelines or a short checklist.

    If `query` contains keywords like 'checklist' or 'principles' the tool will
    return structured guidance. This is a local knowledge tool (no network).
    """
    principles = [
        {
            "name": "Think Before Coding",
            "description": (
                "State assumptions explicitly, present multiple interpretations, "
                "push back when warranted, and stop when confused."
            ),
        },
        {
            "name": "Simplicity First",
            "description": (
                "Prefer the minimal code that solves the problem. Avoid unnecessary "
                "abstractions and features."
            ),
        },
        {
            "name": "Surgical Changes",
            "description": (
                "Make minimal, local edits related to the request. Don't refactor "
                "unrelated code. Remove only dead code you introduce."
            ),
        },
        {
            "name": "Goal-Driven Execution",
            "description": (
                "Define clear success criteria, write verifiable checks, and loop "
                "until they pass."
            ),
        },
    ]

    checklist = [
        "State assumptions and success criteria",
        "Prefer minimal, direct code to meet the goal",
        "Write a failing test or check reproducing the problem",
        "Make a single, surgical change and re-run checks",
        "Avoid unrelated refactors",
    ]

    if not query:
        return {"guidelines": principles, "checklist": checklist}

    q = query.lower()
    if "checklist" in q:
        return {"guidelines": None, "checklist": checklist}
    if "principle" in q or "principles" in q:
        return {"guidelines": principles, "checklist": None}

    # default: return both but filter by keyword if present
    filtered = [p for p in principles if any(k in p["name"].lower() for k in q.split())]
    return {"guidelines": filtered or principles, "checklist": checklist}
