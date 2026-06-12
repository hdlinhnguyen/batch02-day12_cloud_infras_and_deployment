from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from providers.base import Provider, ToolCall
from tools import TOOL_FUNCTIONS, call_tool_safe


@dataclass
class AgentRun:
    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)


class ResearchAgent:
    def __init__(
        self,
        provider: Provider,
        *,
        system_prompt: str,
        tools: list[dict[str, Any]] | None = None,
        model: str | None = None,
    ) -> None:
        self.provider = provider
        self.system_prompt = system_prompt
        self.tools = tools or []
        self.model = model

    def run(self, user_messages: list[dict[str, str]], *, tool_choice: Any | None = None) -> AgentRun:
        messages = [{"role": "system", "content": self.system_prompt}, *user_messages]
        response = self.provider.complete(
            messages,
            self.tools,
            model=self.model,
            temperature=0.0,
            tool_choice=tool_choice,
        )
        results: list[dict[str, Any]] = []
        for call in response.tool_calls:
            # Use safe caller with validation to reduce wrong-arg and missing-param failures
            res = call_tool_safe(call.name, call.args or {})
            results.append(res)
        return AgentRun(text=response.text, tool_calls=response.tool_calls, tool_results=results)
