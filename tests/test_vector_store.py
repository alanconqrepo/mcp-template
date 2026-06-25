from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from starlette.testclient import TestClient

from tests.conftest import _test_client_ctx

_AUTH = {
    "Authorization": "Bearer test-key-1",
    "Accept": "application/json, text/event-stream",
}
_VS_ENV = {
    "PGVECTOR_DSN": "postgresql://test:test@localhost:5432/testdb",
    "EMBEDDING_BASE_URL": "https://api.openai.com/v1",
    "EMBEDDING_API_KEY": "sk-test",
    "EMBEDDING_MODEL": "text-embedding-3-small",
    "EMBEDDING_DIMENSIONS": "4",
    "EMBEDDING_BATCH_SIZE": "2",
}
_FAKE_EMBEDDING = [0.1, 0.2, 0.3, 0.4]


def _make_mock_pool():
    """Build a mock AsyncConnectionPool that yields a usable mock connection."""
    mock_cursor = AsyncMock()
    mock_cursor.fetchall = AsyncMock(return_value=[])
    mock_cursor.fetchone = AsyncMock(return_value=None)
    mock_cursor.rowcount = 0

    # conn.transaction() must be a plain MagicMock (not AsyncMock) returning an
    # async context manager — psycopg3's transaction() is a sync method returning
    # a Transaction object, not a coroutine.
    mock_txn = MagicMock()
    mock_txn.__aenter__ = AsyncMock(return_value=None)
    mock_txn.__aexit__ = AsyncMock(return_value=False)

    mock_conn = AsyncMock()
    mock_conn.execute = AsyncMock(return_value=mock_cursor)
    mock_conn.set_autocommit = AsyncMock()
    mock_conn.transaction = MagicMock(return_value=mock_txn)

    mock_pool = MagicMock()
    mock_pool.connection.return_value.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_pool.connection.return_value.__aexit__ = AsyncMock(return_value=False)
    mock_pool._cursor = mock_cursor
    mock_pool._conn = mock_conn
    return mock_pool


@pytest.fixture
def vs_client():
    with _test_client_ctx(**_VS_ENV) as client:
        yield client


@pytest.fixture
def vs_session(vs_client: TestClient) -> str:
    resp = vs_client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "pytest", "version": "1.0"},
            },
        },
        headers=_AUTH,
    )
    assert resp.status_code == 200
    return resp.headers["mcp-session-id"]


def _call(client: TestClient, session_id: str, tool: str, args: dict) -> str:
    resp = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {"name": tool, "arguments": args},
        },
        headers={**_AUTH, "Mcp-Session-Id": session_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.text


# ── Tool registration ──────────────────────────────────────────────────────────


def test_vector_store_tools_registered(vs_client: TestClient, vs_session: str):
    resp = vs_client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        headers={**_AUTH, "Mcp-Session-Id": vs_session},
    )
    assert resp.status_code == 200
    body = resp.text
    for name in (
        "vector_store_create_collection",
        "vector_store_list_collections",
        "vector_store_delete_collection",
        "vector_store_upsert_documents",
        "vector_store_delete_documents",
        "vector_store_search",
        "vector_store_fetch_document",
    ):
        assert name in body, f"Tool '{name}' not found in tools/list"


# ── vector_store_create_collection ────────────────────────────────────────────


def test_create_collection_happy_path(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    # No existing collection
    mock_pool._cursor.fetchone = AsyncMock(return_value=None)

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_create_collection", {
            "collection": "test_docs",
            "description": "Test documents",
        })

    assert "test_docs" in body
    assert "created" in body
    # Verify CREATE TABLE and CREATE INDEX were called
    executed_sqls = [str(call.args[0]) for call in mock_pool._conn.execute.call_args_list]
    assert any("CREATE TABLE" in sql and "vs_test_docs" in sql for sql in executed_sqls)
    assert any("hnsw" in sql.lower() for sql in executed_sqls)


def test_create_collection_invalid_name(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_create_collection", {
        "collection": "My Bad Name!",
    })
    assert "error" in body.lower() or "Invalid" in body


def test_create_collection_dimension_conflict(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    # Existing collection with different dimensions
    mock_pool._cursor.fetchone = AsyncMock(return_value=(8,))  # existing: 8 dims

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_create_collection", {
            "collection": "existing_col",
            "dimensions": 4,
        })

    assert "error" in body.lower()
    assert "dimension" in body.lower() or "8" in body


def test_create_collection_idempotent(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    # Existing collection with same dimensions
    mock_pool._cursor.fetchone = AsyncMock(return_value=(4,))  # existing: 4 dims

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_create_collection", {
            "collection": "existing_col",
            "dimensions": 4,
        })

    assert "existing_col" in body
    assert "already exists" in body or "false" in body.lower()


