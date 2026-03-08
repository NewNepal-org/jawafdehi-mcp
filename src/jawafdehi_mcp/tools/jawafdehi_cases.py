import json
import os
import urllib.parse
from typing import Any

import httpx
from mcp.types import TextContent

from .base import BaseTool


class SearchJawafdehiCasesTool(BaseTool):
    """Tool for searching Jawafdehi accountability cases."""

    @property
    def name(self) -> str:
        return "search_jawafdehi_cases"

    @property
    def description(self) -> str:
        return (
            "Search for published Jawafdehi accountability cases (corruption) "
            "by typing keywords or tags."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "search": {
                    "type": "string",
                    "description": (
                        "Full-text search across title, description, "
                        "and key allegations."
                    ),
                },
                "tags": {
                    "type": "string",
                    "description": "Filter cases containing a specific tag.",
                },
                "page": {
                    "type": "integer",
                    "description": "Page number for pagination (defaults to 1).",
                    "default": 1,
                },
            },
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        query_params = {"case_type": "CORRUPTION"}

        if "search" in arguments and arguments["search"]:
            query_params["search"] = arguments["search"]

        if "tags" in arguments and arguments["tags"]:
            query_params["tags"] = arguments["tags"]

        if "page" in arguments:
            query_params["page"] = str(arguments["page"])

        query_string = urllib.parse.urlencode(query_params)
        base_url = os.getenv("JAWAFDEHI_API_BASE_URL", "https://portal.jawafdehi.org")
        url = f"{base_url.rstrip('/')}/api/cases/?{query_string}"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url, timeout=30.0)
                response.raise_for_status()
                data = response.json()

                return [
                    TextContent(
                        type="text", text=json.dumps(data, indent=2, ensure_ascii=False)
                    )
                ]
        except httpx.HTTPError as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error accessing Jawafdehi cases API: {str(e)}\n\n"
                    f"Consider narrowing your search or checking parameters.",
                )
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]


class GetJawafdehiCaseTool(BaseTool):
    """Tool for retrieving detailed info on a specific Jawafdehi case."""

    @property
    def name(self) -> str:
        return "get_jawafdehi_case"

    @property
    def description(self) -> str:
        return (
            "Retrieve detailed information about a specific published Jawafdehi "
            "case, including its allegations, evidence, timeline, and audit history."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "case_id": {
                    "type": "integer",
                    "description": "A unique integer value identifying the case.",
                },
                "fetch_sources": {
                    "type": "boolean",
                    "description": (
                        "If true, the tool will also fetch detailed information "
                        "for each source referenced in the case."
                    ),
                    "default": False,
                },
            },
            "required": ["case_id"],
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        case_id = arguments.get("case_id")
        if not case_id:
            return [TextContent(type="text", text="Error: case_id is required")]

        fetch_sources = arguments.get("fetch_sources", False)
        base_url = os.getenv("JAWAFDEHI_API_BASE_URL", "https://portal.jawafdehi.org")
        case_url = f"{base_url.rstrip('/')}/api/cases/{case_id}/"

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(case_url, timeout=30.0)
                if response.status_code == 404:
                    return [TextContent(type="text", text=f"Case {case_id} not found.")]
                response.raise_for_status()
                case_data = response.json()

                if fetch_sources and "evidence" in case_data:
                    # Resolve sources listed in the evidence property
                    resolved_sources = []
                    source_ids_to_fetch = set()

                    if isinstance(case_data.get("evidence"), list):
                        for ev in case_data["evidence"]:
                            if isinstance(ev, dict):
                                source_id = ev.get("source_id")
                                if source_id:
                                    source_ids_to_fetch.add(source_id)

                    for src_id in source_ids_to_fetch:
                        try:
                            src_url = f"{base_url.rstrip('/')}/api/sources/{src_id}/"
                            src_response = await client.get(src_url, timeout=30.0)
                            if src_response.status_code == 200:
                                resolved_sources.append(src_response.json())
                        except Exception as e:
                            print(f"Failed to fetch source {src_id}: {e}")

                    if resolved_sources:
                        case_data["_resolved_sources"] = resolved_sources

                return [
                    TextContent(
                        type="text",
                        text=json.dumps(case_data, indent=2, ensure_ascii=False),
                    )
                ]
        except httpx.HTTPError as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error accessing Jawafdehi API for case {case_id}: {str(e)}",
                )
            ]
        except Exception as e:
            return [TextContent(type="text", text=f"Unexpected error: {str(e)}")]
