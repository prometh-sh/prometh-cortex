"""Document routing for multi-collection RAG indexing."""

import logging
from typing import Dict, List, Optional
from pathlib import Path

from prometh_cortex.config import CollectionConfig

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Raised when routing operations fail."""
    pass


class DocumentRouter:
    """Routes documents to collections based on source patterns."""

    def __init__(self, collections: List[CollectionConfig]):
        """
        Initialize document router.

        Args:
            collections: List of collection configurations with source patterns

        Raises:
            RouterError: If collections configuration is invalid
        """
        self.collections = collections
        self._validate_collections()

        # Build sorted collection list for pattern matching (longest patterns first)
        self._sorted_collections = self._sort_collections_by_specificity()

    def _validate_collections(self) -> None:
        """Validate collections configuration."""
        if not self.collections:
            raise RouterError("At least one collection must be configured")

        collection_names = set()
        has_default = False
        has_catchall = False

        for collection in self.collections:
            # Check for duplicate names
            if collection.name in collection_names:
                raise RouterError(f"Duplicate collection name: {collection.name}")
            collection_names.add(collection.name)

            # Check for required patterns
            if not collection.source_patterns:
                raise RouterError(
                    f"Collection '{collection.name}' must have at least one source pattern"
                )

            # Track default collection and catch-all pattern
            if collection.name == "default":
                has_default = True
            if "*" in collection.source_patterns:
                has_catchall = True

        # Ensure we have a default collection with catch-all pattern
        if not has_default:
            raise RouterError(
                "A collection named 'default' with source pattern '*' is required"
            )

        if not has_catchall:
            raise RouterError(
                "At least one collection must have '*' as a source pattern (catch-all)"
            )

    def _sort_collections_by_specificity(self) -> List[CollectionConfig]:
        """
        Sort collections by pattern specificity for matching priority.

        Longer patterns (more specific) are checked first.
        Catch-all (*) pattern is checked last.

        Returns:
            Sorted list of collections
        """
        def specificity_score(collection: CollectionConfig) -> tuple:
            # Calculate specificity score for each collection
            # Higher score = more specific = checked first
            max_pattern_length = max(
                len(p) for p in collection.source_patterns
            ) if collection.source_patterns else 0

            # Catch-all pattern gets lowest score
            has_catchall = "*" in collection.source_patterns
            catch_all_penalty = 0 if has_catchall else 1000

            # Return tuple for sorting: (catch_all_penalty, max_pattern_length)
            # Descending order, so we negate the pattern length
            return (catch_all_penalty, -max_pattern_length)

        return sorted(self.collections, key=specificity_score)

    def route_document(self, doc_path: str) -> str:
        """
        Route document to appropriate collection based on source patterns.

        Uses longest-prefix-match algorithm: more specific patterns take precedence.

        Args:
            doc_path: Document file path

        Returns:
            Collection name the document should be routed to

        Raises:
            RouterError: If no valid collection found (should not happen with valid config)
        """
        # Normalize path for matching
        normalized_path = Path(doc_path).as_posix()

        # Check each collection in order of specificity
        for collection in self._sorted_collections:
            for pattern in collection.source_patterns:
                if self._matches_pattern(normalized_path, pattern):
                    logger.debug(
                        f"Document {doc_path} routed to '{collection.name}' "
                        f"(pattern: {pattern})"
                    )
                    return collection.name

        # Should never reach here if validation passed
        raise RouterError(f"No collection found for document: {doc_path}")

    def _matches_pattern(self, doc_path: str, pattern: str) -> bool:
        """
        Check if document path matches a source pattern.

        Supports:
        - Exact path match: "docs/specs"
        - Prefix match: "docs" matches "docs/specs/feature-auth.md"
        - Catch-all: "*" matches any document

        Args:
            doc_path: Normalized document path (posix format)
            pattern: Source pattern to match against

        Returns:
            True if path matches pattern, False otherwise
        """
        # Catch-all pattern
        if pattern == "*":
            return True

        # Normalize pattern path
        normalized_pattern = Path(pattern).as_posix()

        # Exact match or prefix match (longest-prefix-match)
        # "docs/specs" should match "docs/specs/feature-auth.md"
        if doc_path == normalized_pattern:
            return True

        if doc_path.startswith(normalized_pattern + "/"):
            return True

        return False

    def get_collection_config(self, name: str) -> CollectionConfig:
        """
        Get configuration for specific collection.

        Args:
            name: Collection name

        Returns:
            CollectionConfig for the collection

        Raises:
            RouterError: If collection not found
        """
        for collection in self.collections:
            if collection.name == name:
                return collection

        raise RouterError(f"Collection '{name}' not found")

    def list_collections(self) -> List[CollectionConfig]:
        """
        Get list of all collections.

        Returns:
            List of all collection configurations
        """
        return self.collections.copy()

    def get_collection_names(self) -> List[str]:
        """
        Get names of all collections.

        Returns:
            Sorted list of collection names
        """
        return sorted(c.name for c in self.collections)
