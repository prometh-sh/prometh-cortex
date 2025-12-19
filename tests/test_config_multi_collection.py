"""Unit tests for configuration with multi-collection support."""

import json
import pytest
from pathlib import Path
import tempfile
import os

from prometh_cortex.config import Config, CollectionConfig, ConfigValidationError


class TestCollectionConfig:
    """Test suite for CollectionConfig."""

    def test_collection_config_creation(self):
        """Test creating a collection configuration."""
        config = CollectionConfig(
            name="knowledge_base",
            chunk_size=512,
            chunk_overlap=50,
            source_patterns=["docs/specs", "docs/prds"]
        )
        assert config.name == "knowledge_base"
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
        assert len(config.source_patterns) == 2

    def test_collection_config_defaults(self):
        """Test collection config with default values."""
        config = CollectionConfig(
            name="default",
            source_patterns=["*"]
        )
        assert config.chunk_size == 512  # Default
        assert config.chunk_overlap == 50  # Default

    def test_collection_config_chunk_size_validation(self):
        """Test chunk_size validation (128-2048 range)."""
        # Valid values
        CollectionConfig(name="test", chunk_size=128, source_patterns=["*"])
        CollectionConfig(name="test", chunk_size=512, source_patterns=["*"])
        CollectionConfig(name="test", chunk_size=2048, source_patterns=["*"])

        # Invalid values
        with pytest.raises(ValueError):
            CollectionConfig(name="test", chunk_size=100, source_patterns=["*"])

        with pytest.raises(ValueError):
            CollectionConfig(name="test", chunk_size=3000, source_patterns=["*"])

    def test_collection_config_overlap_validation(self):
        """Test chunk_overlap validation (0-256 range)."""
        # Valid values
        CollectionConfig(name="test", chunk_overlap=0, source_patterns=["*"])
        CollectionConfig(name="test", chunk_overlap=50, source_patterns=["*"])
        CollectionConfig(name="test", chunk_overlap=256, source_patterns=["*"])

        # Invalid values
        with pytest.raises(ValueError):
            CollectionConfig(name="test", chunk_overlap=-1, source_patterns=["*"])

        with pytest.raises(ValueError):
            CollectionConfig(name="test", chunk_overlap=300, source_patterns=["*"])


class TestConfigWithCollections:
    """Test suite for Config with multi-collection support."""

    def test_config_with_default_collections(self):
        """Test config initializes with default collection."""
        config = Config(datalake_repos=[Path("/tmp")])
        assert len(config.collections) == 1
        assert config.collections[0].name == "default"
        assert "*" in config.collections[0].source_patterns

    def test_config_with_custom_collections(self):
        """Test config with custom collections."""
        collections = [
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
            CollectionConfig(
                name="knowledge_base",
                source_patterns=["docs/specs"]
            ),
        ]
        config = Config(
            datalake_repos=[Path("/tmp")],
            collections=collections
        )
        assert len(config.collections) == 2

    def test_config_collections_validation(self):
        """Test collections configuration validation."""
        # Missing default collection
        collections = [
            CollectionConfig(
                name="knowledge_base",
                source_patterns=["docs"]
            )
        ]
        with pytest.raises(ValueError, match="default"):
            Config(datalake_repos=[Path("/tmp")], collections=collections)

    def test_config_parse_collections_from_json(self):
        """Test parsing collections from JSON string."""
        json_str = json.dumps([
            {
                "name": "default",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "source_patterns": ["*"]
            },
            {
                "name": "knowledge_base",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "source_patterns": ["docs/specs"]
            }
        ])
        config = Config(
            datalake_repos=[Path("/tmp")],
            collections=json_str
        )
        assert len(config.collections) == 2
        assert config.collections[1].name == "knowledge_base"

    def test_config_parse_collections_invalid_json(self):
        """Test error handling for invalid JSON collections."""
        with pytest.raises(ValueError, match="Invalid JSON"):
            Config(
                datalake_repos=[Path("/tmp")],
                collections="{invalid json"
            )

    def test_config_parse_collections_non_array(self):
        """Test error handling for non-array JSON collections."""
        with pytest.raises(ValueError, match="must be a JSON array"):
            Config(
                datalake_repos=[Path("/tmp")],
                collections='{"name": "test"}'
            )


