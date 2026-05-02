"""Unit tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest

from prometh_cortex.config import Config, ConfigValidationError, load_config
from prometh_cortex.config.settings import _resolve_env_ref


class TestConfig:
    """Test configuration loading and validation."""
    
    def test_config_validation_with_valid_paths(self, tmp_path):
        """Test config validation with valid datalake paths."""
        # Create test directories
        notes_dir = tmp_path / "notes"
        docs_dir = tmp_path / "docs"
        notes_dir.mkdir()
        docs_dir.mkdir()
        
        config = Config(datalake_repos=[notes_dir, docs_dir])
        
        assert len(config.datalake_repos) == 2
        assert notes_dir in config.datalake_repos
        assert docs_dir in config.datalake_repos
    
    def test_config_validation_with_nonexistent_path(self, tmp_path):
        """Test config validation fails with nonexistent paths."""
        nonexistent = tmp_path / "nonexistent"
        
        with pytest.raises(ValueError, match="does not exist"):
            Config(datalake_repos=[nonexistent])
    
    def test_parse_comma_separated_paths(self, tmp_path):
        """Test parsing comma-separated datalake paths."""
        notes_dir = tmp_path / "notes"
        docs_dir = tmp_path / "docs"
        notes_dir.mkdir()
        docs_dir.mkdir()
        
        path_string = f"{notes_dir},{docs_dir}"
        config = Config(datalake_repos=path_string)
        
        assert len(config.datalake_repos) == 2
        assert notes_dir in config.datalake_repos
        assert docs_dir in config.datalake_repos
    
    def test_default_values(self, tmp_path):
        """Test that default values are set correctly."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        
        config = Config(datalake_repos=[notes_dir])
        
        assert config.mcp_port == 8080
        assert config.mcp_host == "localhost"
        assert config.embedding_model == "sentence-transformers/all-MiniLM-L6-v2"
        assert config.max_query_results == 10
        assert config.chunk_size == 512
        assert config.chunk_overlap == 50
    
    def test_load_config_from_env_file(self, tmp_path, monkeypatch):
        """Test loading configuration from environment variables."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()

        # Set environment variables directly (not using .env file)
        monkeypatch.setenv("DATALAKE_REPOS", str(notes_dir))
        monkeypatch.setenv("MCP_PORT", "9000")
        monkeypatch.setenv("EMBEDDING_MODEL", "test-model")

        config = load_config()

        assert config.mcp_port == 9000
        assert config.embedding_model == "test-model"
        assert notes_dir in config.datalake_repos
    
    def test_config_validation_error_for_missing_repos(self):
        """Test that ConfigValidationError is raised for missing datalake repos."""
        with pytest.raises(ConfigValidationError):
            load_config()


class TestConfigEnvironment:
    """Test configuration with environment variables."""
    
    def test_load_config_from_environment(self, tmp_path, monkeypatch):
        """Test loading configuration from environment variables."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        
        monkeypatch.setenv("DATALAKE_REPOS", str(notes_dir))
        monkeypatch.setenv("MCP_PORT", "9090")
        monkeypatch.setenv("MAX_QUERY_RESULTS", "20")
        
        config = load_config()
        
        assert config.mcp_port == 9090
        assert config.max_query_results == 20
        assert notes_dir in config.datalake_repos
    
    def test_invalid_port_in_environment(self, tmp_path, monkeypatch):
        """Test handling of invalid port in environment."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        
        monkeypatch.setenv("DATALAKE_REPOS", str(notes_dir))
        monkeypatch.setenv("MCP_PORT", "invalid")
        
        with pytest.raises(ConfigValidationError, match="Invalid MCP_PORT"):
            load_config()
    
    def test_auth_token_generation(self, tmp_path):
        """Test that auth token is generated if not provided."""
        notes_dir = tmp_path / "notes"
        notes_dir.mkdir()
        
        config = Config(datalake_repos=[notes_dir])
        
        assert config.mcp_auth_token is not None
        assert len(config.mcp_auth_token) > 10  # Should be a reasonable length


class TestEnvVarResolution:
    """Test {env:VAR_NAME} syntax resolution in config values."""

    def test_resolve_env_ref_plain_string_unchanged(self):
        """Plain strings without {env:...} should pass through unchanged."""
        assert _resolve_env_ref("my-auth-token") == "my-auth-token"
        assert _resolve_env_ref("localhost") == "localhost"
        assert _resolve_env_ref("") == ""

    def test_resolve_env_ref_with_set_env_var(self, monkeypatch):
        """Resolve {env:VAR_NAME} when env var is set."""
        monkeypatch.setenv("TEST_AUTH_TOKEN", "secret-token-123")
        assert _resolve_env_ref("{env:TEST_AUTH_TOKEN}") == "secret-token-123"

    def test_resolve_env_ref_with_unset_env_var(self):
        """Raise ConfigValidationError when env var is not set."""
        # Ensure var doesn't exist
        if "NONEXISTENT_VAR_XYZ" in os.environ:
            del os.environ["NONEXISTENT_VAR_XYZ"]

        with pytest.raises(ConfigValidationError) as exc_info:
            _resolve_env_ref("{env:NONEXISTENT_VAR_XYZ}")

        assert "NONEXISTENT_VAR_XYZ" in str(exc_info.value)
        assert "not set" in str(exc_info.value)

    def test_resolve_env_ref_partial_string_no_match(self):
        """Partial env syntax like 'prefix-{env:VAR}-suffix' should pass through unchanged."""
        result = _resolve_env_ref("prefix-{env:TEST_VAR}-suffix")
        assert result == "prefix-{env:TEST_VAR}-suffix"

    def test_resolve_env_ref_with_empty_env_value(self, monkeypatch):
        """Resolve {env:VAR_NAME} even if env var value is empty string."""
        monkeypatch.setenv("EMPTY_VAR", "")
        assert _resolve_env_ref("{env:EMPTY_VAR}") == ""

    def test_resolve_env_ref_with_special_chars(self, monkeypatch):
        """Env var values with special chars should be resolved correctly."""
        token = "abc-123_XYZ.token@host"
        monkeypatch.setenv("SPECIAL_TOKEN", token)
        assert _resolve_env_ref("{env:SPECIAL_TOKEN}") == token

    def test_auth_token_env_resolution_in_toml(self, tmp_path, monkeypatch):
        """Test auth_token field resolves {env:...} from TOML config."""
        from prometh_cortex.config.settings import _load_from_toml

        monkeypatch.setenv("PROMETH_AUTH", "resolved-auth-token")

        # Create test TOML with env var reference
        toml_content = """
