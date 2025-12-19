"""Configuration settings and TOML configuration management."""

import os
import json
from pathlib import Path
from typing import List, Optional, Dict, Any

import toml
from pydantic import BaseModel, Field, validator


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class SourceConfig(BaseModel):
    """Configuration for a document source with chunking parameters."""

    name: str = Field(
        ...,
        description="Semantic name for source type (e.g., 'knowledge_base', 'meetings')"
    )
    chunk_size: int = Field(
        default=512,
        ge=128, le=2048,
        description="Size of text chunks for documents from this source"
    )
    chunk_overlap: int = Field(
        default=50,
        ge=0, le=256,
        description="Overlap between text chunks for this source"
    )
    source_patterns: List[str] = Field(
        default_factory=list,
        description="Path patterns that route documents to this source (e.g., ['docs/specs', 'docs/prds'])"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


class CollectionConfig(BaseModel):
    """Configuration for the unified RAG collection."""

    name: str = Field(
        default="prometh_cortex",
        description="Name of the unified RAG collection"
    )

    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True


class Config(BaseModel):
    """Configuration settings for prometh-cortex."""
    
    # Optional settings with defaults
    rag_index_dir: Path = Field(
        default=Path(".rag_index"),
        description="Directory to store RAG index files"
    )
    mcp_port: int = Field(
        default=8080,
        ge=1024, le=65535,
        description="Port for MCP server"
    )
    mcp_host: str = Field(
        default="localhost",
        description="Host for MCP server"
    )
    mcp_auth_token: Optional[str] = Field(
        default=None,
        description="Authentication token for MCP server"
    )
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        description="Name of the embedding model to use"
    )
    max_query_results: int = Field(
        default=10,
        ge=1, le=100,
        description="Maximum number of results to return per query"
    )

    # Single unified collection configuration
    collection: CollectionConfig = Field(
        default_factory=lambda: CollectionConfig(name="prometh_cortex"),
        description="Configuration for the unified RAG collection"
    )

    # Document sources with per-source chunking configuration
    sources: List[SourceConfig] = Field(
        default_factory=lambda: [
            SourceConfig(
                name="default",
                chunk_size=512,
                chunk_overlap=50,
                source_patterns=["*"]
            )
        ],
        description="Document source configurations with chunking parameters"
    )
    
    # Vector store configuration
    vector_store_type: str = Field(
        default="faiss",
        description="Type of vector store to use: 'faiss' or 'qdrant'"
    )
    
    # Qdrant-specific configuration
    qdrant_host: str = Field(
        default="localhost",
        description="Qdrant server host"
    )
    qdrant_port: int = Field(
        default=6333,
        ge=1, le=65535,
        description="Qdrant server port"
    )
    qdrant_collection_name: str = Field(
        default="prometh_cortex",
        description="Qdrant collection name"
    )
    qdrant_api_key: Optional[str] = Field(
        default=None,
        description="Qdrant API key (for cloud deployments)"
    )
    qdrant_use_https: bool = Field(
        default=False,
        description="Use HTTPS for Qdrant connection"
    )
    
    # Structured query configuration (Option 1: Hybrid auto-discovery + user config)
    structured_query_core_fields: List[str] = Field(
        default=["tags", "created", "modified", "category", "author"],
        description="Core fields always available for structured queries"
    )
    structured_query_extended_fields: List[str] = Field(
        default=["status", "focus", "title", "subject", "organizer", "location"],
        description="Extended fields available for structured queries (user configurable)"
    )
    structured_query_auto_discovery: bool = Field(
        default=True,
        description="Enable automatic discovery of additional filterable fields"
    )
    structured_query_max_auto_fields: int = Field(
        default=10,
        ge=0, le=50,
        description="Maximum number of auto-discovered fields to enable"
    )
    
    # MCP timeout configuration
    mcp_default_timeout: int = Field(
        default=60,
        ge=10, le=600,
        description="Default timeout for MCP operations in seconds"
    )
    mcp_max_timeout: int = Field(
        default=300,
        ge=60, le=1800,
        description="Maximum timeout for MCP operations in seconds"
    )
    mcp_progress_interval: int = Field(
        default=5,
        ge=1, le=30,
        description="Progress update interval in seconds"
    )
    mcp_chunk_size: int = Field(
        default=50,
        ge=10, le=200,
        description="Default chunk size for chunked queries"
    )
    mcp_max_concurrent_ops: int = Field(
        default=10,
        ge=1, le=50,
        description="Maximum concurrent operations"
    )
    
    # MCP async operations
    mcp_enable_async: bool = Field(
        default=True,
        description="Enable async operation processing"
    )
    mcp_operation_ttl: int = Field(
        default=1800,
        ge=300, le=86400,
        description="Operation time-to-live in seconds"
    )
    mcp_cleanup_interval: int = Field(
        default=300,
        ge=60, le=3600,
        description="Cleanup interval for completed operations in seconds"
    )
    
    # MCP startup optimization
    mcp_max_startup_time: float = Field(
        default=50.0,
        ge=10.0, le=120.0,
        description="Maximum server startup time in seconds"
    )
    mcp_lazy_load_index: bool = Field(
        default=True,
        description="Enable lazy loading of index to speed up startup"
    )
    
    class Config:
        """Pydantic configuration."""
        env_prefix = ""
        case_sensitive = False
        
    
    @validator("rag_index_dir", pre=True)
    def resolve_rag_index_dir(cls, v):
        """Resolve RAG index directory path."""
        return Path(v).expanduser().resolve()
    
    @validator("mcp_auth_token", pre=True)
    def generate_auth_token_if_needed(cls, v):
        """Generate authentication token if not provided."""
        if v is None or v == "auto_generated_if_empty":
            import secrets
            return secrets.token_urlsafe(32)
        return v
    
    @validator("vector_store_type")
    def validate_vector_store_type(cls, v):
        """Validate vector store type."""
        supported_types = {"faiss", "qdrant"}
        if v.lower() not in supported_types:
            raise ValueError(f"Unsupported vector store type: {v}. Supported types: {supported_types}")
        return v.lower()
    
    @validator("qdrant_use_https", pre=True)
    def parse_qdrant_use_https(cls, v):
        """Parse QDRANT_USE_HTTPS boolean from string."""
        if isinstance(v, str):
            return v.lower() in ("true", "1", "yes", "on")
        return bool(v)

    @validator("sources", pre=True)
    def parse_sources(cls, v):
        """Parse sources from various formats."""
        if isinstance(v, str):
            # Parse JSON string
            try:
                parsed = json.loads(v)
                if isinstance(parsed, list):
                    return [SourceConfig(**c) for c in parsed]
                else:
                    raise ValueError("Sources must be a JSON array")
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON in sources configuration: {e}")
        elif isinstance(v, list):
            # Already a list, convert dicts to SourceConfig
            return [SourceConfig(**c) if isinstance(c, dict) else c for c in v]
        else:
            raise ValueError("Sources must be a list or JSON string")

    @validator("sources")
    def validate_sources(cls, v):
        """Validate sources configuration."""
        if not v:
            raise ValueError("At least one source must be configured")

        source_names = set()
        has_catchall = False

        for source in v:
            # Check for duplicate names
            if source.name in source_names:
                raise ValueError(f"Duplicate source name: {source.name}")
            source_names.add(source.name)

            # Check for required patterns
            if not source.source_patterns:
                raise ValueError(f"Source '{source.name}' must have at least one source pattern")

            # Check for catch-all pattern
            if "*" in source.source_patterns:
                has_catchall = True

        # Optional: catch-all pattern not required
        # Sources can have specific patterns only if desired
        # Documents that don't match any pattern will not be indexed

        return v


