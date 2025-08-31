"""Abstract interface for vector store implementations."""

import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set


@dataclass
class DocumentChange:
    """Represents a document change for incremental indexing."""
    file_path: str
    change_type: str  # 'add', 'update', 'delete'
    file_hash: Optional[str] = None
    modified_time: Optional[float] = None

    def __post_init__(self) -> None:
        """Validate change type."""
        valid_types = {'add', 'update', 'delete'}
        if self.change_type not in valid_types:
            raise ValueError(f"change_type must be one of {valid_types}")


class VectorStoreInterface(ABC):
    """Abstract interface for vector store implementations."""
    
    @abstractmethod
    def initialize(self) -> None:
        """Initialize the vector store connection and setup."""
        pass
    
    @abstractmethod
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents with vectors and metadata.
        
        Args:
            documents: List of documents with 'id', 'vector', 'metadata' keys
        """
        pass
    
    @abstractmethod
    def update_document(self, document_id: str, document: Dict[str, Any]) -> None:
        """Update a single document by ID.
        
        Args:
            document_id: Unique document identifier
            document: Document with 'vector' and 'metadata' keys
        """
        pass
    
    @abstractmethod
    def delete_document(self, document_id: str) -> None:
        """Delete a single document by ID.
        
        Args:
            document_id: Unique document identifier
        """
        pass
    
    @abstractmethod
    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists in the index.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            True if document exists, False otherwise
        """
        pass
    
    @abstractmethod
    def get_indexed_documents(self) -> Set[str]:
        """Get set of all indexed document IDs/paths.
        
        Returns:
            Set of document identifiers currently in the index
        """
        pass
    
    @abstractmethod
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific document.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            Document metadata dict or None if not found
        """
        pass
    
    @abstractmethod
    def apply_incremental_changes(self, changes: List[DocumentChange]) -> Dict[str, int]:
        """Apply incremental changes and return stats.
        
        Args:
            changes: List of document changes to apply
            
        Returns:
            Statistics dict with 'added', 'updated', 'deleted' counts
        """
        pass
    
    @abstractmethod
    def query(self, 
             query_vector: List[float], 
             top_k: int = 10,
             filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Search for similar vectors with optional metadata filters.
        
        Args:
            query_vector: Query vector for similarity search
            top_k: Number of results to return
            filters: Optional metadata filters
            
        Returns:
            List of similar documents with metadata and scores
        """
        pass
    
    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics and health info.
        
        Returns:
            Statistics dict with counts, performance metrics, etc.
        """
        pass
    
    @abstractmethod
    def delete_collection(self) -> None:
        """Delete the entire collection/index."""
        pass
    
    @abstractmethod
    def backup_metadata(self, backup_path: str) -> None:
        """Backup index metadata for recovery.
        
        Args:
            backup_path: Path to save backup metadata
        """
        pass
    
    @abstractmethod
    def restore_metadata(self, backup_path: str) -> None:
        """Restore index metadata from backup.
        
        Args:
            backup_path: Path to backup metadata file
        """
        pass