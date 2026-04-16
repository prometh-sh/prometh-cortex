"""MCP configuration generators for various client integrations."""

import json
import sys
import shutil
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

from prometh_cortex.config.settings import Config, config_to_env_vars


_DEFAULT_SSE_URL = "http://127.0.0.1:3100"


def _format_codex_toml(config_dict: Dict[str, Any]) -> str:
    """Format TOML configuration for Codex CLI with inline env table.

    Args:
        config_dict: Configuration dictionary with special _env_inline marker

    Returns:
        Properly formatted TOML string
    """
    toml_lines = []

    for section_name, section_data in config_dict.items():
        toml_lines.append(f"[{section_name}]")

        for subsection_name, subsection_data in section_data.items():
            toml_lines.append(f"")  # Empty line before subsection
            toml_lines.append(f"[{section_name}.{subsection_name}]")

            for key, value in subsection_data.items():
                if key == "_env_inline":
                    # Format as inline table
                    env_pairs = []
                    for env_key, env_value in value.items():
                        # Escape quotes in values
                        escaped_value = env_value.replace('"', '\\"')
                        env_pairs.append(f'"{env_key}" = "{escaped_value}"')

                    inline_table = "{ " + ", ".join(env_pairs) + " }"
                    toml_lines.append(f"env = {inline_table}")
                elif key == "args":
                    # Format args array
                    args_str = "[" + ", ".join(f'"{arg}"' for arg in value) + "]"
                    toml_lines.append(f'{key} = {args_str}')
                else:
                    # Regular string value
                    toml_lines.append(f'{key} = "{value}"')

    return "\n".join(toml_lines)


