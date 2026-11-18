"""Gemini provider, using the official google-genai SDK."""

import os

from google import genai
from google.genai import types

from agentproof.providers.base import (
    Message,
    ModelResponse,
    ToolCall,
    ToolSpec,
    Usage,
)

# Pinned on purpose: regression tests need the same model on every run.
DEFAULT_MODEL = "gemini-3.1-flash-lite"

# Overloaded or rate-limited requests are common on the free tier, so the SDK
# retries them with exponential backoff before giving up.
_RETRY = types.HttpRetryOptions(attempts=4, http_status_codes=[429, 500, 503, 504])
_TIMEOUT_MS = 60_000


class GeminiProvider:
    def __init__(
        self, model: str, api_key: str | None = None, temperature: float = 0.0
    ) -> None:
        self.model = model
        self.temperature = temperature
        self._client = genai.Client(
            api_key=api_key or os.environ.get("GEMINI_API_KEY"),
            http_options=types.HttpOptions(retry_options=_RETRY, timeout=_TIMEOUT_MS),
        )

    def generate(
        self, system: str, messages: list[Message], tools: list[ToolSpec]
    ) -> ModelResponse:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=self.temperature,
            tools=[to_gemini_tool(tools)] if tools else None,
            # We run the tools ourselves, so we can record and fake them.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(
                disable=True
            ),
        )
        response = self._client.models.generate_content(
            model=self.model, contents=to_gemini_contents(messages), config=config
        )
        return ModelResponse(
            message=from_gemini_response(response), usage=_usage(response)
        )


def to_gemini_tool(tools: list[ToolSpec]) -> types.Tool:
    return types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name=t.name,
                description=t.description,
                parameters_json_schema=t.parameters,
            )
            for t in tools
        ]
    )


def to_gemini_contents(messages: list[Message]) -> list[types.Content]:
    contents: list[types.Content] = []
    for message in messages:
        if message.role == "user":
            contents.append(_content("user", [types.Part(text=message.text)]))
        elif message.role == "assistant":
            # Replay Gemini's own output untouched when we have it.
            contents.append(message.raw or _assistant_content(message))
        else:
            part = _tool_result_part(message)
            previous = contents[-1] if contents else None
            # Results of parallel calls go together in a single user turn.
            if previous is not None and _is_tool_results(previous):
                previous.parts = [*(previous.parts or []), part]
            else:
                contents.append(_content("user", [part]))
    return contents


def from_gemini_response(response: types.GenerateContentResponse) -> Message:
    candidate = (response.candidates or [None])[0]
    content = candidate.content if candidate else None
    parts = (content.parts if content else None) or []

    text = "".join(p.text for p in parts if p.text and not p.thought)
    tool_calls = [
        ToolCall(
            name=p.function_call.name or "",
            arguments=dict(p.function_call.args or {}),
            id=p.function_call.id,
        )
        for p in parts
        if p.function_call
    ]
    return Message(role="assistant", text=text, tool_calls=tool_calls, raw=content)


def _assistant_content(message: Message) -> types.Content:
    parts = [types.Part(text=message.text)] if message.text else []
    parts += [
        types.Part(
            function_call=types.FunctionCall(id=c.id, name=c.name, args=c.arguments)
        )
        for c in message.tool_calls
    ]
    return _content("model", parts)


def _tool_result_part(message: Message) -> types.Part:
    assert message.tool_call is not None, "a tool message needs its tool_call"
    part = types.Part.from_function_response(
        name=message.tool_call.name, response=message.tool_result or {}
    )
    if part.function_response is not None:
        part.function_response.id = message.tool_call.id
    return part


def _is_tool_results(content: types.Content) -> bool:
    parts = content.parts or []
    return (
        content.role == "user"
        and bool(parts)
        and all(p.function_response for p in parts)
    )


def _content(role: str, parts: list[types.Part]) -> types.Content:
    return types.Content(role=role, parts=parts)


def _usage(response: types.GenerateContentResponse) -> Usage:
    meta = response.usage_metadata
    if meta is None:
        return Usage()
    return Usage(
        input_tokens=meta.prompt_token_count or 0,
        output_tokens=meta.candidates_token_count or 0,
    )
