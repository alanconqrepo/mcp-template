from mcp_server.observability.langfuse import trace_tool
from mcp_server.server import mcp
from mcp_server.utils.openwebui_client import get_openwebui_client, raise_for_status


@mcp.tool(
    description=(
        "Call a model hosted in OpenWebUI and return its response. "
        "Use list_openwebui_models to discover available model IDs. "
        "Supports an optional system prompt and conversation history for multi-turn scenarios."
    )
)
async def call_openwebui_model(
    model_id: str,
    prompt: str,
    system_prompt: str = "",
    history: list[dict] = [],
) -> dict:
    """
    Args:
        model_id: OpenWebUI model identifier (e.g. 'llama3.2:3b', 'gpt-4o').
        prompt: User message to send to the model.
        system_prompt: Optional system instruction prepended to the conversation.
        history: Optional prior turns as [{"role": "user"|"assistant", "content": "..."}].
    """
    async with trace_tool("call_openwebui_model", inputs={"model_id": model_id}):
        messages: list[dict] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})

        payload = {"model": model_id, "messages": messages, "stream": False}

        try:
            async with get_openwebui_client() as client:
                response = await client.post("/api/chat/completions", json=payload)
                await raise_for_status(response)
                data = response.json()

            choice = data["choices"][0]["message"]
            return {
                "model": data.get("model", model_id),
                "content": choice["content"],
                "usage": data.get("usage", {}),
            }
        except RuntimeError as e:
            return {"error": str(e)}
        except (KeyError, IndexError) as e:
            return {"error": f"Unexpected response format from OpenWebUI: {e}"}
