"""Unit tests for memory CLI commands and time parsing."""

from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path

import pytest
from click.testing import CliRunner

from prometh_cortex.cli.commands.memory import memory
from prometh_cortex.utils.time_parser import (
    parse_relative_time,
    parse_absolute_date,
    parse_time_filter,
    format_timestamp,
)
from prometh_cortex.indexer import DocumentIndexer, IndexerError


class TestTimeParser:
    """Tests for time parsing utilities."""

    def test_parse_relative_time_days(self):
        """Test parsing relative time in days."""
        ts = parse_relative_time("7d")
        assert ts is not None
        # Should be approximately 7 days ago
        now_ts = datetime.utcnow().timestamp()
        diff_days = (now_ts - ts) / (24 * 3600)
        assert 6.9 < diff_days < 7.1

    def test_parse_relative_time_weeks(self):
        """Test parsing relative time in weeks."""
        ts = parse_relative_time("2w")
        assert ts is not None
        now_ts = datetime.utcnow().timestamp()
        diff_days = (now_ts - ts) / (24 * 3600)
        assert 13.9 < diff_days < 14.1

    def test_parse_relative_time_hours(self):
        """Test parsing relative time in hours."""
        ts = parse_relative_time("24h")
        assert ts is not None
        now_ts = datetime.utcnow().timestamp()
        diff_hours = (now_ts - ts) / 3600
        assert 23.9 < diff_hours < 24.1

    def test_parse_relative_time_minutes(self):
        """Test parsing relative time in minutes."""
        ts = parse_relative_time("30m")
        assert ts is not None
        now_ts = datetime.utcnow().timestamp()
        diff_minutes = (now_ts - ts) / 60
        assert 29.9 < diff_minutes < 30.1

    def test_parse_relative_time_invalid(self):
        """Test that invalid relative times return None."""
        assert parse_relative_time("invalid") is None
        assert parse_relative_time("7x") is None
        assert parse_relative_time("") is None
        assert parse_relative_time("d") is None

    def test_parse_absolute_date_iso(self):
        """Test parsing absolute ISO date."""
        ts = parse_absolute_date("2026-03-01")
        assert ts is not None
        dt = datetime.utcfromtimestamp(ts)
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 1

    def test_parse_absolute_date_with_time(self):
        """Test parsing absolute ISO datetime."""
        ts = parse_absolute_date("2026-03-01T12:30:45")
        assert ts is not None
        dt = datetime.utcfromtimestamp(ts)
        assert dt.year == 2026
        assert dt.month == 3
        assert dt.day == 1
        assert dt.hour == 12
        assert dt.minute == 30
        assert dt.second == 45

    def test_parse_absolute_date_invalid(self):
        """Test that invalid absolute dates return None."""
        assert parse_absolute_date("2026-13-01") is None
        assert parse_absolute_date("invalid-date") is None
        assert parse_absolute_date("") is None

    def test_parse_time_filter_relative(self):
        """Test parse_time_filter with relative format."""
        ts = parse_time_filter("7d")
        assert ts is not None
        now_ts = datetime.utcnow().timestamp()
        diff_days = (now_ts - ts) / (24 * 3600)
        assert 6.9 < diff_days < 7.1

    def test_parse_time_filter_absolute(self):
        """Test parse_time_filter with absolute format."""
        ts = parse_time_filter("2026-03-01")
        assert ts is not None
        dt = datetime.utcfromtimestamp(ts)
        assert dt.year == 2026

    def test_parse_time_filter_tries_relative_first(self):
        """Test that parse_time_filter tries relative format first."""
        # This could be parsed as either format, but relative should win
        ts = parse_time_filter("7d")
        assert ts is not None

    def test_parse_time_filter_invalid(self):
        """Test that invalid expressions return None."""
        assert parse_time_filter("invalid") is None
        assert parse_time_filter("") is None

    def test_format_timestamp(self):
        """Test formatting timestamp to readable string."""
        ts = datetime(2026, 3, 1, 12, 30, 45).timestamp()
        formatted = format_timestamp(ts)
        assert "2026" in formatted
        assert "03" in formatted
        assert "01" in formatted