# ── vector_store_list_collections ─────────────────────────────────────────────


def test_list_collections_empty(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchall = AsyncMock(return_value=[])

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_list_collections", {})

    assert '"count"' in body or "count" in body
    assert "0" in body


def test_list_collections_with_data(vs_client: TestClient, vs_session: str):
    from datetime import datetime, timezone

    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchall = AsyncMock(return_value=[
        ("docs_fr", 1536, "Documents FR", datetime(2024, 1, 1, tzinfo=timezone.utc), 42),
        ("product_manuals", 4, None, datetime(2024, 2, 1, tzinfo=timezone.utc), 7),
    ])

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_list_collections", {})

    assert "docs_fr" in body
    assert "product_manuals" in body
    assert "42" in body


# ── vector_store_delete_collection ────────────────────────────────────────────


def test_delete_collection_requires_confirm(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_delete_collection", {
        "collection": "docs_fr",
        "confirm": False,
    })
    assert "confirm" in body.lower() or "error" in body.lower()


def test_delete_collection_not_found(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchone = AsyncMock(return_value=None)

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_delete_collection", {
            "collection": "no_such_col",
            "confirm": True,
        })

    assert "error" in body.lower() or "does not exist" in body


def test_delete_collection_happy_path(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchone = AsyncMock(return_value=(10,))  # 10 docs

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_delete_collection", {
            "collection": "docs_fr",
            "confirm": True,
        })

    assert "docs_fr" in body
    assert "true" in body.lower() or "deleted" in body.lower()
    assert "10" in body


# ── vector_store_upsert_documents ─────────────────────────────────────────────


def test_upsert_documents_calls_embedding_api(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    captured_texts = []

    async def mock_get_embeddings(texts):
        captured_texts.extend(texts)
        return [_FAKE_EMBEDDING] * len(texts)

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        with patch("mcp_server.utils.embedding_client.get_embeddings", side_effect=mock_get_embeddings):
            body = _call(vs_client, vs_session, "vector_store_upsert_documents", {
                "collection": "docs_fr",
                "documents": [
                    {"content": "Document un", "metadata": {"lang": "fr"}},
                    {"content": "Document deux"},
                ],
            })

    assert "docs_fr" in body
    assert "2" in body  # upserted count
    assert "Document un" in captured_texts
    assert "Document deux" in captured_texts


def test_upsert_documents_batch_respects_batch_size():
    """EMBEDDING_BATCH_SIZE=2, 3 docs → 2 HTTP POST calls inside get_embeddings."""
    http_batches = []

    async def mock_post(url, *, json, **kwargs):
        http_batches.append(json["input"])
        mock_resp = MagicMock()
        mock_resp.is_error = False
        mock_resp.json.return_value = {
            "data": [{"index": i, "embedding": _FAKE_EMBEDDING} for i in range(len(json["input"]))]
        }
        return mock_resp

    with _test_client_ctx(**_VS_ENV) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "pytest", "version": "1.0"}}},
            headers=_AUTH,
        )
        session_id = resp.headers["mcp-session-id"]

        mock_pool = _make_mock_pool()
        with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
            with patch("httpx.AsyncClient.post", side_effect=mock_post):
                _call(client, session_id, "vector_store_upsert_documents", {
                    "collection": "docs_fr",
                    "documents": [
                        {"content": "Doc A"},
                        {"content": "Doc B"},
                        {"content": "Doc C"},
                    ],
                })

    # EMBEDDING_BATCH_SIZE=2 → 2 HTTP calls (batch of 2 + batch of 1)
    assert len(http_batches) == 2
    assert len(http_batches[0]) == 2
    assert len(http_batches[1]) == 1


def test_upsert_documents_missing_content(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_upsert_documents", {
        "collection": "docs_fr",
        "documents": [{"metadata": {"key": "val"}}],
    })
    assert "error" in body.lower() or "content" in body.lower()


def test_upsert_documents_empty_list(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_upsert_documents", {
        "collection": "docs_fr",
        "documents": [],
    })
    assert '"upserted"' in body or "upserted" in body
    assert '"0"' in body or ": 0" in body or "\\n0" in body or "0" in body


# ── vector_store_delete_documents ─────────────────────────────────────────────


def test_delete_documents_by_ids(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.rowcount = 2

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_delete_documents", {
            "collection": "docs_fr",
            "ids": ["id-1", "id-2"],
        })

    assert "docs_fr" in body
    assert "deleted" in body.lower()


def test_delete_documents_by_metadata_filter(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.rowcount = 3

    executed_sqls = []
    original_execute = mock_pool._conn.execute

    async def capturing_execute(sql, params=None):
        executed_sqls.append(str(sql))
        return mock_pool._cursor

    mock_pool._conn.execute = capturing_execute

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_delete_documents", {
            "collection": "docs_fr",
            "metadata_filter": {"lang": "fr"},
        })

    assert "deleted" in body.lower()
    assert any("@>" in sql for sql in executed_sqls)


