---
name: next-task
description: Pick up the next step of the AgentProof plan. Use when the user starts a work session, asks what to do next, or says "next task" or "próximo passo".
---

# Next task

1. Read `docs/PLAN.md` and find the first unchecked item.
2. Check the current state of the repository (`git status`, recent `git log`, the files the item touches) so you build on what already exists.
3. Tell the user, in Brazilian Portuguese and in a few lines:
   - which item is next
   - the 2 to 5 small steps you will take
   - which files you will create or change
4. Wait for the user to confirm before writing code.
5. Implement one small step at a time. After each step, run `uv run pytest` and `uv run ruff check .`.
6. After each step, explain in 2 or 3 short sentences what the code does and why you chose that approach, so the user learns the Python involved.
7. When a logical chunk is done and checks pass, suggest using the `safe-commit` skill.
8. When the whole plan item is done, tick its checkbox in `docs/PLAN.md` in the same commit.

Keep steps small enough that each one fits in a single commit.