class TestMemoryListCommand:
    """Tests for memory list command."""

    def test_memory_list_no_memories(self):
        """Test listing memories when none exist."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []

            mock_config = Mock()
            result = runner.invoke(memory, ["list"], obj={"config": mock_config, "verbose": False})
            assert result.exit_code == 0
            assert "No memories found" in result.output

    def test_memory_list_with_memories(self):
        """Test listing memories when they exist."""
        runner = CliRunner()

        mock_memories = [
            {
                "document_id": "memory_abc123",
                "title": "Session Summary",
                "created": "2026-04-20T10:00:00Z",
                "tags": ["session", "review"],
                "metadata": {"project": "test"},
            },
            {
                "document_id": "memory_def456",
                "title": "Decision Log",
                "created": "2026-04-19T15:30:00Z",
                "tags": ["decision"],
                "metadata": {"project": "prod"},
            },
        ]

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = mock_memories

            mock_config = Mock()
            result = runner.invoke(memory, ["list"], obj={"config": mock_config, "verbose": False})
            assert result.exit_code == 0
            assert "Memory Documents" in result.output
            assert "Session Summary" in result.output
            assert "Decision Log" in result.output

    def test_memory_list_with_since_filter(self):
        """Test listing memories with --since filter."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []

            mock_config = Mock()
            result = runner.invoke(memory, ["list", "--since", "7d"], obj={"config": mock_config, "verbose": False})
            assert result.exit_code == 0

    def test_memory_list_with_invalid_since(self):
        """Test listing memories with invalid --since format."""
        runner = CliRunner()

        mock_config = Mock()
        result = runner.invoke(memory, ["list", "--since", "invalid"], obj={"config": mock_config, "verbose": False})
        assert result.exit_code == 1
        assert "Invalid time format" in result.output

    def test_memory_list_with_project_filter(self):
        """Test listing memories with --project filter."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []

            mock_config = Mock()
            result = runner.invoke(memory, ["list", "--project", "myproject"], obj={"config": mock_config, "verbose": False})
            assert result.exit_code == 0

    def test_memory_list_with_tag_filter(self):
        """Test listing memories with --tag filter."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []

            mock_config = Mock()
            result = runner.invoke(memory, ["list", "--tag", "session"], obj={"config": mock_config, "verbose": False})
            assert result.exit_code == 0