def load_config(config_file: Optional[Path] = None) -> Config:
    """
    Load configuration from TOML file or environment variables (hybrid mode).
    
    Priority: config.toml > environment variables > defaults
    
    Args:
        config_file: Optional path to config.toml file. If not provided, searches for config.toml in common locations.
    
    Returns:
        Config: Validated configuration object
        
    Raises:
        ConfigValidationError: If configuration validation fails
    """
    # Try TOML configuration first
    try:
        return _load_from_toml(config_file)
    except ConfigValidationError:
        # Fallback to environment variables for MCP server compatibility
        return _load_from_env()


def _load_from_toml(config_file: Optional[Path] = None) -> Config:
    """Load configuration from TOML file."""
    # Search for config.toml file if not provided
    if config_file is None:
        # Follow XDG Base Directory Specification
        xdg_config_home = os.getenv("XDG_CONFIG_HOME", str(Path.home() / ".config"))

        search_paths = [
            Path.cwd() / "config.toml",  # Current working directory (highest priority)
            Path(xdg_config_home) / "prometh-cortex" / "config.toml",  # XDG config directory
            Path.home() / ".prometh-cortex" / "config.toml",  # Fallback: hidden directory in home
            Path(__file__).parent.parent.parent / "config.toml",  # Project root (development only)
        ]
        
        config_file = None
        for path in search_paths:
            if path.exists():
                config_file = path
                break
    
    if not config_file or not config_file.exists():
        raise ConfigValidationError(
            f"Configuration file not found. Create config.toml by copying from config.toml.sample.\n"
            f"Searched paths: {search_paths if config_file is None else [config_file]}"
        )
    
    # Load TOML configuration
    try:
        toml_data = toml.load(config_file)
    except Exception as e:
        raise ConfigValidationError(f"Failed to parse TOML configuration file {config_file}: {e}")
    
    # Transform TOML structure to flat config dict
    config_data = _flatten_toml_config(toml_data)
    
    # Validate and create configuration
    try:
        return Config(**config_data)
    except ValueError as e:
        raise ConfigValidationError(f"Configuration validation failed: {e}")


