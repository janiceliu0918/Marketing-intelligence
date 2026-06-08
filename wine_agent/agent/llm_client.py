"""Provider-agnostic LLM client adapter.

Normalises Anthropic and Groq APIs into a single interface so the rest of
the codebase never imports either SDK directly.

Normalised response object
--------------------------
LLMResponse
  .text          str            Final assistant text (may be "" if tool_calls present)
  .tool_calls    list[ToolCall] Populated when the model wants to call tools
  .stop_reason   str            "end_turn" | "tool_use"

ToolCall
  .id    str   Unique call ID (needed when feeding results back)
  .name  str   Tool name
  .input dict  Parsed arguments
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from wine_agent.config.settings import config

logger = logging.getLogger(__name__)


# ── Normalised types ──────────────────────────────────────────────────────────

@dataclass
class ToolCall:
    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    stop_reason: str = "end_turn"

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.tool_calls)


# ── Tool definition converters ────────────────────────────────────────────────

def _to_groq_tools(anthropic_tools: list[dict]) -> list[dict]:
    """Convert Anthropic tool schema → OpenAI/Groq function-calling format."""
    converted = []
    for t in anthropic_tools:
        converted.append({
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("input_schema", {"type": "object", "properties": {}}),
            },
        })
    return converted


# ── Provider clients ──────────────────────────────────────────────────────────

class _AnthropicClient:
    def __init__(self) -> None:
        import anthropic
        self._client = anthropic.Anthropic(api_key=config.anthropic_api_key)

    def chat(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> LLMResponse:
        response = self._client.messages.create(
            model=config.claude_model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )

        text = ""
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))

        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop)

    def append_assistant_turn(self, messages: list[dict], response: LLMResponse, raw_response: Any) -> None:
        """Append the raw Anthropic response object as the assistant turn."""
        messages.append({"role": "assistant", "content": raw_response.content})

    def append_tool_results(self, messages: list[dict], tool_calls: list[ToolCall], results: list[str]) -> None:
        blocks = [
            {"type": "tool_result", "tool_use_id": tc.id, "content": result}
            for tc, result in zip(tool_calls, results)
        ]
        messages.append({"role": "user", "content": blocks})

    # Store raw response for Anthropic's stateful message building
    _last_raw: Any = None

    def chat_raw(self, system, messages, tools, max_tokens=4096):
        response = self._client.messages.create(
            model=config.claude_model,
            max_tokens=max_tokens,
            system=system,
            tools=tools,
            messages=messages,
        )
        self._last_raw = response
        text = ""
        tool_calls: list[ToolCall] = []
        for block in response.content:
            if block.type == "text":
                text = block.text
            elif block.type == "tool_use":
                tool_calls.append(ToolCall(id=block.id, name=block.name, input=block.input))
        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop), response


class _GroqClient:
    def __init__(self) -> None:
        from groq import Groq
        self._client = Groq(api_key=config.groq_api_key)

    def chat_raw(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
        max_tokens: int = 4096,
    ) -> tuple[LLMResponse, Any]:
        groq_messages = [{"role": "system", "content": system}] + messages
        groq_tools = _to_groq_tools(tools) if tools else None

        kwargs: dict = {
            "model": config.groq_model,
            "messages": groq_messages,
            "max_tokens": max_tokens,
        }
        if groq_tools:
            kwargs["tools"] = groq_tools
            kwargs["tool_choice"] = "auto"

        response = self._client.chat.completions.create(**kwargs)
        msg = response.choices[0].message
        finish = response.choices[0].finish_reason

        text = msg.content or ""
        tool_calls: list[ToolCall] = []

        if finish == "tool_calls" and msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {}
                tool_calls.append(ToolCall(id=tc.id, name=tc.function.name, input=args))

        stop = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(text=text, tool_calls=tool_calls, stop_reason=stop), response

    def append_assistant_turn(self, messages: list[dict], response: LLMResponse, raw_response: Any) -> None:
        msg = raw_response.choices[0].message
        assistant_msg: dict = {"role": "assistant", "content": msg.content or ""}
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_msg)

    def append_tool_results(self, messages: list[dict], tool_calls: list[ToolCall], results: list[str]) -> None:
        for tc, result in zip(tool_calls, results):
            messages.append({"role": "tool", "tool_call_id": tc.id, "content": result})


# ── Simple text completion (no tools) ────────────────────────────────────────

def simple_completion(prompt: str, system: str = "", max_tokens: int = 512) -> str:
    """Single-turn text completion — used by the winery scraper."""
    messages = [{"role": "user", "content": prompt}]

    if config.llm_provider == "groq":
        from groq import Groq
        client = Groq(api_key=config.groq_api_key)
        groq_messages = ([{"role": "system", "content": system}] if system else []) + messages
        resp = client.chat.completions.create(
            model=config.groq_model,
            messages=groq_messages,
            max_tokens=max_tokens,
        )
        return resp.choices[0].message.content or ""
    else:
        import anthropic
        client = anthropic.Anthropic(api_key=config.anthropic_api_key)
        kwargs: dict = {"model": config.claude_model, "max_tokens": max_tokens, "messages": messages}
        if system:
            kwargs["system"] = system
        resp = client.messages.create(**kwargs)
        return resp.content[0].text


# ── Factory ───────────────────────────────────────────────────────────────────

def get_llm_client() -> _GroqClient | _AnthropicClient:
    if config.llm_provider == "groq":
        if not config.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is not set.\n"
                "Register free at https://console.groq.com and add it to your .env file."
            )
        logger.info("Using Groq provider (model: %s)", config.groq_model)
        return _GroqClient()
    else:
        if not config.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is not set.\n"
                "Set LLM_PROVIDER=groq in .env to use the free Groq tier instead."
            )
        logger.info("Using Anthropic provider (model: %s)", config.claude_model)
        return _AnthropicClient()