class TestMemoryForgetCommand:
    """Tests for memory forget command."""

    def test_memory_forget_requires_filter(self):
        """Test that memory forget requires at least one filter."""
        runner = CliRunner()

        mock_config = Mock()
        result = runner.invoke(memory, ["forget"], obj={"config": mock_config, "verbose": False})
        assert result.exit_code == 1
        assert "No Filters" in result.output

    def test_memory_forget_all_with_confirm(self):
        """Test memory forget --all with --confirm flag."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = [
                {
                    "document_id": "memory_abc123",
                    "title": "Session",
                    "created": "2026-04-20T10:00:00Z",
                }
            ]
            mock_indexer.delete_memory_documents.return_value = 1

            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--all", "--dry-run"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_indexer.delete_memory_documents.assert_not_called()

    def test_memory_forget_all_requires_confirmation(self):
        """Test that memory forget --all requires confirmation without --confirm."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = [
                {
                    "document_id": "memory_abc123",
                    "title": "Session",
                    "created": "2026-04-20T10:00:00Z",
                }
            ]

            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--all"], input="n\n", obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Cancelled" in result.output

    def test_memory_forget_by_expiry(self):
        """Test memory forget by expiry with --dry-run."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []
            mock_indexer.delete_memory_documents.return_value = 5

            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--expiry", "30d", "--dry-run"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_indexer.delete_memory_documents.assert_not_called()

    def test_memory_forget_by_project(self):
        """Test memory forget by project with --dry-run."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []
            mock_indexer.delete_memory_documents.return_value = 3

            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--project", "archive", "--dry-run"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_indexer.delete_memory_documents.assert_not_called()

    def test_memory_forget_by_id(self):
        """Test memory forget by specific document ID with --dry-run."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.delete_memory_documents.return_value = 1

            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--id", "memory_abc123", "--dry-run"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_indexer.delete_memory_documents.assert_not_called()

    def test_memory_forget_with_invalid_expiry(self):
        """Test that invalid expiry format is handled."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.initialize.return_value = None
            
            mock_config = Mock()
            result = runner.invoke(
                memory, ["forget", "--expiry", "invalid", "--confirm"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 1
            assert "Invalid time format" in result.output

    def test_memory_forget_combined_filters(self):
        """Test memory forget with combined filters and --dry-run."""
        runner = CliRunner()

        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_indexer_class:
            mock_indexer = MagicMock()
            mock_indexer_class.return_value = mock_indexer
            mock_indexer.initialize.return_value = None
            mock_indexer.list_memory_documents.return_value = []
            mock_indexer.delete_memory_documents.return_value = 2

            mock_config = Mock()
            result = runner.invoke(
                memory,
                [
                    "forget",
                    "--expiry",
                    "7d",
                    "--project",
                    "archive",
                    "--dry-run",
                ],
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_indexer.delete_memory_documents.assert_not_called()


class TestIndexerMemoryMethods:
    """Tests for DocumentIndexer memory methods."""

    def test_list_memories_delegates_to_vector_store(self):
        """Test that list_memories delegates to vector_store."""
        config = Mock()
        config.embedding_model = "test-model"

        with patch(
            "prometh_cortex.indexer.document_indexer.create_vector_store"
        ) as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.list_memory_documents.return_value = [{"document_id": "test"}]

            indexer = DocumentIndexer(config)
            result = indexer.list_memory_documents(since=None, project=None, tag=None)

            assert result == [{"document_id": "test"}]
            mock_vs.list_memory_documents.assert_called_once()

    def test_delete_memories_delegates_to_vector_store(self):
        """Test that delete_memories delegates to vector_store."""
        config = Mock()
        config.embedding_model = "test-model"

        with patch(
            "prometh_cortex.indexer.document_indexer.create_vector_store"
        ) as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.delete_memory_documents.return_value = 2

            indexer = DocumentIndexer(config)
            result = indexer.delete_memories(["memory_1", "memory_2"])

            assert result == 2
            mock_vs.delete_memory_documents.assert_called_once_with(
                ["memory_1", "memory_2"]
            )

    def test_clear_memories_all(self):
        """Test clear_memories with all_ flag."""
        config = Mock()
        config.embedding_model = "test-model"

        with patch(
            "prometh_cortex.indexer.document_indexer.create_vector_store"
        ) as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "memory_1"},
                {"document_id": "memory_2"},
            ]
            mock_vs.delete_memory_documents.return_value = 2

            indexer = DocumentIndexer(config)
            result = indexer.delete_memory_documents(all_=True)

            assert result == 2

    def test_clear_memories_by_expiry(self):
        """Test clear_memories with expiry filter."""
        config = Mock()
        config.embedding_model = "test-model"

        expiry_ts = (datetime.utcnow() - timedelta(days=7)).timestamp()

        with patch(
            "prometh_cortex.indexer.document_indexer.create_vector_store"
        ) as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "memory_old"}
            ]
            mock_vs.delete_memory_documents.return_value = 1

            indexer = DocumentIndexer(config)
            result = indexer.delete_memory_documents(expiry=expiry_ts)

            assert result == 1

    def test_clear_memories_by_project(self):
        """Test clear_memories with project filter."""
        config = Mock()
        config.embedding_model = "test-model"

        with patch(
            "prometh_cortex.indexer.document_indexer.create_vector_store"
        ) as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "memory_1"}
            ]
            mock_vs.delete_memory_documents.return_value = 1

            indexer = DocumentIndexer(config)
            result = indexer.delete_memory_documents(project="archive")

            assert result == 1
            mock_vs.list_memory_documents.assert_called_once_with(
                since=None, project="archive", tag=None
            )

    def test_clear_memories_by_id(self):
        """Test clear_memories with specific document ID."""
        config = Mock()
        config.embedding_model = "test-model"

        with patch(
             "prometh_cortex.indexer.document_indexer.create_vector_store"
         ) as mock_create_vs:
             mock_vs = MagicMock()
             mock_create_vs.return_value = mock_vs
             mock_vs.delete_memory_documents.return_value = 1

             indexer = DocumentIndexer(config)
             result = indexer.delete_memory_documents(doc_id="memory_abc123")

             assert result == 1
             mock_vs.delete_memory_documents.assert_called_once_with(["memory_abc123"])