def generate_config(
    target: str,
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate MCP configuration for the specified target.

    Args:
        target: Configuration target
        config: Prometh-Cortex configuration object
        transport: Transport mode - "stdio", "sse", or "streamable-http"
        url: SSE/HTTP server URL (used when transport != "stdio")

    Returns:
        Tuple of (config_dict, default_output_path)

    Raises:
        ValueError: If target is not supported
    """
    generators = {
        "claude": generate_claude_config,
        "vscode": generate_vscode_config,
        "codex": generate_codex_config,
        "perplexity": generate_perplexity_config,
        "opencode": generate_opencode_config,
    }

    generator = generators.get(target)
    if not generator:
        raise ValueError(f"Unsupported target: {target}. Supported: {', '.join(generators)}")

    return generator(config, transport=transport, url=url)


def _sse_url(url: Optional[str], transport: str) -> str:
    """Build the SSE/HTTP endpoint URL."""
    base = url or _DEFAULT_SSE_URL
    base = base.rstrip("/")
    if transport == "sse":
        return f"{base}/sse"
    # streamable-http uses /mcp by default in FastMCP
    return f"{base}/mcp"


def generate_claude_config(
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate Claude Desktop MCP configuration."""
    if transport != "stdio":
        endpoint = _sse_url(url, transport)
        claude_config = {
            "mcpServers": {
                "prometh-cortex": {
                    "url": endpoint
                }
            }
        }
    else:
        pcortex_path = _find_pcortex_executable()
        env_vars = config_to_env_vars(config)
        claude_config = {
            "mcpServers": {
                "prometh-cortex": {
                    "command": pcortex_path,
                    "args": ["mcp", "start"],
                    "env": env_vars
                }
            }
        }

    if sys.platform == "darwin":
        default_path = str(Path.home() / "Library/Application Support/Claude/claude_desktop_config.json")
    elif sys.platform == "win32":
        default_path = str(Path.home() / "AppData/Roaming/Claude/claude_desktop_config.json")
    else:
        default_path = str(Path.home() / ".config/Claude/claude_desktop_config.json")

    return claude_config, default_path


def generate_vscode_config(
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate VSCode MCP configuration."""
    if transport != "stdio":
        endpoint = _sse_url(url, transport)
        vscode_config = {
            "servers": {
                "prometh-cortex": {
                    "type": transport,
                    "url": endpoint
                }
            }
        }
    else:
        pcortex_path = _find_pcortex_executable()
        env_vars = config_to_env_vars(config)
        vscode_config = {
            "servers": {
                "prometh-cortex": {
                    "command": pcortex_path,
                    "args": ["mcp", "start"],
                    "env": env_vars
                }
            }
        }

    if sys.platform == "darwin":
        default_path = str(Path.home() / "Library/Application Support/Code/User/mcp.json")
    elif sys.platform == "win32":
        default_path = str(Path.home() / "AppData/Roaming/Code/User/mcp.json")
    else:
        default_path = str(Path.home() / ".config/Code/User/mcp.json")

    return vscode_config, default_path


def generate_codex_config(
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate Codex CLI MCP configuration."""
    if transport != "stdio":
        endpoint = _sse_url(url, transport)
        codex_config = {
            "mcp_servers": {
                "prometh-cortex": {
                    "type": transport,
                    "url": endpoint
                }
            }
        }
    else:
        pcortex_path = _find_pcortex_executable()
        env_vars = config_to_env_vars(config)
        codex_config = {
            "mcp_servers": {
                "prometh-cortex": {
                    "command": pcortex_path,
                    "args": ["mcp", "start"],
                    "_env_inline": env_vars
                }
            }
        }

    default_path = str(Path.home() / ".codex/config.toml")
    return codex_config, default_path


def generate_perplexity_config(
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate Perplexity MCP configuration."""
    if transport != "stdio":
        endpoint = _sse_url(url, transport)
        perplexity_config = {
            "type": transport,
            "url": endpoint
        }
    else:
        pcortex_path = _find_pcortex_executable()
        env_vars = config_to_env_vars(config)
        perplexity_config = {
            "command": pcortex_path,
            "args": ["mcp", "start"],
            "env": env_vars
        }

    default_path = str(Path.home() / ".perplexity/mcp_servers/prometh-cortex.json")
    return perplexity_config, default_path


def generate_opencode_config(
    config: Config,
    transport: str = "stdio",
    url: Optional[str] = None,
) -> Tuple[Dict[str, Any], str]:
    """Generate OpenCode MCP configuration.

    OpenCode uses "type": "local" for stdio and "type": "remote" for
    SSE/HTTP servers. Remote servers accept a "headers" object for auth.
    Config lives in ~/.config/opencode/opencode.json alongside other
    OpenCode settings (provider, permission, agent, etc.).
    """
    if transport != "stdio":
        endpoint = _sse_url(url, transport)
        server_entry: Dict[str, Any] = {
            "type": "remote",
            "url": endpoint,
            "enabled": True,
            "timeout": 60000
        }
        # Add auth header if token is configured
        if config.mcp_auth_token:
            server_entry["headers"] = {
                "Authorization": f"Bearer {config.mcp_auth_token}"
            }
    else:
        pcortex_path = _find_pcortex_executable()
        env_vars = config_to_env_vars(config)
        server_entry = {
            "type": "local",
            "command": [pcortex_path, "mcp", "start"],
            "environment": env_vars,
            "enabled": True,
            "timeout": 60000
        }

    opencode_config = {
        "mcp": {
            "prometh-cortex": server_entry
        }
    }

    default_path = str(Path.home() / ".config/opencode/opencode.json")
    return opencode_config, default_path


def _find_pcortex_executable() -> str:
    """Find the pcortex executable path.

    Returns:
        Path to pcortex executable

    Raises:
        RuntimeError: If pcortex executable cannot be found
    """
    # Try to find pcortex in the current virtual environment first
    if hasattr(sys, 'real_prefix') or (hasattr(sys, 'base_prefix') and sys.base_prefix != sys.prefix):
        # We're in a virtual environment
        venv_pcortex = Path(sys.prefix) / "bin" / "pcortex"
        if venv_pcortex.exists():
            return str(venv_pcortex)

    # Try to find pcortex in PATH
    pcortex_path = shutil.which("pcortex")
    if pcortex_path:
        return pcortex_path

    # Fallback: try common locations relative to current directory
    current_dir = Path.cwd()
    potential_paths = [
        current_dir / ".venv" / "bin" / "pcortex",
        current_dir / "venv" / "bin" / "pcortex",
        current_dir.parent / ".venv" / "bin" / "pcortex",
    ]

    for path in potential_paths:
        if path.exists():
            return str(path)

    # Last resort: use Python module approach
    python_executable = sys.executable
    return f"{python_executable} -m prometh_cortex.cli.main"


def get_config_summary(target: str, config: Config) -> str:
    """Generate a human-readable summary of the configuration.

    Args:
        target: Configuration target
        config: Prometh-Cortex configuration object

    Returns:
        Formatted summary string
    """
    pcortex_path = _find_pcortex_executable()

    summary = f"""
Configuration Summary for {target.title()}:
========================================

Pcortex Executable: {pcortex_path}
Vector Store: {config.vector_store_type}
Collections: {len(config.collections)} configured
MCP Server Command: pcortex mcp start

Datalake Paths:
"""

    for i, coll in enumerate(config.collections, 1):
        summary += f"  {i}. {coll.name}\n"

    # Show a sample of the environment variables that will be set
    env_vars = config_to_env_vars(config)
    summary += f"\nEnvironment Variables ({len(env_vars)} total):\n"

    # Show key environment variables
    key_vars = ["DATALAKE_REPOS", "VECTOR_STORE_TYPE", "QDRANT_HOST", "RAG_INDEX_DIR"]
    for var in key_vars:
        if var in env_vars:
            # Truncate long values for display
            value = env_vars[var]
            if len(value) > 60:
                value = value[:57] + "..."
            summary += f"  {var}: {value}\n"

    usage = {
        "claude": """
Usage in Claude Desktop:
1. Copy the generated configuration to your claude_desktop_config.json
2. Restart Claude Desktop
3. Use tools: "Search my documents for..." or "Check prometh-cortex health"
""",
        "vscode": """
Usage in VSCode:
1. Add the generated configuration to your settings.json
2. Install the MCP extension if not already installed
3. Reload VSCode window
4. Access via Command Palette: "MCP: List Servers"
""",
        "codex": """
Usage in Codex CLI:
1. Copy the generated configuration to your ~/.codex/config.toml
2. Restart Codex CLI or reload configuration
3. Use tools: "Search my documents for..." or "Check prometh-cortex health"
""",
        "perplexity": """
Usage in Perplexity:
1. Copy the generated configuration to your Perplexity MCP servers directory
2. Restart Perplexity or reload MCP servers
3. Use tools: "Search my documents for..." or "Check prometh-cortex health"
4. Query with: "Search my local knowledge base for information about..."
""",
        "opencode": """
Usage in OpenCode:
1. Copy the generated configuration to ~/.config/opencode/opencode.json
2. Restart OpenCode or reload MCP configuration
3. Use tools: "Search my documents for..." or "Check prometh-cortex health"
""",
    }

    summary += usage.get(target, "")
    return summary
