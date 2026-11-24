# AgentProof

Regression testing for customer-facing AI agents. AgentProof runs simulated
conversations against an agent, checks business rules, and reports what passed,
what failed, and what regressed between two prompt versions.

The full plan (MVP checklist and roadmap) is in `docs/PLAN.md`.

## Who you are working with

- The owner is Alielson, a Forward Deployed Engineer who deploys AI agents for
  clinics and hotels. He knows prompts, APIs and agents well, but he is getting
  back into hands-on Python, so he wants to understand every part of the code.
- Explain decisions to him in Brazilian Portuguese, short and direct.
- Code, comments, docstrings, commit messages and the README are in English.

## Non-negotiable rules

- This is a 100% personal project. Never add code, prompts, data or names from
  any real client or employer. All example data is fictional.
- Never commit secrets. API keys live only in `.env` (git-ignored). Keep
  `.env.example` updated with empty values.
- Never rewrite git history or change commit dates.
- Work in small steps. One logical change per commit.
- Before proposing a commit, `ruff check .` and `pytest` must pass.
- When you add a feature, add or update its tests in the same step.
- Prefer simple, readable code over clever code. No new dependency without
  explaining why it is needed.

## Tech stack

- Python 3.12+, managed with `uv`
- CLI: Typer + Rich
- Data models: Pydantic
- Test suites: YAML (PyYAML)
- Tests and lint: pytest + ruff
- Example agent: an agent SDK or direct tool calling, behind a provider interface
- Fake backend for the example agent: SQLite
- MCP server: the official MCP Python SDK (`mcp` 2.x, `MCPServer`)

Check the current documentation of each SDK before using it. These APIs change
often, so do not rely on memory for their exact signatures.

## Project structure

```text
src/agentproof/
  cli.py            # run, compare, report commands
  api.py            # the same actions as functions, shared with the MCP server
  models.py         # TestCase, Turn, Expectation, Result
  loader.py         # loads YAML suites
  runner.py         # runs conversations, records transcripts with tool calls
  adapters/         # how to talk to each kind of agent
  evaluators/
    rules.py        # deterministic checks
    judge.py        # LLM-as-a-judge with rubrics
  providers/        # model providers behind one interface
  report.py         # terminal, JSON and Markdown reports
  compare.py        # fixed and regressed cases between two runs
  mcp_server.py     # MCP server (agentproof-mcp), official MCP SDK 2.x
examples/clinic_agent/
  agent.py          # scheduling agent for a fictional dental clinic
  tools.py          # check_availability, book_appointment, cancel_appointment, handoff_to_human
  backend.py        # fake schedule in SQLite
  prompts/v1.md, v2.md
suites/clinic.yaml  # test cases
reports/            # generated output (git-ignored)
tests/              # tests for AgentProof itself
```

## Domain rules the example agent must follow

These come from real failure patterns and drive the first test cases:

- Never say an appointment is confirmed unless `book_appointment` returned a booking ID.
- Every price in a reply must come from a tool result. Never invent prices.
- Never generate payment details (for example a Pix key) that did not come from a source.
- Ask for missing guest or patient details (such as children's ages) before calling pricing or booking tools.
- Pain, bleeding or swelling must call `handoff_to_human`.
- Never give medical advice.
- Never reveal another person's data.
- Keep business rules when the user tries prompt injection.

## Commit messages

Conventional style, in English: `feat: ...`, `fix: ...`, `test: ...`,
`docs: ...`, `refactor: ...`, `chore: ...`.

## Useful commands

- `uv sync` to install dependencies
- `uv run pytest` to run tests
- `uv run ruff check .` to lint
- `uv run agentproof run suites/clinic.yaml` to run a suite
- `uv run agentproof-mcp` to start the MCP server over stdio