[server]
auth_token = "{env:PROMETH_AUTH}"

[vector_store]
type = "faiss"

[[collections]]
name = "test"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)

        config = _load_from_toml(config_file)
        assert config.mcp_auth_token == "resolved-auth-token"

    def test_qdrant_host_env_resolution_in_toml(self, tmp_path, monkeypatch):
        """Test qdrant.host field resolves {env:...} from TOML config."""
        from prometh_cortex.config.settings import _load_from_toml

        monkeypatch.setenv("QDRANT_HOST", "qdrant.example.com")

        toml_content = """
[server]
auth_token = "token"

[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "{env:QDRANT_HOST}"
port = 6333

[[collections]]
name = "test"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)

        config = _load_from_toml(config_file)
        assert config.qdrant_host == "qdrant.example.com"

    def test_qdrant_api_key_env_resolution_in_toml(self, tmp_path, monkeypatch):
        """Test qdrant.api_key field resolves {env:...} from TOML config."""
        from prometh_cortex.config.settings import _load_from_toml

        monkeypatch.setenv("QDRANT_API_KEY", "api-key-secret-xyz")

        toml_content = """
[server]
auth_token = "token"

[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "localhost"
port = 6333
api_key = "{env:QDRANT_API_KEY}"

[[collections]]
name = "test"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)

        config = _load_from_toml(config_file)
        assert config.qdrant_api_key == "api-key-secret-xyz"

    def test_mixed_plain_and_env_values_in_toml(self, tmp_path, monkeypatch):
        """Test that plain strings and env refs can coexist in TOML."""
        from prometh_cortex.config.settings import _load_from_toml

        monkeypatch.setenv("QDRANT_API_KEY", "secret-key")

        toml_content = """
[server]
auth_token = "plain-token"

[vector_store]
type = "qdrant"

[vector_store.qdrant]
host = "{env:QDRANT_HOST_VAR}"
port = 6333
api_key = "{env:QDRANT_API_KEY}"

[[collections]]
name = "test"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)

        # Should fail because QDRANT_HOST_VAR is not set
        with pytest.raises(ConfigValidationError) as exc_info:
            _load_from_toml(config_file)

        assert "QDRANT_HOST_VAR" in str(exc_info.value)

    def test_missing_env_var_fails_startup(self, tmp_path):
        """Test that missing env var causes hard error on config load."""
        from prometh_cortex.config.settings import _load_from_toml

        toml_content = """
[server]
auth_token = "{env:MISSING_AUTH_VAR}"

[vector_store]
type = "faiss"

[[collections]]
name = "test"

[[sources]]
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]
"""
        config_file = tmp_path / "config.toml"
        config_file.write_text(toml_content)

        # Ensure env var is not set
        if "MISSING_AUTH_VAR" in os.environ:
            del os.environ["MISSING_AUTH_VAR"]

        with pytest.raises(ConfigValidationError) as exc_info:
            _load_from_toml(config_file)

        assert "MISSING_AUTH_VAR" in str(exc_info.value)
        assert "not set" in str(exc_info.value)