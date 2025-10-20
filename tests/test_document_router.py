"""Unit tests for DocumentRouter with multi-collection support."""

import pytest
from prometh_cortex.config import CollectionConfig
from prometh_cortex.router import DocumentRouter, RouterError


class TestDocumentRouter:
    """Test suite for DocumentRouter."""

    @pytest.fixture
    def sample_collections(self):
        """Create sample collections for testing."""
        return [
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

    def test_router_initialization(self, sample_collections):
        """Test router initializes correctly with valid collections."""
        router = DocumentRouter(sample_collections)
        assert router is not None
        assert len(router.collections) == 3

    def test_router_requires_default_collection(self):
        """Test router requires 'default' collection."""
        collections = [
            CollectionConfig(
                name="knowledge_base",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs"]
            )
        ]
        with pytest.raises(RouterError, match="default.*required"):
            DocumentRouter(collections)

    def test_router_requires_catchall_pattern(self):
        """Test router requires catch-all '*' pattern."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs"]  # Missing catch-all
            )
        ]
        with pytest.raises(RouterError, match="catch-all"):
            DocumentRouter(collections)

    def test_router_rejects_duplicate_names(self):
        """Test router rejects duplicate collection names."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="default",  # Duplicate
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs"]
            ),
        ]
        with pytest.raises(RouterError, match="Duplicate"):
            DocumentRouter(collections)

    def test_document_routing_exact_match(self, sample_collections):
        """Test routing with exact path matches."""
        router = DocumentRouter(sample_collections)

        # Test exact match for meetings
        assert router.route_document("meetings/standup.md") == "meetings"
        assert router.route_document("meetings/2024-12-08.md") == "meetings"

        # Test exact match for knowledge_base
        assert router.route_document("docs/specs/auth.md") == "knowledge_base"
        assert router.route_document("docs/prds/feature.md") == "knowledge_base"

    def test_document_routing_prefix_match(self, sample_collections):
        """Test routing with prefix matching (longest first)."""
        router = DocumentRouter(sample_collections)

        # docs/specs should match knowledge_base (more specific than *)
        assert router.route_document("docs/specs/api/endpoint.md") == "knowledge_base"

        # docs/other should match default (*) since no pattern matches
        assert router.route_document("docs/other/file.md") == "default"

    def test_document_routing_catchall(self, sample_collections):
        """Test catch-all routing for unmatched paths."""
        router = DocumentRouter(sample_collections)

        # Paths not matching any pattern should go to default
        assert router.route_document("todos/task.md") == "default"
        assert router.route_document("notes/random.md") == "default"
        assert router.route_document("projects/readme.md") == "default"

    def test_document_routing_longest_prefix(self, sample_collections):
        """Test longest-prefix-match algorithm."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="docs",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs"]
            ),
            CollectionConfig(
                name="specs",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs/specs"]
            ),
        ]
        router = DocumentRouter(collections)

        # Should match most specific pattern
        assert router.route_document("docs/specs/api.md") == "specs"
        assert router.route_document("docs/readme.md") == "docs"
        assert router.route_document("other/file.md") == "default"

    def test_get_collection_config(self, sample_collections):
        """Test retrieving collection configuration."""
        router = DocumentRouter(sample_collections)

        config = router.get_collection_config("knowledge_base")
        assert config.name == "knowledge_base"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert "docs/specs" in config.source_patterns

    def test_get_collection_config_nonexistent(self, sample_collections):
        """Test error when getting nonexistent collection."""
        router = DocumentRouter(sample_collections)

        with pytest.raises(RouterError, match="not found"):
            router.get_collection_config("nonexistent")

    def test_list_collections(self, sample_collections):
        """Test listing all collections."""
        router = DocumentRouter(sample_collections)
        collections = router.list_collections()

        assert len(collections) == 3
        names = [c.name for c in collections]
        assert "default" in names
        assert "knowledge_base" in names
        assert "meetings" in names

    def test_get_collection_names(self, sample_collections):
        """Test getting collection names."""
        router = DocumentRouter(sample_collections)
        names = router.get_collection_names()

        assert len(names) == 3
        assert names == ["default", "knowledge_base", "meetings"]  # Sorted

    def test_path_normalization(self, sample_collections):
        """Test that paths are normalized (backslashes to forward slashes)."""
        router = DocumentRouter(sample_collections)

        # Both should route to same collection
        assert router.route_document("docs/specs/api.md") == "knowledge_base"
        assert router.route_document("docs\\specs\\api.md") == "knowledge_base"

    def test_empty_collections_error(self):
        """Test error when no collections provided."""
        with pytest.raises(RouterError, match="At least one collection"):
            DocumentRouter([])

    def test_collection_no_patterns_error(self):
        """Test error when collection has no patterns."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=[]  # Empty patterns
            )
        ]
        with pytest.raises(RouterError, match="must have at least one"):
            DocumentRouter(collections)

    def test_specificity_sorting(self):
        """Test that collections are sorted by specificity."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="docs_long",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["documentation/specs/implementation"]
            ),
            CollectionConfig(
                name="docs_short",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["documentation"]
            ),
        ]
        router = DocumentRouter(collections)

        # More specific pattern should match first
        assert router.route_document("documentation/specs/implementation/api.md") == "docs_long"
        assert router.route_document("documentation/readme.md") == "docs_short"
        assert router.route_document("other/file.md") == "default"


class TestRouterEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_case_sensitivity(self):
        """Test that routing is case-sensitive."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="docs",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["Docs"]  # Capital D
            ),
        ]
        router = DocumentRouter(collections)

        # Should not match different case
        assert router.route_document("docs/file.md") == "default"
        assert router.route_document("Docs/file.md") == "docs"

    def test_special_characters_in_paths(self):
        """Test routing with special characters in paths."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="special",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs-special"]
            ),
        ]
        router = DocumentRouter(collections)

        assert router.route_document("docs-special/file.md") == "special"
        assert router.route_document("docs_other/file.md") == "default"

    def test_deep_nested_paths(self):
        """Test routing with deeply nested paths."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="deep",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["a/b/c/d"]
            ),
        ]
        router = DocumentRouter(collections)

        assert router.route_document("a/b/c/d/e/f/g/file.md") == "deep"
        assert router.route_document("a/b/c/file.md") == "default"

    def test_root_level_documents(self):
        """Test routing for documents at root level."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="root",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=[""]  # Root level
            ),
        ]
        router = DocumentRouter(collections)

        # Root level document should match root pattern
        assert router.route_document("readme.md") == "root"
        assert router.route_document("file.md") == "root"

    def test_multiple_patterns_per_collection(self):
        """Test collection with multiple source patterns."""
        collections = [
            CollectionConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="mixed",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["docs", "guides", "tutorials", "examples"]
            ),
        ]
        router = DocumentRouter(collections)

        # Should match any of the patterns
        assert router.route_document("docs/file.md") == "mixed"
        assert router.route_document("guides/file.md") == "mixed"
        assert router.route_document("tutorials/file.md") == "mixed"
        assert router.route_document("examples/file.md") == "mixed"
        assert router.route_document("other/file.md") == "default"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