class TestConfigEnvironmentVariables:
    """Test suite for environment variable parsing."""

    def test_rag_collections_env_var_json(self):
        """Test RAG_COLLECTIONS environment variable with JSON."""
        json_str = json.dumps([
            {
                "name": "default",
                "chunk_size": 512,
                "chunk_overlap": 50,
                "source_patterns": ["*"]
            },
            {
                "name": "meetings",
                "chunk_size": 256,
                "chunk_overlap": 25,
                "source_patterns": ["meetings"]
            }
        ])
        os.environ["RAG_COLLECTIONS"] = json_str

        try:
            from prometh_cortex.config import load_config
            config = load_config()
            assert len(config.collections) >= 2
        finally:
            del os.environ["RAG_COLLECTIONS"]

    def test_rag_collections_env_var_comma_separated(self):
        """Test RAG_COLLECTIONS with comma-separated names."""
        os.environ["RAG_COLLECTIONS"] = "knowledge_base,meetings,default"

        try:
            from prometh_cortex.config import load_config
            config = load_config()
            # Should create default configs for each
            names = [c.name for c in config.collections]
            assert "knowledge_base" in names
            assert "meetings" in names
            assert "default" in names
        finally:
            del os.environ["RAG_COLLECTIONS"]


class TestConfigTomlSupport:
    """Test suite for TOML configuration with collections."""

    def test_config_from_toml_with_collections(self):
        """Test loading configuration from TOML with collections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_file = Path(tmpdir) / "config.toml"
            toml_content = """
[datalake]
repos = ["/tmp/docs"]

[storage]
rag_index_dir = "/tmp/index"

[[collections]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]

[[collections]]
name = "knowledge_base"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["docs/specs", "docs/prds"]

[[collections]]
name = "meetings"
chunk_size = 256
chunk_overlap = 25
source_patterns = ["meetings"]
"""
            toml_file.write_text(toml_content)

            # Change to tmpdir so config loading finds the file
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                from prometh_cortex.config import load_config
                config = load_config(toml_file)

                assert len(config.collections) == 3
                assert config.collections[0].name == "default"
                assert config.collections[1].name == "knowledge_base"
                assert config.collections[2].name == "meetings"
                assert config.collections[2].chunk_size == 256
            finally:
                os.chdir(old_cwd)


class TestConfigExportToEnvVars:
    """Test suite for exporting config to environment variables."""

    def test_config_export_collections_to_env(self):
        """Test exporting collections configuration to env vars."""
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
                source_patterns=["docs"]
            ),
        ]
        config = Config(
            datalake_repos=[Path("/tmp")],
            collections=collections
        )

        from prometh_cortex.config import config_to_env_vars
        env_vars = config_to_env_vars(config)

        # Check RAG_COLLECTIONS is set
        assert "RAG_COLLECTIONS" in env_vars
        parsed = json.loads(env_vars["RAG_COLLECTIONS"])
        assert len(parsed) == 2
        assert parsed[0]["name"] == "default"
        assert parsed[1]["name"] == "knowledge_base"


class TestConfigValidationErrors:
    """Test suite for configuration validation errors."""

    def test_config_duplicate_collection_names(self):
        """Test error when collections have duplicate names."""
        collections = [
            CollectionConfig(
                name="knowledge_base",
                source_patterns=["docs"]
            ),
            CollectionConfig(
                name="knowledge_base",  # Duplicate
                source_patterns=["other"]
            ),
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
        ]
        with pytest.raises(ValueError, match="Duplicate"):
            Config(datalake_repos=[Path("/tmp")], collections=collections)

    def test_config_missing_default_collection(self):
        """Test error when 'default' collection is missing."""
        collections = [
            CollectionConfig(
                name="knowledge_base",
                source_patterns=["docs"]
            ),
            CollectionConfig(
                name="meetings",
                source_patterns=["meetings"]
            ),
        ]
        with pytest.raises(ValueError, match="default.*required"):
            Config(datalake_repos=[Path("/tmp")], collections=collections)

    def test_config_missing_catchall_pattern(self):
        """Test error when no catch-all '*' pattern exists."""
        collections = [
            CollectionConfig(
                name="default",
                source_patterns=["specific_path"]  # No catch-all
            ),
            CollectionConfig(
                name="knowledge_base",
                source_patterns=["docs"]
            ),
        ]
        with pytest.raises(ValueError, match="catch-all"):
            Config(datalake_repos=[Path("/tmp")], collections=collections)

    def test_config_empty_collection_patterns(self):
        """Test error when collection has empty patterns."""
        collections = [
            CollectionConfig(
                name="invalid",
                source_patterns=[]  # Empty
            ),
            CollectionConfig(
                name="default",
                source_patterns=["*"]
            ),
        ]
        with pytest.raises(ValueError, match="at least one"):
            Config(datalake_repos=[Path("/tmp")], collections=collections)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
