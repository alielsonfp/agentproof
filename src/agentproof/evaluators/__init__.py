"""Turn a case's expectations into check results."""

from agentproof.evaluators.rules import RULES
from agentproof.models import CheckResult, Suite, TestCase, Transcript


def evaluate(case: TestCase, transcript: Transcript) -> list[CheckResult]:
    results = []
    for expectation in case.expect:
        rule = RULES.get(expectation.rule)
        if rule is None:
            results.append(
                CheckResult(
                    rule=expectation.rule,
                    passed=False,
                    detail=f"unknown rule '{expectation.rule}'",
                )
            )
            continue
        results.append(rule.check(transcript, expectation.params))
    return results


def check_suite(suite: Suite) -> list[str]:
    """Find unknown rules and missing rule options before anything runs."""
    problems = []
    for case in suite.cases:
        for expectation in case.expect:
            rule = RULES.get(expectation.rule)
            if rule is None:
                known = ", ".join(sorted(RULES))
                problems.append(
                    f"{case.id}: unknown rule '{expectation.rule}' (known: {known})"
                )
                continue
            missing = [opt for opt in rule.required if opt not in expectation.params]
            if missing:
                problems.append(
                    f"{case.id}: rule '{rule.name}' needs {', '.join(missing)}"
                )
    return problems


__all__ = ["check_suite", "evaluate"]
