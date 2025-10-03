"""Document indexer with support for multiple vector stores."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Set

from llama_index.embeddings.huggingface import HuggingFaceEmbedding

from prometh_cortex.config import Config
from prometh_cortex.parser import (
    MarkdownDocument, 
    parse_markdown_file, 
    extract_document_chunks,
    QueryParser,
    ParsedQuery,
    parse_query
)
from prometh_cortex.vector_store import (
    VectorStoreInterface,
    DocumentChange,
    DocumentChangeDetector,
    create_vector_store
)

logger = logging.getLogger(__name__)


class IndexerError(Exception):
    """Raised when indexer operations fail."""
    pass


class DocumentIndexer:
    """Document indexer for RAG operations with support for multiple vector stores."""
    
    def __init__(self, config: Config):
        """
        Initialize document indexer.
        
        Args:
            config: Configuration object with indexing settings
        """
        self.config = config
        self.embed_model = None
        self.vector_store: Optional[VectorStoreInterface] = None
        self.change_detector: Optional[DocumentChangeDetector] = None
        self.auto_discovered_fields: Optional[Set[str]] = None
        self.query_parser = QueryParser(config=config)
        
        # Initialize components
        self._initialize_embedding_model()
        self._initialize_vector_store()
        self._initialize_change_detector()
    
    def _initialize_embedding_model(self):
        """Initialize the embedding model."""
        try:
            self.embed_model = HuggingFaceEmbedding(model_name=self.config.embedding_model)
        except Exception as e:
            raise IndexerError(f"Failed to initialize embedding model {self.config.embedding_model}: {e}")
    
    def _initialize_vector_store(self):
        """Initialize the vector store based on configuration."""
        try:
            self.vector_store = create_vector_store(self.config, self.embed_model)
            self.vector_store.initialize()
        except Exception as e:
            raise IndexerError(f"Failed to initialize vector store: {e}")
    
    def _initialize_change_detector(self):
        """Initialize the change detector for incremental indexing."""
        try:
            # Use different metadata paths for different vector store types
            if self.config.vector_store_type == 'faiss':
                metadata_path = self.config.rag_index_dir / "change_metadata.json"
            else:
                # For Qdrant, store metadata in a separate directory
                metadata_path = Path(f".prometh_cortex_{self.config.vector_store_type}") / "change_metadata.json"
            
            self.change_detector = DocumentChangeDetector(str(metadata_path))
        except Exception as e:
            raise IndexerError(f"Failed to initialize change detector: {e}")
    
    def discover_documents(self, datalake_paths: List[Path]) -> List[str]:
        """Discover all Markdown documents in the specified datalake paths.
        
        Args:
            datalake_paths: List of paths to search for documents
            
        Returns:
            List of document file paths
        """
        document_paths = []
        for datalake_path in datalake_paths:
            if datalake_path.exists() and datalake_path.is_dir():
                # Find all markdown files recursively
                markdown_files = list(datalake_path.rglob("*.md"))
                document_paths.extend(str(f) for f in markdown_files)
        
        return sorted(document_paths)
    
    def add_document(self, file_path: Path) -> bool:
        """
        Add a single document to the index.
        
        Args:
            file_path: Path to markdown file to index
            
        Returns:
            True if successful, False otherwise
            
        Raises:
            IndexerError: If indexing fails
        """
        try:
            # Parse markdown document
            markdown_doc = parse_markdown_file(file_path)
            
            # Extract chunks for embedding
            chunks = extract_document_chunks(
                markdown_doc, 
                chunk_size=self.config.chunk_size,
                chunk_overlap=self.config.chunk_overlap
            )
            
            # Convert chunks to documents for vector store
            documents = []
            for chunk in chunks:
                doc = {
                    'id': f"{file_path}_{chunk['chunk_index']}",
                    'text': chunk["content"],
                    'metadata': {
                        **chunk["metadata"],
                        'file_path': str(file_path),
                        'chunk_index': chunk['chunk_index']
                    }
                }
                documents.append(doc)
            
            # Add to vector store
            self.vector_store.add_documents(documents)
            
            return True
            
        except Exception as e:
            raise IndexerError(f"Failed to add document {file_path}: {e}")
    
    def add_documents(self, file_paths: List[Path]) -> Dict[str, int]:
        """Add multiple documents to the index.
        
        Args:
            file_paths: List of document file paths to index
            
        Returns:
            Statistics dict with success/failure counts
        """
        stats = {'added': 0, 'failed': 0, 'errors': []}
        
        for file_path in file_paths:
            try:
                if self.add_document(file_path):
                    stats['added'] += 1
            except Exception as e:
                stats['failed'] += 1
                stats['errors'].append(f"{file_path}: {str(e)}")
                logger.error(f"Failed to add document {file_path}: {e}")
        
        return stats
    
    def build_index(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build the complete index from all datalake repositories.
        
        Args:
            force_rebuild: If True, rebuild entire index ignoring incremental changes
            
        Returns:
            Statistics dict with indexing results
        """
        try:
            # Discover all documents
            document_paths = self.discover_documents(self.config.datalake_repos)
            
            if force_rebuild:
                # Force full rebuild
                logger.info("Performing full index rebuild")
                self.change_detector.reset()
                self.vector_store.delete_collection()
                self.vector_store.initialize()

                # Add all documents
                stats = self.add_documents([Path(p) for p in document_paths])

                # Update change detector metadata with proper hashes and mtimes
                changes = []
                for p in document_paths:
                    import os
                    if os.path.exists(p):
                        changes.append(DocumentChange(
                            file_path=p,
                            change_type='add',
                            file_hash=self.change_detector._compute_file_hash(p),
                            modified_time=os.path.getmtime(p)
                        ))
                self.change_detector.update_metadata(changes)
                
            else:
                # Incremental build
                logger.info("Performing incremental index update")
                changes = self.change_detector.detect_changes(document_paths)
                
                if not changes:
                    logger.info("No changes detected, index is up to date")
                    return {'message': 'No changes detected', 'changes': 0}
                
                logger.info(f"Detected {len(changes)} changes")
                
                # Apply incremental changes
                vector_stats = self.vector_store.apply_incremental_changes(changes)
                
                # Process documents that need content updates (add/update)
                docs_to_process = []
                for change in changes:
                    if change.change_type in ['add', 'update']:
                        docs_to_process.append(Path(change.file_path))
                
                if docs_to_process:
                    add_stats = self.add_documents(docs_to_process)
                    vector_stats.update(add_stats)
                
                # Update change detector metadata
                successful_changes = [
                    change for change in changes 
                    if change.change_type == 'delete' or 
                    change.file_path not in [str(p) for p in docs_to_process if str(p) in [e.split(':')[0] for e in add_stats.get('errors', [])]]
                ]
                self.change_detector.update_metadata(successful_changes)
                
                stats = vector_stats
            
            # Save vector store if needed (for FAISS)
            if hasattr(self.vector_store, 'save_index'):
                self.vector_store.save_index()
            
            # Update auto-discovered fields after building
            self.update_query_parser_fields()
            
            logger.info(f"Index build completed: {stats}")
            return stats
            
        except Exception as e:
            raise IndexerError(f"Failed to build index: {e}")
    
    def load_index(self):
        """Load existing index if needed (for FAISS compatibility)."""
        try:
            # Vector store is already initialized, but we can load persisted data
            if hasattr(self.vector_store, 'load_index'):
                self.vector_store.load_index()
            
            # Trigger auto-discovery of filterable fields after loading
            self.update_query_parser_fields()
            
        except Exception as e:
            # For new installations or Qdrant, this is not necessarily an error
            logger.info(f"Could not load existing index: {e}")
    
    def query(self, query_text: str, max_results: Optional[int] = None, 
             filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Query the index for similar documents with support for structured queries.
        
        Supports both simple semantic queries and structured queries with metadata filters:
        - Simple: "meeting notes discussion"
        - Structured: "category:meetings created:2025-08-25 discussion agenda"
        
        Args:
            query_text: Query text (simple or structured)
            max_results: Maximum number of results to return
            filters: Optional metadata filters (merged with parsed filters)
            
        Returns:
            List of result dictionaries with content, metadata, and scores
            
        Raises:
            IndexerError: If querying fails
        """
        if not self.vector_store:
            raise IndexerError("Vector store not initialized.")
        
        if max_results is None:
            max_results = self.config.max_query_results
        
        try:
            # Parse structured query
            parsed_query = self.query_parser.parse_query(query_text)
            
            # Build semantic query for vector search
            semantic_query = self.query_parser.build_semantic_query(parsed_query)
            
            # Merge parsed metadata filters with provided filters
            combined_filters = {}
            post_processing_filters = {}
            
            if filters:
                combined_filters.update(filters)
            
            if parsed_query.metadata_filters:
                qdrant_filters = self.query_parser.convert_to_qdrant_filters(
                    parsed_query.metadata_filters
                )
                combined_filters.update(qdrant_filters)
                
                # Extract date filters for post-processing
                for field, value in parsed_query.metadata_filters.items():
                    if field in ['created', 'modified']:
                        post_processing_filters[field] = value
            
            # Generate query vector from semantic text
            query_vector = self.embed_model.get_text_embedding(semantic_query)
            
            # Perform vector search with Qdrant-compatible filters
            # Get more results if we need to post-filter
            search_limit = max_results * 3 if post_processing_filters else max_results
            
            results = self.vector_store.query(
                query_vector=query_vector,
                top_k=search_limit,
                filters=combined_filters if combined_filters else None
            )
            
            # Apply post-processing filters (mainly for date filtering)
            if post_processing_filters and results:
                filtered_results = []
                for result in results:
                    include_result = True
                    result_metadata = result.get('metadata', {})
                    
                    # Apply date filters
                    for filter_field, filter_value in post_processing_filters.items():
                        if filter_field in ['created', 'modified']:
                            result_date_str = result_metadata.get(filter_field, '')
                            if result_date_str:
                                # Extract date part for comparison
                                result_date = result_date_str.split('T')[0]
                                
                                if isinstance(filter_value, dict):
                                    # Range filter
                                    if 'gte' in filter_value:
                                        filter_date = filter_value['gte'].split('T')[0]
                                        if result_date < filter_date:
                                            include_result = False
                                            break
                                    if 'lte' in filter_value:
                                        filter_date = filter_value['lte'].split('T')[0]
                                        if result_date > filter_date:
                                            include_result = False
                                            break
                                else:
                                    # Exact date match
                                    filter_date = str(filter_value).split('T')[0]
                                    if result_date != filter_date:
                                        include_result = False
                                        break
                            else:
                                # No date field in result
                                include_result = False
                                break
                    
                    if include_result:
                        filtered_results.append(result)
                
                results = filtered_results[:max_results]
            
            # Add query metadata to results for debugging
            if results and len(results) > 0 and isinstance(results[0], dict):
                for result in results:
                    if 'query_info' not in result:
                        result['query_info'] = {
                            'original_query': parsed_query.original_query,
                            'semantic_query': semantic_query,
                            'applied_filters': combined_filters,
                            'parsed_filters': parsed_query.metadata_filters
                        }
            
            return results
            
        except Exception as e:
            raise IndexerError(f"Query failed: {e}")
    
    def query_by_text(self, query_text: str, max_results: Optional[int] = None,
                     filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Convenience method that delegates to query."""
        return self.query(query_text, max_results, filters)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the index.
        
        Returns:
            Dictionary with index statistics
        """
        base_stats = {
            "vector_store_type": self.config.vector_store_type,
            "embedding_model": self.config.embedding_model,
            "chunk_size": self.config.chunk_size,
            "chunk_overlap": self.config.chunk_overlap,
        }
        
        # Get vector store stats
        if self.vector_store:
            vector_stats = self.vector_store.get_stats()
            base_stats.update(vector_stats)
        
        # Get change detector stats
        if self.change_detector:
            change_stats = self.change_detector.get_stats()
            base_stats.update(change_stats)
        
        return base_stats
    
    def auto_discover_filterable_fields(self, min_frequency: float = 0.1, sample_size: int = 50) -> Set[str]:
        """
        Auto-discover fields that are good candidates for structured query filtering.
        
        Args:
            min_frequency: Minimum frequency (0.0-1.0) for a field to be considered
            sample_size: Number of documents to sample for analysis
            
        Returns:
            Set of field names suitable for filtering
        """
        if not self.vector_store:
            return set()
        
        try:
            # Get a larger sample for better field analysis
            sample_results = self.vector_store.query(
                query_vector=self.embed_model.get_text_embedding("sample documents"),
                top_k=sample_size,
                filters=None
            )
            
            if not sample_results:
                return set()
            
            # Analyze field frequency and types
            field_stats = {}
            total_docs = len(sample_results)
            
            for result in sample_results:
                metadata = result.get('metadata', {})
                
                for field_name, field_value in metadata.items():
                    # Skip internal fields
                    if field_name in ['file_path', 'chunk_index']:
                        continue
                    
                    if field_name not in field_stats:
                        field_stats[field_name] = {
                            'count': 0,
                            'types': set(),
                            'sample_values': set()
                        }
                    
                    field_stats[field_name]['count'] += 1
                    field_stats[field_name]['types'].add(type(field_value).__name__)
                    
                    # Collect sample values for analysis
                    if len(field_stats[field_name]['sample_values']) < 5:
                        if isinstance(field_value, (str, int, float)):
                            field_stats[field_name]['sample_values'].add(str(field_value)[:50])
                        elif isinstance(field_value, list):
                            field_stats[field_name]['sample_values'].add(f"[{len(field_value)} items]")
            
            # Score fields for filtering suitability
            filterable_fields = set()
            
            for field_name, stats in field_stats.items():
                frequency = stats['count'] / total_docs
                
                # Must meet minimum frequency
                if frequency < min_frequency:
                    continue
                
                # Score based on field characteristics
                score = 0
                
                # High frequency is good
                score += min(frequency, 1.0) * 10
                
                # Certain types are better for filtering
                if 'str' in stats['types']:
                    score += 5
                if 'list' in stats['types']:
                    score += 8  # Lists (like tags) are excellent for filtering
                if 'int' in stats['types'] or 'float' in stats['types']:
                    score += 3
                
                # Field name patterns indicate filtering suitability
                field_lower = field_name.lower()
                if any(pattern in field_lower for pattern in [
                    'tag', 'category', 'status', 'type', 'author', 'owner', 'priority'
                ]):
                    score += 15
                elif any(pattern in field_lower for pattern in [
                    'subject', 'title', 'name', 'organizer', 'location', 'focus'
                ]):
                    score += 10
                elif any(pattern in field_lower for pattern in [
                    'event', 'project', 'reminder', 'list', 'duration'
                ]):
                    score += 8
                
                # If score is high enough, consider it filterable
                if score >= 15:  # Threshold for auto-discovery
                    filterable_fields.add(field_name)
            
            return filterable_fields
            
        except Exception as e:
            logger.warning(f"Auto-discovery failed: {e}")
            return set()
    
    def update_query_parser_fields(self) -> None:
        """Update query parser with auto-discovered fields."""
        if self.config.structured_query_auto_discovery:
            discovered = self.auto_discover_filterable_fields()
            self.auto_discovered_fields = discovered
            self.query_parser.update_auto_discovered_fields(discovered)
            logger.info(f"Auto-discovered {len(discovered)} filterable fields: {sorted(discovered)}")
    
    def discover_available_fields(self, sample_size: int = 10) -> Dict[str, Any]:
        """
        Discover available metadata fields from indexed documents.
        
        Args:
            sample_size: Number of documents to sample for field discovery
            
        Returns:
            Dictionary with available fields and their sample values
        """
        if not self.vector_store:
            raise IndexerError("Vector store not initialized.")
        
        try:
            # Get a sample of documents to analyze their metadata
            sample_results = self.vector_store.query(
                query_vector=self.embed_model.get_text_embedding("sample documents"),
                top_k=sample_size,
                filters=None
            )
            
            # Analyze metadata fields
            field_analysis = {}
            
            for result in sample_results:
                metadata = result.get('metadata', {})
                
                for field_name, field_value in metadata.items():
                    if field_name not in field_analysis:
                        field_analysis[field_name] = {
                            'type': type(field_value).__name__,
                            'sample_values': set(),
                            'count': 0
                        }
                    
                    field_analysis[field_name]['count'] += 1
                    
                    # Collect sample values (limit to avoid memory issues)
                    if len(field_analysis[field_name]['sample_values']) < 5:
                        if isinstance(field_value, (list, dict)):
                            field_analysis[field_name]['sample_values'].add(str(field_value)[:100])
                        else:
                            field_analysis[field_name]['sample_values'].add(str(field_value)[:100])
            
            # Convert sets to lists for JSON serialization
            for field_info in field_analysis.values():
                field_info['sample_values'] = list(field_info['sample_values'])
                
            # Add recommendations
            recommendations = {
                'recommended_for_filtering': [],
                'recommended_for_tags': [],
                'recommended_for_semantic': []
            }
            
            for field_name, info in field_analysis.items():
                # Tags and lists are great for filtering
                if info['type'] == 'list' or field_name.lower() in ['tags', 'categories']:
                    recommendations['recommended_for_filtering'].append(field_name)
                    recommendations['recommended_for_tags'].append(field_name)
                # Common categorical fields
                elif field_name.lower() in ['category', 'author', 'status', 'focus']:
                    recommendations['recommended_for_filtering'].append(field_name)
                # Text fields better for semantic search
                elif field_name.lower() in ['title', 'description', 'content']:
                    recommendations['recommended_for_semantic'].append(field_name)
            
            return {
                'fields': field_analysis,
                'total_documents_sampled': len(sample_results),
                'recommendations': recommendations,
                'query_parser_config': {
                    'core_fields': list(self.query_parser.config.structured_query_core_fields) if self.query_parser.config else [],
                    'extended_fields': list(self.query_parser.config.structured_query_extended_fields) if self.query_parser.config else [],
                    'auto_discovered_fields': list(self.auto_discovered_fields) if self.auto_discovered_fields else [],
                    'all_available_fields': sorted(self.query_parser.available_fields),
                    'auto_discovery_enabled': self.query_parser.config.structured_query_auto_discovery if self.query_parser.config else False
                }
            }
            
        except Exception as e:
            raise IndexerError(f"Field discovery failed: {e}")
    
    def delete_index(self):
        """Delete the entire index."""
        try:
            if self.vector_store:
                self.vector_store.delete_collection()
            if self.change_detector:
                self.change_detector.reset()
        except Exception as e:
            raise IndexerError(f"Failed to delete index: {e}")
    
    def backup_index(self, backup_path: str):
        """Backup index metadata."""
        try:
            if self.vector_store:
                vector_backup_path = f"{backup_path}_vector_store.json"
                self.vector_store.backup_metadata(vector_backup_path)
                
            if self.change_detector:
                change_backup_path = f"{backup_path}_change_detector.json"
                self.change_detector.backup_metadata(change_backup_path)
                
        except Exception as e:
            raise IndexerError(f"Failed to backup index: {e}")
    
    def restore_index(self, backup_path: str):
        """Restore index from backup."""
        try:
            if self.vector_store:
                vector_backup_path = f"{backup_path}_vector_store.json"
                self.vector_store.restore_metadata(vector_backup_path)
                
            if self.change_detector:
                change_backup_path = f"{backup_path}_change_detector.json"
                self.change_detector.restore_metadata(change_backup_path)
                
        except Exception as e:
            raise IndexerError(f"Failed to restore index: {e}")