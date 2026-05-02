"""FAISS vector store implementation wrapper for existing functionality."""

import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import faiss
from llama_index.core import (
    Document,
    StorageContext,
    VectorStoreIndex,
    load_index_from_storage,
)
from llama_index.core.retrievers import VectorIndexRetriever
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore

from .interface import DocumentChange, VectorStoreInterface


class FAISSVectorStore(VectorStoreInterface):
    """FAISS vector store implementation using LlamaIndex."""

    def __init__(self, config, embed_model=None):
        """Initialize FAISS vector store.

        Args:
            config: Configuration object
            embed_model: Pre-initialized embedding model (optional)
        """
        self.config = config
        self.index: Optional[VectorStoreIndex] = None
        self.embed_model = embed_model or HuggingFaceEmbedding(
            model_name=config.embedding_model
        )
        self._document_metadata: Dict[str, Dict[str, Any]] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Initialize the vector store connection and setup."""
        try:
            # Try to load existing index first
            if self._index_exists():
                self.load_index()
            self._initialized = True
        except Exception as e:
            # If loading fails, we'll create a new index on first add_documents
            self._initialized = True

    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents with vectors and metadata.

        Args:
            documents: List of documents with 'id', 'text', 'metadata' keys
        """
        if not documents:
            return

        # Convert to LlamaIndex Document objects
        llama_docs = []
        for doc in documents:
            llama_doc = Document(
                text=doc["text"], metadata=doc.get("metadata", {}), id_=doc["id"]
            )
            llama_docs.append(llama_doc)

            # Store metadata for later retrieval
            self._document_metadata[doc["id"]] = doc.get("metadata", {})

        # Create or update index
        if self.index is None:
            self.index = VectorStoreIndex.from_documents(
                llama_docs, embed_model=self.embed_model
            )
        else:
            for doc in llama_docs:
                self.index.insert(doc)

        # Save metadata
        self._save_metadata()

    def update_document(self, document_id: str, document: Dict[str, Any]) -> None:
        """Update a single document by ID."""
        # LlamaIndex doesn't have direct update, so we delete and add
        self.delete_document(document_id)

        # Add the updated document
        doc_with_id = document.copy()
        doc_with_id["id"] = document_id
        self.add_documents([doc_with_id])

    def delete_document(self, document_id: str) -> None:
        """Delete a single document by ID."""
        if self.index is None:
            return

        try:
            # LlamaIndex doesn't have direct delete, this is a limitation
            # We'll track this in metadata and filter during queries
            self._document_metadata.pop(document_id, None)
            self._save_metadata()

            # Note: This is a limitation of the current LlamaIndex FAISS implementation
            # For true deletion, we'd need to rebuild the entire index
        except Exception:
            pass

    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists in the index."""
        return document_id in self._document_metadata

    def get_indexed_documents(self) -> Set[str]:
        """Get set of all indexed document IDs/paths."""
        return set(self._document_metadata.keys())

    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific document.

        For chunked documents (e.g., memory chunks like memory_hash_0, memory_hash_1),
        this tries exact match first, then falls back to finding the first chunk
        of the parent document (e.g., memory_hash).
        """
        # Try exact match first
        if document_id in self._document_metadata:
            return self._document_metadata[document_id]

        # For chunked documents, try to find the first chunk of the parent
        first_chunk_id = f"{document_id}_0"
        if first_chunk_id in self._document_metadata:
            return self._document_metadata[first_chunk_id]

        return None

    def apply_incremental_changes(
        self, changes: List[DocumentChange]
    ) -> Dict[str, int]:
        """Apply incremental changes and return stats."""
        stats = {"added": 0, "updated": 0, "deleted": 0, "failed": 0}

        # Group changes by type for efficiency
        to_add = []
        to_update = []
        to_delete = []

        for change in changes:
            if change.change_type == "add":
                to_add.append(change)
            elif change.change_type == "update":
                to_update.append(change)
            elif change.change_type == "delete":
                to_delete.append(change)

        # Process deletions first
        for change in to_delete:
            try:
                self.delete_document(change.file_path)
                stats["deleted"] += 1
            except Exception:
                stats["failed"] += 1

        # Process updates (delete + add)
        for change in to_update:
            try:
                self.delete_document(change.file_path)
                # Note: The actual document content would need to be loaded
                # This is handled at a higher level in the DocumentIndexer
                stats["updated"] += 1
            except Exception:
                stats["failed"] += 1

        # Additions are handled by add_documents() calls from higher level

        return stats

    def query(
        self,
        query_vector: List[float],
        top_k: int = 10,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Search for similar vectors with optional metadata filters."""
        if self.index is None:
            return []

        try:
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k,
            )

            # Convert query vector to text (limitation of current approach)
            # In practice, this would be called with query text from higher level
            query_text = "query"  # This is a limitation of the wrapper approach

            nodes = retriever.retrieve(query_text)

            results = []
            for node in nodes:
                # Apply metadata filters if specified
                if filters and not self._matches_filters(node.node.metadata, filters):
                    continue

                result = {
                    "content": node.node.get_content(),
                    "metadata": dict(node.node.metadata),
                    "similarity_score": (
                        float(node.score) if node.score is not None else 0.0
                    ),
                    "source_file": node.node.metadata.get("file_path", "Unknown"),
                }
                results.append(result)

            return results[:top_k]  # Ensure we don't exceed requested count

        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")

    def query_by_text(
        self, query_text: str, top_k: int = 10, filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Query using text (convenience method for FAISS)."""
        if self.index is None:
            return []

        try:
            retriever = VectorIndexRetriever(
                index=self.index,
                similarity_top_k=top_k,
            )

            nodes = retriever.retrieve(query_text)

            results = []
            for node in nodes:
                # Apply metadata filters if specified
                if filters and not self._matches_filters(node.node.metadata, filters):
                    continue

                result = {
                    "content": node.node.get_content(),
                    "metadata": dict(node.node.metadata),
                    "similarity_score": (
                        float(node.score) if node.score is not None else 0.0
                    ),
                    "source_file": node.node.metadata.get("file_path", "Unknown"),
                }
                results.append(result)

            return results[:top_k]

        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics and health info."""
        stats = {
            "type": "faiss",
            "index_exists": self.index is not None,
            "embedding_model": self.config.embedding_model,
            "total_documents": len(self._document_metadata),
        }

        if self.index:
            try:
                vector_store = self.index.vector_store
                if hasattr(vector_store, "_faiss_index") and vector_store._faiss_index:
                    stats["total_vectors"] = vector_store._faiss_index.ntotal
                    stats["vector_dimension"] = vector_store._faiss_index.d
            except Exception:
                pass

        # Check index directory size
        index_path = self.config.rag_index_dir
        if index_path.exists():
            stats["index_directory_size"] = sum(
                f.stat().st_size for f in index_path.rglob("*") if f.is_file()
            )

        return stats

    def delete_collection(self) -> None:
        """Delete the entire collection/index."""
        self.index = None
        self._document_metadata.clear()

        # Delete index files
        index_path = self.config.rag_index_dir
        if index_path.exists():
            import shutil

            shutil.rmtree(index_path)

    def delete_documents_except_source(self, excluded_source: str) -> int:
        """Delete all documents except those from a specific source.

        For FAISS backend, we preserve memory metadata in a sidecar file
        and restore it after rebuild.

        Args:
            excluded_source: Source type to preserve (e.g., "prmth_memory")

        Returns:
            Number of documents deleted
        """
        import logging

        logger = logging.getLogger(__name__)

        # Find and backup memory documents metadata
        memory_metadata = {}
        for doc_id, metadata in self._document_metadata.items():
            if metadata.get("source_type") == excluded_source:
                memory_metadata[doc_id] = metadata

        deleted_count = len(self._document_metadata) - len(memory_metadata)

        # Save memory metadata to sidecar for restoration after rebuild
        if memory_metadata:
            sidecar_path = (
                self.config.rag_index_dir / f".{excluded_source}_sidecar.json"
            )
            # Create parent dir if needed (before delete_collection wipes everything)
            sidecar_path.parent.mkdir(parents=True, exist_ok=True)

            sidecar_data = {
                "timestamp": time.time(),
                "excluded_source": excluded_source,
                "memory_metadata": memory_metadata,
            }

            try:
                with open(sidecar_path, "w", encoding="utf-8") as f:
                    json.dump(sidecar_data, f, indent=2)
                logger.info(
                    f"Backed up {len(memory_metadata)} memory doc metadata to {sidecar_path}"
                )
            except Exception as e:
                logger.warning(f"Failed to backup memory metadata: {e}")

        # Clear everything
        self.delete_collection()

        # Restore memory metadata (vectors will be re-embedded on next query or rebuild)
        if memory_metadata:
            try:
                self._document_metadata = memory_metadata.copy()
                self._save_metadata()
                logger.info(
                    f"Restored {len(memory_metadata)} memory doc metadata after clear"
                )
            except Exception as e:
                logger.warning(f"Failed to restore memory metadata: {e}")

        logger.info(
            f"Deleted {deleted_count} documents (kept source_type='{excluded_source}')"
        )
        return deleted_count

    def backup_metadata(self, backup_path: str) -> None:
        """Backup index metadata for recovery."""
        backup_data = {
            "timestamp": time.time(),
            "document_metadata": self._document_metadata.copy(),
            "config": {
                "embedding_model": self.config.embedding_model,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
            },
        }

        backup_path_obj = Path(backup_path)
        backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_path_obj, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, indent=2)

    def restore_metadata(self, backup_path: str) -> None:
        """Restore index metadata from backup."""
        backup_path_obj = Path(backup_path)
        if not backup_path_obj.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")

        with open(backup_path_obj, "r", encoding="utf-8") as f:
            backup_data = json.load(f)

        self._document_metadata = backup_data.get("document_metadata", {})
        self._save_metadata()

    def load_index(self) -> None:
        """Load existing index from disk."""
        if not self._index_exists():
            raise RuntimeError("No index found. Run 'pcortex build' first.")

        try:
            # Load LlamaIndex storage
            self.index = load_index_from_storage(
                StorageContext.from_defaults(
                    persist_dir=str(self.config.rag_index_dir)
                ),
                embed_model=self.embed_model,
            )

            # Load metadata
            self._load_metadata()

        except Exception as e:
            raise RuntimeError(f"Failed to load index: {e}")

    def save_index(self) -> None:
        """Save index to disk."""
        if self.index is None:
            return

        try:
            # Ensure index directory exists
            self.config.rag_index_dir.mkdir(parents=True, exist_ok=True)

            # Save LlamaIndex storage
            self.index.storage_context.persist(str(self.config.rag_index_dir))

            # Save metadata
            self._save_metadata()

            # Save configuration
            config_path = self.config.rag_index_dir / "config.json"
            with open(config_path, "w") as f:
                json.dump(
                    {
                        "embedding_model": self.config.embedding_model,
                        "chunk_size": self.config.chunk_size,
                        "chunk_overlap": self.config.chunk_overlap,
                        "vector_store_type": "faiss",
                        "created_at": time.strftime(
                            "%Y-%m-%dT%H:%M:%SZ", time.gmtime()
                        ),
                    },
                    f,
                    indent=2,
                )

        except Exception as e:
            raise RuntimeError(f"Failed to save index: {e}")

    def _index_exists(self) -> bool:
        """Check if index exists on disk."""
        return self.config.rag_index_dir.exists() and any(
            self.config.rag_index_dir.iterdir()
        )

    def list_memory_documents(
        self,
        since: Optional[float] = None,
        project: Optional[str] = None,
        tag: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """List memory documents with optional filtering.

        Returns one entry per unique document_id (deduplicated across chunks).

        Args:
            since: Unix timestamp - only include docs created after this time
            project: Filter by metadata.project value
            tag: Filter by tag value

        Returns:
            List of memory documents with metadata, deduplicated by document_id
        """
        from logging import getLogger

        logger = getLogger(__name__)

        # Collect unique documents by document_id
        docs_by_id: Dict[str, Dict[str, Any]] = {}

        for doc_id, metadata in self._document_metadata.items():
            # Filter by source_type
            if metadata.get("source_type") != "prmth_memory":
                continue

            # Get the base document_id (remove chunk suffix if present)
            base_doc_id = metadata.get("document_id", doc_id)

            # Skip if already processed
            if base_doc_id in docs_by_id:
                continue

            # Apply time filter
            if since is not None:
                created_str = metadata.get("created")
                if created_str:
                    try:
                        # Parse ISO timestamp
                        from datetime import datetime

                        created_dt = datetime.fromisoformat(created_str.replace("Z", "+00:00"))
                        created_ts = created_dt.timestamp()
                        if created_ts < since:
                            continue
                    except Exception:
                        pass

            # Apply project filter
            if project is not None:
                if metadata.get("metadata", {}).get("project") != project:
                    continue

            # Apply tag filter
            if tag is not None:
                doc_tags = metadata.get("tags", [])
                if tag not in doc_tags:
                    continue

            # Add to results (deduplicated)
            docs_by_id[base_doc_id] = metadata

        # Convert to list and sort by created date (newest first)
        result = list(docs_by_id.values())
        try:
            from datetime import datetime

            result.sort(
                key=lambda x: datetime.fromisoformat(
                    x.get("created", "").replace("Z", "+00:00")
                ),
                reverse=True,
            )
        except Exception:
            pass

        return result

    def delete_memory_documents(self, document_ids: List[str]) -> int:
        """Delete specific memory documents by their document_ids.

        For FAISS, this removes metadata entries and rebuilds the index
        to exclude deleted documents.

        Args:
            document_ids: List of document_ids to delete

        Returns:
            Number of documents deleted
        """
        from logging import getLogger

        logger = getLogger(__name__)

        if not document_ids:
            return 0

        # Track which chunk IDs to delete
        chunk_ids_to_delete = set()

        # Find all chunk IDs that belong to the documents being deleted
        for doc_id, metadata in list(self._document_metadata.items()):
            if metadata.get("document_id") in document_ids:
                chunk_ids_to_delete.add(doc_id)

        if not chunk_ids_to_delete:
            logger.info(f"No chunks found for document_ids: {document_ids}")
            return 0

        # Remove from metadata
        for chunk_id in chunk_ids_to_delete:
            self._document_metadata.pop(chunk_id, None)

        # Save updated metadata
        self._save_metadata()

        # Rebuild index without deleted documents
        # This is necessary because FAISS doesn't support selective deletion
        if self.index is not None:
            try:
                # Save current metadata backup
                remaining_docs = {
                    doc_id: metadata
                    for doc_id, metadata in self._document_metadata.items()
                }

                # Clear index
                self.delete_collection()

                # Rebuild with remaining documents
                if remaining_docs:
                    from llama_index.core import Document

                    llama_docs = []
                    for doc_id, metadata in remaining_docs.items():
                        llama_doc = Document(
                            text=metadata.get("text", ""),
                            metadata=metadata,
                            id_=doc_id,
                        )
                        llama_docs.append(llama_doc)

                    if llama_docs:
                        self.index = VectorStoreIndex.from_documents(
                            llama_docs, embed_model=self.embed_model
                        )
                        self._save_metadata()

                logger.info(
                    f"Deleted {len(chunk_ids_to_delete)} chunks from {len(document_ids)} memory documents"
                )
            except Exception as e:
                logger.error(f"Failed to rebuild index after deletion: {e}")
                raise

        return len(document_ids)

    def _matches_filters(
        self, metadata: Dict[str, Any], filters: Dict[str, Any]
    ) -> bool:
        """Check if metadata matches the given filters."""
        for key, expected_value in filters.items():
            metadata_value = metadata.get(key)

            if isinstance(expected_value, list):
                # Check if any of the expected values match
                if metadata_value not in expected_value:
                    return False
            else:
                if metadata_value != expected_value:
                    return False

        return True

    def _save_metadata(self) -> None:
        """Save document metadata to disk."""
        metadata_path = self.config.rag_index_dir / "document_metadata.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(self._document_metadata, f, indent=2)

    def _load_metadata(self) -> None:
        """Load document metadata from disk."""
        metadata_path = self.config.rag_index_dir / "document_metadata.json"

        if metadata_path.exists():
            try:
                with open(metadata_path, "r", encoding="utf-8") as f:
                    self._document_metadata = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._document_metadata = {}
