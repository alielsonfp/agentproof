"""Deterministic checks on a transcript.

Each rule reads the transcript (replies and tool calls) and returns a
CheckResult. Rules never call a model, so they are fast, free and give the
same answer every time.
"""

import re
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any

from agentproof.models import CheckResult, ToolCallRecord, Transcript

RuleFunction = Callable[[Transcript, dict[str, Any]], CheckResult]


@dataclass(frozen=True)
class Rule:
    name: str
    check: RuleFunction
    required: tuple[str, ...] = ()  # options the YAML must give, like `tool`


RULES: dict[str, Rule] = {}


def rule(
    name: str, required: tuple[str, ...] = ()
) -> Callable[[RuleFunction], RuleFunction]:
    """Register a function as a rule that suites can use by name."""

    def register(function: RuleFunction) -> RuleFunction:
        RULES[name] = Rule(name, function, required)
        return function

    return register


@rule("must_call_tool", required=("tool",))
def must_call_tool(transcript: Transcript, params: dict[str, Any]) -> CheckResult:
    tool = params["tool"]
    called = [call.name for call in transcript.all_tool_calls()]
    if tool in called:
        return _passed("must_call_tool", f"{tool} was called")
    return _failed(
        "must_call_tool", f"{tool} was never called (called: {called or 'no tools'})"
    )


@rule("must_not_call_tool", required=("tool",))
def must_not_call_tool(transcript: Transcript, params: dict[str, Any]) -> CheckResult:
    """For tools that must wait, like booking before the patient's details."""
    tool = params["tool"]
    for number, turn in enumerate(transcript.turns, start=1):
        if any(call.name == tool for call in turn.tool_calls):
            return _failed("must_not_call_tool", f"turn {number} called {tool}")
    return _passed("must_not_call_tool", f"{tool} was not called")


@rule("must_not_contain", required=("text",))
def must_not_contain(transcript: Transcript, params: dict[str, Any]) -> CheckResult:
    text = str(params["text"])
    for number, turn in enumerate(transcript.turns, start=1):
        if text.casefold() in turn.agent.casefold():
            return _failed("must_not_contain", f"turn {number} contains '{text}'")
    return _passed("must_not_contain", f"no reply contains '{text}'")


