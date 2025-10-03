#!/usr/bin/env python3
"""
CPRT Database Insertion Script

This script reads CPRT-formatted Excel files from data/cprt_spreadsheets/ 
and inserts the data into the graph.db SQLite database. The script handles
the proper insertion order and foreign key relationships.
"""

import os
import sqlite3
import pandas as pd
from typing import Dict, List, Any, Optional
from pathlib import Path
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('insert_cprt_data.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def get_db_connection():
    """Get SQLite database connection."""
    conn = sqlite3.connect('graph.db')
    conn.row_factory = sqlite3.Row
    return conn


def create_tables_if_not_exist(conn: sqlite3.Connection):
    """Create database tables if they don't exist."""
    from table_create_statements import create_statements_map
    
    for table_name, create_statement in create_statements_map.items():
        try:
            conn.execute(create_statement)
            logger.info(f"Table '{table_name}' ready")
        except sqlite3.OperationalError as e:
            if "already exists" in str(e):
                logger.info(f"Table '{table_name}' already exists")
            else:
                logger.error(f"Error creating table '{table_name}': {e}")
                raise


def process_cprt_file(file_path: str) -> Dict[str, List[Dict[str, Any]]]:
    """
    Process a CPRT-formatted Excel file and return structured data.
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        Dictionary with keys: documents, elements, relationship_types, relationships
    """
    logger.info(f"Processing CPRT file: {file_path}")
    
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CPRT file not found: {file_path}")
    
    xl = pd.ExcelFile(file_path)
    result = {
        'documents': [],
        'elements': [],
        'relationship_types': [],
        'relationships': []
    }
    
    # Process each sheet type
    for sheet_name in xl.sheet_names:
        if sheet_name in result:
            df = pd.read_excel(xl, sheet_name=sheet_name)
            if not df.empty:
                # Clean column names and convert to records
                df.columns = [col.replace('\n', ' ').strip() for col in df.columns]
                sheet_data = df.fillna('').to_dict('records')
                result[sheet_name] = sheet_data
                logger.info(f"  Sheet '{sheet_name}': {len(sheet_data)} records")
            else:
                logger.info(f"  Sheet '{sheet_name}': empty")
        else:
            logger.info(f"  Sheet '{sheet_name}': not a standard CPRT sheet, skipping")
    
    return result


def insert_documents(conn: sqlite3.Connection, documents: List[Dict[str, Any]]) -> int:
    """
    Insert documents into the database.
    
    Args:
        conn: Database connection
        documents: List of document records
        
    Returns:
        Number of documents inserted
    """
    if not documents:
        logger.info("No documents to insert")
        return 0
        
    insert_count = 0
    insert_query = """
        INSERT OR IGNORE INTO documents (doc_identifier, name, version, website, type)
        VALUES (?, ?, ?, ?, ?)
    """
    
    for doc in documents:
        try:
            # Map CPRT schema to database schema
            name = doc.get('title', doc.get('name', ''))
            doc_identifier = doc.get('document_identifier', '')
            version = doc.get('version', '1.0')
            website = doc.get('website', '')
            doc_type = doc.get('type', 'unknown')
            
            conn.execute(insert_query, (doc_identifier, name, version, website, doc_type))
            insert_count += 1
            logger.debug(f"Inserted document: {doc_identifier}")
            
        except sqlite3.Error as e:
            logger.error(f"Error inserting document {doc.get('document_identifier', 'unknown')}: {e}")
    
    logger.info(f"Inserted {insert_count} documents")
    return insert_count


def insert_elements(conn: sqlite3.Connection, elements: List[Dict[str, Any]]) -> int:
    """
    Insert elements into the database.
    
    Args:
        conn: Database connection  
        elements: List of element records
        
    Returns:
        Number of elements inserted
    """
    if not elements:
        logger.info("No elements to insert")
        return 0
        
    insert_count = 0
    
    # First get document IDs mapping
    doc_query = "SELECT document_id, doc_identifier FROM documents"
    doc_results = conn.execute(doc_query).fetchall()
    doc_id_map = {row['doc_identifier']: row['document_id'] for row in doc_results}
    
    insert_query = """
        INSERT OR IGNORE INTO elements (document_id, element_type, element_identifier, title, text)
        VALUES (?, ?, ?, ?, ?)
    """
    
    for element in elements:
        try:
            doc_identifier = element.get('document_identifier', '')
            document_id = doc_id_map.get(doc_identifier)
            
            if not document_id:
                logger.warning(f"Document not found for element: {element.get('element_identifier', 'unknown')} (doc: {doc_identifier})")
                continue
                
            element_type = element.get('type', element.get('element_type', 'unknown'))
            element_identifier = element.get('element_identifier', '')
            title = element.get('title', 'N/A') or 'N/A'  # Handle None/empty values
            text = element.get('text', '')
            
            conn.execute(insert_query, (document_id, element_type, element_identifier, title, text))
            insert_count += 1
            logger.debug(f"Inserted element: {element_identifier}")
            
        except sqlite3.Error as e:
            logger.error(f"Error inserting element {element.get('element_identifier', 'unknown')}: {e}")
    
    logger.info(f"Inserted {insert_count} elements")
    return insert_count


def insert_relationship_types(conn: sqlite3.Connection, relationship_types: List[Dict[str, Any]]) -> int:
    """
    Insert relationship types into the database.
    
    Args:
        conn: Database connection
        relationship_types: List of relationship type records
        
    Returns:
        Number of relationship types inserted
    """
    if not relationship_types:
        logger.info("No relationship types to insert")
        return 0
        
    insert_count = 0
    insert_query = """
        INSERT OR IGNORE INTO relationship_types (relationship_identifier, description, value)
        VALUES (?, ?, ?)
    """
    
    for rel_type in relationship_types:
        try:
            relationship_identifier = rel_type.get('relationship_identifier', '')
            description = rel_type.get('description', '')
            value = rel_type.get('value', '')
            
            conn.execute(insert_query, (relationship_identifier, description, value))
            insert_count += 1
            logger.debug(f"Inserted relationship type: {relationship_identifier}")
            
        except sqlite3.Error as e:
            logger.error(f"Error inserting relationship type {rel_type.get('relationship_identifier', 'unknown')}: {e}")
    
    logger.info(f"Inserted {insert_count} relationship types")
    return insert_count


def insert_relationships(conn: sqlite3.Connection, relationships: List[Dict[str, Any]]) -> int:
    """
    Insert relationships into the database.
    
    Args:
        conn: Database connection
        relationships: List of relationship records
        
    Returns:
        Number of relationships inserted
    """
    if not relationships:
        logger.info("No relationships to insert")
        return 0
        
    insert_count = 0
    
    # Get element IDs mapping
    element_query = """
        SELECT e.element_id, e.element_identifier, d.doc_identifier 
        FROM elements e 
        JOIN documents d ON e.document_id = d.document_id
    """
    element_results = conn.execute(element_query).fetchall()
    element_id_map = {}
    for row in element_results:
        key = (row['doc_identifier'], row['element_identifier'])
        element_id_map[key] = row['element_id']
    
    # Get document IDs mapping
    doc_query = "SELECT document_id, doc_identifier FROM documents"
    doc_results = conn.execute(doc_query).fetchall()
    doc_id_map = {row['doc_identifier']: row['document_id'] for row in doc_results}
    
    # Get relationship type IDs mapping
    rel_type_query = "SELECT type_id, relationship_identifier FROM relationship_types"
    rel_type_results = conn.execute(rel_type_query).fetchall()
    rel_type_id_map = {row['relationship_identifier']: row['type_id'] for row in rel_type_results}
    
    insert_query = """
        INSERT OR IGNORE INTO relationships (source_id, dest_id, prov_doc_id, relationship_type, comment)
        VALUES (?, ?, ?, ?, ?)
    """
    
    for relationship in relationships:
        try:
            source_doc_id = relationship.get('source_doc_identifier', '')
            source_element_id = relationship.get('source_element_identifier', '')
            dest_doc_id = relationship.get('dest_doc_identifier', '')  
            dest_element_id = relationship.get('dest_element_identifier', '')
            prov_doc_id = relationship.get('provenance_doc_identifier', '')
            rel_type = relationship.get('relationship_identifier', '')
            comment = relationship.get('comment', '')
            
            # Look up IDs
            source_id = element_id_map.get((source_doc_id, source_element_id))
            dest_id = element_id_map.get((dest_doc_id, dest_element_id))
            prov_id = doc_id_map.get(prov_doc_id)
            rel_type_id = rel_type_id_map.get(rel_type)
            
            if not all([source_id, dest_id, prov_id, rel_type_id]):
                missing = []
                if not source_id: missing.append(f"source ({source_doc_id}, {source_element_id})")
                if not dest_id: missing.append(f"dest ({dest_doc_id}, {dest_element_id})")
                if not prov_id: missing.append(f"provenance doc ({prov_doc_id})")
                if not rel_type_id: missing.append(f"relationship type ({rel_type})")
                logger.warning(f"Skipping relationship due to missing: {', '.join(missing)}")
                continue
            
            conn.execute(insert_query, (source_id, dest_id, prov_id, rel_type_id, comment))
            insert_count += 1
            logger.debug(f"Inserted relationship: {source_element_id} -> {dest_element_id}")
            
        except sqlite3.Error as e:
            logger.error(f"Error inserting relationship: {e}")
    
    logger.info(f"Inserted {insert_count} relationships")
    return insert_count


def main():
    """Main function to process CPRT spreadsheets and insert data into database."""
    logger.info("Starting CPRT data insertion process")
    
    # Find CPRT spreadsheets
    cprt_dir = Path("data/cprt_spreadsheets")
    if not cprt_dir.exists():
        logger.error(f"CPRT directory not found: {cprt_dir}")
        return
    
    excel_files = list(cprt_dir.glob("*.xlsx"))
    if not excel_files:
        logger.error(f"No Excel files found in {cprt_dir}")
        return
    
    logger.info(f"Found {len(excel_files)} CPRT files to process")
    
    # Connect to database
    conn = get_db_connection()
    
    try:
        # Ensure tables exist
        create_tables_if_not_exist(conn)
        
        total_stats = {
            'documents': 0,
            'elements': 0, 
            'relationship_types': 0,
            'relationships': 0
        }
        
        # Process each file
        for file_path in excel_files:
            logger.info(f"\n{'='*60}")
            logger.info(f"Processing: {file_path.name}")
            logger.info(f"{'='*60}")
            
            try:
                # Start transaction for this file
                conn.execute("BEGIN TRANSACTION")
                
                # Process the file
                cprt_data = process_cprt_file(str(file_path))
                
                # Insert data in proper order (documents first, relationships last)
                doc_count = insert_documents(conn, cprt_data['documents'])
                elem_count = insert_elements(conn, cprt_data['elements'])
                rel_type_count = insert_relationship_types(conn, cprt_data['relationship_types'])
                rel_count = insert_relationships(conn, cprt_data['relationships'])
                
                # Commit transaction
                conn.commit()
                
                # Update totals
                total_stats['documents'] += doc_count
                total_stats['elements'] += elem_count
                total_stats['relationship_types'] += rel_type_count
                total_stats['relationships'] += rel_count
                
                logger.info(f"Successfully processed {file_path.name}")
                
            except Exception as e:
                logger.error(f"Error processing {file_path.name}: {e}")
                conn.rollback()
                continue
        
        # Print summary
        logger.info(f"\n{'='*60}")
        logger.info("INSERTION SUMMARY")
        logger.info(f"{'='*60}")
        for table, count in total_stats.items():
            logger.info(f"{table.upper()}: {count} records inserted")
        
        logger.info("CPRT data insertion completed successfully!")
        
    except Exception as e:
        logger.error(f"Fatal error during processing: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()