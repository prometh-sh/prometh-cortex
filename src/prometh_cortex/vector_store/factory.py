"""Vector store factory for selecting between different implementations."""

from typing import Optional

from prometh_cortex.config import Config
from .interface import VectorStoreInterface
from .faiss_store import FAISSVectorStore
from .qdrant_store import QdrantVectorStore


class VectorStoreFactory:
    """Factory for creating vector store instances based on configuration."""
    
    @staticmethod
    def create_vector_store(config: Config, embed_model=None) -> VectorStoreInterface:
        """Create a vector store instance based on configuration.
        
        Args:
            config: Configuration object with vector store settings
            embed_model: Pre-initialized embedding model (optional)
            
        Returns:
            Vector store instance (FAISS or Qdrant)
            
        Raises:
            ValueError: If vector store type is not supported
        """
        vector_store_type = getattr(config, 'vector_store_type', 'faiss').lower()
        
        if vector_store_type == 'faiss':
            return FAISSVectorStore(config, embed_model)
        elif vector_store_type == 'qdrant':
            return QdrantVectorStore(config, embed_model)
        else:
            raise ValueError(
                f"Unsupported vector store type: {vector_store_type}. "
                f"Supported types: 'faiss', 'qdrant'"
            )
    
    @staticmethod
    def get_supported_types() -> list[str]:
        """Get list of supported vector store types.
        
        Returns:
            List of supported vector store type names
        """
        return ['faiss', 'qdrant']


def create_vector_store(config: Config, embed_model=None) -> VectorStoreInterface:
    """Convenience function for creating vector store instances.
    
    Args:
        config: Configuration object with vector store settings
        embed_model: Pre-initialized embedding model (optional)
        
    Returns:
        Vector store instance based on configuration
    """
    return VectorStoreFactory.create_vector_store(config, embed_model)