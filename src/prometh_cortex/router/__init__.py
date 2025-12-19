"""Document routing for per-document-source chunking in RAG indexing."""

import logging
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from prometh_cortex.config import SourceConfig

logger = logging.getLogger(__name__)


class RouterError(Exception):
    """Raised when routing operations fail."""
    pass


class DocumentRouter:
    """Routes documents to sources based on source patterns and returns chunking parameters."""

    def __init__(self, sources: List[SourceConfig]):
        """
        Initialize document router.

        Args:
            sources: List of source configurations with chunking parameters and patterns

        Raises:
            RouterError: If sources configuration is invalid
        """
        self.sources = sources
        self._validate_sources()

        # Build sorted sources list for pattern matching (longest patterns first)
        self._sorted_sources = self._sort_sources_by_specificity()

    def _validate_sources(self) -> None:
        """Validate sources configuration."""
        if not self.sources:
            raise RouterError("At least one source must be configured")

        source_names = set()
        has_catchall = False

        for source in self.sources:
            # Check for duplicate names
            if source.name in source_names:
                raise RouterError(f"Duplicate source name: {source.name}")
            source_names.add(source.name)

            # Check for required patterns
            if not source.source_patterns:
                raise RouterError(
                    f"Source '{source.name}' must have at least one source pattern"
                )

            # Check for catch-all pattern
            if "*" in source.source_patterns:
                has_catchall = True

        # Optional: catch-all pattern not required
        # Sources can have specific patterns only if desired
        # Documents that don't match any pattern will raise RouterError during routing


    def _sort_sources_by_specificity(self) -> List[SourceConfig]:
        """
        Sort sources by pattern specificity for matching priority.

        Longer patterns (more specific) are checked first.
        Catch-all (*) pattern is checked last.

        Returns:
            Sorted list of sources
        """
        def specificity_score(source: SourceConfig) -> tuple:
            # Calculate specificity score for each source
            # Higher score = more specific = checked first
            max_pattern_length = max(
                len(p) for p in source.source_patterns
            ) if source.source_patterns else 0

            # Catch-all pattern gets lowest score
            has_catchall = "*" in source.source_patterns
            catch_all_penalty = 0 if has_catchall else 1000

            # Return tuple for sorting: (catch_all_penalty, max_pattern_length)
            # Descending order, so we negate the pattern length
            return (catch_all_penalty, -max_pattern_length)

        return sorted(self.sources, key=specificity_score)

    def route_document(self, doc_path: str) -> Tuple[str, int, int]:
        """
        Route document to appropriate source and return chunking parameters.

        Uses longest-prefix-match algorithm: more specific patterns take precedence.

        Args:
            doc_path: Document file path

        Returns:
            Tuple of (source_name, chunk_size, chunk_overlap)

        Raises:
            RouterError: If no valid source found (should not happen with valid config)
        """
        # Normalize path for matching
        normalized_path = Path(doc_path).as_posix()

        # Check each source in order of specificity
        for source in self._sorted_sources:
            for pattern in source.source_patterns:
                if self._matches_pattern(normalized_path, pattern):
                    logger.debug(
                        f"Document {doc_path} routed to '{source.name}' "
                        f"(pattern: {pattern}, chunk_size: {source.chunk_size})"
                    )
                    return (source.name, source.chunk_size, source.chunk_overlap)

        # Should never reach here if validation passed
        raise RouterError(f"No source found for document: {doc_path}")

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

    def get_source_config(self, name: str) -> SourceConfig:
        """
        Get configuration for specific source.

        Args:
            name: Source name

        Returns:
            SourceConfig for the source

        Raises:
            RouterError: If source not found
        """
        for source in self.sources:
            if source.name == name:
                return source

        raise RouterError(f"Source '{name}' not found")

    def list_sources(self) -> List[SourceConfig]:
        """
        Get list of all sources.

        Returns:
            List of all source configurations
        """
        return self.sources.copy()

    def get_source_names(self) -> List[str]:
        """
        Get names of all sources.

        Returns:
            Sorted list of source names
        """
        return sorted(s.name for s in self.sources)
