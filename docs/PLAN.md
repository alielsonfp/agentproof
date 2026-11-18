# AgentProof plan

## MVP (two weeks)

### Week 1: foundation and the example agent

- [x] Day 1: repository (WSL2 postponed), `uv init`, `pyproject.toml`, MIT license, `.gitignore`, `.env.example`, README with the vision, ruff and pytest running with one simple test
- [x] Day 2: fake clinic backend in SQLite and the tools (`check_availability`, `book_appointment`, `cancel_appointment`, `handoff_to_human`), with unit tests
- [x] Day 3: example agent with prompt v1 and the tools, chatting from the terminal
- [x] Day 4: Pydantic models (TestCase, Turn, Expectation, Result), YAML loader and a first suite with 3 cases
- [x] Day 5: runner that executes the cases and saves each transcript as JSON, including tool calls and results

### Week 2: evaluation and reports

- [x] Day 6: rule evaluators: `no_confirmation_without_booking_id`, `must_call_tool`, `must_not_contain`, `price_matches_tool`
- [x] Day 7: terminal report (Rich), plus JSON and Markdown
- [x] Day 8: simulated tool failures (`fail_tool`) and the false confirmation and invented price cases
- [x] Day 9: LLM-as-a-judge with a rubric, plus the out-of-scope and prompt injection cases
- [ ] Day 10: version comparison: run prompt v1 and v2 and show what improved and what regressed
- [ ] Days 11 and 12: full README with a screenshot or GIF, more tests, refactoring

### MVP is done when

- `agentproof run suites/clinic.yaml` runs end to end and produces a report
- At least 8 of the initial test cases work
- Comparing two prompt versions shows what regressed
- The README explains the problem, how to use it and the roadmap
- AgentProof's own tests pass

## Week 3: MCP server

- [ ] MCP server exposing `run_suite`, `list_cases`, `compare_versions` and `get_report`
- [ ] Tests and README section for the MCP server

## Initial test cases

| Case | What the test checks | Evaluator | Severity |
| --- | --- | --- | --- |
| False confirmation | Only confirms if `book_appointment` returned an ID | Rule | High |
| Invented price | Every price in the reply exists in a tool result | Rule | High |
| Invented payment details | Never generates payment data that did not come from a source | Rule | Critical |
| Incomplete guest details | Asks for children's ages before checking price or availability | Rule (tool order) | High |
| Cut-off reply | Reply is complete; repeat N times and measure the failure rate | Rule + repetition | Medium |
| Urgency | Calls `handoff_to_human` | Rule | High |
| Insurance rule | States the rule and offers an alternative, without booking | Rule + judge | Medium |
| Out of scope | Gives no medical advice | Judge | High |
| Prompt injection | Keeps the business rules | Judge | High |
| Another person's data | Does not reveal third-party data | Rule + judge | Critical |
| Tone and clarity | Rubric for tone, clarity and conciseness | Judge | Low |

## Roadmap after the MVP

### Phase 2: genuinely useful

- Simulated users with personas over multiple turns
- Repeat each case N times and report the failure rate, to catch intermittent failures
- Multiple model providers and cost per run
- Validate extracted details (guest count, ages, dates) before tool calls

### Phase 3: product

- Parallel runs and run history
- GitHub Actions running the suite on every prompt change
- HTML report with the conversation and highlighted failures

### Phase 4: WhatsApp and production

- Split messages, transcribed audio, buttons and lists
- 24-hour window, follow-ups and CRM stages
- Generic HTTP adapter to test agents from any platform through an API
- Web interface to create cases and browse results
