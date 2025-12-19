"""Multi-collection document indexer for RAG operations (v0.2.0+)."""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Callable
from copy import deepcopy

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from prometh_cortex.config import Config, CollectionConfig
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
    """Multi-collection document indexer for RAG operations (v0.2.0+)."""

    def __init__(self, config: Config):
        """
        Initialize multi-collection document indexer.

        Args:
            config: Configuration object with collection settings

        Raises:
            IndexerError: If initialization fails
        """
        self.config = config
        self.embed_model = None
        self.router = None
        self.collection_stores: Dict[str, VectorStoreInterface] = {}
        self.change_detectors: Dict[str, DocumentChangeDetector] = {}
        self.query_parser = QueryParser(config=config)
        self.auto_discovered_fields: Optional[Set[str]] = None

        # Initialize components
        self._initialize_embedding_model()
        self._initialize_router()
        self._initialize_collections()

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
        """Initialize the document router."""
        try:
            self.router = DocumentRouter(self.config.collections)
            logger.info(
                f"Document router initialized with {len(self.config.collections)} collections"
            )
        except RouterError as e:
            raise IndexerError(f"Failed to initialize router: {e}")

    def _initialize_collections(self) -> None:
        """Initialize vector stores for all collections."""
        for collection_config in self.config.collections:
            try:
                # Create collection storage directory
                storage_path = (
                    self.config.rag_index_dir / "collections" / collection_config.name
                )
                storage_path.mkdir(parents=True, exist_ok=True)

                # Create collection-specific config
                collection_store_config = self._create_collection_config(collection_config)

                # Initialize vector store
                vector_store = create_vector_store(collection_store_config, self.embed_model)
                vector_store.initialize()

                self.collection_stores[collection_config.name] = vector_store

                # Initialize change detector for collection
                metadata_path = storage_path / "change_metadata.json"
                self.change_detectors[collection_config.name] = DocumentChangeDetector(
                    str(metadata_path)
                )

                logger.info(f"Initialized collection: {collection_config.name}")

            except Exception as e:
                raise IndexerError(f"Failed to initialize collection '{collection_config.name}': {e}")

    def _create_collection_config(self, collection_config: CollectionConfig) -> Config:
        """
        Create a Config object for a specific collection.

        Args:
            collection_config: Collection configuration

        Returns:
            Config object with collection-specific settings

        Raises:
            IndexerError: If config creation fails
        """
        try:
            # Clone the main config
            config_dict = self.config.dict()

            # Override collection-specific settings
            config_dict["chunk_size"] = collection_config.chunk_size
            config_dict["chunk_overlap"] = collection_config.chunk_overlap

            # Override storage path for collection
            config_dict["rag_index_dir"] = (
                self.config.rag_index_dir / "collections" / collection_config.name
            )

            # Set unique collection name for vector stores
            if self.config.vector_store_type == "qdrant":
                config_dict["qdrant_collection_name"] = collection_config.name
            elif self.config.vector_store_type == "faiss":
                # FAISS uses filesystem paths, so collection name is handled by rag_index_dir
                pass

            # Create new Config object
            collection_config_obj = Config(**config_dict)

            return collection_config_obj

        except Exception as e:
            raise IndexerError(f"Failed to create collection config: {e}")

    def discover_documents(self) -> List[str]:
        """
        Discover all Markdown documents from source patterns in collections.

        Scans each collection's source_patterns directories for markdown files.

        Returns:
            List of document file paths
        """
        document_paths = []
        discovered_patterns = set()

        # Collect all unique source patterns from all collections
        for collection in self.config.collections:
            for pattern in collection.source_patterns:
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
        Route documents to their collections.

        Args:
            document_paths: List of document file paths

        Returns:
            Dictionary mapping collection names to list of document paths
        """
        routed = {coll.name: [] for coll in self.config.collections}

        for doc_path in document_paths:
            try:
                collection = self.router.route_document(doc_path)
                routed[collection].append(doc_path)
            except RouterError as e:
                logger.warning(f"Failed to route document {doc_path}: {e}")
                # Default to "default" collection on routing failure
                routed["default"].append(doc_path)

        return routed

    def add_document(self, file_path: Path, collection: str) -> bool:
        """
        Add a single document to a specific collection.

        Args:
            file_path: Path to markdown file to index
            collection: Target collection name

        Returns:
            True if successful, False otherwise

        Raises:
            IndexerError: If document addition fails
        """
        if collection not in self.collection_stores:
            raise IndexerError(f"Collection '{collection}' not found")

        try:
            # Parse markdown document
            markdown_doc = parse_markdown_file(file_path)

            # Get collection-specific chunking config
            collection_config = self.router.get_collection_config(collection)

            # Extract chunks with collection-specific parameters
            chunks = extract_document_chunks(
                markdown_doc,
                chunk_size=collection_config.chunk_size,
                chunk_overlap=collection_config.chunk_overlap,
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
                        "collection": collection,
                        "chunk_config": {
                            "chunk_size": collection_config.chunk_size,
                            "chunk_overlap": collection_config.chunk_overlap,
                        },
                    },
                }
                documents.append(doc)

            # Add to collection's vector store
            vector_store = self.collection_stores[collection]
            vector_store.add_documents(documents)

            return True

        except Exception as e:
            raise IndexerError(f"Failed to add document {file_path} to collection '{collection}': {e}")

    def add_documents(self, collection_docs: Dict[str, List[Path]]) -> Dict[str, Any]:
        """
        Add multiple documents to their respective collections.

        Args:
            collection_docs: Dictionary mapping collection names to list of document paths

        Returns:
            Statistics dict with per-collection success/failure counts
        """
        stats = {"collections": {}, "total_added": 0, "total_failed": 0, "errors": []}

        for collection_name, file_paths in collection_docs.items():
            collection_stats = {"added": 0, "failed": 0, "errors": []}

            for file_path in file_paths:
                try:
                    if self.add_document(Path(file_path), collection_name):
                        collection_stats["added"] += 1
                except Exception as e:
                    collection_stats["failed"] += 1
                    error_msg = f"{file_path}: {str(e)}"
                    collection_stats["errors"].append(error_msg)
                    stats["errors"].append(error_msg)
                    logger.error(f"Failed to add document {file_path}: {e}")

            stats["collections"][collection_name] = collection_stats
            stats["total_added"] += collection_stats["added"]
            stats["total_failed"] += collection_stats["failed"]

        return stats

    def build_index(
        self,
        force_rebuild: bool = False,
        progress_callback: Optional[Callable[[str, str, Any], None]] = None
    ) -> Dict[str, Any]:
        """
        Build indexes for all collections.

        Args:
            force_rebuild: If True, rebuild entire indexes ignoring changes
            progress_callback: Optional callback function to report progress.
                             Signature: callback(event_type: str, collection_name: str, data: Any)
                             event_type can be: "start", "complete", "error"
                             Example: callback("start", "prmth_projects", {"doc_count": 20})

        Returns:
            Statistics dict with per-collection results
        """
        try:
            # Discover all documents from collection source patterns
            document_paths = self.discover_documents()

            if not document_paths:
                logger.warning("No documents found from collection source patterns")
                return {"message": "No documents found", "collections": {}}

            # Route documents to collections
            routed_docs = self._route_documents(document_paths)

            stats = {"collections": {}, "total_added": 0, "total_failed": 0}

            # Build each collection
            for collection_name, docs in routed_docs.items():
                if not docs:
                    logger.info(f"No documents for collection '{collection_name}'")
                    stats["collections"][collection_name] = {"added": 0, "failed": 0}
                    continue

                try:
                    # Report start of collection build
                    if progress_callback:
                        progress_callback("start", collection_name, {"doc_count": len(docs)})

                    collection_stats = self._build_collection(
                        collection_name, docs, force_rebuild
                    )
                    stats["collections"][collection_name] = collection_stats
                    stats["total_added"] += collection_stats.get("added", 0)
                    stats["total_failed"] += collection_stats.get("failed", 0)

                    # Report completion of collection build
                    if progress_callback:
                        progress_callback("complete", collection_name, collection_stats)

                except Exception as e:
                    logger.error(f"Failed to build collection '{collection_name}': {e}")
                    stats["collections"][collection_name] = {"added": 0, "failed": len(docs), "error": str(e)}
                    stats["total_failed"] += len(docs)

                    # Report error in collection build
                    if progress_callback:
                        progress_callback("error", collection_name, {"error": str(e)})

            logger.info(f"Index build completed: {stats}")
            return stats

        except Exception as e:
            raise IndexerError(f"Failed to build indexes: {e}")

    def _build_collection(
        self, collection_name: str, docs: List[str], force: bool
    ) -> Dict[str, Any]:
        """
        Build index for a specific collection.

        Args:
            collection_name: Name of collection to build
            docs: List of document paths for this collection
            force: Force full rebuild

        Returns:
            Collection statistics
        """
        vector_store = self.collection_stores[collection_name]
        change_detector = self.change_detectors[collection_name]

        if force:
            # Force full rebuild
            logger.info(f"Performing full rebuild for collection '{collection_name}'")
            change_detector.reset()
            vector_store.delete_collection()
            vector_store.initialize()

            # Add all documents
            add_stats = self.add_documents({collection_name: [Path(d) for d in docs]})

            # Update change detector metadata
            changes = []
            for doc_path in docs:
                if Path(doc_path).exists():
                    import os
                    changes.append(
                        DocumentChange(
                            file_path=doc_path,
                            change_type="add",
                            file_hash=change_detector._compute_file_hash(doc_path),
                            modified_time=os.path.getmtime(doc_path),
                        )
                    )
            change_detector.update_metadata(changes)

            return add_stats["collections"][collection_name]

        else:
            # Incremental build
            logger.info(f"Performing incremental update for collection '{collection_name}'")
            changes = change_detector.detect_changes(docs)

            if not changes:
                logger.info(f"No changes detected for collection '{collection_name}'")
                return {"added": 0, "failed": 0, "message": "No changes detected"}

            logger.info(f"Detected {len(changes)} changes in collection '{collection_name}'")

            # Apply incremental changes
            vector_store.apply_incremental_changes(changes)

            # Process documents that need content updates
            docs_to_process = [
                Path(c.file_path)
                for c in changes
                if c.change_type in ["add", "update"]
            ]

            add_stats = self.add_documents({collection_name: docs_to_process})

            # Update change detector
            successful_changes = [
                c for c in changes
                if c.change_type == "delete" or
                str(c.file_path) not in [
                    e.split(":")[0] for e in add_stats.get("errors", [])
                ]
            ]
            change_detector.update_metadata(successful_changes)

            return add_stats["collections"][collection_name]

    def load_index(self) -> None:
        """Load existing indexes for all collections."""
        try:
            for collection_name, vector_store in self.collection_stores.items():
                try:
                    if hasattr(vector_store, "load_index"):
                        vector_store.load_index()
                    logger.info(f"Loaded index for collection '{collection_name}'")
                except Exception as e:
                    logger.debug(f"Could not load index for collection '{collection_name}': {e}")

            # Trigger auto-discovery of filterable fields
            self.update_query_parser_fields()

        except Exception as e:
            logger.warning(f"Error during index loading: {e}")

    def query(
        self,
        query_text: str,
        collection: Optional[str] = None,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query the indexes with optional collection filtering.

        Args:
            query_text: Query text (simple or structured)
            collection: Specific collection name to query (None = all collections)
            max_results: Maximum number of results to return
            filters: Optional metadata filters

        Returns:
            List of result dictionaries with content, metadata, and scores

        Raises:
            IndexerError: If querying fails
        """
        if not self.collection_stores:
            raise IndexerError("No collections initialized")

        if max_results is None:
            max_results = self.config.max_query_results

        try:
            if collection:
                # Query specific collection
                if collection not in self.collection_stores:
                    raise IndexerError(f"Collection '{collection}' not found")
                return self._query_collection(collection, query_text, max_results, filters)
            else:
                # Query all collections and merge results
                return self._query_all_collections(query_text, max_results, filters)

        except Exception as e:
            raise IndexerError(f"Query failed: {e}")

    def _query_collection(
        self,
        collection: str,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query a single collection."""
        vector_store = self.collection_stores[collection]
        collection_config = self.router.get_collection_config(collection)

        # Parse structured query
        parsed_query = self.query_parser.parse_query(query_text)

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

        # Perform vector search
        search_limit = max_results * 3 if parsed_query.metadata_filters else max_results
        results = vector_store.query(
            query_vector=query_vector,
            top_k=search_limit,
            filters=combined_filters if combined_filters else None,
        )

        # Add collection metadata to results
        for result in results:
            result["collection"] = collection
            result["chunk_config"] = {
                "chunk_size": collection_config.chunk_size,
                "chunk_overlap": collection_config.chunk_overlap,
            }

        return results[:max_results]

    def _query_all_collections(
        self,
        query_text: str,
        max_results: int,
        filters: Optional[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Query all collections and merge results by score."""
        all_results = []

        for collection_name in self.router.get_collection_names():
            try:
                collection_results = self._query_collection(
                    collection_name, query_text, max_results * 2, filters
                )
                all_results.extend(collection_results)
            except Exception as e:
                logger.warning(f"Failed to query collection '{collection_name}': {e}")

        # Sort by similarity score
        all_results.sort(key=lambda x: x.get("similarity_score", 0), reverse=True)

        return all_results[:max_results]

    def query_by_text(
        self,
        query_text: str,
        collection: Optional[str] = None,
        max_results: Optional[int] = None,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Convenience method that delegates to query."""
        return self.query(query_text, collection, max_results, filters)

    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about all collections."""
        stats = {
            "embedding_model": self.config.embedding_model,
            "total_collections": len(self.collection_stores),
            "collections": {},
        }

        for collection_name, vector_store in self.collection_stores.items():
            collection_config = self.router.get_collection_config(collection_name)
            collection_stats = vector_store.get_stats()
            collection_stats["chunk_size"] = collection_config.chunk_size
            collection_stats["chunk_overlap"] = collection_config.chunk_overlap
            stats["collections"][collection_name] = collection_stats

        return stats

    def list_collections(self) -> List[Dict[str, Any]]:
        """List all collections with metadata."""
        collections = []

        for collection_config in self.config.collections:
            metadata_path = (
                self.config.rag_index_dir
                / "collections"
                / collection_config.name
                / "metadata.json"
            )

            collection_info = {
                "name": collection_config.name,
                "chunk_size": collection_config.chunk_size,
                "chunk_overlap": collection_config.chunk_overlap,
                "source_patterns": collection_config.source_patterns,
                "document_count": 0,
                "last_updated": None,
            }

            # Try to load metadata if it exists
            if metadata_path.exists():
                try:
                    with open(metadata_path) as f:
                        metadata = json.load(f)
                        collection_info.update(metadata)
                except Exception as e:
                    logger.warning(f"Could not load metadata for collection '{collection_config.name}': {e}")

            collections.append(collection_info)

        return collections

    def auto_discover_filterable_fields(
        self, min_frequency: float = 0.1, sample_size: int = 50
    ) -> Set[str]:
        """
        Auto-discover fields that are good candidates for structured query filtering.

        Args:
            min_frequency: Minimum frequency (0.0-1.0) for a field to be considered
            sample_size: Number of documents to sample for analysis

        Returns:
            Set of field names suitable for filtering
        """
        # Collect fields from all collections
        all_field_stats = {}

        for collection_name, vector_store in self.collection_stores.items():
            try:
                if not vector_store:
                    continue

                # Get sample from this collection
                sample_results = vector_store.query(
                    query_vector=self.embed_model.get_text_embedding("sample"),
                    top_k=sample_size,
                    filters=None,
                )

                for result in sample_results:
                    metadata = result.get("metadata", {})

                    for field_name, field_value in metadata.items():
                        if field_name in ["file_path", "chunk_index", "collection", "chunk_config"]:
                            continue

                        if field_name not in all_field_stats:
                            all_field_stats[field_name] = {
                                "count": 0,
                                "types": set(),
                                "sample_values": set(),
                            }

                        all_field_stats[field_name]["count"] += 1
                        all_field_stats[field_name]["types"].add(type(field_value).__name__)

                        if len(all_field_stats[field_name]["sample_values"]) < 5:
                            if isinstance(field_value, (str, int, float)):
                                all_field_stats[field_name]["sample_values"].add(
                                    str(field_value)[:50]
                                )
                            elif isinstance(field_value, list):
                                all_field_stats[field_name]["sample_values"].add(
                                    f"[{len(field_value)} items]"
                                )

            except Exception as e:
                logger.warning(f"Failed to auto-discover fields in collection '{collection_name}': {e}")

        # Score fields
        filterable_fields = set()
        total_samples = len(self.collection_stores) * sample_size

        for field_name, stats in all_field_stats.items():
            frequency = stats["count"] / max(total_samples, 1)

            if frequency < min_frequency:
                continue

            score = 0
            score += min(frequency, 1.0) * 10

            if "str" in stats["types"]:
                score += 5
            if "list" in stats["types"]:
                score += 8
            if "int" in stats["types"] or "float" in stats["types"]:
                score += 3

            field_lower = field_name.lower()
            if any(pattern in field_lower for pattern in [
                "tag", "category", "status", "type", "author", "owner", "priority"
            ]):
                score += 15
            elif any(pattern in field_lower for pattern in [
                "subject", "title", "name", "organizer", "location", "focus"
            ]):
                score += 10

            if score >= 15:
                filterable_fields.add(field_name)

        return filterable_fields

    def update_query_parser_fields(self) -> None:
        """Update query parser with auto-discovered fields."""
        if self.config.structured_query_auto_discovery:
            discovered = self.auto_discover_filterable_fields()
            self.auto_discovered_fields = discovered
            self.query_parser.update_auto_discovered_fields(discovered)
            logger.info(f"Auto-discovered {len(discovered)} filterable fields: {sorted(discovered)}")

    def delete_index(self) -> None:
        """Delete all collection indexes."""
        try:
            for collection_name, vector_store in self.collection_stores.items():
                if vector_store:
                    vector_store.delete_collection()

                # Reset change detector
                if collection_name in self.change_detectors:
                    self.change_detectors[collection_name].reset()

            logger.info("All indexes deleted")
        except Exception as e:
            raise IndexerError(f"Failed to delete indexes: {e}")

    def backup_index(self, backup_path: str) -> None:
        """Backup all collection indexes metadata."""
        try:
            for collection_name, vector_store in self.collection_stores.items():
                if vector_store:
                    vector_backup_path = f"{backup_path}_{collection_name}_vector_store.json"
                    vector_store.backup_metadata(vector_backup_path)

                if collection_name in self.change_detectors:
                    change_backup_path = f"{backup_path}_{collection_name}_change_detector.json"
                    self.change_detectors[collection_name].backup_metadata(change_backup_path)

            logger.info("Indexes backed up")
        except Exception as e:
            raise IndexerError(f"Failed to backup indexes: {e}")

    def restore_index(self, backup_path: str) -> None:
        """Restore all collection indexes metadata."""
        try:
            for collection_name, vector_store in self.collection_stores.items():
                if vector_store:
                    vector_backup_path = f"{backup_path}_{collection_name}_vector_store.json"
                    vector_store.restore_metadata(vector_backup_path)

                if collection_name in self.change_detectors:
                    change_backup_path = f"{backup_path}_{collection_name}_change_detector.json"
                    self.change_detectors[collection_name].restore_metadata(change_backup_path)

            logger.info("Indexes restored")
        except Exception as e:
            raise IndexerError(f"Failed to restore indexes: {e}")
