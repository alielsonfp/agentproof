"""Conversion tests for the Gemini provider. No network calls."""

from google.genai import types

from agentproof.providers import Message, ToolCall, ToolSpec
from agentproof.providers.gemini import (
    from_gemini_response,
    to_gemini_contents,
    to_gemini_tool,
)

CALL_A = ToolCall("check_availability", {"date": "2027-03-01"}, id="a")
CALL_B = ToolCall("handoff_to_human", {"reason": "pain"}, id="b")


def test_tool_spec_becomes_function_declaration() -> None:
    schema = {"type": "object", "properties": {}}
    tool = to_gemini_tool([ToolSpec("ping", "Check the service.", schema)])

    declaration = (tool.function_declarations or [])[0]
    assert declaration.name == "ping"
    assert declaration.parameters_json_schema == schema


def test_user_and_assistant_messages_get_gemini_roles() -> None:
    contents = to_gemini_contents(
        [Message(role="user", text="oi"), Message(role="assistant", text="Ola!")]
    )

    assert [c.role for c in contents] == ["user", "model"]
    assert [(c.parts or [])[0].text for c in contents] == ["oi", "Ola!"]


def test_assistant_raw_content_is_replayed_untouched() -> None:
    raw = types.Content(
        role="model", parts=[types.Part(text="Ola!", thought_signature=b"sig")]
    )

    contents = to_gemini_contents([Message(role="assistant", text="x", raw=raw)])

    assert contents == [raw]


def test_parallel_tool_results_are_merged_in_one_turn() -> None:
    messages = [
        Message(role="assistant", tool_calls=[CALL_A, CALL_B]),
        Message(role="tool", tool_call=CALL_A, tool_result={"ok": True}),
        Message(role="tool", tool_call=CALL_B, tool_result={"ok": True}),
    ]

    contents = to_gemini_contents(messages)

    assert len(contents) == 2
    results = contents[1].parts or []
    assert [p.function_response.name for p in results if p.function_response] == [
        "check_availability",
        "handoff_to_human",
    ]
    assert [p.function_response.id for p in results if p.function_response] == [
        "a",
        "b",
    ]


def test_response_text_and_tool_calls_are_extracted() -> None:
    content = types.Content(
        role="model",
        parts=[
            types.Part(text="thinking...", thought=True),
            types.Part(text="Vou verificar."),
            types.Part(
                function_call=types.FunctionCall(
                    id="a", name="check_availability", args={"date": "2027-03-01"}
                )
            ),
        ],
    )
    response = types.GenerateContentResponse(
        candidates=[types.Candidate(content=content)]
    )

    message = from_gemini_response(response)

    assert message.text == "Vou verificar."  # thoughts are not part of the reply
    assert message.tool_calls == [CALL_A]
    assert message.raw is content


def test_empty_response_gives_empty_message() -> None:
    message = from_gemini_response(types.GenerateContentResponse(candidates=[]))

    assert message.text == ""
    assert message.tool_calls == []
