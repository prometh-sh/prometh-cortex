"""YAML frontmatter parsing with structured schema support."""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import yaml
from pydantic import BaseModel, Field, field_validator


class ProjectInfo(BaseModel):
    """Project information from frontmatter."""
    name: str
    uuid: str


class ReminderInfo(BaseModel):
    """Reminder information from frontmatter."""
    subject: str
    uuid: str
    list: Optional[str] = None


class EventInfo(BaseModel):
    """Event information from frontmatter."""
    subject: str
    uuid: str
    short_uuid: Optional[str] = Field(None, alias="shortUUID")
    created: Optional[datetime] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    duration: Optional[str] = None
    organizer: Optional[str] = None
    attendees: Optional[List[str]] = None
    location: Optional[str] = None
    
    @field_validator("created", "start", "end", mode="before")
    @classmethod
    def parse_datetime(cls, v):
        """Parse datetime strings in various formats."""
        if v is None or isinstance(v, datetime):
            return v
        
        if isinstance(v, str):
            # Try common datetime formats
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S", 
                "%Y-%m-%d",
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
            
            # If no format matches, return as string for now
            return v
        
        return v


class FrontmatterSchema(BaseModel):
    """Complete frontmatter schema based on specification."""
    
    # Basic document metadata
    title: Optional[str] = None
    created: Optional[datetime] = None
    author: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    focus: Optional[str] = None
    uuid: Optional[str] = None
    
    # Related items
    project: Optional[List[ProjectInfo]] = None
    reminder: Optional[List[ReminderInfo]] = None
    event: Optional[EventInfo] = None
    related: Optional[List[str]] = None
    
    # Custom fields - catch any additional metadata
    extra_fields: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = {"extra": "allow", "populate_by_name": True}
    
    @field_validator("created", mode="before")
    @classmethod
    def parse_created_datetime(cls, v):
        """Parse created datetime field."""
        if v is None or isinstance(v, datetime):
            return v
        
        if isinstance(v, str):
            formats = [
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d",
            ]
            
            for fmt in formats:
                try:
                    return datetime.strptime(v, fmt)
                except ValueError:
                    continue
        
        return v
    
    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        """Normalize tags to list of strings."""
        if v is None:
            return None
        
        if isinstance(v, str):
            # Handle comma-separated or space-separated tags
            return [tag.strip() for tag in v.replace(",", " ").split() if tag.strip()]
        
        if isinstance(v, list):
            # Ensure all tags are strings
            return [str(tag) for tag in v if tag]
        
        return v
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FrontmatterSchema":
        """Create FrontmatterSchema from raw dictionary, handling extra fields."""
        # Extract known fields
        known_fields = {}
        extra_fields = {}
        
        for key, value in data.items():
            if key in cls.model_fields:
                known_fields[key] = value
            else:
                extra_fields[key] = value
        
        # Create instance with known fields
        try:
            instance = cls(**known_fields)
            instance.extra_fields = extra_fields
            return instance
        except Exception:
            # If validation fails, create minimal instance with all data in extra_fields
            instance = cls()
            instance.extra_fields = data
            return instance


def parse_frontmatter(frontmatter_text: str) -> Optional[FrontmatterSchema]:
    """
    Parse YAML frontmatter text into structured schema.
    
    Args:
        frontmatter_text: Raw YAML frontmatter content
        
    Returns:
        FrontmatterSchema object or None if parsing fails
    """
    if not frontmatter_text.strip():
        return None
    
    try:
        # Parse YAML
        yaml_data = yaml.safe_load(frontmatter_text)
        
        if not isinstance(yaml_data, dict):
            return None
        
        # Convert to structured schema
        return FrontmatterSchema.from_dict(yaml_data)
    
    except yaml.YAMLError:
        # Return minimal schema with raw data if YAML parsing fails
        return FrontmatterSchema(extra_fields={"raw_frontmatter": frontmatter_text})
    except Exception:
        # Fallback for any other parsing errors
        return None


def extract_searchable_text(frontmatter: FrontmatterSchema) -> str:
    """
    Extract searchable text content from frontmatter.
    
    Args:
        frontmatter: Parsed frontmatter schema
        
    Returns:
        Concatenated searchable text from frontmatter fields
    """
    searchable_parts = []
    
    # Add basic text fields
    if frontmatter.title:
        searchable_parts.append(frontmatter.title)
    
    if frontmatter.author:
        searchable_parts.append(frontmatter.author)
    
    if frontmatter.category:
        searchable_parts.append(frontmatter.category)
    
    if frontmatter.focus:
        searchable_parts.append(frontmatter.focus)
    
    # Add tags
    if frontmatter.tags:
        searchable_parts.extend(frontmatter.tags)
    
    # Add project information
    if frontmatter.project:
        for project in frontmatter.project:
            searchable_parts.append(project.name)
    
    # Add reminder information
    if frontmatter.reminder:
        for reminder in frontmatter.reminder:
            searchable_parts.append(reminder.subject)
            if reminder.list:
                searchable_parts.append(reminder.list)
    
    # Add event information
    if frontmatter.event:
        searchable_parts.append(frontmatter.event.subject)
        if frontmatter.event.organizer:
            searchable_parts.append(frontmatter.event.organizer)
        if frontmatter.event.location:
            searchable_parts.append(frontmatter.event.location)
        if frontmatter.event.attendees:
            searchable_parts.extend(frontmatter.event.attendees)
    
    # Add related items
    if frontmatter.related:
        searchable_parts.extend(frontmatter.related)
    
    # Add extra fields (as strings)
    for key, value in frontmatter.extra_fields.items():
        if isinstance(value, str):
            searchable_parts.append(value)
        elif isinstance(value, list):
            searchable_parts.extend([str(item) for item in value if item])
    
    return " ".join(searchable_parts)