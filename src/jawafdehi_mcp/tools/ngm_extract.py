"""NGM case data extraction query tool."""

import json
import os
from typing import Any

from mcp.types import TextContent
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

from .base import BaseTool


class NGMExtractCaseDataTool(BaseTool):
    """Tool for extracting complete NGM judicial case data directly to a markdown file."""

    @property
    def name(self) -> str:
        return "ngm_extract_case_data"

    @property
    def description(self) -> str:
        return """Extract complete judicial case information from Nepal's court system (NGM database) into a Markdown file.
This includes case metadata, hearings, and entities (plaintiffs/defendants).

Court IDs (court_identifier):
- Supreme & Special: supreme, special
- High Courts: biratnagarhc, illamhc, dhankutahc, okhaldhungahc, janakpurhc, rajbirajhc, birganjhc, patanhc, hetaudahc, pokharahc, baglunghc, tulsipurhc, butwalhc, nepalgunjhc, surkhethc, jumlahc, dipayalhc, mahendranagarhc
- District Courts: achhamdc, argakhanchidc, etc."""

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "court_identifier": {
                    "type": "string",
                    "description": "Identifier for the court (e.g. supreme, patanhc, special)",
                },
                "case_number": {
                    "type": "string",
                    "description": "The exact case number to extract data for",
                },
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to save the generated Markdown document",
                },
            },
            "required": ["court_identifier", "case_number", "file_path"],
        }

    def _validate_environment(self) -> str:
        db_url = os.getenv("NGM_DATABASE_URL")

        if not db_url:
            raise ValueError(
                "NGM_DATABASE_URL environment variable is required. "
                "Example: postgresql://user:password@host:5432/database"
            )

        if not db_url.startswith(("postgres://", "postgresql://")):
            raise ValueError(
                "NGM_DATABASE_URL must be a PostgreSQL connection string. "
                f"Got: {db_url[:20]}..."
            )

        return db_url

    def _format_markdown(
        self, court_info: dict, case_info: dict, hearings: list, entities: list
    ) -> str:
        """Format the extracted data into a Markdown string."""
        md = []

        # Header
        court_name_en = (
            court_info.get("full_name_english", "Unknown Court")
            if court_info
            else "Unknown Court"
        )
        court_name_np = court_info.get("full_name_nepali", "") if court_info else ""
        case_no = (
            case_info.get("case_number", "Unknown Case")
            if case_info
            else "Unknown Case"
        )

        md.append(f"# Case Extract: {case_no}")
        md.append(f"**Court:** {court_name_en} ({court_name_np})")

        if not case_info:
            md.append(
                "\n*Could not find metadata for this exact case number and court.*"
            )
            return "\n".join(md)

        md.append("\n## Case Information")
        # Format case metadata as a table
        md.append("| Property | Value |")
        md.append("|---|---|")

        # Mapping to readable labels
        props = [
            ("Case Type", "case_type"),
            ("Status", "case_status"),
            ("Registration Date (AD)", "registration_date_ad"),
            ("Registration Date (BS)", "registration_date_bs"),
            ("Division", "division"),
            ("Category", "category"),
            ("Section", "section"),
            ("Priority", "priority"),
            ("Original Case Number", "original_case_number"),
            ("Verdict Date (AD)", "verdict_date_ad"),
            ("Verdict Date (BS)", "verdict_date_bs"),
            ("Verdict Judge", "verdict_judge"),
        ]

        for label, key in props:
            val = case_info.get(key)
            if val is not None and val != "":
                md.append(f"| **{label}** | {val} |")

        # Full JSON details for Case (including extra_data)
        md.append("\n### Full Case Record Details (JSON)")
        md.append("```json")

        # Serialize datetime/date objects if needed by using string conversion
        def default_serializer(obj):
            return str(obj)

        md.append(
            json.dumps(
                case_info, indent=2, ensure_ascii=False, default=default_serializer
            )
        )
        md.append("```")

        # Entities
        if entities:
            md.append("\n## Entities Involved")

            # Group entities by side side
            plaintiffs = [
                e for e in entities if str(e.get("side")).lower() == "plaintiff"
            ]
            defendants = [
                e for e in entities if str(e.get("side")).lower() == "defendant"
            ]
            others = [
                e
                for e in entities
                if str(e.get("side")).lower() not in ["plaintiff", "defendant"]
            ]

            if plaintiffs:
                md.append("\n### Plaintiffs")
                for e in plaintiffs:
                    nes = f" (NES ID: {e.get('nes_id')})" if e.get("nes_id") else ""
                    addr = f" - {e.get('address')}" if e.get("address") else ""
                    md.append(f"- **{e.get('name', 'Unknown')}**{addr}{nes}")

            if defendants:
                md.append("\n### Defendants")
                for e in defendants:
                    nes = f" (NES ID: {e.get('nes_id')})" if e.get("nes_id") else ""
                    addr = f" - {e.get('address')}" if e.get("address") else ""
                    md.append(f"- **{e.get('name', 'Unknown')}**{addr}{nes}")

            if others:
                md.append("\n### Other Entities")
                for e in others:
                    nes = f" (NES ID: {e.get('nes_id')})" if e.get("nes_id") else ""
                    side = f"[{e.get('side')}] " if e.get("side") else ""
                    addr = f" - {e.get('address')}" if e.get("address") else ""
                    md.append(f"- {side}**{e.get('name', 'Unknown')}**{addr}{nes}")

        # Hearings
        if hearings:
            md.append("\n## Hearing History")
            for h in sorted(hearings, key=lambda x: str(x.get("hearing_date_ad", ""))):
                date_ad = h.get("hearing_date_ad")
                date_bs = h.get("hearing_date_bs", "Unknown Date")
                date_str = f"{date_bs} ({date_ad})" if date_ad else f"{date_bs}"

                md.append(f"\n### {date_str} - {h.get('decision_type', 'Hearing')}")

                judge = h.get("judge_names", h.get("bench", "Unknown Bench"))
                md.append(f"- **Judges / Bench:** {judge}")

                if h.get("bench_type"):
                    md.append(f"- **Bench Type:** {h.get('bench_type')}")

                if h.get("case_status"):
                    md.append(f"- **Case Status:** {h.get('case_status')}")

                if h.get("lawyer_names"):
                    md.append(f"- **Lawyers:** {h.get('lawyer_names')}")

                if h.get("remarks"):
                    md.append(f"\n> **Remarks:** {h.get('remarks')}")

                md.append("\n#### Hearing Full Details (JSON)")
                md.append("```json")
                md.append(
                    json.dumps(
                        h, indent=2, ensure_ascii=False, default=default_serializer
                    )
                )
                md.append("```")

        return "\n".join(md)

    async def execute(self, arguments: dict[str, Any]) -> list[TextContent]:
        court_identifier = arguments.get("court_identifier")
        case_number = arguments.get("case_number")
        file_path = arguments.get("file_path")

        if not all([court_identifier, case_number, file_path]):
            error_response = (
                '{"success": false, '
                '"error": "court_identifier, case_number, and file_path parameters are required"}'
            )
            return [TextContent(type="text", text=error_response)]

        # Ensure path is absolute
        if not os.path.isabs(file_path):
            file_path = os.path.abspath(file_path)

        try:
            db_url = self._validate_environment()
            engine = create_engine(db_url, pool_pre_ping=True)

            with engine.connect() as conn:
                # 1. Fetch Court Info
                result_court = conn.execute(
                    text("SELECT * FROM courts WHERE identifier = :court_id"),
                    {"court_id": court_identifier},
                )
                court_row = result_court.fetchone()
                court_info = dict(court_row._mapping) if court_row else {}

                # 2. Fetch Case Info
                result_case = conn.execute(
                    text(
                        "SELECT * FROM court_cases WHERE court_identifier = :court_id AND case_number = :case_no"
                    ),
                    {"court_id": court_identifier, "case_no": case_number},
                )
                case_row = result_case.fetchone()
                case_info = dict(case_row._mapping) if case_row else {}

                # 3. Fetch Entities
                result_entities = conn.execute(
                    text(
                        "SELECT * FROM court_case_entities WHERE court_identifier = :court_id AND case_number = :case_no"
                    ),
                    {"court_id": court_identifier, "case_no": case_number},
                )
                entities = [dict(row._mapping) for row in result_entities.fetchall()]

                # 4. Fetch Hearings
                result_hearings = conn.execute(
                    text(
                        "SELECT * FROM court_case_hearings WHERE court_identifier = :court_id AND case_number = :case_no"
                    ),
                    {"court_id": court_identifier, "case_no": case_number},
                )
                hearings = [dict(row._mapping) for row in result_hearings.fetchall()]

            # 5. Format to Markdown
            markdown_content = self._format_markdown(
                court_info, case_info, hearings, entities
            )

            # 6. Write to File

            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(markdown_content)

            response = {
                "success": True,
                "message": f"Case data successfully extracted to {file_path}",
                "file_path": file_path,
                "stats": {
                    "case_found": bool(case_info),
                    "hearings_count": len(hearings),
                    "entities_count": len(entities),
                },
            }

            return [TextContent(type="text", text=json.dumps(response))]

        except SQLAlchemyError as e:
            error_msg = str(e).replace('"', '\\"')
            error_response = (
                f'{{"success": false, "error": "Database error: {error_msg}"}}'
            )
            return [TextContent(type="text", text=error_response)]
        except Exception as e:
            error_msg = str(e).replace('"', '\\"')
            error_response = (
                f'{{"success": false, "error": "Unexpected error: {error_msg}"}}'
            )
            return [TextContent(type="text", text=error_response)]
        finally:
            if "engine" in locals():
                engine.dispose()
