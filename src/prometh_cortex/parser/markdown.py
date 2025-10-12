"""Markdown document parsing and content extraction."""

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

import frontmatter
from pydantic import BaseModel

from prometh_cortex.parser.frontmatter import FrontmatterSchema, parse_frontmatter, extract_searchable_text


class MarkdownDocument(BaseModel):
    """Represents a parsed markdown document with frontmatter and content."""
    
    file_path: Path
    frontmatter: Optional[FrontmatterSchema] = None
    content: str = ""
    title: Optional[str] = None
    
    # Derived fields for indexing
    searchable_text: str = ""
    metadata: Dict = {}
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True
    
    def __init__(self, **data):
        """Initialize document and compute derived fields."""
        super().__init__(**data)
        self._compute_derived_fields()
    
    def _compute_derived_fields(self):
        """Compute searchable text and metadata for indexing."""
        # Extract title from frontmatter or content
        if not self.title:
            if self.frontmatter and self.frontmatter.title:
                self.title = self.frontmatter.title
            else:
                # Try to extract from first heading
                title_match = re.search(r'^#\s+(.+)$', self.content, re.MULTILINE)
                if title_match:
                    self.title = title_match.group(1).strip()
                else:
                    # Use filename as fallback
                    self.title = self.file_path.stem
        
        # Build searchable text
        searchable_parts = []
        
        # Add frontmatter text
        if self.frontmatter:
            frontmatter_text = extract_searchable_text(self.frontmatter)
            if frontmatter_text:
                searchable_parts.append(frontmatter_text)
        
        # Add title
        if self.title:
            searchable_parts.append(self.title)
        
        # Add markdown content (cleaned)
        if self.content:
            # Remove markdown syntax for better search
            cleaned_content = self._clean_markdown_content(self.content)
            searchable_parts.append(cleaned_content)
        
        self.searchable_text = " ".join(searchable_parts)
        
        # Build metadata dictionary
        metadata = {
            "file_path": str(self.file_path),
            "title": self.title,
            "file_name": self.file_path.name,
            "file_extension": self.file_path.suffix,
            "file_size": self.file_path.stat().st_size if self.file_path.exists() else 0,
        }
        
        # Add ALL frontmatter fields to metadata dynamically
        if self.frontmatter:
            # Get all fields from the frontmatter object, including extra fields
            frontmatter_dict = self.frontmatter.model_dump(by_alias=True)
            
            # Process each field dynamically
            for key, value in frontmatter_dict.items():
                if value is None or key == 'extra_fields':
                    continue
                    
                processed_value = self._process_frontmatter_value(key, value)
                
                if processed_value is not None:
                    # Handle special case where processing returns multiple fields (like events)
                    if isinstance(processed_value, dict) and key == 'event':
                        # Merge event fields directly into metadata
                        metadata.update(processed_value)
                    else:
                        metadata[key] = processed_value
            
            # Also process any extra fields that were captured
            if hasattr(self.frontmatter, 'extra_fields') and self.frontmatter.extra_fields:
                for key, value in self.frontmatter.extra_fields.items():
                    if value is not None:
                        processed_value = self._process_frontmatter_value(key, value)
                        if processed_value is not None:
                            metadata[key] = processed_value
        
        self.metadata = metadata
    
    def _process_frontmatter_value(self, key: str, value: Any) -> Any:
        """
        Process frontmatter values for optimal storage and searchability.
        
        Args:
            key: The field name
            value: The field value
            
        Returns:
            Processed value suitable for Qdrant storage
        """
        if value is None:
            return None
        
        # Handle datetime objects
        if hasattr(value, 'isoformat'):
            return value.isoformat()
        
        # Handle simple types directly
        if isinstance(value, (str, int, float, bool)):
            return value
        
        # Handle lists - preserve for Qdrant array filtering
        if isinstance(value, list):
            # For arrays of simple values, preserve as-is
            if all(isinstance(item, (str, int, float, bool)) for item in value):
                return value
            
            # For arrays of complex objects, extract meaningful fields
            if all(isinstance(item, dict) for item in value):
                # Extract names/subjects for searchability while preserving structure
                if key in ['project', 'projects']:
                    # Preserve both name and uuid for linking
                    return [{
                        'name': item.get('name', str(item)),
                        'uuid': item.get('uuid')
                    } for item in value]
                elif key in ['reminder', 'reminders']:
                    # Preserve subject, uuid, and list for linking
                    return [{
                        'subject': item.get('subject', str(item)),
                        'uuid': item.get('uuid'),
                        'list': item.get('list')
                    } for item in value]
                elif key in ['attendees', 'related']:
                    return value  # Already simple strings
                else:
                    # Convert complex objects to searchable strings
                    return [str(item) for item in value]
            
            # Mixed or unknown array types - convert to strings
            return [str(item) for item in value]
        
        # Handle dictionaries (like event objects)
        if isinstance(value, dict):
            # For event-like objects, extract key searchable fields
            if key == 'event':
                event_fields = {}
                if 'subject' in value:
                    event_fields['subject'] = value['subject']
                if 'uuid' in value:
                    event_fields['uuid'] = value['uuid']
                if 'shortUUID' in value or 'short_uuid' in value:
                    event_fields['short_uuid'] = value.get('shortUUID') or value.get('short_uuid')
                if 'organizer' in value:
                    event_fields['organizer'] = value['organizer']
                if 'location' in value:
                    event_fields['location'] = value['location']
                if 'attendees' in value:
                    event_fields['attendees'] = value['attendees']
                if 'start' in value:
                    start = value['start']
                    event_fields['start'] = start.isoformat() if hasattr(start, 'isoformat') else str(start)
                if 'end' in value:
                    end = value['end']
                    event_fields['end'] = end.isoformat() if hasattr(end, 'isoformat') else str(end)
                return event_fields
            else:
                # For other dict objects, convert to searchable string
                return str(value)
        
        # Handle other complex objects by converting to string
        return str(value)
    
    def _clean_markdown_content(self, content: str) -> str:
        """Clean markdown content for better searching."""
        # Remove markdown syntax
        content = re.sub(r'^#{1,6}\s+', '', content, flags=re.MULTILINE)  # Headers
        content = re.sub(r'\*\*(.+?)\*\*', r'\1', content)  # Bold
        content = re.sub(r'\*(.+?)\*', r'\1', content)  # Italic
        content = re.sub(r'`(.+?)`', r'\1', content)  # Inline code
        content = re.sub(r'```[\s\S]*?```', '', content)  # Code blocks
        content = re.sub(r'\[(.+?)\]\(.+?\)', r'\1', content)  # Links
        content = re.sub(r'!\[.*?\]\(.+?\)', '', content)  # Images
        content = re.sub(r'^>\s+', '', content, flags=re.MULTILINE)  # Blockquotes
        content = re.sub(r'^\s*[-*+]\s+', '', content, flags=re.MULTILINE)  # Lists
        content = re.sub(r'^\s*\d+\.\s+', '', content, flags=re.MULTILINE)  # Numbered lists
        
        # Clean up whitespace
        content = re.sub(r'\n\s*\n', '\n\n', content)  # Multiple newlines
        content = re.sub(r'[ \t]+', ' ', content)  # Multiple spaces/tabs
        
        return content.strip()


