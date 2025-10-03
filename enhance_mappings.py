#!/usr/bin/env python3
"""
Mapping Enhancement Script

This script enhances downloaded mapping files by adding text field columns
for both source and destination elements in each relationship. It reads Excel
files from the data/mappings/ directory and creates enhanced versions with
full element text descriptions from the database.
"""

import os
import sqlite3
import pandas as pd
from pathlib import Path
from datetime import datetime
import logging
from typing import Dict, List, Tuple, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('enhance_mappings.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MappingEnhancer:
    """Class to handle enhancement of mapping files with element text data."""
    
    def __init__(self, db_path: str = 'graph.db', mappings_dir: str = 'data/mappings'):
        self.db_path = db_path
        self.mappings_dir = Path(mappings_dir)
        self.element_cache = {}  # Cache for element lookups
        
    def get_db_connection(self) -> sqlite3.Connection:
        """Get SQLite database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn
        
    def validate_database_structure(self) -> bool:
        """Validate that the database has the required structure."""
        try:
            conn = self.get_db_connection()
            
            # Check if required tables exist
            tables_query = "SELECT name FROM sqlite_master WHERE type='table'"
            tables = [row[0] for row in conn.execute(tables_query).fetchall()]
            
            required_tables = ['documents', 'elements']
            missing_tables = [table for table in required_tables if table not in tables]
            
            if missing_tables:
                logger.error(f"Missing required tables: {missing_tables}")
                return False
                
            # Check elements table structure
            columns_query = "PRAGMA table_info(elements)"
            columns = [row[1] for row in conn.execute(columns_query).fetchall()]
            
            required_columns = ['element_identifier', 'text', 'title', 'document_id']
            missing_columns = [col for col in required_columns if col not in columns]
            
            if missing_columns:
                logger.error(f"Missing required columns in elements table: {missing_columns}")
                return False
                
            logger.info("Database structure validation passed")
            return True
            
        except Exception as e:
            logger.error(f"Database validation error: {e}")
            return False
        finally:
            conn.close()
            
    def lookup_element_text(self, document_id: str, element_id: str) -> Dict[str, str]:
        """
        Look up element text and title from database.
        
        Args:
            document_id: Document identifier (e.g., 'RSAT_2_0_0')
            element_id: Element identifier (e.g., 'Q1')
            
        Returns:
            Dictionary with 'title' and 'text' keys
        """
        cache_key = f"{document_id}::{element_id}"
        
        # Check cache first
        if cache_key in self.element_cache:
            return self.element_cache[cache_key]
            
        try:
            conn = self.get_db_connection()
            
            query = """
                SELECT e.title, e.text
                FROM elements e
                JOIN documents d ON e.document_id = d.document_id
                WHERE d.doc_identifier = ? AND e.element_identifier = ?
            """
            
            result = conn.execute(query, (document_id, element_id)).fetchone()
            
            if result:
                element_data = {
                    'title': result['title'] or 'N/A',
                    'text': result['text'] or ''
                }
                logger.debug(f"Found element {element_id} in {document_id}")
            else:
                logger.warning(f"Element not found: {element_id} in {document_id}")
                element_data = {
                    'title': 'Element not found',
                    'text': f'Could not locate element {element_id} in document {document_id}'
                }
                
            # Cache the result
            self.element_cache[cache_key] = element_data
            return element_data
            
        except Exception as e:
            logger.error(f"Error looking up element {element_id} in {document_id}: {e}")
            return {
                'title': 'Lookup error',
                'text': f'Error retrieving element data: {str(e)}'
            }
        finally:
            conn.close()
            
    def enhance_mapping_file(self, file_path: Path) -> Optional[Path]:
        """
        Enhance a single mapping file with element text data.
        
        Args:
            file_path: Path to the Excel file to enhance
            
        Returns:
            Path to the enhanced file, or None if enhancement failed
        """
        logger.info(f"Enhancing mapping file: {file_path.name}")
        
        try:
            # Read the Excel file
            xl = pd.ExcelFile(file_path)
            
            if 'Relationships' not in xl.sheet_names:
                logger.error(f"No 'Relationships' sheet found in {file_path.name}")
                return None
                
            df = pd.read_excel(xl, sheet_name='Relationships')
            logger.info(f"Loaded {len(df)} relationships from {file_path.name}")
            
            # Validate required columns
            required_columns = ['source_element', 'source_document', 'dest_element', 'dest_document']
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                logger.error(f"Missing required columns: {missing_columns}")
                return None
                
            # Add new columns for element text data
            source_texts = []
            dest_texts = []
            
            logger.info("Looking up element text data...")
            
            for index, row in df.iterrows():
                # Lookup source element
                source_data = self.lookup_element_text(
                    row['source_document'], 
                    row['source_element']
                )
                source_texts.append(source_data['text'])
                
                # Lookup destination element  
                dest_data = self.lookup_element_text(
                    row['dest_document'],
                    row['dest_element']
                )
                dest_texts.append(dest_data['text'])
                
                if (index + 1) % 25 == 0:
                    logger.info(f"Processed {index + 1}/{len(df)} relationships")
                    
            # Add the new columns to the DataFrame
            # Insert after existing columns but before relationship_type
            insert_pos = df.columns.get_loc('dest_title') + 1
            
            df.insert(insert_pos, 'source_text', source_texts)
            df.insert(insert_pos + 1, 'dest_text', dest_texts)
            
            logger.info("Added source_text and dest_text columns")
            
            # Generate output filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_filename = file_path.stem + f"_enhanced_{timestamp}.xlsx"
            output_path = file_path.parent / output_filename
            
            # Save enhanced file
            with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Relationships', index=False)
                
            logger.info(f"Enhanced file saved: {output_path}")
            
            # Print summary statistics
            self.print_enhancement_summary(df, file_path.name)
            
            return output_path
            
        except Exception as e:
            logger.error(f"Error enhancing file {file_path.name}: {e}")
            return None
            
    def print_enhancement_summary(self, df: pd.DataFrame, filename: str):
        """Print summary statistics for the enhanced file."""
        logger.info(f"\n=== Enhancement Summary for {filename} ===")
        logger.info(f"Total relationships processed: {len(df)}")
        
        # Count relationships by type
        if 'relationship_type' in df.columns:
            type_counts = df['relationship_type'].value_counts()
            logger.info("Relationship types:")
            for rel_type, count in type_counts.items():
                logger.info(f"  {rel_type}: {count}")
                
        # Count relationships by document pairs
        doc_pairs = df.groupby(['source_document', 'dest_document']).size()
        logger.info("Document mappings:")
        for (source_doc, dest_doc), count in doc_pairs.items():
            logger.info(f"  {source_doc} -> {dest_doc}: {count} relationships")
            
        # Check for missing text data
        empty_source_text = df['source_text'].str.contains('not found|error', case=False, na=False).sum()
        empty_dest_text = df['dest_text'].str.contains('not found|error', case=False, na=False).sum()
        
        if empty_source_text > 0:
            logger.warning(f"Source elements with missing/error text: {empty_source_text}")
        if empty_dest_text > 0:
            logger.warning(f"Destination elements with missing/error text: {empty_dest_text}")
            
        logger.info(f"Enhancement completed successfully")
        
    def process_all_mappings(self) -> List[Path]:
        """
        Process all mapping files in the mappings directory.
        
        Returns:
            List of paths to enhanced files
        """
        if not self.mappings_dir.exists():
            logger.error(f"Mappings directory does not exist: {self.mappings_dir}")
            return []
            
        # Find all Excel files in mappings directory
        excel_files = list(self.mappings_dir.glob("*.xlsx"))
        
        # Filter out files that are already enhanced
        mapping_files = [f for f in excel_files if '_enhanced_' not in f.name]
        
        if not mapping_files:
            logger.warning("No mapping files found to enhance")
            return []
            
        logger.info(f"Found {len(mapping_files)} mapping files to enhance")
        
        enhanced_files = []
        
        for file_path in mapping_files:
            logger.info(f"\nProcessing: {file_path.name}")
            enhanced_path = self.enhance_mapping_file(file_path)
            
            if enhanced_path:
                enhanced_files.append(enhanced_path)
            else:
                logger.error(f"Failed to enhance: {file_path.name}")
                
        logger.info(f"\nCompleted enhancement of {len(enhanced_files)}/{len(mapping_files)} files")
        return enhanced_files


def main(file_path: str = None):
    """Main function to run the mapping enhancement process."""
    logger.info("Starting Mapping Enhancement Script")
    
    enhancer = MappingEnhancer()
    
    # Validate database structure
    if not enhancer.validate_database_structure():
        logger.error("Database validation failed. Cannot proceed.")
        return
        
    if file_path:
        # Process single specified file
        file_path_obj = Path(file_path)
        if not file_path_obj.exists():
            logger.error(f"File does not exist: {file_path}")
            return
            
        logger.info(f"Processing single file: {file_path_obj.name}")
        enhanced_file = enhancer.enhance_mapping_file(file_path_obj)
        
        if enhanced_file:
            logger.info(f"\n🎉 Successfully enhanced file: {enhanced_file.name}")
        else:
            logger.warning("File enhancement failed")
    else:
        # Process all mapping files
        enhanced_files = enhancer.process_all_mappings()
        
        if enhanced_files:
            logger.info(f"\n🎉 Successfully enhanced {len(enhanced_files)} mapping files:")
            for file_path in enhanced_files:
                logger.info(f"  ✓ {file_path.name}")
        else:
            logger.warning("No files were enhanced")
        
    logger.info("Mapping enhancement process completed")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        main(sys.argv[1])
    else:
        main()