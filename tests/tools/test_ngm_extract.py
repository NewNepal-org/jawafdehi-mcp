"""Tests for NGMExtractCaseDataTool."""

from unittest.mock import MagicMock, mock_open, patch

from jawafdehi_mcp.tools.ngm_extract import NGMExtractCaseDataTool


class TestNGMExtractCaseDataTool:
    """Test functionality of NGMExtractCaseDataTool."""

    def setup_method(self):
        """Set up test fixtures."""
        self.tool = NGMExtractCaseDataTool()
        self.valid_args = {
            "court_identifier": "supreme",
            "case_number": "079-WO-0123",
            "file_path": "/tmp/test_output.md",
        }

    def test_missing_arguments(self):
        """Test missing required arguments."""
        import asyncio

        arguments = {"court_identifier": "supreme"}
        result = asyncio.run(self.tool.execute(arguments))
        assert not result[0].text.startswith('{"success": true')
        assert "required" in result[0].text

    def test_format_markdown_empty_data(self):
        """Test format_markdown when no data is found."""
        md = self.tool._format_markdown({}, {}, [], [])
        assert "Unknown Court" in md
        assert "Unknown Case" in md
        assert "Could not find metadata" in md

    def test_format_markdown_with_data(self):
        """Test formatting valid case data into markdown."""
        court_info = {
            "full_name_english": "Supreme Court",
            "full_name_nepali": "सर्वोच्च अदालत",
        }
        case_info = {
            "case_number": "079-WO-123",
            "case_type": "Writ",
            "case_status": "Pending",
        }
        entities = [
            {"side": "Plaintiff", "name": "Ram", "address": "Kathmandu"},
            {"side": "Defendant", "name": "Shyam"},
        ]
        hearings = [
            {
                "hearing_date_ad": "2023-01-01",
                "decision_type": "Order",
                "judge_names": "Judge A",
            }
        ]

        md = self.tool._format_markdown(court_info, case_info, hearings, entities)

        assert "Supreme Court" in md
        assert "सर्वोच्च अदालत" in md
        assert "079-WO-123" in md
        assert "Writ" in md
        assert "Pending" in md
        assert "Ram" in md
        assert "Kathmandu" in md
        assert "Shyam" in md
        assert "2023-01-01" in md
        assert "Judge A" in md

    @patch("os.makedirs")
    @patch("builtins.open", new_callable=mock_open)
    @patch("jawafdehi_mcp.tools.ngm_extract.create_engine")
    @patch(
        "jawafdehi_mcp.tools.ngm_extract.NGMExtractCaseDataTool._validate_environment"
    )
    def test_successful_extraction(
        self, mock_env, mock_create_engine, mock_file_open, mock_makedirs
    ):
        """Test a full successful extraction flow."""
        mock_env.return_value = "postgresql://test:test@localhost:5432/test"

        # Mock database connection and returns
        mock_engine = MagicMock()
        mock_conn = MagicMock()

        # Mock fetchone for court and case
        mock_result_single = MagicMock()
        mock_row = MagicMock()
        mock_row._mapping = {"full_name_english": "Test Court", "case_number": "123"}
        mock_result_single.fetchone.return_value = mock_row

        # Mock fetchall for hearings and entities
        mock_result_multi = MagicMock()
        mock_result_multi.fetchall.return_value = [mock_row]

        # Return predefined mock results for the sequential execute calls
        mock_conn.execute.side_effect = [
            mock_result_single,  # Courts
            mock_result_single,  # Cases
            mock_result_multi,  # Entities
            mock_result_multi,  # Hearings
        ]

        mock_engine.connect.return_value.__enter__.return_value = mock_conn
        mock_create_engine.return_value = mock_engine

        import asyncio

        result = asyncio.run(self.tool.execute(self.valid_args))

        # Validate successful execution
        assert '{"success": true' in result[0].text
        assert mock_makedirs.called
        mock_file_open.assert_called_with("/tmp/test_output.md", "w", encoding="utf-8")

        # Verify content written includes formatted markdown
        handle = mock_file_open()
        written_content = "".join(
            [call.args[0] for call in handle.write.call_args_list]
        )
        assert "Test Court" in written_content
