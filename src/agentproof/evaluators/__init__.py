"""Turn a case's expectations into check results."""

from agentproof.evaluators.judge import JUDGE_RULE, Judge
from agentproof.evaluators.rules import RULES
from agentproof.models import CheckResult, Expectation, Suite, TestCase, Transcript


def evaluate(
    case: TestCase, transcript: Transcript, judge: Judge | None = None
) -> list[CheckResult]:
    return [_evaluate_one(e, transcript, judge) for e in case.expect]


def _evaluate_one(
    expectation: Expectation, transcript: Transcript, judge: Judge | None
) -> CheckResult:
    if expectation.rule == JUDGE_RULE:
        if judge is None:
            return _failed(JUDGE_RULE, "no judge model configured")
        return judge.check(transcript, str(expectation.params["rubric"]))

    rule = RULES.get(expectation.rule)
    if rule is None:
        return _failed(expectation.rule, f"unknown rule '{expectation.rule}'")
    return rule.check(transcript, expectation.params)


def uses_judge(suite: Suite) -> bool:
    return any(e.rule == JUDGE_RULE for case in suite.cases for e in case.expect)


def check_suite(suite: Suite) -> list[str]:
    """Find unknown rules and missing rule options before anything runs."""
    problems = []
    for case in suite.cases:
        for expectation in case.expect:
            if expectation.rule == JUDGE_RULE:
                required: tuple[str, ...] = ("rubric",)
            elif expectation.rule in RULES:
                required = RULES[expectation.rule].required
            else:
                known = ", ".join(sorted([*RULES, JUDGE_RULE]))
                problems.append(
                    f"{case.id}: unknown rule '{expectation.rule}' (known: {known})"
                )
                continue
            missing = [opt for opt in required if opt not in expectation.params]
            if missing:
                problems.append(
                    f"{case.id}: rule '{expectation.rule}' needs {', '.join(missing)}"
                )
    return problems


def _failed(rule: str, detail: str) -> CheckResult:
    return CheckResult(rule=rule, passed=False, detail=detail)


__all__ = ["Judge", "check_suite", "evaluate", "uses_judge"]