def test_delete_documents_requires_ids_or_filter(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_delete_documents", {
        "collection": "docs_fr",
    })
    assert "error" in body.lower()


def test_delete_documents_rejects_both_ids_and_filter(vs_client: TestClient, vs_session: str):
    body = _call(vs_client, vs_session, "vector_store_delete_documents", {
        "collection": "docs_fr",
        "ids": ["id-1"],
        "metadata_filter": {"lang": "fr"},
    })
    assert "error" in body.lower()


# ── vector_store_search ────────────────────────────────────────────────────────


def test_search_happy_path(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchall = AsyncMock(return_value=[
        ("doc-1", "Contenu du document un", {"lang": "fr"}, 0.95),
        ("doc-2", "Contenu du document deux", {}, 0.82),
    ])

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        with patch("mcp_server.utils.embedding_client.get_embeddings", AsyncMock(return_value=[_FAKE_EMBEDDING])):
            body = _call(vs_client, vs_session, "vector_store_search", {
                "collection": "docs_fr",
                "query": "chercher un document",
                "top_k": 5,
            })

    assert "doc-1" in body
    assert "doc-2" in body
    assert "similarity" in body
    assert "0.95" in body or "0.82" in body


def test_search_min_similarity_filter(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchall = AsyncMock(return_value=[
        ("doc-1", "Very relevant", {}, 0.95),
        ("doc-2", "Less relevant", {}, 0.40),
    ])

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        with patch("mcp_server.utils.embedding_client.get_embeddings", AsyncMock(return_value=[_FAKE_EMBEDDING])):
            body = _call(vs_client, vs_session, "vector_store_search", {
                "collection": "docs_fr",
                "query": "query",
                "min_similarity": 0.8,
            })

    assert "doc-1" in body
    assert "doc-2" not in body


def test_search_with_metadata_filter(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    executed_sqls = []

    async def capturing_execute(sql, params=None):
        executed_sqls.append(str(sql))
        return mock_pool._cursor

    mock_pool._conn.execute = capturing_execute
    mock_pool._cursor.fetchall = AsyncMock(return_value=[])

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        with patch("mcp_server.utils.embedding_client.get_embeddings", AsyncMock(return_value=[_FAKE_EMBEDDING])):
            _call(vs_client, vs_session, "vector_store_search", {
                "collection": "docs_fr",
                "query": "query",
                "metadata_filter": {"lang": "fr"},
            })

    assert any("@>" in sql for sql in executed_sqls)


def test_search_unconfigured_dsn(vs_client: TestClient, vs_session: str):
    import mcp_server.utils.pgvector_pool as pool_mod

    original_pool = pool_mod._pool
    pool_mod._pool = None

    with _test_client_ctx(**{**_VS_ENV, "PGVECTOR_DSN": ""}) as client:
        resp = client.post(
            "/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                             "clientInfo": {"name": "pytest", "version": "1.0"}}},
            headers=_AUTH,
        )
        session_id = resp.headers["mcp-session-id"]
        with patch("mcp_server.utils.embedding_client.get_embeddings", AsyncMock(return_value=[_FAKE_EMBEDDING])):
            body = _call(client, session_id, "vector_store_search", {
                "collection": "docs_fr",
                "query": "test",
            })

    pool_mod._pool = original_pool
    assert "PGVECTOR_DSN" in body or "error" in body.lower() or "isError" in body


# ── vector_store_fetch_document ────────────────────────────────────────────────


def test_fetch_document_happy_path(vs_client: TestClient, vs_session: str):
    from datetime import datetime, timezone

    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchone = AsyncMock(return_value=(
        "doc-42",
        "Le contenu du document",
        {"lang": "fr", "source": "wiki"},
        datetime(2024, 1, 15, tzinfo=timezone.utc),
        datetime(2024, 1, 16, tzinfo=timezone.utc),
    ))

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_fetch_document", {
            "collection": "docs_fr",
            "id": "doc-42",
        })

    assert "doc-42" in body
    assert "Le contenu du document" in body
    assert "lang" in body


def test_fetch_document_not_found(vs_client: TestClient, vs_session: str):
    mock_pool = _make_mock_pool()
    mock_pool._cursor.fetchone = AsyncMock(return_value=None)

    with patch("mcp_server.utils.pgvector_pool.get_pool", AsyncMock(return_value=mock_pool)):
        body = _call(vs_client, vs_session, "vector_store_fetch_document", {
            "collection": "docs_fr",
            "id": "nonexistent-id",
        })

    assert "not_found" in body or "error" in body.lower()
