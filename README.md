# AgentProof

Regression testing for customer-facing AI agents.

AgentProof runs simulated conversations against an AI agent, checks business rules,
and tells you when a prompt change breaks something that used to work.

## Why

I deploy AI agents for clinics, hotels and small businesses on WhatsApp and Instagram.
The most expensive failures I've seen in production were not bad wording. They were
agents that sounded right and were wrong: confirming appointments that were never
booked, inventing prices, or making up payment details. A better prompt reduces these
failures but never removes them, so every prompt change needs to be tested.

## What it does

- Runs test suites written in YAML against an agent, through pluggable adapters
- Records full transcripts, including tool calls and tool results
- Deterministic rule checks (for example: never confirm without a booking ID,
  every price must come from a tool result, urgent cases must hand off to a human)
- LLM-as-a-judge with rubrics for tone, clarity and instruction following
- Compares two prompt versions and shows what improved and what regressed
- Reports in the terminal, JSON and Markdown
- (planned) Simulated users with personas, repeated runs to catch intermittent
  failures, and an MCP server so any MCP-compatible assistant can run the tests

## Example agent

`examples/clinic_agent` is a scheduling agent for a fictional dental clinic,
with tools to check availability, book, cancel and hand off to a human.
All data is made up.

## Quick start

(coming soon)

## Roadmap

- [ ] Core runner, YAML suites and rule evaluators
- [ ] Version comparison and reports
- [ ] LLM judge with rubrics
- [ ] MCP server
- [ ] Simulated users and repeated runs
- [ ] CI with GitHub Actions

## License

MIT
