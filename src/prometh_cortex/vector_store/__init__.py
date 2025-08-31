"""Vector store abstraction layer for supporting multiple vector databases."""

from .interface import VectorStoreInterface, DocumentChange
from .factory import VectorStoreFactory, create_vector_store
from .faiss_store import FAISSVectorStore
from .qdrant_store import QdrantVectorStore
from .change_detector import DocumentChangeDetector

__all__ = [
    "VectorStoreInterface",
    "DocumentChange", 
    "VectorStoreFactory",
    "create_vector_store",
    "FAISSVectorStore",
    "QdrantVectorStore",
    "DocumentChangeDetector",
]