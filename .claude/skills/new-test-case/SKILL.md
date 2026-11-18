---
name: new-test-case
description: Turn a described AI agent failure into a new AgentProof test case. Use when the user describes a way an agent failed or could fail, or asks to add a test case or scenario to a suite.
---

# New test case

1. Ask the user, if not already clear:
   - what the agent did wrong (or could do wrong)
   - what it should have done
   - how serious it is (critical, high, medium, low)
2. Rewrite the scenario with fictional data only. Remove any real client, person or business detail.
3. Decide how to check it:
   - **Rule** when the check is objective (a tool was or was not called, a value matches a tool result, a word must not appear)
   - **Judge** when it needs judgment (tone, clarity, medical advice, resisting manipulation)
   - Both when an objective check covers part of it
4. Add the case to the right file in `suites/`, following the existing format: `id`, `description`, `turns`, optional `setup` (for example `fail_tool`), `expect` and `severity`.
5. If the case needs a rule that does not exist yet, add it to `src/agentproof/evaluators/rules.py` with unit tests in `tests/` covering a passing and a failing transcript.
6. Run the suite and the tests. Show the user, in Brazilian Portuguese, whether the new case passes or fails against the current prompt, and what that means.
7. Suggest using the `safe-commit` skill.