def _load_from_env() -> Config:
    """Load configuration from environment variables (for MCP server compatibility)."""
    # Prepare configuration data from environment variables
    config_data = {}
    
    # Required settings
    # Optional settings
    if rag_index_dir := os.getenv("RAG_INDEX_DIR"):
        config_data["rag_index_dir"] = rag_index_dir
    
    if mcp_port := os.getenv("MCP_PORT"):
        try:
            config_data["mcp_port"] = int(mcp_port)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_PORT value: {mcp_port}")
    
    if mcp_host := os.getenv("MCP_HOST"):
        config_data["mcp_host"] = mcp_host
    
    if mcp_auth_token := os.getenv("MCP_AUTH_TOKEN"):
        config_data["mcp_auth_token"] = mcp_auth_token
    
    if embedding_model := os.getenv("EMBEDDING_MODEL"):
        config_data["embedding_model"] = embedding_model
    
    if max_query_results := os.getenv("MAX_QUERY_RESULTS"):
        try:
            config_data["max_query_results"] = int(max_query_results)
        except ValueError:
            raise ConfigValidationError(f"Invalid MAX_QUERY_RESULTS value: {max_query_results}")

    # Document sources configuration
    if rag_sources := os.getenv("RAG_SOURCES"):
        try:
            # Try to parse as JSON first
            sources = json.loads(rag_sources)
            config_data["sources"] = sources
        except json.JSONDecodeError:
            # If not JSON, treat as simple source names and create default config
            # This allows: RAG_SOURCES='knowledge_base,meetings,default'
            source_names = [name.strip() for name in rag_sources.split(",") if name.strip()]

            # Ensure "default" source exists
            if "default" not in source_names:
                source_names.append("default")

            # Create simple default configurations
            sources = []
            for name in source_names:
                if name == "default":
                    sources.append({
                        "name": "default",
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "source_patterns": ["*"]
                    })
                else:
                    sources.append({
                        "name": name,
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "source_patterns": []  # Will need to be configured
                    })

            config_data["sources"] = sources

    # Backward compatibility: support old RAG_COLLECTIONS env var mapping to sources
    if not (rag_sources := os.getenv("RAG_SOURCES")) and (rag_collections := os.getenv("RAG_COLLECTIONS")):
        try:
            # Try to parse as JSON first
            sources = json.loads(rag_collections)
            config_data["sources"] = sources
        except json.JSONDecodeError:
            # If not JSON, treat as simple source names
            source_names = [name.strip() for name in rag_collections.split(",") if name.strip()]
            if "default" not in source_names:
                source_names.append("default")

            sources = []
            for name in source_names:
                if name == "default":
                    sources.append({
                        "name": "default",
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "source_patterns": ["*"]
                    })
                else:
                    sources.append({
                        "name": name,
                        "chunk_size": 512,
                        "chunk_overlap": 50,
                        "source_patterns": []
                    })

            config_data["sources"] = sources
    
    # Vector store configuration
    if vector_store_type := os.getenv("VECTOR_STORE_TYPE"):
        config_data["vector_store_type"] = vector_store_type
    
    # Qdrant configuration
    if qdrant_host := os.getenv("QDRANT_HOST"):
        config_data["qdrant_host"] = qdrant_host
    
    if qdrant_port := os.getenv("QDRANT_PORT"):
        try:
            config_data["qdrant_port"] = int(qdrant_port)
        except ValueError:
            raise ConfigValidationError(f"Invalid QDRANT_PORT value: {qdrant_port}")
    
    if qdrant_collection_name := os.getenv("QDRANT_COLLECTION_NAME"):
        config_data["qdrant_collection_name"] = qdrant_collection_name
    
    if qdrant_api_key := os.getenv("QDRANT_API_KEY"):
        config_data["qdrant_api_key"] = qdrant_api_key
    
    if qdrant_use_https := os.getenv("QDRANT_USE_HTTPS"):
        config_data["qdrant_use_https"] = qdrant_use_https
    
    # Structured query configuration
    if structured_query_core_fields := os.getenv("STRUCTURED_QUERY_CORE_FIELDS"):
        config_data["structured_query_core_fields"] = [
            field.strip() for field in structured_query_core_fields.split(",") if field.strip()
        ]
    
    if structured_query_extended_fields := os.getenv("STRUCTURED_QUERY_EXTENDED_FIELDS"):
        config_data["structured_query_extended_fields"] = [
            field.strip() for field in structured_query_extended_fields.split(",") if field.strip()
        ]
    
    if structured_query_auto_discovery := os.getenv("STRUCTURED_QUERY_AUTO_DISCOVERY"):
        config_data["structured_query_auto_discovery"] = structured_query_auto_discovery.lower() in ("true", "1", "yes", "on")
    
    if structured_query_max_auto_fields := os.getenv("STRUCTURED_QUERY_MAX_AUTO_FIELDS"):
        try:
            config_data["structured_query_max_auto_fields"] = int(structured_query_max_auto_fields)
        except ValueError:
            raise ConfigValidationError(f"Invalid STRUCTURED_QUERY_MAX_AUTO_FIELDS value: {structured_query_max_auto_fields}")
    
    # MCP timeout configuration
    if mcp_default_timeout := os.getenv("MCP_DEFAULT_TIMEOUT"):
        try:
            config_data["mcp_default_timeout"] = int(mcp_default_timeout)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_DEFAULT_TIMEOUT value: {mcp_default_timeout}")
    
    if mcp_max_timeout := os.getenv("MCP_MAX_TIMEOUT"):
        try:
            config_data["mcp_max_timeout"] = int(mcp_max_timeout)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_MAX_TIMEOUT value: {mcp_max_timeout}")
    
    if mcp_progress_interval := os.getenv("MCP_PROGRESS_INTERVAL"):
        try:
            config_data["mcp_progress_interval"] = int(mcp_progress_interval)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_PROGRESS_INTERVAL value: {mcp_progress_interval}")
    
    if mcp_chunk_size := os.getenv("MCP_CHUNK_SIZE"):
        try:
            config_data["mcp_chunk_size"] = int(mcp_chunk_size)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_CHUNK_SIZE value: {mcp_chunk_size}")
    
    if mcp_max_concurrent_ops := os.getenv("MCP_MAX_CONCURRENT_OPS"):
        try:
            config_data["mcp_max_concurrent_ops"] = int(mcp_max_concurrent_ops)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_MAX_CONCURRENT_OPS value: {mcp_max_concurrent_ops}")
    
    # MCP async operations
    if mcp_enable_async := os.getenv("MCP_ENABLE_ASYNC"):
        config_data["mcp_enable_async"] = mcp_enable_async.lower() in ("true", "1", "yes", "on")
    
    if mcp_operation_ttl := os.getenv("MCP_OPERATION_TTL"):
        try:
            config_data["mcp_operation_ttl"] = int(mcp_operation_ttl)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_OPERATION_TTL value: {mcp_operation_ttl}")
    
    if mcp_cleanup_interval := os.getenv("MCP_CLEANUP_INTERVAL"):
        try:
            config_data["mcp_cleanup_interval"] = int(mcp_cleanup_interval)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_CLEANUP_INTERVAL value: {mcp_cleanup_interval}")
    
    # MCP startup optimization
    if mcp_max_startup_time := os.getenv("MCP_MAX_STARTUP_TIME"):
        try:
            config_data["mcp_max_startup_time"] = float(mcp_max_startup_time)
        except ValueError:
            raise ConfigValidationError(f"Invalid MCP_MAX_STARTUP_TIME value: {mcp_max_startup_time}")
    
    if mcp_lazy_load_index := os.getenv("MCP_LAZY_LOAD_INDEX"):
        config_data["mcp_lazy_load_index"] = mcp_lazy_load_index.lower() in ("true", "1", "yes", "on")
    
    # Validate and create configuration
    try:
        return Config(**config_data)
    except ValueError as e:
        raise ConfigValidationError(f"Configuration validation failed: {e}")


