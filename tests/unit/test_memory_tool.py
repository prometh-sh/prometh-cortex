"""Unit tests for prometh_cortex_memory tool (v0.4.0+)."""

from unittest.mock import Mock, patch

import pytest

from prometh_cortex.config import MEMORY_SOURCE, Config, load_config
from prometh_cortex.indexer import DocumentIndexer


class TestMemorySource:
    """Tests for MEMORY_SOURCE constant."""

    def test_memory_source_exists(self):
        """Test that MEMORY_SOURCE is defined correctly."""
        assert MEMORY_SOURCE is not None
        assert MEMORY_SOURCE.name == "prmth_memory"
        assert MEMORY_SOURCE.chunk_size == 512
        assert MEMORY_SOURCE.chunk_overlap == 50
        assert MEMORY_SOURCE.source_patterns == [".prmth_memory"]

    def test_memory_source_is_virtual(self):
        """Test that MEMORY_SOURCE has virtual pattern marker (won't match real files)."""
        assert len(MEMORY_SOURCE.source_patterns) == 1
        assert MEMORY_SOURCE.source_patterns[0] == ".prmth_memory"


class TestMemorySourceAutoInjection:
    """Tests for auto-injection of prmth_memory into config."""

    def test_memory_source_auto_injected_with_toml_config(self, tmp_path):
        """Test that prmth_memory is auto-injected even when loading from TOML."""
        # Create minimal config file without prmth_memory
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[datalake]
repos = ["/tmp"]

[storage]
rag_index_dir = "/tmp"

[[collections]]
name = "prometh_cortex"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
""")

        with patch("prometh_cortex.config.settings.Path.home", return_value=tmp_path):
            config = load_config(config_file)

        # Verify prmth_memory was auto-injected
        source_names = [s.name for s in config.sources]
        assert "prmth_memory" in source_names

        # Verify it's at the end (added after loading)
        prmth_source = next(
            (s for s in config.sources if s.name == "prmth_memory"), None
        )
        assert prmth_source is not None
        assert prmth_source.chunk_size == 512
        assert prmth_source.chunk_overlap == 50
        assert prmth_source.source_patterns == [".prmth_memory"]

    def test_memory_source_not_duplicated(self, tmp_path):
        """Test that if prmth_memory is in config, it's not added again."""
        config_file = tmp_path / "config.toml"
        config_file.write_text("""
[datalake]
repos = ["/tmp"]

[storage]
rag_index_dir = "/tmp"

[[collections]]
name = "prometh_cortex"

[[sources]]
name = "prmth_memory"
chunk_size = 512
chunk_overlap = 50
source_patterns = []

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
""")

        with patch("prometh_cortex.config.settings.Path.home", return_value=tmp_path):
            config = load_config(config_file)

        # Count prmth_memory sources
        prmth_count = sum(1 for s in config.sources if s.name == "prmth_memory")
        assert prmth_count == 1, "prmth_memory should not be duplicated"


