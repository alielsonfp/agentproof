"""Load test suites from YAML files."""

from pathlib import Path

import yaml
from pydantic import ValidationError

from agentproof.models import Suite


class SuiteError(Exception):
    """The suite file is missing, is not valid YAML, or has invalid fields."""


def load_suite(path: str | Path) -> Suite:
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SuiteError(f"{path}: cannot read file ({error.strerror})") from None

    try:
        # safe_load only builds plain data (dicts, lists, strings), never
        # arbitrary Python objects, so a suite file cannot run code.
        data = yaml.safe_load(text)
    except yaml.YAMLError as error:
        raise SuiteError(f"{path}: invalid YAML\n{error}") from None

    if not isinstance(data, dict):
        raise SuiteError(f"{path}: a suite must be a mapping with 'name' and 'cases'")

    try:
        return Suite.model_validate(data)
    except ValidationError as error:
        raise SuiteError(f"{path}: invalid suite\n{_describe(error, data)}") from None


def _describe(error: ValidationError, data: dict) -> str:
    """Turn Pydantic errors into lines like `cases[urgency].severity: ...`."""
    lines = []
    for item in error.errors():
        location = _location(item["loc"], data)
        lines.append(f"  - {location or 'suite'}: {item['msg']}")
    return "\n".join(lines)


def _location(loc: tuple, data: dict) -> str:
    parts: list[str] = []
    node: object = data
    for key in loc:
        if isinstance(key, int):
            # Show the case id when there is one; it is easier to find.
            item = node[key] if isinstance(node, list) and key < len(node) else None
            case_id = item.get("id") if isinstance(item, dict) else None
            parts[-1] += f"[{case_id or key}]"
            node = item
        else:
            parts.append(str(key))
            node = node.get(key) if isinstance(node, dict) else None
    return ".".join(parts)