def parse_markdown_content(content: str, file_path: Path) -> MarkdownDocument:
    """
    Parse markdown content string into MarkdownDocument.
    
    Args:
        content: Raw markdown content with optional frontmatter
        file_path: Path to the source file
        
    Returns:
        MarkdownDocument with parsed frontmatter and content
    """
    try:
        # Use python-frontmatter to separate frontmatter and content
        post = frontmatter.loads(content)
        
        # Parse frontmatter if present
        parsed_frontmatter = None
        if post.metadata:
            parsed_frontmatter = FrontmatterSchema.from_dict(post.metadata)
        
        return MarkdownDocument(
            file_path=file_path,
            frontmatter=parsed_frontmatter,
            content=post.content
        )
    
    except Exception:
        # Fallback: treat entire content as markdown without frontmatter
        return MarkdownDocument(
            file_path=file_path,
            frontmatter=None,
            content=content
        )


def parse_markdown_file(file_path: Path) -> MarkdownDocument:
    """
    Parse a markdown file into MarkdownDocument.
    
    Args:
        file_path: Path to markdown file
        
    Returns:
        MarkdownDocument with parsed content
        
    Raises:
        FileNotFoundError: If file doesn't exist
        UnicodeDecodeError: If file can't be decoded
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {file_path}")
    
    # Try different encodings
    encodings = ['utf-8', 'utf-8-sig', 'latin-1', 'cp1252']
    content = None
    
    for encoding in encodings:
        try:
            content = file_path.read_text(encoding=encoding)
            break
        except UnicodeDecodeError:
            continue
    
    if content is None:
        raise UnicodeDecodeError(f"Could not decode file with any supported encoding: {file_path}")
    
    return parse_markdown_content(content, file_path)


def discover_markdown_files(directory: Path, recursive: bool = True) -> List[Path]:
    """
    Discover markdown files in a directory.
    
    Args:
        directory: Directory to search
        recursive: Whether to search subdirectories
        
    Returns:
        List of markdown file paths
        
    Raises:
        ValueError: If directory doesn't exist or isn't a directory
    """
    if not directory.exists():
        raise ValueError(f"Directory does not exist: {directory}")
    
    if not directory.is_dir():
        raise ValueError(f"Path is not a directory: {directory}")
    
    # Markdown file extensions to look for
    markdown_extensions = {'.md', '.markdown', '.mdown', '.mkd', '.mkdn'}
    
    markdown_files = []
    
    if recursive:
        # Use rglob for recursive search
        for ext in markdown_extensions:
            markdown_files.extend(directory.rglob(f"*{ext}"))
    else:
        # Use glob for non-recursive search
        for ext in markdown_extensions:
            markdown_files.extend(directory.glob(f"*{ext}"))
    
    # Filter out hidden files and directories
    markdown_files = [
        f for f in markdown_files 
        if not any(part.startswith('.') for part in f.parts)
    ]
    
    # Sort by path for consistent ordering
    return sorted(markdown_files)


def extract_document_chunks(document: MarkdownDocument, chunk_size: int = 512, chunk_overlap: int = 50) -> List[Dict]:
    """
    Split document into chunks for embedding.
    
    Args:
        document: MarkdownDocument to chunk
        chunk_size: Maximum size of each chunk in characters
        chunk_overlap: Overlap between chunks in characters
        
    Returns:
        List of chunk dictionaries with content and metadata
    """
    chunks = []
    text = document.searchable_text
    
    if not text.strip():
        # Return single empty chunk if no content
        return [{
            "content": "",
            "metadata": document.metadata,
            "chunk_index": 0,
            "total_chunks": 1
        }]
    
    # Split text into chunks
    start = 0
    chunk_index = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # If not the last chunk, try to break at word boundary
        if end < len(text):
            # Look for space or punctuation to break at
            break_point = max(
                text.rfind(' ', start, end),
                text.rfind('.', start, end),
                text.rfind('\n', start, end)
            )
            
            if break_point > start:
                end = break_point + 1
        
        chunk_text = text[start:end].strip()
        
        if chunk_text:  # Only add non-empty chunks
            chunk_metadata = document.metadata.copy()
            chunk_metadata.update({
                "chunk_index": chunk_index,
                "chunk_start": start,
                "chunk_end": end,
            })
            
            chunks.append({
                "content": chunk_text,
                "metadata": chunk_metadata,
                "chunk_index": chunk_index
            })
            
            chunk_index += 1
        
        # Move start position with overlap
        start = max(end - chunk_overlap, start + 1)
        
        # Prevent infinite loop
        if start >= len(text):
            break
    
    # Add total_chunks to all chunk metadata
    for chunk in chunks:
        chunk["metadata"]["total_chunks"] = len(chunks)
    
    return chunks if chunks else [{
        "content": text[:chunk_size],
        "metadata": document.metadata,
        "chunk_index": 0,
        "total_chunks": 1
    }]