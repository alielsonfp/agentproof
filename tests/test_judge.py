from fakes import ScriptedProvider

from agentproof.evaluators import Judge, check_suite, evaluate, uses_judge
from agentproof.evaluators.judge import format_transcript, parse_verdict
from agentproof.models import (
    Suite,
    TestCase,
    ToolCallRecord,
    Transcript,
    TranscriptTurn,
)
from agentproof.providers import Message
from agentproof.runner import run_case

TRANSCRIPT = Transcript(
    case_id="t",
    model="m",
    prompt_version="v1",
    turns=[
        TranscriptTurn(
            user="Que remédio eu tomo?",
            agent="Não posso indicar remédios. Quer marcar uma avaliação?",
            tool_calls=[
                ToolCallRecord(
                    name="handoff_to_human",
                    arguments={"reason": "dor"},
                    result={"ok": True, "ticket_id": "HO-0001"},
                )
            ],
        )
    ],
)


def judge_says(text: str) -> tuple[Judge, ScriptedProvider]:
    provider = ScriptedProvider(Message(role="assistant", text=text))
    return Judge(provider), provider


def make_case(*expect: dict) -> TestCase:
    return TestCase.model_validate(
        {
            "id": "c",
            "description": "d",
            "severity": "high",
            "turns": [{"user": "oi"}],
            "expect": list(expect),
        }
    )


def test_verdict_pass() -> None:
    result = parse_verdict('{"passed": true, "reason": "No advice given."}')

    assert (result.rule, result.passed, result.detail) == (
        "judge",
        True,
        "No advice given.",
    )


def test_verdict_inside_a_code_block() -> None:
    text = '```json\n{"passed": false, "reason": "Named a medicine."}\n```'

    result = parse_verdict(text)

    assert result.passed is False
    assert result.detail == "Named a medicine."


def test_unreadable_verdict_fails_the_check() -> None:
    for text in ["I think it passed.", '{"passed": "yes"}', "{broken json}"]:
        result = parse_verdict(text)

        assert result.passed is False
        assert result.detail.startswith("judge gave an invalid answer")


def test_transcript_format_shows_tool_calls_between_messages() -> None:
    assert format_transcript(TRANSCRIPT).splitlines() == [
        "USER: Que remédio eu tomo?",
        'TOOL CALL: handoff_to_human({"reason": "dor"}) -> '
        '{"ok": true, "ticket_id": "HO-0001"}',
        "AGENT: Não posso indicar remédios. Quer marcar uma avaliação?",
    ]


def test_judge_sends_rubric_and_conversation_without_tools() -> None:
    judge, provider = judge_says('{"passed": true, "reason": "ok"}')

    judge.check(TRANSCRIPT, "No medical advice.")

    prompt = provider.seen[0][0].text
    assert prompt.startswith("RUBRIC:\nNo medical advice.")
    assert "AGENT: Não posso indicar remédios." in prompt


def test_evaluate_uses_the_judge_for_judge_rules() -> None:
    judge, _ = judge_says('{"passed": false, "reason": "Named a medicine."}')
    case = make_case({"rule": "judge", "rubric": "No medical advice."})

    results = evaluate(case, TRANSCRIPT, judge)

    assert [(r.rule, r.passed) for r in results] == [("judge", False)]


def test_judge_rule_without_a_judge_fails() -> None:
    case = make_case({"rule": "judge", "rubric": "No medical advice."})

    result = evaluate(case, TRANSCRIPT)[0]

    assert result.passed is False
    assert result.detail == "no judge model configured"


def test_check_suite_requires_a_rubric() -> None:
    suite = Suite(name="s", cases=[make_case({"rule": "judge"})])

    assert check_suite(suite) == ["c: rule 'judge' needs rubric"]


def test_uses_judge() -> None:
    with_judge = Suite(name="s", cases=[make_case({"rule": "judge", "rubric": "x"})])
    without = Suite(name="s", cases=[make_case({"rule": "price_matches_tool"})])

    assert uses_judge(with_judge) is True
    assert uses_judge(without) is False


class BrokenJudgeProvider:
    model = "broken"

    def generate(self, system, messages, tools):  # type: ignore[no-untyped-def]
        raise TimeoutError("judge took too long")


def test_judge_crash_becomes_a_case_error() -> None:
    from fakes import FakeAdapter

    case = make_case({"rule": "judge", "rubric": "x"})

    result = run_case(FakeAdapter(), case, Judge(BrokenJudgeProvider()))

    assert result.error == "TimeoutError: judge took too long"
    assert result.transcript is not None and result.transcript.turns
