from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import streamlit as st

from env_loader import load_lab_env
from providers import make_provider
from tools import load_tool_declarations, to_openai_tools
from versioning import build_artifact_version

# Reuse the same tool-loop logic as the CLI chat.
from chat import run_model_tool_loop, trim_history


ROOT = Path(__file__).parent
ARTIFACTS_DIR = ROOT / "artifacts"

load_lab_env(ROOT)


def _now_stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, default=str)


def main() -> None:
    st.set_page_config(page_title="Day04 Research Agent (Streamlit)", layout="wide")
    st.title("Day04 Research Agent — Streamlit Demo")
    st.markdown(
        """
<style>
/* Slightly tighter spacing + nicer code blocks in dark mode */
div[data-testid="stChatMessage"] { padding-top: 0.25rem; padding-bottom: 0.25rem; }
pre code { font-size: 0.85rem !important; }
/* Make expanders a bit more subtle */
details > summary { opacity: 0.9; }
</style>
""",
        unsafe_allow_html=True,
    )

    with st.sidebar:
        st.header("Run config")
        provider_name = st.selectbox("Provider", ["openrouter", "openai", "anthropic", "gemini"], index=3)
        version = st.text_input("Version label", value="v0")
        model = st.text_input("Model override (optional)", value="")
        history_window = st.number_input("History window (user/assistant pairs)", min_value=0, max_value=20, value=5, step=1)
        max_tool_rounds = st.number_input("Max tool rounds", min_value=1, max_value=8, value=4, step=1)

        st.divider()
        st.caption("Artifacts")
        system_prompt_path = st.text_input("system_prompt", value=str(ARTIFACTS_DIR / "system_prompt.md"))
        tools_path = st.text_input("tools.yaml", value=str(ARTIFACTS_DIR / "tools.yaml"))

        if st.button("Reset chat", type="secondary", use_container_width=True):
            st.session_state.pop("history", None)
            st.session_state.pop("turns", None)
            st.rerun()

    if "history" not in st.session_state:
        st.session_state.history: list[dict[str, str]] = []
    if "turns" not in st.session_state:
        st.session_state.turns: list[dict[str, Any]] = []

    # Load artifacts
    prompt_text = Path(system_prompt_path).read_text(encoding="utf-8")
    tool_declarations = load_tool_declarations(Path(tools_path))
    openai_tools = to_openai_tools(tool_declarations)

    provider = make_provider(provider_name)
    selected_model = (model.strip() or getattr(provider, "default_model", None))
    artifact_version = build_artifact_version(version, Path(system_prompt_path), Path(tools_path))

    st.caption(
        f"artifact_version=`{artifact_version.artifact_version}` · provider=`{provider_name}` · model=`{selected_model}`"
    )

    # Render prior turns
    for turn in st.session_state.turns:
        with st.chat_message("user"):
            st.markdown(turn["user"])
        with st.chat_message("assistant"):
            st.markdown(turn.get("assistant_text") or "")
            with st.expander("Details (tool rounds / tool events)"):
                st.code(_json({"status": turn.get("status"), "rounds": turn.get("rounds"), "tool_events": turn.get("tool_events")}))

    user_text = st.chat_input("Nhập câu hỏi research…")
    if not user_text:
        return

    with st.chat_message("user"):
        st.markdown(user_text)

    messages = [
        {"role": "system", "content": prompt_text},
        *trim_history(st.session_state.history, int(history_window)),
        {"role": "user", "content": user_text},
    ]

    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = run_model_tool_loop(
                provider=provider,
                messages=messages,
                tools=openai_tools,
                model=(model.strip() or None),
                max_tool_rounds=int(max_tool_rounds),
            )
        assistant_text = result.get("assistant_text") or ""
        st.markdown(assistant_text)

        with st.expander("Details (tool rounds / tool events)"):
            st.code(_json(result))

    # Update session history
    st.session_state.history.append({"role": "user", "content": user_text})
    st.session_state.history.append({"role": "assistant", "content": assistant_text})

    # Save a turn record (in-memory; Streamlit reruns)
    st.session_state.turns.append({
        "at": _now_stamp(),
        "user": user_text,
        **result,
    })


if __name__ == "__main__":
    main()

