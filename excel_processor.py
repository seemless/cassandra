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


def process_new_excel_files(file_path: str) -> List[Dict[str, Any]]:
    """
    Process Excel files with single-sheet format (CSF v1.1 and CSF v2.0).
    
    These files have a different structure than the SP 800-53 format:
    - Single "Relationships" sheet instead of multiple sheets
    - Missing "Security Control Baseline" column
    - Same core relationship columns
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        List of dictionaries representing all rows from the single sheet
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    
    # Read the Excel file
    xl = pd.ExcelFile(file_path)
    
    print(f"Processing Excel file: {file_path}")
    print(f"Found {len(xl.sheet_names)} sheet(s): {xl.sheet_names}")
    
    # For new format files, there should be only one sheet
    if len(xl.sheet_names) != 1:
        raise ValueError(f"Expected single sheet for new format, found {len(xl.sheet_names)} sheets")
    
    sheet_name = xl.sheet_names[0]
    print(f"\nProcessing sheet: {sheet_name}")
    
    # Read the sheet
    df = pd.read_excel(xl, sheet_name=sheet_name)
    
    # Clean column names (remove newlines and extra spaces)
    df.columns = [col.replace('\n', ' ').strip() for col in df.columns]
    
    # Convert DataFrame to list of dictionaries
    # fillna('') replaces NaN values with empty strings
    sheet_data = df.fillna('').to_dict('records')
    
    print(f"  - Processed {len(sheet_data)} rows")
    print(f"Total rows: {len(sheet_data)}")
    
    return sheet_data


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


def detect_excel_file_type(file_path: str) -> str:
    """
    Detect the Excel file type based on its structure.
    
    Args:
        file_path: Path to the Excel file
        
    Returns:
        String indicating file type: "sp800-53" or "csf"
        
    Raises:
        ValueError: If file type cannot be determined
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Excel file not found: {file_path}")
    
    try:
        xl = pd.ExcelFile(file_path)
        
        # Check number of sheets first
        num_sheets = len(xl.sheet_names)
        
        # Read first sheet to check columns
        first_sheet = xl.sheet_names[0]
        df = pd.read_excel(xl, sheet_name=first_sheet, nrows=0)  # Just read headers
        
        # Clean column names for comparison
        columns = [col.replace('\n', ' ').strip() for col in df.columns]
        
        # SP 800-53 format characteristics:
        # - Multiple sheets (typically 20)
        # - Has "Security Control Baseline" column
        if num_sheets > 1 and "Security Control Baseline" in columns:
            return "sp800-53"
        
        # CSF format characteristics:
        # - Single sheet (typically named "Relationships")
        # - No "Security Control Baseline" column
        # - Has the core relationship columns
        elif num_sheets == 1 and "Security Control Baseline" not in columns:
            # Verify it has the expected CSF columns
            expected_columns = [
                "Focal Document Element",
                "Focal Document Element Description",
                "Reference Document Element"
            ]
            if all(col in columns for col in expected_columns):
                return "csf"
        
        # If we can't determine the type, raise an error
        raise ValueError(f"Cannot determine file type for {file_path}. "
                        f"Sheets: {num_sheets}, Columns: {columns}")
        
    except Exception as e:
        raise ValueError(f"Error detecting file type for {file_path}: {str(e)}")


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
            # Detect file type and process accordingly
            file_type = detect_excel_file_type(file_path)
            print(f"Detected file type: {file_type}")
            
            if file_type == "sp800-53":
                data = process_excel_file(file_path)
                
                # Example mapping for SP 800-53 files (includes Security Control Baseline)
                elements_mapping = {
                    "element_identifier": "Focal Document Element",
                    "text": "Focal Document Element Description",
                    "element_type": "Security Control Baseline"
                }
                
            elif file_type == "csf":
                data = process_new_excel_files(file_path)
                
                # Example mapping for CSF files (no Security Control Baseline)
                elements_mapping = {
                    "element_identifier": "Focal Document Element",
                    "text": "Focal Document Element Description"
                }
            
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            # Display summary
            print(f"\nSummary for {excel_file}:")
            print(f"  File type: {file_type}")
            print(f"  Total rows: {len(data)}")
            if data:
                print(f"  Columns: {list(data[0].keys())}")
                print(f"  First row sample:")
                for key, value in list(data[0].items())[:3]:  # Show first 3 fields
                    print(f"    {key}: {str(value)[:100]}{'...' if len(str(value)) > 100 else ''}")
            
            # Example: Map dictionaries to database schema
            mapped_data = map_dictionaries(data, elements_mapping)
            
            print(f"\nMapping example - first 3 mapped rows:")
            for row in mapped_data[:3]:
                for key, value in row.items():
                    print(f"  {key}: {str(value)[:50]}{'...' if len(str(value)) > 50 else ''}")
                print("  ---")
            
        except Exception as e:
            print(f"Error processing {excel_file}: {str(e)}")


if __name__ == "__main__":
    main()