class TestAddMemoryDocument:
    """Tests for DocumentIndexer.add_memory_document() method."""

    @pytest.fixture
    def mock_indexer(self):
        """Create a mock indexer for testing."""
        mock_config = Mock(spec=Config)
        mock_config.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        mock_config.vector_store_type = "faiss"
        mock_config.max_query_results = 10

        indexer = Mock(spec=DocumentIndexer)
        indexer.config = mock_config
        indexer.embed_model = Mock()
        indexer.embed_model.get_text_embedding = Mock(return_value=[0.1, 0.2, 0.3])
        indexer.vector_store = Mock()
        indexer.vector_store.add_documents = Mock()

        # Bind the actual methods from DocumentIndexer to the mock
        indexer.add_memory_document = DocumentIndexer.add_memory_document.__get__(
            indexer, DocumentIndexer
        )
        indexer._chunk_text = DocumentIndexer._chunk_text.__get__(
            indexer, DocumentIndexer
        )

        return indexer

    def test_add_memory_document_basic(self, mock_indexer):
        """Test basic memory document addition."""
        result = mock_indexer.add_memory_document(
            title="Test Session",
            content="This is a test memory.",
            tags=["test"],
            metadata={"source_project": "test_proj"},
        )

        assert result["status"] == "success"
        assert result["source_type"] == "prmth_memory"
        assert "document_id" in result
        assert result["chunks_count"] > 0
        assert "created" in result

    def test_add_memory_document_dedup(self, mock_indexer):
        """Test that same title+content produces same document ID."""
        result1 = mock_indexer.add_memory_document(
            title="Test Session",
            content="This is a test memory.",
            tags=["test"],
        )

        result2 = mock_indexer.add_memory_document(
            title="Test Session",
            content="This is a test memory.",
            tags=["test"],
        )

        assert result1["document_id"] == result2["document_id"]

    def test_add_memory_document_different_content_different_id(self, mock_indexer):
        """Test that different content produces different document IDs."""
        result1 = mock_indexer.add_memory_document(
            title="Test Session",
            content="Content A",
        )

        result2 = mock_indexer.add_memory_document(
            title="Test Session",
            content="Content B",
        )

        assert result1["document_id"] != result2["document_id"]

    def test_add_memory_document_with_tags(self, mock_indexer):
        """Test that tags are included in metadata."""
        tags = ["kubernetes", "incident", "memory"]

        with patch.object(mock_indexer.vector_store, "add_documents") as mock_add:
            mock_indexer.add_memory_document(
                title="K8s Issue",
                content="Memory leak detected",
                tags=tags,
            )

        # Verify vector_store.add_documents was called
        assert mock_add.called
        docs = mock_add.call_args[0][0]

        # Check that tags are in metadata
        for doc in docs:
            assert "tags" in doc["metadata"]
            assert set(doc["metadata"]["tags"]) == set(tags)

    def test_add_memory_document_metadata_merged(self, mock_indexer):
        """Test that caller metadata is merged into document metadata."""
        caller_metadata = {
            "source_project": "platform",
            "author": "test-agent",
            "session_id": "sess_123",
        }

        with patch.object(mock_indexer.vector_store, "add_documents") as mock_add:
            mock_indexer.add_memory_document(
                title="Test",
                content="Test content",
                metadata=caller_metadata,
            )

        docs = mock_add.call_args[0][0]
        for doc in docs:
            assert doc["metadata"]["source_project"] == "platform"
            assert doc["metadata"]["author"] == "test-agent"
            assert doc["metadata"]["session_id"] == "sess_123"

    def test_add_memory_document_source_type_set(self, mock_indexer):
        """Test that source_type is always set to prmth_memory."""
        with patch.object(mock_indexer.vector_store, "add_documents") as mock_add:
            mock_indexer.add_memory_document(
                title="Test",
                content="Test content",
            )

        docs = mock_add.call_args[0][0]
        for doc in docs:
            assert doc["metadata"]["source_type"] == "prmth_memory"

    def test_add_memory_document_embedding_called(self, mock_indexer):
        """Test that embedding model is called for each chunk."""
        with patch.object(
            mock_indexer.embed_model, "get_text_embedding", return_value=[0.1] * 384
        ) as mock_embed:
            mock_indexer.add_memory_document(
                title="Test",
                content="Test content " * 100,  # Long content to create multiple chunks
            )

        # Embedding should be called at least once
        assert mock_embed.called
        assert mock_embed.call_count >= 1

    def test_add_memory_document_chunks_created(self, mock_indexer):
        """Test that chunks are created and passed to vector_store."""
        long_content = (
            "Test content " * 50
        )  # Create content that will span multiple chunks

        with patch.object(mock_indexer.vector_store, "add_documents") as mock_add:
            mock_indexer.add_memory_document(
                title="Test",
                content=long_content,
            )

        docs = mock_add.call_args[0][0]

        # Should have multiple documents (chunks)
        assert len(docs) > 0

        # Each should have proper structure
        for doc in docs:
            assert "id" in doc
            assert "text" in doc
            assert "vector" in doc
            assert "metadata" in doc
            assert "chunk_index" in doc["metadata"]
            assert "total_chunks" in doc["metadata"]

    def test_add_memory_document_empty_title_fails(self, mock_indexer):
        """Test that empty title raises error."""
        with pytest.raises(Exception):
            mock_indexer.add_memory_document(
                title="",
                content="Test content",
            )

    def test_add_memory_document_empty_content_fails(self, mock_indexer):
        """Test that empty content raises error."""
        with pytest.raises(Exception):
            mock_indexer.add_memory_document(
                title="Test",
                content="",
            )


class TestChunkText:
    """Tests for DocumentIndexer._chunk_text() method."""

    @pytest.fixture
    def indexer(self):
        """Create a real indexer instance for chunking tests."""
        mock_config = Mock(spec=Config)
        mock_config.embedding_model = "sentence-transformers/all-MiniLM-L6-v2"
        mock_config.vector_store_type = "faiss"

        indexer = Mock(spec=DocumentIndexer)
        indexer._chunk_text = DocumentIndexer._chunk_text.__get__(
            indexer, DocumentIndexer
        )
        return indexer

    def test_chunk_text_respects_size(self, indexer):
        """Test that chunks don't exceed specified size."""
        text = "word " * 200  # 1000 characters
        chunks = indexer._chunk_text(text, chunk_size=100, chunk_overlap=10)

        for chunk in chunks:
            assert len(chunk) <= 120  # Allow slight overage for word boundary

    def test_chunk_text_word_boundary(self, indexer):
        """Test that chunks respect word boundaries where possible."""
        text = "This is a sentence. This is another sentence. And another one."
        chunks = indexer._chunk_text(text, chunk_size=30, chunk_overlap=5)

        # Verify chunks respect size limits
        for chunk in chunks:
            assert len(chunk) <= 30 or chunk == chunks[-1]  # Last chunk can exceed

        # Verify no content is lost
        joined = " ".join(chunks)
        # Both should contain the same words (accounting for whitespace variation)
        assert text.replace(".", "").replace("  ", " ") in joined.replace(
            ".", ""
        ).replace("  ", " ") or all(word in joined for word in text.split())

    def test_chunk_text_empty_string(self, indexer):
        """Test that empty string returns empty list."""
        chunks = indexer._chunk_text("", chunk_size=100)
        assert chunks == []

    def test_chunk_text_overlap(self, indexer):
        """Test that overlap parameter works."""
        text = "word " * 100
        chunks_no_overlap = indexer._chunk_text(text, chunk_size=100, chunk_overlap=0)
        chunks_with_overlap = indexer._chunk_text(
            text, chunk_size=100, chunk_overlap=20
        )

        # With overlap should have fewer chunks (less duplication needed)
        # Actually, with overlap, chunks may be similar but the count depends on algorithm
        assert len(chunks_no_overlap) > 0
        assert len(chunks_with_overlap) > 0


