# MCP Server Template

A production-ready Python MCP server template built with [FastMCP](https://github.com/jlowin/fastmcp) and FastAPI. Exposes tools over **Streamable HTTP** transport, ready to connect to Open WebUI or any MCP-compatible client. Clone, configure, and extend with your own tools.

---

## Quick Start

```bash
git clone <this-repo> my-mcp-server
cd my-mcp-server
cp .env.example .env
# Edit .env — set your API key and server name
docker compose up
```

Test it:
```bash
# Health check (no auth required)
curl http://localhost:8000/health

# Call the ping tool
curl -X POST http://localhost:8000/mcp \
  -H "Authorization: Bearer sk-dev-key-1" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"ping","arguments":{}}}'
```

---

## Adding a New Tool

**To add a tool to an existing family** (e.g., `text`):

1. Create `src/mcp_server/tools/text/word_count.py`:
   ```python
   from mcp_server.server import mcp
   from mcp_server.utils.text import word_count

   @mcp.tool(description="Count words in text.")
   async def count_words(content: str) -> dict:
       return {"word_count": word_count(content)}
   ```
2. Add `from . import word_count` to `src/mcp_server/tools/text/__init__.py`.

Done. No other changes needed.

---

## Adding a New Tool Family

1. Create `src/mcp_server/tools/files/` with an `__init__.py`.
2. Add your tool files under that folder.
3. In `__init__.py`, import each tool module: `from . import read_file`.

The top-level `src/mcp_server/tools/__init__.py` auto-discovers all sub-packages via `pkgutil.iter_modules` — **no manual registration required**.

---

## Shared Utilities

Utils in `src/mcp_server/utils/` are pure functions with no side effects, safe to import anywhere:

| File | Functions |
|---|---|
| `utils/text.py` | `truncate(text, max_length, suffix)`, `word_count(text)`, `sanitize(text)` |
| `utils/datetime.py` | `iso_now()`, `elapsed_ms(start)` |

To add a new util: create a new file in `utils/` and import it where needed. If a util file grows beyond ~10 functions, split it.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `SERVER_HOST` | `0.0.0.0` | Bind address |
| `SERVER_PORT` | `8000` | Port |
| `LOG_LEVEL` | `info` | `debug` / `info` / `warning` / `error` |
| `MCP_SERVER_NAME` | `mcp-server-template` | Name shown in MCP metadata |
| `MCP_MOUNT_PATH` | `/mcp` | URL prefix for the MCP endpoint |
| `AUTH_MODE` | `api_key` | `api_key` / `oauth2` / `none` |
| `API_KEYS` | `[]` | JSON list of valid Bearer keys, e.g. `["sk-key-1","sk-key-2"]` |
| `OAUTH2_TOKEN_URL` | — | Token endpoint (informational) |
| `OAUTH2_JWKS_URL` | — | **Required** when `AUTH_MODE=oauth2` |
| `OAUTH2_AUDIENCE` | — | Expected JWT `aud` claim |
| `OAUTH2_ISSUER` | — | Expected JWT `iss` claim |
| `CORS_ORIGINS` | `[]` | JSON list of allowed CORS origins. Empty = CORS disabled |
| `LANGFUSE_ENABLED` | `false` | Enable Langfuse tracing |
| `LANGFUSE_SECRET_KEY` | — | Langfuse secret key |
| `LANGFUSE_PUBLIC_KEY` | — | Langfuse public key |
| `LANGFUSE_HOST` | — | Langfuse base URL |

---

## Authentication

### API Key mode (`AUTH_MODE=api_key`)

Pass keys in `API_KEYS` as a JSON list:
```env
API_KEYS=["sk-prod-key-abc","sk-client-2-xyz"]
```

Clients send: `Authorization: Bearer sk-prod-key-abc`

### OAuth2 Client Credentials (`AUTH_MODE=oauth2`)

Set the JWKS endpoint and claim validators:
```env
AUTH_MODE=oauth2
OAUTH2_JWKS_URL=https://your-idp.example.com/.well-known/jwks.json
OAUTH2_AUDIENCE=https://my-mcp-server
OAUTH2_ISSUER=https://your-idp.example.com
```

JWKS is cached for 1 hour. Tokens must pass `iss`, `aud`, and `exp` validation.

### No auth (`AUTH_MODE=none`)

Disables all authentication. A warning is logged at startup. **Do not use in production.**

---

## Open WebUI Integration

In Open WebUI's MCP server settings:

| Field | Value |
|---|---|
| **URL** | `http://mcp-server:8000/mcp` (Docker network) or `http://localhost:8000/mcp` |
| **Transport** | Streamable HTTP |
| **Authorization header** | `Bearer <your-api-key>` |

Example Open WebUI config snippet:
```json
{
  "url": "http://mcp-server:8000/mcp",
  "transport": "streamable-http",
  "headers": {
    "Authorization": "Bearer sk-dev-key-1"
  }
}
```

To connect from the same Docker Compose network, add your MCP server to Open WebUI's network:
```yaml
# docker-compose.override.yml
services:
  mcp-server:
    networks:
      - open-webui_default

networks:
  open-webui_default:
    external: true
```

---

## Development

### Run with hot-reload

Create `docker-compose.override.yml`:
```yaml
services:
  mcp-server:
    volumes:
      - ./src:/app/src
    command: uvicorn mcp_server.app:app --host 0.0.0.0 --port 8000 --reload
```

Then `docker compose up`.

### Run tests

```bash
# Install dev dependencies
uv pip install -e ".[dev]"

# Set up test env
cp .env.example .env.test

# Run tests
pytest tests/ -v
```

### Linting

```bash
uv pip install ruff
ruff check src/ tests/
ruff format src/ tests/
```

---

## Project Structure

```
mcp-server-template/
│
├── src/mcp_server/
│   ├── app.py              # FastAPI app factory + MCP mount + auth middleware
│   ├── config.py           # Pydantic Settings (all env vars)
│   ├── server.py           # Shared FastMCP instance
│   │
│   ├── auth/
│   │   ├── dependencies.py # Routes auth to correct backend by AUTH_MODE
│   │   ├── api_key.py      # API key Bearer token validation
│   │   └── oauth2.py       # JWT validation against JWKS with 1h cache
│   │
│   ├── utils/
│   │   ├── text.py         # truncate, word_count, sanitize
│   │   └── datetime.py     # iso_now, elapsed_ms
│   │
│   ├── tools/
│   │   ├── __init__.py     # Auto-discovers all tool family sub-packages
│   │   ├── system/
│   │   │   └── ping.py     # Ping/pong connectivity tool
│   │   └── text/
│   │       └── summary.py  # Text truncation + word count tool
│   │
│   └── observability/
│       └── langfuse.py     # Langfuse singleton + trace_tool context manager
│
├── tests/
│   ├── conftest.py         # Fixtures: settings overrides, async client, mock Langfuse
│   ├── test_health.py      # Health endpoint shape and auth exclusion
│   ├── test_auth.py        # API key validation (valid/missing/invalid/none mode)
│   └── test_ping.py        # MCP tools/call ping + tools/list integration tests
│
├── Dockerfile              # python:3.12-slim, uv install, non-root user
├── docker-compose.yml      # Single mcp-server service with healthcheck
├── .env.example            # All env vars documented
└── pyproject.toml          # Dependencies, ruff config
```
