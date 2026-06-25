from __future__ import annotations

import math
from datetime import datetime, timezone

_SAFE = {k: getattr(math, k) for k in dir(math) if not k.startswith("_")}
_SAFE |= {"abs": abs, "round": round}


def calculate(expression: str) -> str:
    try:
        return str(eval(expression, {"__builtins__": {}}, _SAFE))  # noqa: S307
    except Exception as e:
        return f"Error: {e}"


def get_current_time() -> str:
    return datetime.now(timezone.utc).isoformat()


TOOLS = [
    {
        "name": "calculate",
        "description": "Evaluate a math expression (e.g. '2 + sqrt(9)').",
        "input_schema": {
            "type": "object",
            "properties": {"expression": {"type": "string", "description": "A Python math expression"}},
            "required": ["expression"],
        },
    },
    {
        "name": "get_current_time",
        "description": "Return the current UTC date and time as an ISO 8601 string.",
        "input_schema": {"type": "object", "properties": {}},
    },
]

DISPATCH: dict[str, callable] = {
    "calculate": lambda inp: calculate(inp["expression"]),
    "get_current_time": lambda _: get_current_time(),
}
