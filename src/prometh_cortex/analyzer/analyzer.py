"""Document analyzer for chunk optimization."""

import logging
from pathlib import Path
from typing import List, Dict, Any

from prometh_cortex.analyzer.metrics import DocumentMetrics, CollectionAnalysisResult
from prometh_cortex.analyzer.recommender import ChunkRecommender
from prometh_cortex.config import CollectionConfig

logger = logging.getLogger(__name__)


class DocumentAnalyzer:
    """Analyze documents to recommend optimal chunk sizes."""

    def __init__(self):
        """Initialize the analyzer."""
        self.recommender = ChunkRecommender()

    def analyze_collection(
        self,
        collection_config: CollectionConfig,
        max_samples: int = 5,
    ) -> CollectionAnalysisResult:
        """
        Analyze a collection and provide recommendations.

        Args:
            collection_config: Configuration for the collection
            max_samples: Maximum number of files to sample (most recent)

        Returns:
            CollectionAnalysisResult with analysis and recommendations
        """
        # Sample files (most recent first)
        sampled_files = self._sample_documents(
            collection_config.source_patterns,
            max_samples=max_samples,
        )

        # Analyze each file
        metrics_list = []
        for file_path in sampled_files:
            try:
                metrics = self._analyze_document(file_path)
                metrics_list.append(metrics)
                logger.debug(f"Analyzed: {file_path} ({metrics.size_chars} chars)")
            except Exception as e:
                logger.warning(f"Failed to analyze {file_path}: {e}")

        # Get recommendations
        recommended_chunk, recommended_overlap, rationale = self.recommender.recommend(
            collection_config.name,
            metrics_list,
        )

        # Create result
        result = CollectionAnalysisResult(
            collection_name=collection_config.name,
            source_patterns=collection_config.source_patterns,
            sampled_files=sampled_files,
            metrics_list=metrics_list,
            current_chunk_size=collection_config.chunk_size,
            current_overlap=collection_config.chunk_overlap,
            recommended_chunk_size=recommended_chunk,
            recommended_overlap=recommended_overlap,
            rationale=rationale,
        )

        return result

    def _sample_documents(
        self,
        source_patterns: List[str],
        max_samples: int = 5,
    ) -> List[str]:
        """
        Sample most recent markdown files from source patterns.

        Args:
            source_patterns: List of directory patterns to search
            max_samples: Maximum files to return

        Returns:
            List of file paths, sorted by modification time (newest first)
        """
        all_files = []

        for pattern in source_patterns:
            if pattern == "*":
                # Skip catch-all pattern
                continue

            try:
                path = Path(pattern).expanduser().resolve()

                if not path.exists():
                    logger.debug(f"Source pattern not found: {pattern}")
                    continue

                if path.is_dir():
                    # Find all markdown files recursively
                    for md_file in path.rglob("*.md"):
                        try:
                            mtime = md_file.stat().st_mtime
                            all_files.append((str(md_file), mtime))
                        except OSError:
                            logger.debug(f"Could not stat file: {md_file}")
                elif path.is_file() and path.suffix == ".md":
                    # Single file
                    try:
                        mtime = path.stat().st_mtime
                        all_files.append((str(path), mtime))
                    except OSError:
                        logger.debug(f"Could not stat file: {path}")

            except Exception as e:
                logger.debug(f"Error processing pattern '{pattern}': {e}")

        if not all_files:
            logger.warning(f"No markdown files found in patterns: {source_patterns}")
            return []

        # Sort by modification time (newest first)
        all_files.sort(key=lambda x: x[1], reverse=True)

        # Return top N files
        return [f[0] for f in all_files[:max_samples]]

    def _analyze_document(self, file_path: str) -> DocumentMetrics:
        """
        Analyze a single document file.

        Args:
            file_path: Path to the markdown file

        Returns:
            DocumentMetrics with analysis results
        """
        path = Path(file_path)
        mtime = path.stat().st_mtime

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        # Basic metrics
        size_chars = len(content)
        lines = content.split("\n")
        line_count = len(lines)

        # Count sections (markdown headings)
        sections = sum(1 for line in lines if line.startswith("#"))

        # Count paragraphs (non-empty lines that aren't headings)
        paragraphs = sum(
            1 for line in lines if line.strip() and not line.startswith("#")
        )

        # Average line length
        non_empty_lines = [l for l in lines if l.strip()]
        avg_line_length = (
            sum(len(l) for l in non_empty_lines) // len(non_empty_lines)
            if non_empty_lines
            else 0
        )

        # Feature detection
        has_code_blocks = "```" in content
        has_tables = "|" in content and any(
            "---" in line for line in lines
        )  # Simple heuristic
        has_lists = any(line.strip().startswith(("-", "*", "+", "1.")) for line in lines)
        has_yaml_frontmatter = content.startswith("---")

        # Determine complexity
        if sections > 15 or size_chars > 15000:
            complexity = "complex"
        elif sections > 5 or size_chars > 5000:
            complexity = "moderate"
        else:
            complexity = "simple"

        return DocumentMetrics(
            file_path=file_path,
            modified_time=mtime,
            size_chars=size_chars,
            lines=line_count,
            sections=sections,
            paragraphs=paragraphs,
            avg_line_length=avg_line_length,
            has_code_blocks=has_code_blocks,
            has_tables=has_tables,
            has_lists=has_lists,
            has_yaml_frontmatter=has_yaml_frontmatter,
            structure_complexity=complexity,
        )

    def generate_report(
        self,
        analysis_results: List[CollectionAnalysisResult],
    ) -> str:
        """
        Generate a markdown report from analysis results.

        Args:
            analysis_results: List of CollectionAnalysisResult

        Returns:
            Markdown formatted report
        """
        lines = []

        # Header
        lines.append("# Prometh Cortex - Chunk Size Analysis Report")
        lines.append("")
        lines.append(
            f"**Generated:** Analysis of {sum(len(r.metrics_list) for r in analysis_results)} files across {len(analysis_results)} collections"
        )
        lines.append("")

        # Executive Summary
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(
            "| Collection | Current | Recommended | Change |"
        )
        lines.append("|---|---|---|---|")

        for result in analysis_results:
            current = f"{result.current_chunk_size}/{result.current_overlap}"
            recommended = f"{result.recommended_chunk_size}/{result.recommended_overlap}"
            change = result.chunk_change
            lines.append(
                f"| {result.collection_name} | {current} | {recommended} | {change} |"
            )

        lines.append("")

        # Detailed Analysis per Collection
        lines.append("## Detailed Analysis")
        lines.append("")

        for result in analysis_results:
            lines.append(f"### {result.collection_name}")
            lines.append("")

            # Sampled files
            lines.append("**Sampled Files (most recent):**")
            lines.append("")
            for file_path in result.sampled_files:
                lines.append(f"- `{file_path}`")
            lines.append("")

            # Average metrics
            if result.metrics_list:
                avg = result.average_metrics
                lines.append("**Average Metrics:**")
                lines.append("")
                lines.append(f"- Size: {avg['avg_size_chars']:,} chars | Lines: {avg['avg_lines']} | Sections: {avg['avg_sections']}")
                lines.append(
                    f"- Code blocks: {avg['has_code_blocks']} | Tables: {avg['has_tables']} | Lists: {avg['has_lists']}"
                )
                lines.append("")

            # Recommendations
            lines.append("**Recommendation:**")
            lines.append("")
            lines.append(f"- **Current:** `chunk_size={result.current_chunk_size}, chunk_overlap={result.current_overlap}`")
            lines.append(
                f"- **Recommended:** `chunk_size={result.recommended_chunk_size}, chunk_overlap={result.recommended_overlap}`"
            )
            lines.append(f"- **Rationale:** {result.rationale}")
            lines.append("")

        # Implementation
        lines.append("## Implementation")
        lines.append("")
        lines.append("Update your `config.toml` with the recommended values:")
        lines.append("")
        lines.append("```toml")
        for result in analysis_results:
            lines.append(f"[[collections]]")
            lines.append(f"name = \"{result.collection_name}\"")
            lines.append(f"chunk_size = {result.recommended_chunk_size}")
            lines.append(f"chunk_overlap = {result.recommended_overlap}")
            lines.append(f"source_patterns = {result.source_patterns!r}")
            lines.append("")
        lines.append("```")
        lines.append("")

        lines.append("Then rebuild the index:")
        lines.append("")
        lines.append("```bash")
        lines.append("pcortex rebuild --confirm")
        lines.append("```")
        lines.append("")

        return "\n".join(lines)
