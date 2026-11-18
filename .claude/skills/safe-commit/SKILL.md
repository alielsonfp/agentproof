---
name: safe-commit
description: Check and commit the current changes safely. Use when the user wants to commit, says "commit", "commita" or "faz o commit", or when a logical chunk of work is finished.
---

# Safe commit

Run these checks in order. Stop and tell the user if any of them fails.

1. **Lint and tests:** run `uv run ruff check .` and `uv run pytest`. Both must pass.
2. **Review the diff:** run `git status` and `git diff --staged` (or `git diff` if nothing is staged). Make sure the changes belong to one logical change. If they mix unrelated things, propose splitting them into separate commits.
3. **Secrets check:** look in the diff for API keys, tokens, passwords, `.env` files or anything that looks like a credential. Never commit them.
4. **Personal project check:** make sure the diff has no real client names, real phone numbers, real addresses or data that looks like it came from a real business. All example data must be fictional.
5. **Commit message:** write a conventional commit message in English, for example `feat: add booking tool to clinic backend` or `test: cover false confirmation rule`. Keep the first line under 72 characters. Add a short body only if the reason for the change is not obvious.
6. Show the user the message and the list of files, in Brazilian Portuguese, and commit after they confirm.
7. Remind the user to `git push` at the end of the session.

Never use `--no-verify`, never amend a commit that was already pushed, and never change commit dates.
