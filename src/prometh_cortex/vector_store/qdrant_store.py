"""Qdrant vector store implementation."""

import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from qdrant_client import QdrantClient
from qdrant_client.models import (
    CollectionStatus,
    Distance,
    PointStruct,
    VectorParams,
    SearchRequest,
    Filter,
    FieldCondition,
    MatchValue,
    MatchAny,
    Range,
)

from .interface import VectorStoreInterface, DocumentChange


class QdrantVectorStore(VectorStoreInterface):
    """Qdrant vector store implementation."""
    
    def __init__(self, config, embed_model=None):
        """Initialize Qdrant vector store.
        
        Args:
            config: Configuration object with Qdrant settings
            embed_model: Pre-initialized embedding model
        """
        self.config = config
        self.embed_model = embed_model
        self.client: Optional[QdrantClient] = None
        self.collection_name = config.qdrant_collection_name
        self._initialized = False
        
        # Get embedding dimension
        if embed_model:
            test_embedding = embed_model.get_text_embedding("test")
            self.vector_dimension = len(test_embedding)
        else:
            # Default for all-MiniLM-L6-v2
            self.vector_dimension = 384
    
    def initialize(self) -> None:
        """Initialize the vector store connection and setup."""
        try:
            # Create Qdrant client
            self.client = QdrantClient(
                host=self.config.qdrant_host,
                port=self.config.qdrant_port,
                api_key=self.config.qdrant_api_key,
                https=self.config.qdrant_use_https,
                timeout=30.0,
            )
            
            # Test connection
            self.client.get_collections()
            
            # Create collection if it doesn't exist
            self._ensure_collection_exists()
            
            self._initialized = True
            
        except Exception as e:
            raise RuntimeError(f"Failed to initialize Qdrant client: {e}")
    
    def add_documents(self, documents: List[Dict[str, Any]]) -> None:
        """Add documents with vectors and metadata.
        
        Args:
            documents: List of documents with 'id', 'text', 'metadata', 'vector' keys
        """
        if not self._initialized:
            self.initialize()
        
        if not documents:
            return
        
        points = []
        for doc in documents:
            # Generate vector if not provided
            vector = doc.get('vector')
            if vector is None and self.embed_model:
                vector = self.embed_model.get_text_embedding(doc['text'])
            elif vector is None:
                raise ValueError("No vector provided and no embedding model available")
            
            # Create point
            point = PointStruct(
                id=self._generate_point_id(doc['id']),
                vector=vector,
                payload={
                    "document_id": doc['id'],
                    "text": doc['text'],
                    **doc.get('metadata', {})
                }
            )
            points.append(point)
        
        # Upload points to Qdrant
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=points
            )
        except Exception as e:
            raise RuntimeError(f"Failed to add documents to Qdrant: {e}")
    
    def update_document(self, document_id: str, document: Dict[str, Any]) -> None:
        """Update a single document by ID.
        
        Args:
            document_id: Unique document identifier
            document: Document with 'text', 'metadata', and optionally 'vector'
        """
        if not self._initialized:
            self.initialize()
        
        # Generate vector if not provided
        vector = document.get('vector')
        if vector is None and self.embed_model:
            vector = self.embed_model.get_text_embedding(document['text'])
        elif vector is None:
            raise ValueError("No vector provided and no embedding model available")
        
        # Create point
        point = PointStruct(
            id=self._generate_point_id(document_id),
            vector=vector,
            payload={
                "document_id": document_id,
                "text": document['text'],
                **document.get('metadata', {})
            }
        )
        
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[point]
            )
        except Exception as e:
            raise RuntimeError(f"Failed to update document in Qdrant: {e}")
    
    def delete_document(self, document_id: str) -> None:
        """Delete a single document by ID.
        
        Args:
            document_id: Unique document identifier
        """
        if not self._initialized:
            self.initialize()
        
        try:
            # Delete by document_id in payload
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                )
            )
        except Exception as e:
            raise RuntimeError(f"Failed to delete document from Qdrant: {e}")
    
    def document_exists(self, document_id: str) -> bool:
        """Check if a document exists in the index.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            True if document exists, False otherwise
        """
        if not self._initialized:
            self.initialize()
        
        try:
            result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                limit=1
            )
            return len(result[0]) > 0
        except Exception:
            return False
    
    def get_indexed_documents(self) -> Set[str]:
        """Get set of all indexed document IDs/paths.
        
        Returns:
            Set of document identifiers currently in the index
        """
        if not self._initialized:
            self.initialize()
        
        document_ids = set()
        try:
            # Scroll through all points to get document IDs
            next_page_offset = None
            while True:
                result = self.client.scroll(
                    collection_name=self.collection_name,
                    limit=100,
                    offset=next_page_offset,
                    with_payload=["document_id"]
                )
                
                points, next_page_offset = result
                
                for point in points:
                    if "document_id" in point.payload:
                        document_ids.add(point.payload["document_id"])
                
                if next_page_offset is None:
                    break
                    
        except Exception as e:
            raise RuntimeError(f"Failed to get indexed documents: {e}")
        
        return document_ids
    
    def get_document_metadata(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a specific document.
        
        Args:
            document_id: Unique document identifier
            
        Returns:
            Document metadata dict or None if not found
        """
        if not self._initialized:
            self.initialize()
        
        try:
            result = self.client.scroll(
                collection_name=self.collection_name,
                scroll_filter=Filter(
                    must=[
                        FieldCondition(
                            key="document_id",
                            match=MatchValue(value=document_id)
                        )
                    ]
                ),
                limit=1,
                with_payload=True
            )
            
            points = result[0]
            if points:
                payload = points[0].payload
                # Remove internal fields
                metadata = payload.copy()
                metadata.pop("document_id", None)
                metadata.pop("text", None)
                return metadata
                
        except Exception:
            pass
        
        return None
    
    def apply_incremental_changes(self, changes: List[DocumentChange]) -> Dict[str, int]:
        """Apply incremental changes and return stats.
        
        Args:
            changes: List of document changes to apply
            
        Returns:
            Statistics dict with 'added', 'updated', 'deleted' counts
        """
        if not self._initialized:
            self.initialize()
        
        stats = {'added': 0, 'updated': 0, 'deleted': 0, 'failed': 0}
        
        for change in changes:
            try:
                if change.change_type == 'delete':
                    self.delete_document(change.file_path)
                    stats['deleted'] += 1
                elif change.change_type in ['add', 'update']:
                    # Note: Actual document content loading happens at higher level
                    # This just tracks the change types
                    if change.change_type == 'add':
                        stats['added'] += 1
                    else:
                        stats['updated'] += 1
            except Exception:
                stats['failed'] += 1
        
        return stats
    
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
        if not self._initialized:
            self.initialize()
        
        try:
            # Build filter conditions
            filter_conditions = None
            if filters:
                conditions = []
                for key, value in filters.items():
                    if isinstance(value, list):
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchAny(any=value)
                            )
                        )
                    elif isinstance(value, dict) and "gte" in value or "lte" in value:
                        # Range filter
                        range_params = {}
                        if "gte" in value:
                            range_params["gte"] = value["gte"]
                        if "lte" in value:
                            range_params["lte"] = value["lte"]
                        conditions.append(
                            FieldCondition(
                                key=key,
                                range=Range(**range_params)
                            )
                        )
                    else:
                        conditions.append(
                            FieldCondition(
                                key=key,
                                match=MatchValue(value=value)
                            )
                        )
                
                if conditions:
                    filter_conditions = Filter(must=conditions)
            
            # Perform search using updated API
            search_results = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=filter_conditions,
                limit=top_k,
                with_payload=True
            ).points
            
            # Format results
            results = []
            for result in search_results:
                payload = result.payload
                formatted_result = {
                    "content": payload.get("text", ""),
                    "metadata": {k: v for k, v in payload.items() 
                               if k not in ["document_id", "text"]},
                    "similarity_score": float(result.score),
                    "source_file": payload.get("file_path", payload.get("document_id", "Unknown"))
                }
                results.append(formatted_result)
            
            return results
            
        except Exception as e:
            raise RuntimeError(f"Query failed: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics and health info.
        
        Returns:
            Statistics dict with counts, performance metrics, etc.
        """
        stats = {
            "type": "qdrant",
            "host": self.config.qdrant_host,
            "port": self.config.qdrant_port,
            "collection_name": self.collection_name,
            "vector_dimension": self.vector_dimension,
        }
        
        if not self._initialized:
            stats["status"] = "not_initialized"
            return stats
        
        try:
            # Get collection info
            collection_info = self.client.get_collection(self.collection_name)
            stats.update({
                "status": collection_info.status.value,
                "total_vectors": collection_info.points_count or 0,
                "total_points": collection_info.points_count or 0,
                "disk_usage": collection_info.segments_count or 0,
            })
            
        except Exception as e:
            stats["status"] = "error"
            stats["error"] = str(e)
        
        return stats
    
    def delete_collection(self) -> None:
        """Delete the entire collection/index."""
        if not self._initialized:
            self.initialize()
        
        try:
            self.client.delete_collection(self.collection_name)
            self._initialized = False
        except Exception as e:
            raise RuntimeError(f"Failed to delete collection: {e}")
    
    def backup_metadata(self, backup_path: str) -> None:
        """Backup index metadata for recovery.
        
        Args:
            backup_path: Path to save backup metadata
        """
        if not self._initialized:
            self.initialize()
        
        backup_data = {
            'timestamp': time.time(),
            'collection_name': self.collection_name,
            'vector_dimension': self.vector_dimension,
            'config': {
                'qdrant_host': self.config.qdrant_host,
                'qdrant_port': self.config.qdrant_port,
                'embedding_model': self.config.embedding_model,
            }
        }
        
        # Get collection info
        try:
            collection_info = self.client.get_collection(self.collection_name)
            backup_data['collection_info'] = {
                'vectors_count': collection_info.vectors_count,
                'points_count': collection_info.points_count,
                'status': collection_info.status.value,
            }
        except Exception:
            pass
        
        backup_path_obj = Path(backup_path)
        backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
        
        import json
        with open(backup_path_obj, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
    
    def restore_metadata(self, backup_path: str) -> None:
        """Restore index metadata from backup.
        
        Args:
            backup_path: Path to backup metadata file
        """
        # For Qdrant, this would mainly be configuration restoration
        # The actual data restoration would require more complex operations
        backup_path_obj = Path(backup_path)
        if not backup_path_obj.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        import json
        with open(backup_path_obj, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        # Validate that collection configuration matches
        if backup_data.get('collection_name') != self.collection_name:
            raise ValueError("Backup collection name doesn't match current configuration")
    
    def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists in Qdrant."""
        try:
            # Check if collection exists
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                # Create collection
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.vector_dimension,
                        distance=Distance.COSINE
                    )
                )
                
            # Wait for collection to be ready
            self._wait_for_collection_ready()
            
        except Exception as e:
            raise RuntimeError(f"Failed to ensure collection exists: {e}")
    
    def _wait_for_collection_ready(self, timeout: int = 30) -> None:
        """Wait for collection to be ready."""
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                collection_info = self.client.get_collection(self.collection_name)
                if collection_info.status == CollectionStatus.GREEN:
                    return
                time.sleep(1)
            except Exception:
                time.sleep(1)
        
        raise RuntimeError(f"Collection {self.collection_name} not ready after {timeout} seconds")
    
    def _generate_point_id(self, document_id: str) -> str:
        """Generate a consistent point ID from document ID.
        
        Args:
            document_id: Document identifier
            
        Returns:
            UUID string for Qdrant point
        """
        # Create a UUID5 based on document_id for consistency
        namespace = uuid.UUID('6ba7b810-9dad-11d1-80b4-00c04fd430c8')  # DNS namespace
        return str(uuid.uuid5(namespace, document_id))