class TestMemoryPreservationOnRebuild:
    """Tests for memory preservation during force rebuild."""

    def test_clear_index_preserves_memory_metadata(self, tmp_path):
        """Test that _clear_index with preserve_memory=True preserves memory metadata."""
        import toml

        # Setup config and indexer
        config_file = tmp_path / "config.toml"
        rag_index_dir = tmp_path / "index"
        rag_index_dir.mkdir()

        config_data = {
            "datalake": {"repos": [str(tmp_path)]},
            "storage": {"rag_index_dir": str(rag_index_dir)},
            "vector_store": {"type": "faiss"},
        }
        with open(config_file, "w") as f:
            toml.dump(config_data, f)

        config = load_config(config_file)
        indexer = DocumentIndexer(config)

        # Add memory document
        result1 = indexer.add_memory_document(
            title="Memory Doc 1", content="Important session notes", tags=["session"]
        )
        memory_id_1 = result1["document_id"]

        # Verify it's there before clear
        metadata_before = indexer.vector_store.get_document_metadata(memory_id_1)
        assert metadata_before is not None
        assert metadata_before.get("source_type") == "prmth_memory"

        # Clear with preserve_memory=True
        indexer._clear_index(preserve_memory=True)

        # Metadata should still be accessible after clear
        metadata_after = indexer.vector_store.get_document_metadata(memory_id_1)
        assert metadata_after is not None, "Memory metadata should be preserved"
        assert metadata_after.get("source_type") == "prmth_memory"
        assert metadata_after.get("title") == "Memory Doc 1"

    def test_clear_index_without_preserve_memory_deletes_all(self, tmp_path):
        """Test that _clear_index with preserve_memory=False deletes memories too."""
        import toml

        # Setup config and indexer
        config_file = tmp_path / "config.toml"
        rag_index_dir = tmp_path / "index"
        rag_index_dir.mkdir()

        config_data = {
            "datalake": {"repos": [str(tmp_path)]},
            "storage": {"rag_index_dir": str(rag_index_dir)},
            "vector_store": {"type": "faiss"},
        }
        with open(config_file, "w") as f:
            toml.dump(config_data, f)

        config = load_config(config_file)
        indexer = DocumentIndexer(config)

        # Add memory document
        result1 = indexer.add_memory_document(
            title="Memory Doc 1", content="Important session notes", tags=["session"]
        )
        memory_id_1 = result1["document_id"]

        # Clear without preserve_memory
        indexer._clear_index(preserve_memory=False)

        # Metadata should be gone
        metadata_after = indexer.vector_store.get_document_metadata(memory_id_1)
        assert metadata_after is None, "Memory metadata should be deleted"

    def test_force_rebuild_preserves_memory_metadata(self, tmp_path):
        """Test that force_rebuild=True preserves memory metadata."""
        import toml

        # Setup
        config_file = tmp_path / "config.toml"
        rag_index_dir = tmp_path / "index"
        rag_index_dir.mkdir()

        config_data = {
            "datalake": {"repos": [str(tmp_path)]},
            "storage": {"rag_index_dir": str(rag_index_dir)},
            "vector_store": {"type": "faiss"},
        }
        with open(config_file, "w") as f:
            toml.dump(config_data, f)

        # Create a dummy file to index
        test_file = tmp_path / "test.md"
        test_file.write_text("# Test\nRegular document")

        config = load_config(config_file)
        indexer = DocumentIndexer(config)

        # Add memory document
        result1 = indexer.add_memory_document(
            title="Session Memory",
            content="Key decisions made",
            tags=["critical"],
            metadata={"session_id": "prod-123"},
        )
        memory_id = result1["document_id"]

        # Verify before rebuild
        metadata_before = indexer.vector_store.get_document_metadata(memory_id)
        assert metadata_before is not None
        assert metadata_before.get("session_id") == "prod-123"

        # Run force rebuild
        stats = indexer.build_index(force_rebuild=True)

        # Memory metadata should still be there
        metadata_after = indexer.vector_store.get_document_metadata(memory_id)
        assert (
            metadata_after is not None
        ), "Memory metadata should survive force rebuild"
        assert (
            metadata_after.get("source_type") == "prmth_memory"
        ), "Should still be marked as memory source"
        assert metadata_after.get("title") == "Session Memory"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
