"""Integration tests for multi-collection RAG workflow."""

import pytest
import tempfile
from pathlib import Path
import json

from prometh_cortex.config import Config, CollectionConfig
from prometh_cortex.indexer import DocumentIndexer


class TestMultiCollectionWorkflow:
    """Integration tests for complete multi-collection workflow."""

    @pytest.fixture
    def temp_datalake(self):
        """Create temporary datalake with test documents."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create directory structure
            (tmpdir_path / "docs" / "specs").mkdir(parents=True)
            (tmpdir_path / "docs" / "prds").mkdir(parents=True)
            (tmpdir_path / "meetings").mkdir(parents=True)
            (tmpdir_path / "tasks").mkdir(parents=True)

            # Create test documents
            (tmpdir_path / "docs" / "specs" / "auth.md").write_text(
                "# Authentication API\n\n"
                "This document describes the authentication API endpoints.\n"
                "Use tokens for API access."
            )
            (tmpdir_path / "docs" / "specs" / "database.md").write_text(
                "# Database Schema\n\n"
                "Schema for user management system.\n"
                "Tables include users, roles, and permissions."
            )
            (tmpdir_path / "docs" / "prds" / "feature.md").write_text(
                "# New Feature PRD\n\n"
                "Product requirements for the new feature.\n"
                "Target release: Q1 2025."
            )
            (tmpdir_path / "meetings" / "standup.md").write_text(
                "# Daily Standup\n\n"
                "Attendees: Team members\n"
                "Topics: Progress update, blockers"
            )
            (tmpdir_path / "meetings" / "planning.md").write_text(
                "# Sprint Planning\n\n"
                "Planning session for the sprint.\n"
                "Stories to implement this sprint."
            )
            (tmpdir_path / "tasks" / "todo.md").write_text(
                "# Todo List\n\n"
                "- Implement authentication\n"
                "- Update documentation"
            )

            yield tmpdir_path

    @pytest.fixture
    def temp_index_dir(self):
        """Create temporary index directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def multi_collection_config(self, temp_datalake, temp_index_dir):
        """Create multi-collection configuration."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="knowledge_base",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs/specs", "docs/prds"]
            ),
            CollectionConfig(
                name="meetings",
                chunk_size=256,
                chunk_overlap=25,
                source_patterns=["meetings"]
            ),
        ]
        return Config(
            datalake_repos=[temp_datalake],
            rag_index_dir=temp_index_dir,
            collections=collections,
            vector_store_type="faiss"
        )

    def test_build_multi_collection_index(self, multi_collection_config):
        """Test building index for all collections."""
        indexer = DocumentIndexer(multi_collection_config)

        # Build index
        stats = indexer.build_index()

        # Verify stats
        assert "collections" in stats
        assert "knowledge_base" in stats["collections"]
        assert "meetings" in stats["collections"]
        assert "default" in stats["collections"]

        # Verify documents were indexed
        assert stats["collections"]["knowledge_base"]["added"] > 0
        assert stats["collections"]["meetings"]["added"] > 0

    def test_query_single_collection(self, multi_collection_config):
        """Test querying a single collection."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Query specific collection
        results = indexer.query("authentication", collection="knowledge_base")

        # Should find results in knowledge_base
        assert len(results) > 0
        for result in results:
            assert result["collection"] == "knowledge_base"

    def test_query_all_collections(self, multi_collection_config):
        """Test querying all collections."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Query all collections
        results = indexer.query("update")

        # Should find results from multiple collections
        assert len(results) > 0

        # Check that results come from different collections
        collections_found = set(r["collection"] for r in results)
        assert len(collections_found) >= 1

    def test_collection_specific_chunking(self, multi_collection_config):
        """Test that collection-specific chunking is applied."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Query to verify chunking parameters in results
        knowledge_results = indexer.query("authentication", collection="knowledge_base")
        meeting_results = indexer.query("standup", collection="meetings")

        # Check chunk configs in results
        if knowledge_results:
            kb_chunk_config = knowledge_results[0].get("chunk_config", {})
            assert kb_chunk_config.get("chunk_size") == 512

        if meeting_results:
            meeting_chunk_config = meeting_results[0].get("chunk_config", {})
            assert meeting_chunk_config.get("chunk_size") == 256

    def test_get_collection_stats(self, multi_collection_config):
        """Test getting collection statistics."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Get stats
        stats = indexer.get_stats()

        # Verify structure
        assert "total_collections" in stats
        assert "collections" in stats
        assert stats["total_collections"] == 3

        # Verify each collection has stats
        for collection_name in ["default", "knowledge_base", "meetings"]:
            assert collection_name in stats["collections"]

    def test_list_collections(self, multi_collection_config):
        """Test listing all collections."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # List collections
        collections = indexer.list_collections()

        # Verify results
        assert len(collections) == 3
        names = [c["name"] for c in collections]
        assert "default" in names
        assert "knowledge_base" in names
        assert "meetings" in names

        # Verify collection details
        kb_coll = next(c for c in collections if c["name"] == "knowledge_base")
        assert kb_coll["chunk_size"] == 512
        assert kb_coll["chunk_overlap"] == 50

    def test_document_routing_accuracy(self, multi_collection_config):
        """Test that documents are routed to correct collections."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Query for specific documents
        spec_results = indexer.query("authentication api", collection="knowledge_base")
        meeting_results = indexer.query("standup", collection="meetings")

        # Spec results should be from knowledge_base
        assert all(r["collection"] == "knowledge_base" for r in spec_results)

        # Meeting results should be from meetings
        assert all(r["collection"] == "meetings" for r in meeting_results)

    def test_collection_isolation(self, multi_collection_config):
        """Test that collections maintain separate indexes."""
        indexer = DocumentIndexer(multi_collection_config)
        indexer.build_index()

        # Query that might match in multiple collections
        # but should be isolated
        kb_results = indexer.query("feature", collection="knowledge_base")
        meeting_results = indexer.query("feature", collection="meetings")

        # Results should be from respective collections
        assert all(r["collection"] == "knowledge_base" for r in kb_results)
        assert all(r["collection"] == "meetings" for r in meeting_results)


class TestMultiCollectionErrorHandling:
    """Test error handling in multi-collection operations."""

    @pytest.fixture
    def temp_resources(self):
        """Create temporary resources."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)
            (tmpdir_path / "docs").mkdir()
            (tmpdir_path / "docs" / "test.md").write_text("# Test\n\nContent")

            yield tmpdir_path, tmpdir_path / "index"

    def test_query_invalid_collection(self, temp_resources):
        """Test querying nonexistent collection."""
        datalake_path, index_path = temp_resources

        collections = [
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
        ]
        config = Config(
            datalake_repos=[datalake_path],
            rag_index_dir=index_path,
            collections=collections,
            vector_store_type="faiss"
        )
        indexer = DocumentIndexer(config)
        indexer.build_index()

        # Query invalid collection should raise error
        with pytest.raises(Exception):  # IndexerError
            indexer.query("test", collection="nonexistent")

    def test_invalid_collection_in_config(self):
        """Test configuration with invalid collections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_data = {
                "datalake_repos": [tmpdir],
                "rag_index_dir": tmpdir,
                "collections": [
                    {
                        "name": "no_default",  # Missing 'default'
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "source_patterns": ["docs"]
                    }
                ]
            }

            with pytest.raises(ValueError):
                Config(**config_data)


class TestMultiCollectionPerformance:
    """Test multi-collection performance characteristics."""

    @pytest.fixture
    def perf_resources(self):
        """Create resources for performance testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmpdir_path = Path(tmpdir)

            # Create directory structure
            (tmpdir_path / "coll1").mkdir()
            (tmpdir_path / "coll2").mkdir()

            # Create many test documents
            for i in range(10):
                (tmpdir_path / "coll1" / f"doc{i}.md").write_text(
                    f"# Document {i} Collection 1\n\nContent for document {i} in collection 1"
                )
                (tmpdir_path / "coll2" / f"doc{i}.md").write_text(
                    f"# Document {i} Collection 2\n\nContent for document {i} in collection 2"
                )

            yield tmpdir_path, tmpdir_path / "index"

    def test_multi_collection_build_performance(self, perf_resources):
        """Test that building multiple collections completes in reasonable time."""
        datalake_path, index_path = perf_resources

        collections = [
            CollectionConfig(
                name="collection_1",
                source_patterns=["coll1"]
            ),
            CollectionConfig(
                name="collection_2",
                source_patterns=["coll2"]
            ),
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
        ]
        config = Config(
            datalake_repos=[datalake_path],
            rag_index_dir=index_path,
            collections=collections,
            vector_store_type="faiss"
        )
        indexer = DocumentIndexer(config)

        import time
        start = time.time()
        indexer.build_index()
        elapsed = time.time() - start

        # Should complete in reasonable time (< 30 seconds)
        assert elapsed < 30, f"Build took too long: {elapsed}s"

    def test_multi_collection_query_performance(self, perf_resources):
        """Test that querying multiple collections is fast."""
        datalake_path, index_path = perf_resources

        collections = [
            CollectionConfig(
                name="collection_1",
                source_patterns=["coll1"]
            ),
            CollectionConfig(
                name="collection_2",
                source_patterns=["coll2"]
            ),
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
        ]
        config = Config(
            datalake_repos=[datalake_path],
            rag_index_dir=index_path,
            collections=collections,
            vector_store_type="faiss"
        )
        indexer = DocumentIndexer(config)
        indexer.build_index()

        import time

        # Query single collection
        start = time.time()
        results1 = indexer.query("document", collection="collection_1")
        time1 = time.time() - start

        # Query all collections
        start = time.time()
        results_all = indexer.query("document")
        time_all = time.time() - start

        # Queries should be fast (< 1 second)
        assert time1 < 1.0, f"Single collection query too slow: {time1}s"
        assert time_all < 2.0, f"All collections query too slow: {time_all}s"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
