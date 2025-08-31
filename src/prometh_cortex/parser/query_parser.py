"""Structured query parser for enhanced search capabilities."""

import re
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Union
from dataclasses import dataclass


@dataclass
class ParsedQuery:
    """Parsed query with filters and semantic text."""
    semantic_text: str
    metadata_filters: Dict[str, Any]
    original_query: str


class QueryParser:
    """Parser for structured queries with metadata filtering support."""
    
    def __init__(self, config=None, auto_discovered_fields=None):
        """Initialize query parser with hybrid auto-discovery + user config.
        
        Args:
            config: Configuration object with structured query settings
            auto_discovered_fields: Set of auto-discovered fields from documents
        """
        self.config = config
        self.auto_discovered_fields = auto_discovered_fields or set()
        
        # Build available fields from config (hybrid approach)
        self.available_fields = self._build_available_fields()
        
        # Define core patterns (always reliable)
        self.core_patterns = {
            'tags': re.compile(r'tags:([^\s]+)', re.IGNORECASE),
            'created': re.compile(r'created:([^\s]+)', re.IGNORECASE),
            'modified': re.compile(r'modified:([^\s]+)', re.IGNORECASE),
        }
        
        # Dynamic pattern for any field (fallback)
        self.dynamic_pattern = re.compile(r'([a-zA-Z_][a-zA-Z0-9_]*):([^\s]+)', re.IGNORECASE)
    
    def _build_available_fields(self) -> set:
        """Build set of available fields using hybrid approach."""
        available = set()
        
        if self.config:
            # Add core fields (always enabled)
            available.update(self.config.structured_query_core_fields)
            
            # Add extended fields (user configurable)
            available.update(self.config.structured_query_extended_fields)
            
            # Add auto-discovered fields if enabled
            if self.config.structured_query_auto_discovery and self.auto_discovered_fields:
                # Limit to max_auto_fields
                sorted_auto_fields = sorted(self.auto_discovered_fields)[:self.config.structured_query_max_auto_fields]
                available.update(sorted_auto_fields)
        else:
            # Fallback: use reasonable defaults
            available.update([
                "tags", "created", "modified", "category", "author", 
                "status", "focus", "title", "subject", "organizer", "location"
            ])
        
        return available
    
    def update_auto_discovered_fields(self, fields: set) -> None:
        """Update the set of auto-discovered fields."""
        self.auto_discovered_fields = fields
        self.available_fields = self._build_available_fields()
    
    def parse_query(self, query: str) -> ParsedQuery:
        """
        Parse a query string into semantic text and metadata filters.
        
        Args:
            query: Raw query string (e.g., "category:meetings created:2025-08-25 discussion")
            
        Returns:
            ParsedQuery object with separated semantic text and filters
            
        Example:
            >>> parser = QueryParser()
            >>> result = parser.parse_query("category:meetings created:2025-08-25 discussion agenda")
            >>> result.semantic_text  # "discussion agenda"
            >>> result.metadata_filters  # {"category": "meetings", "created": "2025-08-25"}
        """
        remaining_query = query
        metadata_filters = {}
        unknown_fields = []
        
        # First, extract core reliable filters
        for field, pattern in self.core_patterns.items():
            matches = pattern.findall(remaining_query)
            if matches:
                # Handle multiple values for same field (take last one for now)
                filter_value = matches[-1]
                
                # Parse the filter value based on field type
                parsed_value = self._parse_filter_value(field, filter_value)
                if parsed_value is not None:
                    metadata_filters[field] = parsed_value
                
                # Remove the filter from the remaining query
                remaining_query = pattern.sub('', remaining_query)
        
        # Then, find any other field:value patterns
        dynamic_matches = self.dynamic_pattern.findall(remaining_query)
        for field_name, field_value in dynamic_matches:
            field_lower = field_name.lower()
            
            # Skip if already processed by core patterns
            if field_lower in self.core_patterns:
                continue
            
            # Use hybrid approach: Check if field is in our available fields
            # (combines core + extended + auto-discovered fields)
            
            if field_lower in self.available_fields:
                # Treat as a metadata filter
                parsed_value = self._parse_filter_value(field_lower, field_value)
                if parsed_value is not None:
                    metadata_filters[field_lower] = parsed_value
            else:
                # Add to unknown fields for semantic enhancement
                unknown_fields.append((field_name, field_value))
        
        # Remove all field:value patterns from the query
        remaining_query = self.dynamic_pattern.sub('', remaining_query)
        
        # Clean up remaining query text
        semantic_text = ' '.join(remaining_query.split()).strip()
        
        # Enhance semantic text with unknown field values for better matching
        if unknown_fields:
            semantic_parts = [semantic_text] if semantic_text else []
            for field_name, field_value in unknown_fields:
                # Add field name and value to semantic search
                semantic_parts.extend([field_name, field_value])
            semantic_text = ' '.join(semantic_parts)
        
        return ParsedQuery(
            semantic_text=semantic_text,
            metadata_filters=metadata_filters,
            original_query=query
        )
    
    def _parse_filter_value(self, field: str, value: str) -> Any:
        """
        Parse filter value based on field type.
        
        Args:
            field: Filter field name
            value: Raw filter value string
            
        Returns:
            Parsed value in appropriate type
        """
        if field in ['created', 'modified']:
            return self._parse_date_filter(value)
        elif field == 'tags':
            return self._parse_tags_filter(value)
        elif field == 'category':
            return value.lower()  # Normalize case
        elif field in ['author', 'status', 'focus', 'file_name', 'file_extension']:
            return value
        else:
            return value
    
    def _parse_date_filter(self, value: str) -> Optional[Dict[str, str]]:
        """
        Parse date filter value into appropriate format for Qdrant.
        
        Supports:
        - Exact dates: "2025-08-25"
        - Date ranges: "2025-08-20:2025-08-25"
        - Relative dates: "today", "yesterday", "last_week" (future enhancement)
        
        Args:
            value: Date filter value
            
        Returns:
            Dictionary with date range for Qdrant filtering
        """
        try:
            # Handle date ranges
            if ':' in value:
                start_date, end_date = value.split(':', 1)
                return {
                    "gte": self._parse_single_date(start_date),
                    "lte": self._parse_single_date(end_date)
                }
            
            # Handle single dates (treat as exact day range)
            single_date = self._parse_single_date(value)
            if single_date:
                # Create range for entire day
                date_obj = datetime.fromisoformat(single_date.replace('Z', '+00:00'))
                start_of_day = date_obj.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = date_obj.replace(hour=23, minute=59, second=59, microsecond=999999)
                
                return {
                    "gte": start_of_day.isoformat() + 'Z',
                    "lte": end_of_day.isoformat() + 'Z'
                }
            
        except (ValueError, AttributeError):
            pass
        
        return None
    
    def _parse_single_date(self, date_str: str) -> Optional[str]:
        """
        Parse a single date string into ISO format.
        
        Args:
            date_str: Date string in various formats
            
        Returns:
            ISO date string or None if parsing fails
        """
        # Common date formats to try
        formats = [
            '%Y-%m-%d',           # 2025-08-25
            '%Y-%m-%dT%H:%M:%S',  # 2025-08-25T14:30:00
            '%Y-%m-%d %H:%M:%S',  # 2025-08-25 14:30:00
            '%m/%d/%Y',           # 08/25/2025
            '%d/%m/%Y',           # 25/08/2025
        ]
        
        for fmt in formats:
            try:
                parsed_date = datetime.strptime(date_str, fmt)
                return parsed_date.isoformat() + 'Z'
            except ValueError:
                continue
        
        # Handle special cases like "today", "yesterday"
        if date_str.lower() == 'today':
            return datetime.now().isoformat() + 'Z'
        elif date_str.lower() == 'yesterday':
            yesterday = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = yesterday.replace(day=yesterday.day - 1)
            return yesterday.isoformat() + 'Z'
        
        return None
    
    def _parse_tags_filter(self, value: str) -> List[str]:
        """
        Parse tags filter value with enhanced format support.
        
        Supports:
        - Single tag: "work"
        - Multiple tags: "work,meetings" or "work|meetings" or "work+meetings"
        - Negation: "!internal" or "-private"
        - Mixed: "work,meetings,!internal"
        
        Args:
            value: Tags filter value
            
        Returns:
            List of tag strings (with negation preserved)
        """
        # Support multiple separators: comma, pipe, plus
        separators = [',', '|', '+']
        tags = [value]
        
        # Split by all supported separators
        for sep in separators:
            if any(sep in tag for tag in tags):
                new_tags = []
                for tag in tags:
                    if sep in tag:
                        new_tags.extend([t.strip() for t in tag.split(sep)])
                    else:
                        new_tags.append(tag)
                tags = new_tags
        
        # Clean up and normalize tags
        cleaned_tags = []
        for tag in tags:
            tag = tag.strip()
            if tag:
                # Handle negation indicators
                if tag.startswith('!') or tag.startswith('-'):
                    # Keep negation for potential future use
                    cleaned_tags.append(tag)
                else:
                    cleaned_tags.append(tag)
        
        return cleaned_tags
    
    def convert_to_qdrant_filters(self, metadata_filters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parsed metadata filters to Qdrant-compatible filter format.
        
        Args:
            metadata_filters: Parsed metadata filters
            
        Returns:
            Dictionary compatible with Qdrant filtering
        """
        qdrant_filters = {}
        
        for field, value in metadata_filters.items():
            if field in ['created', 'modified']:
                # For date filtering, we'll implement post-processing filtering
                # since Qdrant date range filtering is complex with ISO strings
                # Skip date filters here and handle them in post-processing
                pass
            elif field == 'tags':
                # Tags are stored as arrays, use MatchAny
                if isinstance(value, list):
                    qdrant_filters[field] = value
                else:
                    qdrant_filters[field] = [value]
            else:
                # Exact string match
                qdrant_filters[field] = value
        
        return qdrant_filters
    
    def _iso_to_timestamp(self, iso_string: str) -> float:
        """
        Convert ISO date string to Unix timestamp.
        
        Args:
            iso_string: ISO format date string
            
        Returns:
            Unix timestamp as float
        """
        try:
            # Parse ISO string (handle various formats)
            if iso_string.endswith('Z'):
                iso_string = iso_string[:-1] + '+00:00'
            
            dt = datetime.fromisoformat(iso_string)
            return dt.timestamp()
        except (ValueError, AttributeError) as e:
            # If parsing fails, try to extract just the date part and use that
            try:
                date_part = iso_string.split('T')[0]
                dt = datetime.fromisoformat(f"{date_part}T00:00:00+00:00")
                return dt.timestamp()
            except Exception:
                raise ValueError(f"Could not parse date string: {iso_string}") from e
    
    def build_semantic_query(self, parsed_query: ParsedQuery) -> str:
        """
        Build enhanced semantic query text for vector search with tag boosting.
        
        Args:
            parsed_query: Parsed query object
            
        Returns:
            Enhanced semantic query text optimized for vector search
        """
        semantic_parts = []
        
        # Start with explicit semantic text
        if parsed_query.semantic_text:
            semantic_parts.append(parsed_query.semantic_text)
        
        # Strongly boost tags for semantic matching (tags are very reliable)
        if 'tags' in parsed_query.metadata_filters:
            tags = parsed_query.metadata_filters['tags']
            if isinstance(tags, list):
                # Add positive tags to semantic search
                positive_tags = [tag for tag in tags if not tag.startswith(('!', '-'))]
                if positive_tags:
                    # Add tags multiple times for stronger semantic boost
                    semantic_parts.extend(positive_tags)  # Add once as-is
                    semantic_parts.extend(positive_tags)  # Add again for boost
            else:
                if not str(tags).startswith(('!', '-')):
                    semantic_parts.extend([str(tags), str(tags)])  # Double boost
        
        # Add other metadata with lighter touch
        filter_boost_map = {
            'category': lambda v: f"{v}",
            'author': lambda v: f"author {v}",
            'status': lambda v: f"status {v}",
            'focus': lambda v: f"focus {v}",
        }
        
        for field, value in parsed_query.metadata_filters.items():
            if field in filter_boost_map and field != 'tags':  # Skip tags (handled above)
                boost_text = filter_boost_map[field](value)
                semantic_parts.append(boost_text)
        
        # If no semantic content exists, use filter values
        if not semantic_parts:
            if 'tags' in parsed_query.metadata_filters:
                tags = parsed_query.metadata_filters['tags']
                if isinstance(tags, list):
                    positive_tags = [tag for tag in tags if not tag.startswith(('!', '-'))]
                    semantic_parts.extend(positive_tags if positive_tags else ["documents"])
                else:
                    semantic_parts.append(str(tags) if not str(tags).startswith(('!', '-')) else "documents")
            else:
                semantic_parts.append("documents")
        
        return ' '.join(semantic_parts)


def parse_query(query: str) -> ParsedQuery:
    """
    Convenience function to parse a query string.
    
    Args:
        query: Raw query string
        
    Returns:
        ParsedQuery object
    """
    parser = QueryParser()
    return parser.parse_query(query)


# Example usage and testing
if __name__ == "__main__":
    # Test examples
    parser = QueryParser()
    
    test_queries = [
        "category:meetings created:2025-08-25 discussion agenda",
        "tags:work,urgent author:john deadline project",
        "category:notes created:2025-08-20:2025-08-25",
        "status:finished focus:work quarterly review",
        "just regular semantic search text",
        "category:meetings"
    ]
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        result = parser.parse_query(query)
        print(f"  Semantic: '{result.semantic_text}'")
        print(f"  Filters: {result.metadata_filters}")
        print(f"  Qdrant: {parser.convert_to_qdrant_filters(result.metadata_filters)}")