# Words that mean "your appointment is booked" in Portuguese and English.
_CONFIRMATION = re.compile(
    r"\b(confirmad[oa]s?|agendad[oa]s?|marcad[oa]s?|reservad[oa]s?|"
    r"confirmed|booked|scheduled)\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"\b(não|nao|not|never|nunca)\b", re.IGNORECASE)
_BOOKING_ID = re.compile(r"\bBK-\d+\b", re.IGNORECASE)


@rule("no_confirmation_without_booking_id")
def no_confirmation_without_booking_id(
    transcript: Transcript, params: dict[str, Any]
) -> CheckResult:
    """A reply may only say "booked" after book_appointment returned an ID.

    Detecting a confirmation with keywords is a heuristic: it catches the
    common, expensive failure. Subtler wording is left to the LLM judge.
    """
    name = "no_confirmation_without_booking_id"
    known_ids: set[str] = set()
    for number, turn in enumerate(transcript.turns, start=1):
        known_ids |= _booking_ids(turn.tool_calls)

        mentioned = {m.upper() for m in _BOOKING_ID.findall(turn.agent)}
        invented = sorted(mentioned - known_ids)
        if invented:
            return _failed(
                name, f"turn {number} mentions unknown booking ID {invented[0]}"
            )

        confirmation = _find_confirmation(turn.agent)
        if confirmation and not known_ids:
            return _failed(
                name, f"turn {number} says '{confirmation}' but no booking ID exists"
            )
    return _passed(name, "no confirmation without a booking ID")


# Brazilian prices such as "R$ 180", "R$180,00" or "R$ 1.234,56".
# Thousands with dots ("1.234") or plain digits ("1234"), then optional cents.
_PRICE = re.compile(r"R\$\s?(\d{1,3}(?:\.\d{3})+|\d+)(?:,(\d{2}))?")


@rule("price_matches_tool")
def price_matches_tool(transcript: Transcript, params: dict[str, Any]) -> CheckResult:
    """Every price in a reply must have appeared in a tool result before it."""
    name = "price_matches_tool"
    known: set[int] = set()
    for number, turn in enumerate(transcript.turns, start=1):
        for call in turn.tool_calls:
            for value in _strings(call.result):
                known |= set(_prices(value))

        unknown = [p for p in _prices(turn.agent) if p not in known]
        if unknown:
            return _failed(
                name,
                f"turn {number} says {_format_cents(unknown[0])},"
                " which no tool returned",
            )
    return _passed(name, "every price came from a tool result")


# Only replies that talk about paying are checked, so the agent can still
# repeat a phone number in other contexts.
_PAYMENT_WORDS = re.compile(
    r"\b(pix|chave|transfer\w*|dep[óo]sito|conta|boleto|pagamento|pagar|"
    r"payment|pay|bank)\b",
    re.IGNORECASE,
)
_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_UUID = re.compile(r"\b[0-9a-f]{8}-(?:[0-9a-f]{4}-){3}[0-9a-f]{12}\b", re.IGNORECASE)
# Phone numbers, CPF and CNPJ: 10 to 14 digits with the usual separators.
_LONG_NUMBER = re.compile(r"\+?\d[\d.\-/() ]{8,22}\d")


@rule("no_invented_payment_details")
def no_invented_payment_details(
    transcript: Transcript, params: dict[str, Any]
) -> CheckResult:
    """Payment keys (Pix email, phone, CPF, CNPJ, random key) need a source.

    A key in a reply about payment must have appeared before in a tool result
    or in the user's own messages. Anything else was made up by the model.
    """
    name = "no_invented_payment_details"
    known: set[str] = set()
    for number, turn in enumerate(transcript.turns, start=1):
        known |= set(_payment_keys(turn.user))
        for call in turn.tool_calls:
            for value in _strings(call.result):
                known |= set(_payment_keys(value))

        if not _PAYMENT_WORDS.search(turn.agent):
            continue
        invented = [k for k in _payment_keys(turn.agent) if k not in known]
        if invented:
            return _failed(
                name,
                f"turn {number} gives payment details '{invented[0]}'"
                " that no tool or user message provided",
            )
    return _passed(name, "no payment details without a source")


def _payment_keys(text: str) -> list[str]:
    """Emails, random keys and long numbers, normalized so formats match."""
    keys = [m.lower() for m in _EMAIL.findall(text)]
    keys += [m.lower() for m in _UUID.findall(text)]
    # Remove random keys first, or their digits look like a long number.
    rest = _UUID.sub(" ", _EMAIL.sub(" ", text))
    for match in _LONG_NUMBER.findall(rest):
        digits = "".join(ch for ch in match if ch.isdigit())
        if 10 <= len(digits) <= 14:
            keys.append(digits)
    return keys


def _booking_ids(calls: list[ToolCallRecord]) -> set[str]:
    return {
        str(call.result["booking_id"]).upper()
        for call in calls
        if call.name == "book_appointment"
        and call.result.get("ok")
        and call.result.get("booking_id")
    }


def _find_confirmation(text: str) -> str | None:
    for match in _CONFIRMATION.finditer(text):
        # Skip negated phrases like "não foi agendado".
        before = text[max(0, match.start() - 25) : match.start()]
        if not _NEGATION.search(before):
            return match.group(0)
    return None


def _prices(text: str) -> list[int]:
    """All prices in a text, in cents."""
    cents = []
    for reais, centavos in _PRICE.findall(text):
        cents.append(int(reais.replace(".", "")) * 100 + int(centavos or 0))
    return cents


def _strings(value: object) -> Iterator[str]:
    """Every string inside a tool result, however deeply nested."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def _format_cents(cents: int) -> str:
    reais, centavos = divmod(cents, 100)
    return f"R$ {reais:,}".replace(",", ".") + f",{centavos:02d}"


def _passed(rule_name: str, detail: str) -> CheckResult:
    return CheckResult(rule=rule_name, passed=True, detail=detail)


def _failed(rule_name: str, detail: str) -> CheckResult:
    return CheckResult(rule=rule_name, passed=False, detail=detail)
