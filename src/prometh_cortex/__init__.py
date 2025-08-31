"""
Multi-Datalake RAG Indexer with Local MCP Integration.

A local-first, extensible system to index multiple datalake repositories 
containing Markdown files and expose their content for RAG workflows through
a local MCP server.
"""

__version__ = "0.1.0"
__author__ = "Ivan Nagy"
__email__ = "contact@example.com"

from prometh_cortex.config import Config, load_config
from prometh_cortex.parser import MarkdownDocument, parse_markdown_file
from prometh_cortex.indexer import DocumentIndexer

__all__ = [
    "Config",
    "load_config", 
    "MarkdownDocument",
    "parse_markdown_file",
    "DocumentIndexer",
]