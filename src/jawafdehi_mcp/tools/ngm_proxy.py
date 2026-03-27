"""Shared helpers for NGM proxy access via Jawafdehi API."""

import json
import os
from typing import Any

import httpx


def get_jawafdehi_api_config() -> tuple[str, str]:
    """Return validated Jawafdehi API base URL and token."""
    base_url = os.getenv("JAWAFDEHI_API_BASE_URL", "https://portal.jawafdehi.org")
    base_url = base_url.rstrip("/")
    token = os.getenv("JAWAFDEHI_API_TOKEN", "").strip()

    if not token:
        raise ValueError("JAWAFDEHI_API_TOKEN environment variable is required.")

    if not base_url.startswith(("http://", "https://")):
        raise ValueError(
            "JAWAFDEHI_API_BASE_URL must be an HTTP(S) URL. " f"Got: {base_url[:30]}..."
        )

    return base_url, token


def rows_to_dicts(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Convert proxy response rows+columns payload into dict records."""
    data = payload.get("data") or {}
    columns = data.get("columns") or []
    rows = data.get("rows") or []
    return [dict(zip(columns, row)) for row in rows]


def sql_quote(value: str) -> str:
    """Quote a SQL string literal by escaping single quotes."""
    return value.replace("'", "''")


async def execute_ngm_proxy_query(
    client: httpx.AsyncClient,
    base_url: str,
    token: str,
    query: str,
    timeout: float = 15,
) -> dict[str, Any]:
    """Execute a query via Jawafdehi's NGM proxy endpoint."""
    response = await client.post(
        f"{base_url}/api/ngm/query_judicial",
        json={"query": query, "timeout": timeout},
        headers={"Authorization": f"Token {token}"},
        timeout=30.0,
    )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError:
        payload = {
            "success": False,
            "error": f"Non-JSON response from proxy ({response.status_code})",
            "raw": response.text,
        }

    if not response.is_success or not payload.get("success"):
        raise RuntimeError(
            f"NGM proxy query failed ({response.status_code}): "
            f"{json.dumps(payload, ensure_ascii=False)}"
        )

    return payload
