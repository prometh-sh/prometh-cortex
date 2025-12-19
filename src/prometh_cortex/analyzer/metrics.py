"""Document metrics for chunking analysis."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class DocumentMetrics:
    """Metrics extracted from a document for chunking analysis."""

    file_path: str
    """Path to the document file."""

    modified_time: float
    """Modification timestamp (seconds since epoch)."""

    size_chars: int
    """Total character count in document."""

    lines: int
    """Total line count in document."""

    sections: int
    """Number of heading sections (H1-H6)."""

    paragraphs: int
    """Number of text paragraphs (non-empty lines excluding headings)."""

    avg_line_length: int
    """Average characters per line."""

    has_code_blocks: bool
    """Whether document contains code blocks (triple backticks)."""

    has_tables: bool
    """Whether document contains markdown tables."""

    has_lists: bool
    """Whether document contains bullet/numbered lists."""

    has_yaml_frontmatter: bool
    """Whether document has YAML frontmatter."""

    structure_complexity: str
    """Complexity level: 'simple', 'moderate', or 'complex'."""

    def __post_init__(self):
        """Validate metrics after initialization."""
        if self.size_chars < 0:
            raise ValueError("size_chars must be non-negative")
        if self.lines < 0:
            raise ValueError("lines must be non-negative")
        if self.sections < 0:
            raise ValueError("sections must be non-negative")

    @property
    def modified_datetime(self) -> datetime:
        """Get modification time as datetime object."""
        return datetime.fromtimestamp(self.modified_time)

    @property
    def avg_section_length(self) -> int:
        """Calculate average characters per section."""
        if self.sections == 0:
            return 0
        return self.size_chars // self.sections

    def to_dict(self) -> dict:
        """Convert metrics to dictionary for reporting."""
        return {
            "file_path": self.file_path,
            "modified_time": self.modified_datetime.isoformat(),
            "size_chars": self.size_chars,
            "lines": self.lines,
            "sections": self.sections,
            "paragraphs": self.paragraphs,
            "avg_line_length": self.avg_line_length,
            "avg_section_length": self.avg_section_length,
            "has_code_blocks": self.has_code_blocks,
            "has_tables": self.has_tables,
            "has_lists": self.has_lists,
            "has_yaml_frontmatter": self.has_yaml_frontmatter,
            "structure_complexity": self.structure_complexity,
        }


@dataclass
class CollectionAnalysisResult:
    """Analysis result for a single collection."""

    collection_name: str
    """Name of the collection."""

    source_patterns: list
    """Source patterns for this collection."""

    sampled_files: list
    """List of file paths sampled for analysis."""

    metrics_list: list
    """List of DocumentMetrics for sampled files."""

    current_chunk_size: int
    """Current chunk_size from config."""

    current_overlap: int
    """Current chunk_overlap from config."""

    recommended_chunk_size: int
    """Recommended chunk_size."""

    recommended_overlap: int
    """Recommended chunk_overlap."""

    rationale: str
    """Explanation for recommendations."""

    @property
    def average_metrics(self) -> dict:
        """Calculate average metrics across sampled files."""
        if not self.metrics_list:
            return {}

        count = len(self.metrics_list)
        return {
            "avg_size_chars": int(sum(m.size_chars for m in self.metrics_list) / count),
            "avg_lines": int(sum(m.lines for m in self.metrics_list) / count),
            "avg_sections": int(sum(m.sections for m in self.metrics_list) / count),
            "avg_line_length": int(sum(m.avg_line_length for m in self.metrics_list) / count),
            "has_code_blocks": any(m.has_code_blocks for m in self.metrics_list),
            "has_tables": any(m.has_tables for m in self.metrics_list),
            "has_lists": any(m.has_lists for m in self.metrics_list),
        }

    @property
    def chunk_change(self) -> str:
        """Get human-readable chunk size change."""
        if self.recommended_chunk_size == self.current_chunk_size:
            return f"≈ +{self.recommended_overlap - self.current_overlap}"
        elif self.recommended_chunk_size > self.current_chunk_size:
            delta = self.recommended_chunk_size - self.current_chunk_size
            overlap_delta = self.recommended_overlap - self.current_overlap
            return f"⬆️ +{delta}/+{overlap_delta}"
        else:
            delta = self.current_chunk_size - self.recommended_chunk_size
            overlap_delta = self.current_overlap - self.recommended_overlap
            return f"⬇️ -{delta}/{overlap_delta}"
