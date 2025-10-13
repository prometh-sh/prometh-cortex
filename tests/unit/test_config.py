"""Unit tests for configuration management."""

import os
import tempfile
from pathlib import Path

import pytest

from prometh_cortex.config import Config, ConfigValidationError, load_config


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