def config_to_env_vars(config: Config) -> Dict[str, str]:
    """Convert Config object back to environment variables for MCP server compatibility.
    
    Args:
        config: Configuration object to convert
        
    Returns:
        Dictionary of environment variable names and values
    """
    env_vars = {}
    
    # Storage configuration
    if config.rag_index_dir:
        env_vars["RAG_INDEX_DIR"] = str(config.rag_index_dir)
    
    # Server configuration
    if config.mcp_port:
        env_vars["MCP_PORT"] = str(config.mcp_port)
    if config.mcp_host:
        env_vars["MCP_HOST"] = config.mcp_host
    if config.mcp_auth_token:
        env_vars["MCP_AUTH_TOKEN"] = config.mcp_auth_token
    
    # Embedding configuration
    if config.embedding_model:
        env_vars["EMBEDDING_MODEL"] = config.embedding_model
    if config.max_query_results:
        env_vars["MAX_QUERY_RESULTS"] = str(config.max_query_results)

    # Document sources configuration
    if config.sources:
        # Export as JSON for env variable
        sources_list = [
            {
                "name": s.name,
                "chunk_size": s.chunk_size,
                "chunk_overlap": s.chunk_overlap,
                "source_patterns": s.source_patterns
            }
            for s in config.sources
        ]
        env_vars["RAG_SOURCES"] = json.dumps(sources_list)
    
    # Vector store configuration
    if config.vector_store_type:
        env_vars["VECTOR_STORE_TYPE"] = config.vector_store_type
    
    # Qdrant configuration
    if config.qdrant_host:
        env_vars["QDRANT_HOST"] = config.qdrant_host
    if config.qdrant_port:
        env_vars["QDRANT_PORT"] = str(config.qdrant_port)
    if config.qdrant_collection_name:
        env_vars["QDRANT_COLLECTION_NAME"] = config.qdrant_collection_name
    if config.qdrant_api_key:
        env_vars["QDRANT_API_KEY"] = config.qdrant_api_key
    if config.qdrant_use_https:
        env_vars["QDRANT_USE_HTTPS"] = str(config.qdrant_use_https).lower()
    
    # Structured query configuration
    if config.structured_query_core_fields:
        env_vars["STRUCTURED_QUERY_CORE_FIELDS"] = ",".join(config.structured_query_core_fields)
    if config.structured_query_extended_fields:
        env_vars["STRUCTURED_QUERY_EXTENDED_FIELDS"] = ",".join(config.structured_query_extended_fields)
    if config.structured_query_auto_discovery is not None:
        env_vars["STRUCTURED_QUERY_AUTO_DISCOVERY"] = str(config.structured_query_auto_discovery).lower()
    if config.structured_query_max_auto_fields:
        env_vars["STRUCTURED_QUERY_MAX_AUTO_FIELDS"] = str(config.structured_query_max_auto_fields)
    
    # MCP timeout configuration
    if config.mcp_default_timeout:
        env_vars["MCP_DEFAULT_TIMEOUT"] = str(config.mcp_default_timeout)
    if config.mcp_max_timeout:
        env_vars["MCP_MAX_TIMEOUT"] = str(config.mcp_max_timeout)
    if config.mcp_progress_interval:
        env_vars["MCP_PROGRESS_INTERVAL"] = str(config.mcp_progress_interval)
    if config.mcp_chunk_size:
        env_vars["MCP_CHUNK_SIZE"] = str(config.mcp_chunk_size)
    if config.mcp_max_concurrent_ops:
        env_vars["MCP_MAX_CONCURRENT_OPS"] = str(config.mcp_max_concurrent_ops)
    
    # MCP async operations
    if config.mcp_enable_async is not None:
        env_vars["MCP_ENABLE_ASYNC"] = str(config.mcp_enable_async).lower()
    if config.mcp_operation_ttl:
        env_vars["MCP_OPERATION_TTL"] = str(config.mcp_operation_ttl)
    if config.mcp_cleanup_interval:
        env_vars["MCP_CLEANUP_INTERVAL"] = str(config.mcp_cleanup_interval)
    
    # MCP startup optimization
    if config.mcp_max_startup_time:
        env_vars["MCP_MAX_STARTUP_TIME"] = str(config.mcp_max_startup_time)
    if config.mcp_lazy_load_index is not None:
        env_vars["MCP_LAZY_LOAD_INDEX"] = str(config.mcp_lazy_load_index).lower()
    
    return env_vars


