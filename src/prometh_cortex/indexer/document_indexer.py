"""Single-collection document indexer with per-document-source chunking for RAG operations (v0.3.0+)."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable, Tuple
from copy import deepcopy

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from prometh_cortex.config import Config, SourceConfig
from prometh_cortex.router import DocumentRouter, RouterError
from prometh_cortex.parser import (
    MarkdownDocument,
    parse_markdown_file,
    extract_document_chunks,
    QueryParser,
    ParsedQuery,
)
from prometh_cortex.vector_store import (
    VectorStoreInterface,
    DocumentChange,
    DocumentChangeDetector,
    create_vector_store,
)

logger = logging.getLogger(__name__)


class IndexerError(Exception):
    """Raised when indexer operations fail."""
    pass


class DocumentIndexer:
    """Single-collection document indexer with per-source chunking (v0.3.0+)."""

    def __init__(self, config: Config):
        """
        Initialize unified document indexer with per-source chunking.

        Args:
            config: Configuration object with sources and unified collection settings

        Raises:
            IndexerError: If initialization fails
        """
        self.config = config
        self.embed_model = None
        self.router = None
        self.vector_store: Optional[VectorStoreInterface] = None
        self.change_detector: Optional[DocumentChangeDetector] = None
        self.query_parser = QueryParser(config=config)
        self.auto_discovered_fields: Optional[Set[str]] = None

        # Initialize components
        self._initialize_embedding_model()
        self._initialize_router()
        self._initialize_vector_store()

    def _initialize_embedding_model(self) -> None:
        """Initialize the embedding model."""
        try:
            self.embed_model = HuggingFaceEmbedding(
                model_name=self.config.embedding_model
            )
            logger.info(f"Embedding model initialized: {self.config.embedding_model}")
        except Exception as e:
            raise IndexerError(
                f"Failed to initialize embedding model {self.config.embedding_model}: {e}"
            )

    def _initialize_router(self) -> None:
        """Initialize the document router for source-based chunking."""
        try:
            self.router = DocumentRouter(self.config.sources)
            logger.info(
                f"Document router initialized with {len(self.config.sources)} sources"
            )
        except RouterError as e:
            raise IndexerError(f"Failed to initialize router: {e}")

    def _initialize_vector_store(self) -> None:
        """Initialize single unified vector store."""
        try:
            storage_path = self.config.rag_index_dir
            storage_path.mkdir(parents=True, exist_ok=True)

            # Create vector store with config (chunk size is not used for storage)
            self.vector_store = create_vector_store(self.config, self.embed_model)
            self.vector_store.initialize()

            # Initialize change detector for single collection
            metadata_path = storage_path / "document_metadata.json"
            self.change_detector = DocumentChangeDetector(str(metadata_path))

            logger.info(
                f"Initialized unified collection: {self.config.collection.name}"
            )

        except Exception as e:
            raise IndexerError(f"Failed to initialize vector store: {e}")

    def discover_documents(self) -> List[str]:
        """
        Discover all Markdown documents from source patterns.

        Scans source pattern directories for markdown files.

        Returns:
            List of document file paths
        """
        document_paths = []
        discovered_patterns = set()

        # Collect all unique source patterns from all sources
        for source in self.config.sources:
            for pattern in source.source_patterns:
                if pattern != "*":  # Skip catch-all for now
                    discovered_patterns.add(pattern)

        # Scan each source pattern directory
        for pattern in discovered_patterns:
            pattern_path = Path(pattern)
            if pattern_path.exists() and pattern_path.is_dir():
                # Find all markdown files recursively in this pattern
                markdown_files = list(pattern_path.rglob("*.md"))
                document_paths.extend(str(f) for f in markdown_files)
            else:
                logger.warning(f"Source pattern path does not exist: {pattern}")

        if not document_paths:
            logger.warning("No documents discovered from source patterns")

        return sorted(document_paths)

    def _route_documents(
        self, document_paths: List[str]
    ) -> Dict[str, List[str]]:
        """
        Route documents to their sources.

        Args:
            document_paths: List of document file paths

        Returns:
            Dictionary mapping source names to list of document paths
        """
        routed: Dict[str, List[str]] = {source.name: [] for source in self.config.sources}

        for doc_path in document_paths:
            try:
                source_name, _, _ = self.router.route_document(doc_path)
                routed[source_name].append(doc_path)
            except RouterError as e:
                logger.warning(f"Failed to route document {doc_path}: {e}")
                # Default to "default" source on routing failure
                if "default" in routed:
                    routed["default"].append(doc_path)

        return routed

    def add_document(self, file_path: Path) -> Dict[str, Any]:
        """
        Add a single document to the unified index with source-specific chunking.

        Args:
            file_path: Path to markdown file to index

        Returns:
            Dictionary with status, source_type, and chunks count

        Raises:
            IndexerError: If document addition fails
        """
        try:
            # Parse markdown document
            markdown_doc = parse_markdown_file(file_path)

            # Route to get source and chunking parameters
            source_name, chunk_size, chunk_overlap = self.router.route_document(
                str(file_path)
            )

            # Extract chunks with source-specific parameters
            chunks = extract_document_chunks(
                markdown_doc,
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
            )

            # Convert chunks to documents for vector store
            documents = []
            for chunk in chunks:
                doc = {
                    "id": f"{file_path}_{chunk['chunk_index']}",
                    "text": chunk["content"],
                    "metadata": {
                        **chunk["metadata"],
                        "file_path": str(file_path),
                        "chunk_index": chunk["chunk_index"],
                        "source_type": source_name,  # Changed from "collection"
                        "chunk_config": {
                            "chunk_size": chunk_size,
                            "chunk_overlap": chunk_overlap,
                        },
                    },
                }
                documents.append(doc)

            # Add to unified vector store
            self.vector_store.add_documents(documents)

            return {
                "status": "success",
                "source_type": source_name,
                "chunks": len(chunks),
            }

        except Exception as e:
            raise IndexerError(f"Failed to add document {file_path}: {e}")

    def add_documents(self, source_docs: Dict[str, List[Path]]) -> Dict[str, Any]:
        """
        Add multiple documents to the unified index with per-source chunking.

        Args:
            source_docs: Dictionary mapping source names to list of document paths

        Returns:
            Statistics dict with per-source success/failure counts
        """
        stats = {"sources": {}, "total_added": 0, "total_failed": 0, "errors": []}

        for source_name, file_paths in source_docs.items():
            source_stats = {"added": 0, "failed": 0, "errors": []}

            for file_path in file_paths:
                try:
                    result = self.add_document(Path(file_path))
                    if result["status"] == "success":
                        source_stats["added"] += 1
                except Exception as e:
                    source_stats["failed"] += 1
                    error_msg = f"{file_path}: {str(e)}"
                    source_stats["errors"].append(error_msg)
                    stats["errors"].append(error_msg)
                    logger.error(f"Failed to add document {file_path}: {e}")

            stats["sources"][source_name] = source_stats
            stats["total_added"] += source_stats["added"]
            stats["total_failed"] += source_stats["failed"]

        return stats

    def build_index(
        self,
        force_rebuild: bool = False,
        progress_callback: Optional[Callable[[str, str, Any], None]] = None
    ) -> Dict[str, Any]:
        """
        Build unified index from all sources.

        Args:
            force_rebuild: If True, rebuild entire index ignoring changes
            progress_callback: Optional callback function to report progress.
                             Signature: callback(event_type: str, source_name: str, data: Any)
                             event_type can be: "start", "complete", "error"

        Returns:
            Statistics dict with per-source results
        """
        try:
            # Discover all documents from source patterns
            document_paths = self.discover_documents()

            if not document_paths:
                logger.warning("No documents found from source patterns")
                return {"message": "No documents found", "sources": {}}

            # Route documents to sources
            routed_docs = self._route_documents(document_paths)

            stats = {
                "total_documents": 0,
                "total_chunks": 0,
                "sources": {},
            }

            # Force rebuild: clear entire index
            if force_rebuild:
                logger.info("Performing full rebuild of unified index")
                self._clear_index()

            # Build unified index with per-document chunking
            index_stats = self._build_unified_index(routed_docs, force_rebuild, progress_callback)

            stats.update(index_stats)

            # Save unified index
            self.vector_store.save_index()

            logger.info(f"Index build completed: {stats}")
            return stats

        except Exception as e:
            raise IndexerError(f"Failed to build index: {e}")

    def _build_unified_index(
        self,
        routed_docs: Dict[str, List[str]],
        force: bool,
        progress_callback: Optional[Callable[[str, str, Any], None]] = None,
    ) -> Dict[str, Any]:
        """
        Build single unified index with per-document-source chunking.

        Args:
            routed_docs: Dictionary mapping source names to document paths
            force: Force full rebuild
            progress_callback: Optional progress callback

        Returns:
            Statistics dict
        """
        stats = {
            "total_documents": 0,
            "total_chunks": 0,
            "sources": {},
        }

        for source_name, docs in routed_docs.items():
            if not docs:
                logger.info(f"No documents for source '{source_name}'")
                stats["sources"][source_name] = {"documents": 0, "chunks": 0}
                continue

            try:
                # Report start of source processing
                if progress_callback:
                    progress_callback("start", source_name, {"doc_count": len(docs)})

                source_stats = {"documents": 0, "chunks": 0}

                for doc_path in docs:
                    # Detect changes
                    if not force and not self.change_detector.has_changed(doc_path):
                        continue

                    # Add document with source-specific chunking
                    result = self.add_document(Path(doc_path))

                    if result["status"] == "success":
                        source_stats["documents"] += 1
                        source_stats["chunks"] += result["chunks"]
                        # Update change detector metadata for incremental indexing
                        from prometh_cortex.vector_store.interface import DocumentChange
                        change = DocumentChange(
                            file_path=doc_path,
                            change_type="add" if doc_path not in self.change_detector.indexed_docs else "update",
                            file_hash=result.get("file_hash"),
                            modified_time=result.get("modified_time")
                        )
                        self.change_detector.update_metadata([change])

                stats["sources"][source_name] = source_stats
                stats["total_documents"] += source_stats["documents"]
                stats["total_chunks"] += source_stats["chunks"]

                # Report completion of source processing
                if progress_callback:
                    progress_callback("complete", source_name, source_stats)

            except Exception as e:
                logger.error(f"Failed to process source '{source_name}': {e}")
                stats["sources"][source_name] = {"documents": 0, "chunks": 0, "error": str(e)}

                # Report error in source processing
                if progress_callback:
                    progress_callback("error", source_name, {"error": str(e)})

        return stats

    def _clear_index(self) -> None:
        """Clear the unified index."""
        try:
            if hasattr(self.vector_store, "delete_collection"):
                self.vector_store.delete_collection()
            if hasattr(self.change_detector, "reset"):
                self.change_detector.reset()
            logger.info("Cleared unified index")
        except Exception as e:
            logger.warning(f"Error clearing index: {e}")

    def load_index(self) -> None:
        """Load existing unified index."""
        try:
            if hasattr(self.vector_store, "load_index"):
                self.vector_store.load_index()
            logger.info("Loaded unified index")

            # Trigger auto-discovery of filterable fields
            self.update_query_parser_fields()

        except Exception as e:
            logger.warning(f"Error during index loading: {e}")

    def query(
        self,
        query_text: str,
        source_type: Optional[str] = None,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the unified index with optional source filtering.

        Args:
            query_text: Query text (simple or structured)
            source_type: Specific source to filter by (None = all sources)
            max_results: Maximum number of results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries with content, metadata, and scores

        Raises:
            IndexerError: If querying fails
        """
        if not self.vector_store:
            raise IndexerError("Vector store not initialized")

        if max_results is None:
            max_results = self.config.max_query_results

        try:
            # Parse structured query
            parsed_query = self.query_parser.parse_query(query_text)

            # Add source filter if specified
            if source_type:
                if filters is None:
                    filters = {}
                filters["source_type"] = source_type

            # Build semantic query
            semantic_query = self.query_parser.build_semantic_query(parsed_query)

            # Generate query vector
            query_vector = self.embed_model.get_text_embedding(semantic_query)

            # Merge filters
            combined_filters = {}
            if filters:
                combined_filters.update(filters)
            if parsed_query.metadata_filters:
                qdrant_filters = self.query_parser.convert_to_qdrant_filters(
                    parsed_query.metadata_filters
                )
                combined_filters.update(qdrant_filters)

            # Perform vector search on unified index
            search_limit = max_results * 3 if parsed_query.metadata_filters else max_results
            results = self.vector_store.query(
                query_vector=query_vector,
                top_k=search_limit,
                filters=combined_filters if combined_filters else None,
            )

            return results[:max_results]

        except Exception as e:
            raise IndexerError(f"Query failed: {e}")

    def query_by_text(
        self,
        query_text: str,
        source_type: Optional[str] = None,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience method that delegates to query."""
        return self.query(query_text, source_type, max_results, filters)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the unified collection and sources."""
        stats = {
            "embedding_model": self.config.embedding_model,
            "collection": self.config.collection.name,
            "sources": {},
        }

        # Add stats for each source
        for source in self.config.sources:
            stats["sources"][source.name] = {
                "chunk_size": source.chunk_size,
                "chunk_overlap": source.chunk_overlap,
                "source_patterns": source.source_patterns,
            }

        # Add vector store stats
        if hasattr(self.vector_store, "get_stats"):
            stats["vector_store"] = self.vector_store.get_stats()

        return stats

    def list_sources(self) -> Dict[str, Any]:
        """
        List all sources with configuration details.

        Returns:
            Dictionary with collection info and list of source configurations
        """
        sources_list = [
            {
                "name": source.name,
                "chunk_size": source.chunk_size,
                "chunk_overlap": source.chunk_overlap,
                "source_patterns": source.source_patterns,
                "document_count": 0,  # Placeholder - would need index stats to populate
            }
            for source in self.config.sources
        ]

        return {
            "collection_name": self.config.collection.name,
            "sources": sources_list,
            "total_sources": len(sources_list),
            "total_documents": 0,  # Placeholder - would need index stats to populate
        }

    def update_query_parser_fields(self) -> None:
        """Update query parser with auto-discovered metadata fields."""
        try:
            if hasattr(self.vector_store, "get_all_metadata_fields"):
                fields = self.vector_store.get_all_metadata_fields()
                if fields:
                    self.query_parser.extended_fields.update(fields)
                    self.auto_discovered_fields = fields
                    logger.info(f"Auto-discovered {len(fields)} metadata fields")
        except Exception as e:
            logger.debug(f"Could not auto-discover metadata fields: {e}")
