"""Chat with the clinic agent in the terminal.

Run from the project root:

    uv run python -m examples.clinic_agent.chat
    uv run python -m examples.clinic_agent.chat v2   # another prompt version
"""

import json
import os
import sys

from dotenv import load_dotenv
from google.genai import errors

from agentproof.providers.gemini import DEFAULT_MODEL, GeminiProvider
from examples.clinic_agent.agent import ClinicAgent, load_prompt
from examples.clinic_agent.backend import ClinicBackend


def main() -> None:
    load_dotenv()
    version = sys.argv[1] if len(sys.argv) > 1 else "v1"
    model = os.environ.get("AGENTPROOF_DEFAULT_MODEL") or DEFAULT_MODEL
    agent = ClinicAgent(GeminiProvider(model), ClinicBackend(), load_prompt(version))

    print(f"Clinic agent (prompt {version}, model {model}). Type 'sair' to quit.\n")
    while True:
        try:
            text = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if text.lower() in {"sair", "exit", "quit"}:
            break
        if not text:
            continue

        try:
            reply = agent.send(text)
        except errors.APIError as error:
            print(f"[model error] {error}. Try again.\n")
            continue

        for record in reply.tool_calls:
            result = json.dumps(record.result, ensure_ascii=False)
            print(f"  [tool] {record.call.name}({record.call.arguments}) -> {result}")
        print(f"agent> {reply.text}\n")


if __name__ == "__main__":
    main()
