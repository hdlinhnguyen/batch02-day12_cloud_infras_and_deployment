from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

# Folder names are intentionally vague to match the tool names students see.
# The imported function names are the underlying implementations (unchanged).
from .clarify.tool import ask_user
from .papers.tool import arxiv_search
from .paper_text.tool import get_arxiv_paper_text
from .timeline.tool import get_user_tweets
from .fetch.tool import read_url
from .format.tool import render_digest
from .policy.tool import search_company_policy
from .social_search.tool import search_tweets
from .send.tool import send_telegram
from .lookup.tool import web_search
from .troll_guard.tool import troll_guard
from .security.tool import security_scan
from .karpathy_guidelines.tool import karpathy_guidelines


# NOTE (starter_v0): tool names here are intentionally vague. These keys are the
# names the model sees AND the names data/eval_base.json + data/eval_research_extension.json
# match against. If a team renames a tool, it MUST stay in sync across ALL of:
#   artifacts/tools.yaml  ->  this dict  ->  data/eval_base.json + data/eval_research_extension.json
# Otherwise the eval raises "not declared in tools.yaml" or scores every call as a name mismatch.
TOOL_FUNCTIONS = {
    "clarify": ask_user,
    "timeline": get_user_tweets,
    "social_search": search_tweets,
    "lookup": web_search,
    "fetch": read_url,
    "format": render_digest,
    "send": send_telegram,
    "policy": search_company_policy,
    "papers": arxiv_search,
    "paper_text": get_arxiv_paper_text,
    "troll_guard": troll_guard,
    "security_scan": security_scan,
    "karpathy_guidelines": karpathy_guidelines,
}


def load_tool_declarations(path: Path) -> list[dict[str, Any]]:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["tools"]


def to_openai_tools(declarations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{
        "type": "function",
        "function": {
            "name": item["name"],
            "description": item.get("description", ""),
            "parameters": item.get("parameters", {"type": "object", "properties": {}}),
        },
    } for item in declarations]


# Validation + safe call helpers
_DECL_CACHE: dict[str, dict[str, Any]] | None = None


def _load_declarations() -> list[dict[str, Any]]:
    global _DECL_CACHE
    if _DECL_CACHE is not None:
        # return cached as list
        return list(_DECL_CACHE.values())
    path = Path(__file__).resolve().parents[1] / "artifacts" / "tools.yaml"
    declarations = load_tool_declarations(path)
    _DECL_CACHE = {item["name"]: item for item in declarations}
    return declarations


def validate_and_normalize_args(tool_name: str, args: dict[str, Any]) -> tuple[bool, dict[str, Any], str | None]:
    """Validate required params and try light normalization.

    Returns (ok, normalized_args, error_message).
    """
    global _DECL_CACHE
    if _DECL_CACHE is None:
        _load_declarations()
    decl = _DECL_CACHE.get(tool_name) if _DECL_CACHE else None
    if not decl:
        return False, args, f"tool {tool_name!r} not declared"
    params = decl.get("parameters", {}) or {}
    required = set(params.get("required", []))
    props = params.get("properties", {})
    normalized: dict[str, Any] = {}
    # check required
    missing = [name for name in required if name not in args or args.get(name) is None or args.get(name) == ""]
    if missing:
        return False, args, f"missing required params: {', '.join(missing)}"
    # basic type normalization
    for key, value in (args or {}).items():
        if key not in props:
            normalized[key] = value
            continue
        schema = props[key]
        typ = schema.get("type")
        if typ == "integer":
            try:
                normalized[key] = int(value)
            except Exception:
                normalized[key] = value
        elif typ == "boolean":
            if isinstance(value, bool):
                normalized[key] = value
            else:
                sval = str(value).lower()
                normalized[key] = sval in ("1", "true", "yes", "y")
        else:
            # string or other
            normalized[key] = value
    return True, normalized, None


def call_tool_safe(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Validate args against tool declaration, call implementation, and return structured result."""
    ok, normalized, err = validate_and_normalize_args(name, args or {})
    if not ok:
        return {"error": "validation_error", "message": err}
    func = TOOL_FUNCTIONS.get(name)
    if not func:
        return {"error": "unknown_tool"}
    try:
        result = func(**normalized)
    except Exception as exc:
        return {"error": type(exc).__name__, "message": str(exc)}
    return {"tool": name, "args": normalized, "result": result}

