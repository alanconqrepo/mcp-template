from __future__ import annotations

from anthropic import AsyncAnthropic

from mcp_server.config import get_settings
from mcp_server.server import mcp

from .functions import DISPATCH, TOOLS


@mcp.tool(description="Run a Claude agent with function-calling tools (calculator, datetime). Returns the final answer and iteration count.")
async def run_agent(prompt: str, max_iterations: int = 10) -> dict:
    client = AsyncAnthropic(api_key=get_settings().ANTHROPIC_API_KEY)
    messages: list[dict] = [{"role": "user", "content": prompt}]

    for i in range(1, max_iterations + 1):
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason == "end_turn":
            text = next((b.text for b in response.content if hasattr(b, "text")), "")
            return {"result": text, "iterations": i}

        # Dispatch tool calls and feed results back
        messages.append({"role": "assistant", "content": response.content})
        messages.append({
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": b.id,
                    "content": DISPATCH[b.name](b.input),
                }
                for b in response.content
                if b.type == "tool_use"
            ],
        })

    return {"result": "max_iterations reached", "iterations": max_iterations}
