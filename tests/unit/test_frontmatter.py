"""Unit tests for YAML frontmatter parsing."""

import pytest
from datetime import datetime

from prometh_cortex.parser.frontmatter import (
    FrontmatterSchema,
    ProjectInfo,
    ReminderInfo,
    EventInfo,
    parse_frontmatter,
    extract_searchable_text
)


class TestFrontmatterSchema:
    """Test frontmatter schema parsing and validation."""
    
    def test_basic_frontmatter_parsing(self):
        """Test parsing basic frontmatter fields."""
        data = {
            "title": "Test Document",
            "author": "Ivan Nagy",
            "category": "#Meetings",
            "tags": ["#RAG", "work"],
            "focus": "Work"
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert schema.title == "Test Document"
        assert schema.author == "Ivan Nagy"
        assert schema.category == "#Meetings"
        assert schema.tags == ["#RAG", "work"]
        assert schema.focus == "Work"
    
    def test_datetime_parsing(self):
        """Test parsing datetime fields."""
        data = {
            "title": "Test",
            "created": "2025-08-23T10:30:00"
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert isinstance(schema.created, datetime)
        assert schema.created.year == 2025
        assert schema.created.month == 8
        assert schema.created.day == 23
    
    def test_project_info_parsing(self):
        """Test parsing project information."""
        data = {
            "title": "Test",
            "project": [
                {
                    "name": "Project Alpha",
                    "uuid": "D86F080E-D47E-42C0-949A-737E85485FF2"
                }
            ]
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert len(schema.project) == 1
        assert schema.project[0].name == "Project Alpha"
        assert schema.project[0].uuid == "D86F080E-D47E-42C0-949A-737E85485FF2"
    
    def test_reminder_info_parsing(self):
        """Test parsing reminder information."""
        data = {
            "title": "Test",
            "reminder": [
                {
                    "subject": "Follow up on meeting",
                    "uuid": "741C071F-EC6A-4036-9A8C-23F80705A1D9",
                    "list": "Work"
                }
            ]
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert len(schema.reminder) == 1
        assert schema.reminder[0].subject == "Follow up on meeting"
        assert schema.reminder[0].list == "Work"
    
    def test_event_info_parsing(self):
        """Test parsing event information."""
        data = {
            "title": "Test",
            "event": {
                "subject": "Team Meeting",
                "uuid": "B897515C-1BE9-41B6-8423-3988BE0C9E3E",
                "shortUUID": "MF042576B",
                "organizer": "John Doe",
                "attendees": ["Alice", "Bob"],
                "location": "Conference Room A"
            }
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert schema.event.subject == "Team Meeting"
        assert schema.event.short_uuid == "MF042576B"
        assert schema.event.organizer == "John Doe"
        assert "Alice" in schema.event.attendees
        assert schema.event.location == "Conference Room A"
    
    def test_tags_normalization(self):
        """Test tag normalization from various formats."""
        # Comma-separated string
        data1 = {"tags": "work, project, meeting"}
        schema1 = FrontmatterSchema.from_dict(data1)
        assert "work" in schema1.tags
        assert "project" in schema1.tags
        assert "meeting" in schema1.tags
        
        # Space-separated string
        data2 = {"tags": "work project meeting"}
        schema2 = FrontmatterSchema.from_dict(data2)
        assert len(schema2.tags) == 3
        
        # List format
        data3 = {"tags": ["work", "project", "meeting"]}
        schema3 = FrontmatterSchema.from_dict(data3)
        assert schema3.tags == ["work", "project", "meeting"]
    
    def test_extra_fields_handling(self):
        """Test handling of extra fields not in schema."""
        data = {
            "title": "Test",
            "custom_field": "custom_value",
            "another_field": {"nested": "data"}
        }
        
        schema = FrontmatterSchema.from_dict(data)
        
        assert schema.title == "Test"
        assert schema.extra_fields["custom_field"] == "custom_value"
        assert schema.extra_fields["another_field"]["nested"] == "data"


class TestParseFrontmatter:
    """Test frontmatter parsing from YAML strings."""
    
    def test_parse_valid_yaml(self):
        """Test parsing valid YAML frontmatter."""
        yaml_content = """
title: Test Document
author: Ivan Nagy
tags:
  - work
  - project
"""
        
        schema = parse_frontmatter(yaml_content)
        
        assert schema is not None
        assert schema.title == "Test Document"
        assert schema.author == "Ivan Nagy"
        assert "work" in schema.tags
    
    def test_parse_invalid_yaml(self):
        """Test handling of invalid YAML."""
        invalid_yaml = "title: Test\n  invalid: [unclosed"
        
        schema = parse_frontmatter(invalid_yaml)
        
        assert schema is not None
        # Should have raw frontmatter in extra_fields
        assert "raw_frontmatter" in schema.extra_fields
    
    def test_parse_empty_frontmatter(self):
        """Test parsing empty frontmatter."""
        schema = parse_frontmatter("")
        assert schema is None
        
        schema = parse_frontmatter("   \n  \n  ")
        assert schema is None


class TestExtractSearchableText:
    """Test extracting searchable text from frontmatter."""
    
    def test_extract_basic_fields(self):
        """Test extracting text from basic fields."""
        schema = FrontmatterSchema(
            title="Test Document",
            author="Ivan Nagy",
            category="#Meetings",
            focus="Work",
            tags=["RAG", "search"]
        )
        
        searchable_text = extract_searchable_text(schema)
        
        assert "Test Document" in searchable_text
        assert "Ivan Nagy" in searchable_text
        assert "#Meetings" in searchable_text
        assert "Work" in searchable_text
        assert "RAG" in searchable_text
        assert "search" in searchable_text
    
    def test_extract_project_info(self):
        """Test extracting project information."""
        schema = FrontmatterSchema(
            title="Test",
            project=[
                ProjectInfo(name="Project Alpha", uuid="123"),
                ProjectInfo(name="Project Beta", uuid="456")
            ]
        )
        
        searchable_text = extract_searchable_text(schema)
        
        assert "Project Alpha" in searchable_text
        assert "Project Beta" in searchable_text
    
    def test_extract_event_info(self):
        """Test extracting event information."""
        schema = FrontmatterSchema(
            title="Test",
            event=EventInfo(
                subject="Team Meeting",
                uuid="123",
                organizer="John Doe",
                attendees=["Alice", "Bob"],
                location="Conference Room"
            )
        )
        
        searchable_text = extract_searchable_text(schema)
        
        assert "Team Meeting" in searchable_text
        assert "John Doe" in searchable_text
        assert "Alice" in searchable_text
        assert "Bob" in searchable_text
        assert "Conference Room" in searchable_text
    
    def test_extract_extra_fields(self):
        """Test extracting extra fields."""
        schema = FrontmatterSchema(
            title="Test",
            extra_fields={
                "custom_text": "This is custom",
                "custom_list": ["item1", "item2"],
                "custom_number": 42
            }
        )
        
        searchable_text = extract_searchable_text(schema)
        
        assert "This is custom" in searchable_text
        assert "item1" in searchable_text
        assert "item2" in searchable_text