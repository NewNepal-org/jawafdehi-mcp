"""MarkItDown document conversion tool for converting various document formats to Markdown."""

from pathlib import Path
from typing import Any

from markitdown import MarkItDown
from mcp.types import TextContent

from .base import BaseTool


class MarkItDownConverterTool(BaseTool):
    """Tool for converting various document formats to Markdown.

    Wraps MarkItDown to convert documents (DOCX, PPTX, XLSX, PDFs, web pages)
    into Markdown format. When plugins are enabled, plugin converters can extend
    MarkItDown's default behavior.
    """

    @property
    def name(self) -> str:
        return "convert_to_markdown"

    @property
    def description(self) -> str:
        return (
            "Convert documents to Markdown from file:, http:, https:, or data: URIs. "
            "Handles DOCX, PPTX, XLSX, PDFs, and web pages through MarkItDown. "
            "When plugins are enabled, plugin-based converters such as `likhit` may "
            "intercept supported documents.\n\n"
            "Supports:\n"
            "- Office documents: DOCX, PPTX, XLSX\n"
            "- PDFs\n"
            "- Web pages: http://, https:// URLs\n"
            "- Local files: file:///absolute/path/to/file\n"
            "- Data URIs: data:text/plain;base64,...\n\n"
            "The tool can optionally write the converted Markdown to a file."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "uri": {
                    "type": "string",
                    "description": (
                        "URI of the resource to convert. Supports:\n"
                        "- file:///absolute/path/to/document (local files)\n"
                        "- http://example.com/document (web resources)\n"
                        "- https://example.com/document (secure web resources)\n"
                        "- data:text/plain;base64,... (data URIs)"
                    ),
                },
                "output_path": {
                    "type": "string",
                    "description": (
                        "Optional. Absolute path to write the converted Markdown file. "
                        "Parent directories are created automatically. "
                        "If not provided, the markdown content is returned directly."
                    ),
                },
                "enable_plugins": {
                    "type": "boolean",
                    "description": (
                        "Optional. Enable MarkItDown plugins for enhanced conversion. "
                        "Defaults to True."
                    ),
                    "default": True,
                },
            },
            "required": ["uri"],
        }

    def _get_output_path(self, arguments: dict[str, Any], uri: str) -> Path | None:
        """Write a sibling markdown file by default for local file URIs."""
        output_path = arguments.get("output_path")
        if output_path:
            return Path(output_path)

        if uri.startswith("file://"):
            return Path(uri.replace("file://", "")).with_suffix(".md")

        return None

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        uri = arguments.get("uri")

        if not uri:
            return [
                TextContent(
                    type="text",
                    text="Error: 'uri' is a required parameter.",
                )
            ]

        # Validate file:// URIs point to existing files
        if uri.startswith("file://"):
            file_path = uri.replace("file://", "")
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
            enable_plugins = arguments.get("enable_plugins", True)
            converter = MarkItDown(enable_plugins=enable_plugins)
            result = converter.convert_uri(uri)
            markdown = result.markdown

            output_path = self._get_output_path(arguments, uri)
            if output_path:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown, encoding="utf-8")
                return [
                    TextContent(
                        type="text",
                        text=f"✅ Markdown written to {output_path}",
                    )
                ]

            return [TextContent(type="text", text=markdown)]

        except Exception as e:
            return [
                TextContent(
                    type="text",
                    text=f"Error converting document: {e}",
                )
            ]