def _flatten_toml_config(toml_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform nested TOML structure to flat configuration dictionary.
    
    Args:
        toml_data: Parsed TOML data
        
    Returns:
        Flattened configuration dictionary
    """
    config_data = {}
    
    # Storage configuration
    if "storage" in toml_data:
        storage = toml_data["storage"]
        if "rag_index_dir" in storage:
            config_data["rag_index_dir"] = storage["rag_index_dir"]
    
    # Server configuration
    if "server" in toml_data:
        server = toml_data["server"]
        if "port" in server:
            config_data["mcp_port"] = server["port"]
        if "host" in server:
            config_data["mcp_host"] = server["host"]
        if "auth_token" in server:
            config_data["mcp_auth_token"] = server["auth_token"]
    
    # Embedding configuration
    if "embedding" in toml_data:
        embedding = toml_data["embedding"]
        if "model" in embedding:
            config_data["embedding_model"] = embedding["model"]
        if "max_query_results" in embedding:
            config_data["max_query_results"] = embedding["max_query_results"]

    # Collection configuration
    if "collections" in toml_data:
        # Single collection config: [[collections]]
        collections_list = toml_data["collections"]
        if collections_list and isinstance(collections_list, list):
            # Take the first (should only be one)
            config_data["collection"] = collections_list[0]

    # Document sources configuration
    if "sources" in toml_data:
        # TOML array of tables format: [[sources]]
        config_data["sources"] = toml_data["sources"]
    elif "collections" in toml_data and not ("sources" in toml_data):
        # Backward compatibility: map old collections to sources
        config_data["sources"] = toml_data["collections"]
    
    # Vector store configuration
    if "vector_store" in toml_data:
        vector_store = toml_data["vector_store"]
        if "type" in vector_store:
            config_data["vector_store_type"] = vector_store["type"]
        
        # Qdrant-specific configuration
        if "qdrant" in vector_store:
            qdrant = vector_store["qdrant"]
            if "host" in qdrant:
                config_data["qdrant_host"] = qdrant["host"]
            if "port" in qdrant:
                config_data["qdrant_port"] = qdrant["port"]
            if "collection_name" in qdrant:
                config_data["qdrant_collection_name"] = qdrant["collection_name"]
            if "api_key" in qdrant:
                config_data["qdrant_api_key"] = qdrant["api_key"]
            if "use_https" in qdrant:
                config_data["qdrant_use_https"] = qdrant["use_https"]
    
    # Structured query configuration
    if "structured_query" in toml_data:
        structured_query = toml_data["structured_query"]
        if "core_fields" in structured_query:
            config_data["structured_query_core_fields"] = structured_query["core_fields"]
        if "extended_fields" in structured_query:
            config_data["structured_query_extended_fields"] = structured_query["extended_fields"]
        if "auto_discovery" in structured_query:
            config_data["structured_query_auto_discovery"] = structured_query["auto_discovery"]
        if "max_auto_fields" in structured_query:
            config_data["structured_query_max_auto_fields"] = structured_query["max_auto_fields"]
    
    # MCP timeout configuration
    if "mcp" in toml_data:
        mcp = toml_data["mcp"]
        
        # Timeout settings
        if "timeouts" in mcp:
            timeouts = mcp["timeouts"]
            if "default_query_timeout" in timeouts:
                config_data["mcp_default_timeout"] = timeouts["default_query_timeout"]
            if "max_query_timeout" in timeouts:
                config_data["mcp_max_timeout"] = timeouts["max_query_timeout"]
            if "progress_update_interval" in timeouts:
                config_data["mcp_progress_interval"] = timeouts["progress_update_interval"]
            if "chunk_size_default" in timeouts:
                config_data["mcp_chunk_size"] = timeouts["chunk_size_default"]
            if "max_concurrent_operations" in timeouts:
                config_data["mcp_max_concurrent_ops"] = timeouts["max_concurrent_operations"]
        
        # Async operations
        if "async_operations" in mcp:
            async_ops = mcp["async_operations"]
            if "enable_async_processing" in async_ops:
                config_data["mcp_enable_async"] = async_ops["enable_async_processing"]
            if "operation_ttl_seconds" in async_ops:
                config_data["mcp_operation_ttl"] = async_ops["operation_ttl_seconds"]
            if "cleanup_interval_seconds" in async_ops:
                config_data["mcp_cleanup_interval"] = async_ops["cleanup_interval_seconds"]
        
        # Startup optimization
        if "startup" in mcp:
            startup = mcp["startup"]
            if "max_startup_time" in startup:
                config_data["mcp_max_startup_time"] = startup["max_startup_time"]
            if "lazy_load_index" in startup:
                config_data["mcp_lazy_load_index"] = startup["lazy_load_index"]
    
    return config_data


def create_sample_config_file(path: Path = Path("config.toml.sample")) -> None:
    """Create a sample config.toml file with configuration options."""
    sample_content = """# Prometh Cortex Configuration Sample
# Copy this file to config.toml and customize for your environment

[datalake]
# Add your document directories here - supports multiple paths
repos = [
    "/path/to/your/notes",
    "/path/to/your/documents",
    "/path/to/your/projects"
]

[storage]
# Directory where RAG index will be stored
rag_index_dir = "/path/to/index/storage"

[server]
# MCP and HTTP server configuration
port = 8080
host = "localhost"
auth_token = "your-secure-token-here"

[embedding]
# Embedding model and query configuration
model = "sentence-transformers/all-MiniLM-L6-v2"
max_query_results = 10

# Unified Collection Configuration
# Single collection for all documents with per-source chunking

[[collections]]
name = "prometh_cortex"

# Document Sources Configuration
# Each source defines chunking parameters and path patterns
# Required: At least one source with source_patterns = ["*"]

[[sources]]
# Default source (catch-all for unmatched documents)
name = "default"
chunk_size = 512
chunk_overlap = 50
source_patterns = ["*"]

# Example: Knowledge base source for technical documentation
[[sources]]
name = "knowledge_base"
chunk_size = 768
chunk_overlap = 76
source_patterns = ["docs/specs", "docs/prds"]

# Example: Meetings source with smaller chunks for context
[[sources]]
name = "meetings"
chunk_size = 512
chunk_overlap = 51
source_patterns = ["meetings"]

# Example: Activity logs source for task-like documents
[[sources]]
name = "activity_logs"
chunk_size = 256
chunk_overlap = 26
source_patterns = ["todos", "reminders"]

[vector_store]
# Vector store backend: "faiss" (local) or "qdrant" (scalable)
type = "faiss"

# Qdrant configuration (when type = "qdrant")
[vector_store.qdrant]
host = "localhost"
port = 6333
collection_name = "prometh_cortex"
# api_key = "your-qdrant-api-key"  # For Qdrant Cloud
# use_https = true  # For Qdrant Cloud

# FAISS configuration (when type = "faiss") 
[vector_store.faiss]
# FAISS uses local file storage - no additional config needed

[structured_query]
# Enhanced search with metadata filtering
core_fields = ["tags", "created", "modified", "category", "author"]
extended_fields = ["status", "focus", "title", "subject", "organizer", "location"]
auto_discovery = true
max_auto_fields = 10

# MCP timeout handling configuration
[mcp.timeouts]
# Timeout settings for MCP operations
default_query_timeout = 60          # Default timeout in seconds
max_query_timeout = 300             # Maximum timeout in seconds
progress_update_interval = 5        # Progress update interval in seconds
chunk_size_default = 50             # Default chunk size for chunked queries
max_concurrent_operations = 10      # Maximum concurrent operations

[mcp.async_operations]
# Async operation management
enable_async_processing = true      # Enable async operation processing
operation_ttl_seconds = 1800        # Operation time-to-live (30 minutes)
cleanup_interval_seconds = 300      # Cleanup interval (5 minutes)

[mcp.startup]
# Startup optimization settings
max_startup_time = 50.0             # Maximum server startup time in seconds
lazy_load_index = true              # Enable lazy loading of index
"""
    
    path.write_text(sample_content)
    print(f"Sample configuration file created at: {path}")
    print("Copy this file to config.toml and edit it with your specific settings.")


if __name__ == "__main__":
    # Create sample config.toml file if run directly
    create_sample_config_file()