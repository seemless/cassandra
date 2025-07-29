#!/usr/bin/env python3
"""
Excel Tab to Dictionary Processor

This script reads an Excel file from the data/ directory and processes each tab,
converting each row into a dictionary where the header row provides the keys
and each data row provides the values.
"""

import pandas as pd
import os
from typing import Dict, List, Any, Optional


def process_excel_file(file_path: str) -> List[Dict[str, Any]]:
    """
    Process an Excel file and convert all tabs to a single list of dictionaries.
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        List of dictionaries representing all rows from all sheets
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    
    # Read all sheets from the Excel file
    xl = pd.ExcelFile(file_path)
    all_rows = []
    
    print(f"Processing Excel file: {file_path}")
    print(f"Found {len(xl.sheet_names)} sheets: {xl.sheet_names}")
    
    for sheet_name in xl.sheet_names:
        print(f"\nProcessing sheet: {sheet_name}")
        
        # Read the sheet
        df = pd.read_excel(xl, sheet_name=sheet_name)
        
        # Clean column names (remove newlines and extra spaces)
        df.columns = [col.replace('\n', ' ').strip() for col in df.columns]
        
        # Convert DataFrame to list of dictionaries
        # fillna('') replaces NaN values with empty strings
        sheet_data = df.fillna('').to_dict('records')
        
        # Add all rows to the combined list
        all_rows.extend(sheet_data)
        print(f"  - Processed {len(sheet_data)} rows")
    
    print(f"\nTotal rows across all sheets: {len(all_rows)}")
    return all_rows


def map_dictionaries(data: List[Dict[str, Any]], mapping: Dict[str, str]) -> List[Dict[str, Any]]:
    """
    Transform a list of dictionaries by mapping keys according to the provided mapping.
    
    This function is designed to work with database table columns from table_create_statements.py.
    The mapping dictionary keys should match the database column names, and the values should
    match the keys in the input dictionaries.
    
    Args:
        data: List of dictionaries to transform
        mapping: Dictionary mapping database column names (keys) to dictionary keys (values)
                Example: {"element_identifier": "Focal Document Element", 
                         "text": "Focal Document Element Description"}
                         
    Returns:
        List of dictionaries with keys mapped according to the mapping dictionary
        
    Example:
        Database columns from elements table: element_identifier, title, text
        Excel columns: "Focal Document Element", "Focal Document Element Description"
        
        mapping = {
            "element_identifier": "Focal Document Element",
            "text": "Focal Document Element Description"
        }
        
        Input:  [{"Focal Document Element": "AC-01", "Focal Document Element Description": "Access control policy"}]
        Output: [{"element_identifier": "AC-01", "text": "Access control policy"}]
    """
    mapped_data = []
    
    for row in data:
        mapped_row = {}
        for db_column, excel_column in mapping.items():
            # Get the value from the original dictionary, default to empty string if not found
            mapped_row[db_column] = row.get(excel_column, "")
        mapped_data.append(mapped_row)
    
    return mapped_data


def main():
    """Main function to process Excel files in the data directory."""
    data_dir = "data"
    
    if not os.path.exists(data_dir):
        print(f"Data directory '{data_dir}' not found!")
        return
    
    # Find Excel files in the data directory
    excel_files = [f for f in os.listdir(data_dir) 
                   if f.endswith(('.xlsx', '.xls'))]
    
    if not excel_files:
        print(f"No Excel files found in '{data_dir}' directory!")
        return
    
    for excel_file in excel_files:
        file_path = os.path.join(data_dir, excel_file)
        print(f"\n{'='*60}")
        print(f"Processing: {excel_file}")
        print(f"{'='*60}")
        
        try:
            # Process the Excel file
            data = process_excel_file(file_path)
            
            # Example: Print summary and sample rows
            print(f"\nSummary for {excel_file}:")
            print(f"  Total rows: {len(data)}")
            if data:
                print(f"  Columns: {list(data[0].keys())}")
                print(f"  First row sample:")
                for key, value in list(data[0].items())[:3]:  # Show first 3 fields
                    print(f"    {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
            
            # Example: Map dictionaries to database schema
            # Mapping for elements table columns
            elements_mapping = {
                "element_identifier": "Focal Document Element",
                "text": "Focal Document Element Description",
                "element_type": "Security Control Baseline"
            }
            
            mapped_data = map_dictionaries(data, elements_mapping)
            
            print(f"\nMapping example - first 3 mapped rows:")
            for row in mapped_data[:3]:
                print(f"  element_identifier: {row['element_identifier']}")
                print(f"  text: {row['text'][:50]}{'...' if len(row['text']) > 50 else ''}")
                print(f"  element_type: {row['element_type']}")
                print("  ---")
            
        except Exception as e:
            print(f"Error processing {excel_file}: {str(e)}")


if __name__ == "__main__":
    main()