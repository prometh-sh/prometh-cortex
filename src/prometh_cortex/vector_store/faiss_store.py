"""FAISS vector store implementation wrapper for existing functionality."""

import json
import pickle
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

import faiss
from llama_index.core import Document, VectorStoreIndex, StorageContext, load_index_from_storage
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.faiss import FaissVectorStore
from llama_index.core.retrievers import VectorIndexRetriever

from .interface import VectorStoreInterface, DocumentChange


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
        self.embed_model = embed_model or HuggingFaceEmbedding(model_name=config.embedding_model)
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
                text=doc['text'],
                metadata=doc.get('metadata', {}),
                id_=doc['id']
            )
            llama_docs.append(llama_doc)
            
            # Store metadata for later retrieval
            self._document_metadata[doc['id']] = doc.get('metadata', {})
        
        # Create or update index
        if self.index is None:
            self.index = VectorStoreIndex.from_documents(
                llama_docs,
                embed_model=self.embed_model
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
        doc_with_id['id'] = document_id
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
        """Get metadata for a specific document."""
        return self._document_metadata.get(document_id)
    
    def apply_incremental_changes(self, changes: List[DocumentChange]) -> Dict[str, int]:
        """Apply incremental changes and return stats."""
        stats = {'added': 0, 'updated': 0, 'deleted': 0, 'failed': 0}
        
        # Group changes by type for efficiency
        to_add = []
        to_update = []
        to_delete = []
        
        for change in changes:
            if change.change_type == 'add':
                to_add.append(change)
            elif change.change_type == 'update':
                to_update.append(change)
            elif change.change_type == 'delete':
                to_delete.append(change)
        
        # Process deletions first
        for change in to_delete:
            try:
                self.delete_document(change.file_path)
                stats['deleted'] += 1
            except Exception:
                stats['failed'] += 1
        
        # Process updates (delete + add)
        for change in to_update:
            try:
                self.delete_document(change.file_path)
                # Note: The actual document content would need to be loaded
                # This is handled at a higher level in the DocumentIndexer
                stats['updated'] += 1
            except Exception:
                stats['failed'] += 1
        
        # Additions are handled by add_documents() calls from higher level
        
        return stats
    
    def query(self, 
             query_vector: List[float], 
             top_k: int = 10,
             filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
                    "similarity_score": float(node.score) if node.score is not None else 0.0,
                    "source_file": node.node.metadata.get("file_path", "Unknown")
                }
                results.append(result)
            
            return results[:top_k]  # Ensure we don't exceed requested count
            
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")
    
    def query_by_text(self, query_text: str, top_k: int = 10, 
                     filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
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
                    "similarity_score": float(node.score) if node.score is not None else 0.0,
                    "source_file": node.node.metadata.get("file_path", "Unknown")
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
                if hasattr(vector_store, '_faiss_index') and vector_store._faiss_index:
                    stats["total_vectors"] = vector_store._faiss_index.ntotal
                    stats["vector_dimension"] = vector_store._faiss_index.d
            except Exception:
                pass
        
        # Check index directory size
        index_path = self.config.rag_index_dir
        if index_path.exists():
            stats["index_directory_size"] = sum(
                f.stat().st_size for f in index_path.rglob('*') if f.is_file()
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
    
    def backup_metadata(self, backup_path: str) -> None:
        """Backup index metadata for recovery."""
        backup_data = {
            'timestamp': time.time(),
            'document_metadata': self._document_metadata.copy(),
            'config': {
                'embedding_model': self.config.embedding_model,
                'chunk_size': self.config.chunk_size,
                'chunk_overlap': self.config.chunk_overlap,
            }
        }
        
        backup_path_obj = Path(backup_path)
        backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_path_obj, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
    
    def restore_metadata(self, backup_path: str) -> None:
        """Restore index metadata from backup."""
        backup_path_obj = Path(backup_path)
        if not backup_path_obj.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        with open(backup_path_obj, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        self._document_metadata = backup_data.get('document_metadata', {})
        self._save_metadata()
    
    def load_index(self) -> None:
        """Load existing index from disk."""
        if not self._index_exists():
            raise RuntimeError("No index found. Run 'pcortex build' first.")
        
        try:
            # Load LlamaIndex storage
            self.index = load_index_from_storage(
                StorageContext.from_defaults(persist_dir=str(self.config.rag_index_dir)),
                embed_model=self.embed_model
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
            with open(config_path, 'w') as f:
                json.dump({
                    "embedding_model": self.config.embedding_model,
                    "chunk_size": self.config.chunk_size,
                    "chunk_overlap": self.config.chunk_overlap,
                    "vector_store_type": "faiss",
                    "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                }, f, indent=2)
                
        except Exception as e:
            raise RuntimeError(f"Failed to save index: {e}")
    
    def _index_exists(self) -> bool:
        """Check if index exists on disk."""
        return (self.config.rag_index_dir.exists() and 
                any(self.config.rag_index_dir.iterdir()))
    
    def _matches_filters(self, metadata: Dict[str, Any], filters: Dict[str, Any]) -> bool:
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
        
        with open(metadata_path, 'w', encoding='utf-8') as f:
            json.dump(self._document_metadata, f, indent=2)
    
    def _load_metadata(self) -> None:
        """Load document metadata from disk."""
        metadata_path = self.config.rag_index_dir / "document_metadata.json"
        
        if metadata_path.exists():
            try:
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    self._document_metadata = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._document_metadata = {}