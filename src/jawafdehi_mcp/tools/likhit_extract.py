"""Likhit document extraction tool for converting Nepal government PDFs to Markdown."""

from pathlib import Path
from typing import Any

import likhit
from mcp.types import TextContent

from .base import BaseTool

try:
    from likhit.core import render_markdown as likhit_render_markdown
except ImportError:
    likhit_render_markdown = None


class LikhitExtractTool(BaseTool):
    """Tool for extracting Nepal government documents into structured Markdown.

    Wraps the likhit library to convert PDF documents (e.g. CIAA press releases)
    into clean Markdown with YAML frontmatter containing extracted metadata.
    """

    @property
    def name(self) -> str:
        return "likhit_extract"

    @property
    def description(self) -> str:
        return (
            "Convert a Nepal government PDF document to structured Markdown. "
            "Uses the likhit extraction pipeline to parse PDFs with Nepali text "
            "(including Kalimati font fixing) and produce clean Markdown with "
            "YAML frontmatter.\n\n"
            "Supported document types:\n"
            "- ciaa-press-release: CIAA (अख्तियार दुरुपयोग अनुसन्धान आयोग) press release PDFs\n\n"
            "The file_path must point to a PDF file accessible on the local filesystem."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the PDF file on the local filesystem.",
                },
                "doc_type": {
                    "type": "string",
                    "enum": ["ciaa-press-release"],
                    "description": "The type of Nepal government document to extract.",
                },
                "title": {
                    "type": "string",
                    "description": "Optional. Override the title extracted from the document.",
                },
                "publication_date": {
                    "type": "string",
                    "description": "Optional. Override the publication date (YYYY-MM-DD format).",
                },
                "source_url": {
                    "type": "string",
                    "description": "Optional. Attach a source URL to the extracted document metadata.",
                },
                "pages": {
                    "type": "string",
                    "description": "Optional. Page range to extract, e.g. '1-3' or '5'.",
                },
                "output_path": {
                    "type": "string",
                    "description": "Optional. Absolute path to write the extracted Markdown file. Parent directories are created automatically.",
                },
            },
            "required": ["file_path", "doc_type"],
        }

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        file_path = arguments.get("file_path")
        doc_type = arguments.get("doc_type")

        if not file_path or not doc_type:
            return [
                TextContent(
                    type="text",
                    text="Error: 'file_path' and 'doc_type' are required parameters.",
                )
            ]

        path = Path(file_path)
        if not path.exists():
            return [
                TextContent(
                    type="text",
                    text=f"Error: File not found: {file_path}",
                )
            ]

        if not path.is_file():
            return [
                TextContent(
                    type="text",
                    text=f"Error: Path is not a file: {file_path}",
                )
            ]

        try:
            extract_fn = getattr(likhit, "extract", None)
            convert_fn = getattr(likhit, "convert", None)

            if extract_fn and likhit_render_markdown:
                result = extract_fn(
                    str(path),
                    doc_type,
                    title=arguments.get("title"),
                    publication_date=arguments.get("publication_date"),
                    source_url=arguments.get("source_url"),
                    pages=arguments.get("pages"),
                )
                markdown = likhit_render_markdown(result)
            elif convert_fn:
                markdown = convert_fn(str(path))
            else:
                raise RuntimeError(
                    "Installed likhit package does not expose a supported API."
                )

            output_path = arguments.get("output_path")
            if output_path:
                out = Path(output_path)
                out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(markdown, encoding="utf-8")
                return [
                    TextContent(
                        type="text",
                        text=f"Markdown written to {out}\n\n{markdown}",
                    )
                ]

            return [TextContent(type="text", text=markdown)]

        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error extracting document: {e}",
                )
            ]
