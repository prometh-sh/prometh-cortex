"""Chunk size recommendation engine."""

import logging
from typing import List, Tuple

from prometh_cortex.analyzer.metrics import DocumentMetrics

logger = logging.getLogger(__name__)


class ChunkRecommender:
    """Recommend optimal chunk sizes based on document metrics."""

    # Formula: detect content type and complexity from metrics
    TECHNICAL_INDICATORS = {
        "code_blocks": 0.15,  # 15%+ of docs have code blocks
        "sections_high": 20,  # 20+ sections indicates structured technical docs
    }

    MEETING_INDICATORS = {
        "lists": 0.8,  # 80%+ have bullet lists
        "sections_moderate": (5, 20),  # 5-20 sections
        "paragraphs_low": 100,  # Typically < 100 paragraphs
    }

    LOG_INDICATORS = {
        "lines_high": 30,  # 30+ lines
        "avg_line_length_low": 50,  # < 50 chars per line
        "sections_low": 3,  # < 3 sections (mostly data, not narrative)
    }

    def __init__(self):
        """Initialize the recommender."""
        pass

    def recommend(
        self,
        collection_name: str,
        metrics_list: List[DocumentMetrics],
    ) -> Tuple[int, int, str]:
        """
        Recommend chunk size and overlap for a collection.

        Args:
            collection_name: Name of the collection
            metrics_list: List of DocumentMetrics from sampled files

        Returns:
            Tuple of (recommended_chunk_size, recommended_overlap, rationale)
        """
        if not metrics_list:
            return 512, 51, "No metrics available"

        # Detect collection type
        content_type = self._detect_content_type(collection_name, metrics_list)

        # Get recommendations based on content type
        if content_type == "technical":
            return self._recommend_technical(metrics_list)
        elif content_type == "meetings":
            return self._recommend_meetings(metrics_list)
        elif content_type == "logs":
            return self._recommend_logs(metrics_list)
        elif content_type == "metadata":
            return self._recommend_metadata(metrics_list)
        elif content_type == "business":
            return self._recommend_business(metrics_list)
        else:
            return self._recommend_default(metrics_list)

    def _detect_content_type(
        self, collection_name: str, metrics_list: List[DocumentMetrics]
    ) -> str:
        """
        Detect content type from collection name and metrics.

        Returns: One of 'technical', 'meetings', 'logs', 'metadata', 'business', 'default'
        """
        # Name-based detection (most reliable)
        name_lower = collection_name.lower()
        if "knowledge" in name_lower or "runbook" in name_lower:
            return "technical"
        elif "meeting" in name_lower or "sync" in name_lower:
            return "meetings"
        elif "todo" in name_lower or "log" in name_lower or "activity" in name_lower:
            return "logs"
        elif "asset" in name_lower or "context" in name_lower:
            return "metadata"
        elif "project" in name_lower:
            return "business"

        # Metrics-based detection fallback
        avg_metrics = self._calculate_average_metrics(metrics_list)

        # Check for technical content
        if avg_metrics["code_block_ratio"] > 0.15 or avg_metrics["avg_sections"] > 20:
            return "technical"

        # Check for meeting notes
        if avg_metrics["list_ratio"] > 0.8 and avg_metrics["avg_sections"] < 20:
            return "meetings"

        # Check for logs
        if (
            avg_metrics["avg_lines"] > 30
            and avg_metrics["avg_line_length"] < 50
            and avg_metrics["avg_sections"] < 3
        ):
            return "logs"

        # Check for metadata
        if avg_metrics["avg_lines"] < 50 and avg_metrics["frontmatter_ratio"] > 0.5:
            return "metadata"

        return "default"

    def _calculate_average_metrics(self, metrics_list: List[DocumentMetrics]) -> dict:
        """Calculate aggregated metrics from list."""
        if not metrics_list:
            return {}

        count = len(metrics_list)
        code_block_count = sum(1 for m in metrics_list if m.has_code_blocks)
        list_count = sum(1 for m in metrics_list if m.has_lists)
        frontmatter_count = sum(1 for m in metrics_list if m.has_yaml_frontmatter)

        return {
            "avg_size_chars": sum(m.size_chars for m in metrics_list) // count,
            "avg_lines": sum(m.lines for m in metrics_list) // count,
            "avg_sections": sum(m.sections for m in metrics_list) // count,
            "avg_line_length": sum(m.avg_line_length for m in metrics_list) // count,
            "code_block_ratio": code_block_count / count,
            "list_ratio": list_count / count,
            "frontmatter_ratio": frontmatter_count / count,
        }

    def _recommend_technical(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Recommend for technical documentation."""
        avg_metrics = self._calculate_average_metrics(metrics_list)
        avg_doc_size = avg_metrics["avg_size_chars"]

        # Large technical docs benefit from larger chunks
        if avg_doc_size > 15000:
            return 768, 76, "Long technical docs with code blocks need more context (768 chars, 10% overlap)"
        elif avg_doc_size > 10000:
            return 768, 76, "Structured technical documentation with complete sections (768 chars)"
        else:
            return 640, 64, "Technical documentation with code examples (640 chars)"

    def _recommend_meetings(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Recommend for meeting notes."""
        return 512, 51, "Action items & decisions should stay intact (512 chars, 10% overlap)"

    def _recommend_logs(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Recommend for activity logs."""
        return 256, 26, "Log entries need temporal sequences and transitions (256 chars, 10% overlap)"

    def _recommend_metadata(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Recommend for metadata/assets."""
        return 512, 51, "Keep metadata and key-value pairs together (512 chars)"

    def _recommend_business(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Recommend for business documents."""
        avg_metrics = self._calculate_average_metrics(metrics_list)

        if avg_metrics["avg_sections"] > 15:
            return 640, 64, "Business docs with nested sections (640 chars, 10% overlap)"
        else:
            return 640, 64, "Complete value propositions and business context (640 chars)"

    def _recommend_default(self, metrics_list: List[DocumentMetrics]) -> Tuple[int, int, str]:
        """Default recommendation based on document size."""
        avg_metrics = self._calculate_average_metrics(metrics_list)
        avg_doc_size = avg_metrics["avg_size_chars"]

        # Size-based recommendation
        if avg_doc_size > 20000:
            return 768, 76, "Large documents need larger chunks (768 chars)"
        elif avg_doc_size > 10000:
            return 640, 64, "Medium-large documents (640 chars)"
        elif avg_doc_size > 5000:
            return 512, 51, "Medium documents (512 chars, 10% overlap)"
        elif avg_doc_size > 2000:
            return 384, 38, "Small-medium documents (384 chars)"
        else:
            return 256, 26, "Small documents (256 chars)"
