#!/usr/bin/env python3
"""
Migration script to create metadata for existing files that don't have it.
This is needed when upgrading from the old system to the new metadata system.
"""

import os
import json
from datetime import datetime
from pathlib import Path
from config import settings

def migrate_existing_files():
    """Create metadata for existing files that don't have metadata entries"""
    
    if not os.path.exists(settings.UPLOAD_DIR):
        print("Upload directory does not exist. Nothing to migrate.")
        return
    
    metadata_file = os.path.join(settings.UPLOAD_DIR, "file_metadata.json")
    
    # Load existing metadata
    if os.path.exists(metadata_file):
        with open(metadata_file, 'r') as f:
            metadata = json.load(f)
    else:
        metadata = {}
    
    # Find files without metadata
    migrated_count = 0
    
    for filename in os.listdir(settings.UPLOAD_DIR):
        if filename == "file_metadata.json":
            continue
            
        file_path = os.path.join(settings.UPLOAD_DIR, filename)
        
        if not os.path.isfile(file_path):
            continue
        
        # Extract file ID from filename (UUID part)
        file_id = Path(filename).stem
        
        # Skip if metadata already exists
        if file_id in metadata:
            continue
        
        # Get file stats
        file_stats = os.stat(file_path)
        file_size = file_stats.st_size
        upload_timestamp = datetime.fromtimestamp(file_stats.st_ctime).isoformat()
        
        # Determine content type from extension
        extension = Path(filename).suffix.lower()
        content_type_map = {
            '.txt': 'text/plain',
            '.pdf': 'application/pdf',
            '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        }
        content_type = content_type_map.get(extension, 'application/octet-stream')
        
        # For migrated files, we can't recover the original filename
        # So we'll use the current filename as both original and unique filename
        # This is not ideal but maintains compatibility
        original_filename = filename
        
        # Create metadata entry
        metadata[file_id] = {
            "original_filename": original_filename,
            "unique_filename": filename,
            "file_size": file_size,
            "content_type": content_type,
            "upload_timestamp": upload_timestamp
        }
        
        migrated_count += 1
        print(f"Migrated: {filename} -> {file_id}")
    
    # Save updated metadata
    if migrated_count > 0:
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        print(f"\nMigration completed! Migrated {migrated_count} files.")
    else:
        print("No files to migrate.")

if __name__ == "__main__":
    print("Starting file metadata migration...")
    migrate_existing_files()
    print("Migration finished.")
