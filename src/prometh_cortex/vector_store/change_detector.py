"""Document change detection for incremental indexing."""

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Dict, List, Set

from .interface import DocumentChange


class DocumentChangeDetector:
    """Detects changes in document collection for incremental indexing."""
    
    def __init__(self, index_metadata_path: str):
        """Initialize the change detector.
        
        Args:
            index_metadata_path: Path to store index metadata
        """
        self.metadata_path = Path(index_metadata_path)
        self.indexed_docs: Dict[str, Dict] = self._load_metadata()
    
    def detect_changes(self, document_paths: List[str]) -> List[DocumentChange]:
        """Compare current documents with indexed metadata to detect changes.
        
        Args:
            document_paths: List of current document file paths
            
        Returns:
            List of DocumentChange objects representing detected changes
        """
        changes = []
        current_docs = set(document_paths)
        indexed_docs = set(self.indexed_docs.keys())
        
        # New documents
        for doc_path in current_docs - indexed_docs:
            if os.path.exists(doc_path):
                changes.append(DocumentChange(
                    file_path=doc_path,
                    change_type='add',
                    file_hash=self._compute_file_hash(doc_path),
                    modified_time=os.path.getmtime(doc_path)
                ))
        
        # Deleted documents
        for doc_path in indexed_docs - current_docs:
            changes.append(DocumentChange(
                file_path=doc_path,
                change_type='delete'
            ))
        
        # Modified documents
        for doc_path in current_docs & indexed_docs:
            if not os.path.exists(doc_path):
                # File was deleted
                changes.append(DocumentChange(
                    file_path=doc_path,
                    change_type='delete'
                ))
                continue
                
            current_hash = self._compute_file_hash(doc_path)
            indexed_hash = self.indexed_docs[doc_path].get('file_hash')
            current_mtime = os.path.getmtime(doc_path)
            indexed_mtime = self.indexed_docs[doc_path].get('modified_time', 0)
            
            # Check if file content or modification time changed
            if current_hash != indexed_hash or current_mtime > indexed_mtime:
                changes.append(DocumentChange(
                    file_path=doc_path,
                    change_type='update',
                    file_hash=current_hash,
                    modified_time=current_mtime
                ))
        
        return changes
    
    def update_metadata(self, changes: List[DocumentChange]) -> None:
        """Update metadata after successful indexing.
        
        Args:
            changes: List of successfully applied changes
        """
        current_time = time.time()
        
        for change in changes:
            if change.change_type == 'delete':
                self.indexed_docs.pop(change.file_path, None)
            else:
                self.indexed_docs[change.file_path] = {
                    'file_hash': change.file_hash,
                    'modified_time': change.modified_time,
                    'indexed_at': current_time
                }
        
        self._save_metadata()
    
    def get_stats(self) -> Dict[str, any]:
        """Get change detector statistics.
        
        Returns:
            Statistics dict with indexed document counts and metadata
        """
        return {
            'total_indexed_documents': len(self.indexed_docs),
            'metadata_file': str(self.metadata_path),
            'metadata_exists': self.metadata_path.exists(),
            'last_updated': max(
                (doc.get('indexed_at', 0) for doc in self.indexed_docs.values()),
                default=0
            ) if self.indexed_docs else 0
        }
    
    def reset(self) -> None:
        """Reset all metadata (force full rebuild)."""
        self.indexed_docs.clear()
        self._save_metadata()
    
    def _compute_file_hash(self, file_path: str) -> str:
        """Compute SHA256 hash of file content.
        
        Args:
            file_path: Path to file
            
        Returns:
            Hexadecimal hash string
        """
        hasher = hashlib.sha256()
        try:
            with open(file_path, 'rb') as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    hasher.update(chunk)
            return hasher.hexdigest()
        except (OSError, IOError) as e:
            # If file can't be read, return a placeholder hash
            # This will trigger a change detection
            return f"error_{hash(str(e))}"
    
    def _load_metadata(self) -> Dict[str, Dict]:
        """Load existing index metadata.
        
        Returns:
            Dictionary mapping file paths to metadata
        """
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except (json.JSONDecodeError, OSError, IOError):
                # If metadata is corrupted, start fresh
                return {}
        return {}
    
    def _save_metadata(self) -> None:
        """Save index metadata to file."""
        try:
            # Ensure parent directory exists
            self.metadata_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write metadata atomically (write to temp file, then rename)
            temp_path = self.metadata_path.with_suffix('.tmp')
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.indexed_docs, f, indent=2, sort_keys=True)
            
            temp_path.replace(self.metadata_path)
            
        except (OSError, IOError) as e:
            # Log error but don't crash - metadata is not critical
            # In production, you might want to use proper logging here
            print(f"Warning: Failed to save index metadata: {e}")
    
    def backup_metadata(self, backup_path: str) -> None:
        """Create a backup of current metadata.
        
        Args:
            backup_path: Path to save backup
        """
        backup_path_obj = Path(backup_path)
        backup_data = {
            'timestamp': time.time(),
            'indexed_docs': self.indexed_docs.copy()
        }
        
        backup_path_obj.parent.mkdir(parents=True, exist_ok=True)
        with open(backup_path_obj, 'w', encoding='utf-8') as f:
            json.dump(backup_data, f, indent=2)
    
    def restore_metadata(self, backup_path: str) -> None:
        """Restore metadata from backup.
        
        Args:
            backup_path: Path to backup file
        """
        backup_path_obj = Path(backup_path)
        if not backup_path_obj.exists():
            raise FileNotFoundError(f"Backup file not found: {backup_path}")
        
        with open(backup_path_obj, 'r', encoding='utf-8') as f:
            backup_data = json.load(f)
        
        self.indexed_docs = backup_data.get('indexed_docs', {})
        self._save_metadata()