class TestMemoryForgetExpirySemantics:
    """Critical tests to prevent expiry date logic errors."""

    def test_expiry_date_deletes_only_older_documents(self):
        """CRITICAL: --expiry 2026-03-01 should delete docs OLDER than 2026-03-01.
        
        This test prevents regression of the bug where all documents were deleted
        because the filter was inverted (deleting docs created AFTER the date).
        """
        runner = CliRunner()
        
        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            
            # Mock list_memory_documents to return documents with various dates
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "doc1", "title": "Old Doc", "created": "2026-01-15T10:00:00"},
                {"document_id": "doc2", "title": "New Doc", "created": "2026-04-15T10:00:00"},
            ]
            
            mock_config = Mock()
            result = runner.invoke(
                memory,
                ["forget", "--expiry", "2026-03-01", "--dry-run"],
                obj={"config": mock_config, "verbose": False}
            )
            
            # Should succeed with dry-run
            assert result.exit_code == 0, f"Exit code {result.exit_code}, output: {result.output}"
            assert "Dry-run mode" in result.output
            # Should NOT have called delete (it's a dry-run)
            mock_vs.delete_memory_documents.assert_not_called()

    def test_expiry_relative_deletes_only_old_docs(self):
        """CRITICAL: --expiry 7d should delete docs older than 7 days ago."""
        runner = CliRunner()
        
        now = datetime.utcnow()
        old_date = (now - timedelta(days=10)).isoformat()  # 10 days ago (should delete)
        new_date = (now - timedelta(days=3)).isoformat()   # 3 days ago (should keep)
        
        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "old", "title": "Old", "created": old_date},
                {"document_id": "new", "title": "New", "created": new_date},
            ]
            
            mock_config = Mock()
            result = runner.invoke(
                memory,
                ["forget", "--expiry", "7d", "--dry-run"],
                obj={"config": mock_config, "verbose": False}
            )
            
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            mock_vs.delete_memory_documents.assert_not_called()

    def test_dry_run_does_not_delete(self):
        """CRITICAL: --dry-run should show preview without deleting."""
        runner = CliRunner()
        
        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "doc1", "title": "Test Doc", "created": "2026-01-01T10:00:00"},
            ]
            
            mock_config = Mock()
            result = runner.invoke(
                memory,
                ["forget", "--all", "--dry-run"],
                obj={"config": mock_config, "verbose": False}
            )
            
            assert result.exit_code == 0
            assert "Dry-run mode" in result.output
            # delete_memory_documents should NOT have been called
            mock_vs.delete_memory_documents.assert_not_called()

    def test_clear_all_still_requires_confirm_unless_dry_run(self):
        """CRITICAL: --all without --confirm should prompt, even with --dry-run."""
        runner = CliRunner()
        
        with patch("prometh_cortex.cli.commands.memory.create_vector_store") as mock_create_vs:
            mock_vs = MagicMock()
            mock_create_vs.return_value = mock_vs
            mock_vs.list_memory_documents.return_value = [
                {"document_id": "doc1", "title": "Test", "created": "2026-01-01T10:00:00"},
            ]
            
            mock_config = Mock()
            # Provide 'n' (no) to the confirmation prompt
            result = runner.invoke(
                memory,
                ["forget", "--all"],
                input="n\n",
                obj={"config": mock_config, "verbose": False}
            )
            
            assert result.exit_code == 0
            assert "Cancelled" in result.output
            mock_vs.delete_memory_documents.assert_not_called()


def _create_mock_config():
    """Create a mock config with required attributes for DocumentIndexer."""
    mock_config = Mock()
    mock_config.structured_query_core_fields = []
    mock_config.structured_query_extended_fields = []
    return mock_config



class TestMemoryDreamCommand:
    """Tests for memory dream command (consolidation workflow)."""
    
    def test_memory_dream_requires_project(self):
        """Test that memory dream requires --project flag."""
        runner = CliRunner()
        mock_config = Mock()
        result = runner.invoke(memory, ["dream"], obj={"config": mock_config, "verbose": False})
        assert result.exit_code != 0
        assert "Missing option" in result.output or "Error" in result.output

    def test_memory_dream_prepare_no_memories(self):
        """Test prepare mode with no memories to consolidate."""
        runner = CliRunner()

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.list_memories.return_value = []

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory, ["dream", "--project", "myproject"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "No memories found for consolidation" in result.output

    def test_memory_dream_prepare_with_episodic_memories(self):
        """Test prepare mode showing episodic memories for consolidation."""
        runner = CliRunner()

        episodic_memories = [
            {
                "document_id": "memory_ep1",
                "title": "Event 1",
                "created": "2026-05-01T10:00:00Z",
                "memory_type": "episodic",
                "dreaming": False,
            },
            {
                "document_id": "memory_ep2",
                "title": "Event 2",
                "created": "2026-05-02T15:30:00Z",
                "memory_type": "episodic",
                "dreaming": False,
            },
        ]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.list_memories.return_value = episodic_memories

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory, ["dream", "--project", "myproject"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dream Prepare" in result.output
            assert "Event 1" in result.output
            assert "Event 2" in result.output
            assert "Next steps" in result.output

    def test_memory_dream_prepare_with_prior_semantic(self):
        """Test prepare mode showing prior semantic memories."""
        runner = CliRunner()

        all_memories = [
            {
                "document_id": "memory_ep1",
                "title": "Event",
                "created": "2026-05-01T10:00:00Z",
                "memory_type": "episodic",
                "dreaming": False,
            },
            {
                "document_id": "memory_sem1",
                "title": "Previous Summary",
                "created": "2026-04-20T09:00:00Z",
                "memory_type": "semantic",
                "dreaming": False,
            },
        ]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.list_memories.return_value = all_memories

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory, ["dream", "--project", "myproject"], obj={"config": mock_config, "verbose": False}
            )
            assert result.exit_code == 0
            assert "Dream Prepare" in result.output
            assert "Event" in result.output
            assert "Previous Summary" in result.output

    def test_memory_dream_revert_consolidation_not_found(self):
        """Test revert with non-existent consolidation ID."""
        runner = CliRunner()

        mock_store = MagicMock()
        mock_store.initialize.return_value = None
        mock_store.list_memory_documents.return_value = []

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer), \
             patch("prometh_cortex.cli.commands.memory.create_vector_store", return_value=mock_store):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory,
                ["dream", "--project", "myproject", "--revert", "nonexistent_id"],
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 1
            assert "Consolidated memory not found" in result.output

    def test_memory_dream_revert_with_confirmation(self):
        """Test revert mode with user confirmation."""
        runner = CliRunner()

        consolidated_memory = {
            "document_id": "memory_cons1",
            "title": "Consolidated Summary",
            "created": "2026-05-01T12:00:00Z",
            "source_memories": ["memory_ep1", "memory_ep2"],
            "supersedes": ["memory_sem1"],
            "dreaming": True,
        }

        mock_store = MagicMock()
        mock_store.initialize.return_value = None
        mock_store.list_memory_documents.return_value = [consolidated_memory]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.update_memory_metadata.return_value = None
        mock_indexer.delete_memories.return_value = None

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer), \
             patch("prometh_cortex.cli.commands.memory.create_vector_store", return_value=mock_store):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory,
                ["dream", "--project", "myproject", "--revert", "memory_cons1"],
                input="y\n",
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 0
            assert "Revert Preview" in result.output
            assert "2 source episodic" in result.output
            assert "1 superseded semantic" in result.output
            assert "Revert successful" in result.output
            mock_indexer.update_memory_metadata.assert_called()

    def test_memory_dream_revert_with_keep_consolidated(self):
        """Test revert with --keep-consolidated flag."""
        runner = CliRunner()

        consolidated_memory = {
            "document_id": "memory_cons1",
            "title": "Consolidated Summary",
            "created": "2026-05-01T12:00:00Z",
            "source_memories": ["memory_ep1", "memory_ep2"],
            "supersedes": [],
            "dreaming": True,
        }

        mock_store = MagicMock()
        mock_store.initialize.return_value = None
        mock_store.list_memory_documents.return_value = [consolidated_memory]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.update_memory_metadata.return_value = None
        mock_indexer.delete_memories.return_value = None

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer), \
             patch("prometh_cortex.cli.commands.memory.create_vector_store", return_value=mock_store):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory,
                ["dream", "--project", "myproject", "--revert", "memory_cons1", "--keep-consolidated", "--confirm"],
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 0
            assert "Revert successful" in result.output
            assert "kept" in result.output.lower()
            # Should NOT call delete_memories when --keep-consolidated is set
            mock_indexer.delete_memories.assert_not_called()

    def test_memory_dream_revert_cancellation(self):
        """Test revert cancellation when user declines."""
        runner = CliRunner()

        consolidated_memory = {
            "document_id": "memory_cons1",
            "title": "Consolidated Summary",
            "source_memories": ["memory_ep1"],
            "supersedes": [],
        }

        mock_store = MagicMock()
        mock_store.initialize.return_value = None
        mock_store.list_memory_documents.return_value = [consolidated_memory]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer), \
             patch("prometh_cortex.cli.commands.memory.create_vector_store", return_value=mock_store):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory,
                ["dream", "--project", "myproject", "--revert", "memory_cons1"],
                input="n\n",
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 0
            assert "Cancelled" in result.output
            mock_indexer.update_memory_metadata.assert_not_called()

    def test_memory_dream_revert_with_confirm_flag(self):
        """Test revert with --confirm flag skips confirmation prompt."""
        runner = CliRunner()

        consolidated_memory = {
            "document_id": "memory_cons1",
            "title": "Consolidated Summary",
            "source_memories": ["memory_ep1"],
            "supersedes": [],
        }

        mock_store = MagicMock()
        mock_store.initialize.return_value = None
        mock_store.list_memory_documents.return_value = [consolidated_memory]

        mock_indexer = MagicMock()
        mock_indexer.initialize.return_value = None
        mock_indexer.update_memory_metadata.return_value = None
        mock_indexer.delete_memories.return_value = None

        with patch("prometh_cortex.cli.commands.memory.DocumentIndexer", return_value=mock_indexer), \
             patch("prometh_cortex.cli.commands.memory.create_vector_store", return_value=mock_store):
            mock_config = _create_mock_config()
            result = runner.invoke(
                memory,
                ["dream", "--project", "myproject", "--revert", "memory_cons1", "--confirm"],
                obj={"config": mock_config, "verbose": False},
            )
            assert result.exit_code == 0
            assert "Revert successful" in result.output
            mock_indexer.update_memory_metadata.assert_called()
            mock_indexer.delete_memories.assert_called_once()
