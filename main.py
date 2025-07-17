from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import sqlite3
from typing import Optional, List
import json
import jsonschema
from pathlib import Path
import pandas as pd
from pydantic import BaseModel
import io
from datetime import datetime

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Pydantic models for request/response
class RelationshipCreate(BaseModel):
    source_element_identifier: str
    source_doc_identifier: str
    dest_element_identifier: str
    dest_doc_identifier: str
    relationship_identifier: str

class ProvenanceDocumentCreate(BaseModel):
    target_doc_identifier: str
    source_doc_identifier: str

# Load CPRT schema for validation
schema_path = Path("static/cprt_schema.json")
with open(schema_path, 'r') as f:
    CPRT_SCHEMA = json.load(f)


def get_db_connection():
    conn = sqlite3.connect('graph.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/hello/{name}")
async def say_hello(name: str):
    return {"message": f"Hello {name}"}


@app.get("/getDocument")
async def get_document(document_identifier: str = Query(..., description="The document identifier to retrieve")):
    conn = get_db_connection()
    try:
        # Get the document
        doc_query = """
        SELECT doc_identifier, name, version, website 
        FROM documents 
        WHERE doc_identifier = ?
        """
        doc_result = conn.execute(doc_query, (document_identifier,)).fetchone()
        
        if not doc_result:
            raise HTTPException(status_code=404, detail="Document not found")
        
        # Get all elements for this document
        elements_query = """
        SELECT d.doc_identifier, e.element_type, e.element_identifier, e.title, e.text
        FROM elements e
        JOIN documents d ON e.document_id = d.document_id
        WHERE d.doc_identifier = ?
        """
        elements_results = conn.execute(elements_query, (document_identifier,)).fetchall()
        
        # Get all relationship types
        rel_types_query = "SELECT relationship_identifier, description FROM relationship_types"
        rel_types_results = conn.execute(rel_types_query).fetchall()
        
        # Get all relationships involving elements from this document
        relationships_query = """
        SELECT 
            se.element_identifier as source_element_identifier,
            sd.doc_identifier as source_doc_identifier,
            de.element_identifier as dest_element_identifier,
            dd.doc_identifier as dest_doc_identifier,
            pd.doc_identifier as provenance_doc_identifier,
            rt.relationship_identifier
        FROM relationships r
        JOIN elements se ON r.source_id = se.element_id
        JOIN documents sd ON se.document_id = sd.document_id
        JOIN elements de ON r.dest_id = de.element_id
        JOIN documents dd ON de.document_id = dd.document_id
        JOIN documents pd ON r.prov_doc_id = pd.document_id
        JOIN relationship_types rt ON r.relationship_type = rt.type_id
        WHERE sd.doc_identifier = ? OR dd.doc_identifier = ?
        """
        relationships_results = conn.execute(relationships_query, (document_identifier, document_identifier)).fetchall()
        
        # Format response according to CPRT schema
        response = {
            "documents": [dict(doc_result)],
            "elements": [dict(row) for row in elements_results],
            "relationship_types": [dict(row) for row in rel_types_results],
            "relationships": [dict(row) for row in relationships_results]
        }
        
        # Validate response against CPRT schema
        try:
            jsonschema.validate(response, CPRT_SCHEMA)
        except jsonschema.ValidationError as e:
            raise HTTPException(status_code=500, detail=f"Response validation failed: {e.message}")
        
        return response
        
    finally:
        conn.close()


@app.get("/")
async def home():
    return FileResponse('static/index.html')


@app.get("/documents")
async def get_documents():
    conn = get_db_connection()
    try:
        query = """
        SELECT doc_identifier, name, version, website 
        FROM documents
        WHERE type != 'mapping_document'
        ORDER BY name
        """
        results = conn.execute(query).fetchall()
        return {"documents": [dict(row) for row in results]}
    finally:
        conn.close()


@app.get("/documents/{doc_identifier}/elements")
async def get_document_elements(
    doc_identifier: str, 
    search: Optional[str] = Query(None, description="Search term for title and text fields")
):
    conn = get_db_connection()
    try:
        base_query = """
        SELECT e.element_identifier, e.element_type, e.title, e.text
        FROM elements e
        JOIN documents d ON e.document_id = d.document_id
        WHERE d.doc_identifier = ?
        """
        
        params = [doc_identifier]
        
        if search:
            base_query += " AND (e.title LIKE ? OR e.text LIKE ?)"
            search_term = f"%{search}%"
            params.extend([search_term, search_term])
            
        base_query += " ORDER BY e.element_identifier"
        
        results = conn.execute(base_query, params).fetchall()
        return {"elements": [dict(row) for row in results]}
    finally:
        conn.close()


@app.get("/documents/{doc_identifier}/id")
async def get_document_id(doc_identifier: str):
    conn = get_db_connection()
    try:
        query = "SELECT document_id FROM documents WHERE doc_identifier = ?"
        result = conn.execute(query, (doc_identifier,)).fetchone()
        
        if not result:
            raise HTTPException(status_code=404, detail="Document not found")
        
        return {"document_id": result[0]}
    finally:
        conn.close()


@app.post("/provenance-documents")
async def create_provenance_document(doc_info: ProvenanceDocumentCreate):
    conn = get_db_connection()
    try:
        # Generate unique provenance document identifier
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        prov_doc_identifier = f"MAPPING_{doc_info.target_doc_identifier}_TO_{doc_info.source_doc_identifier}_{timestamp}"
        
        # Get target and source document names for the provenance document name
        target_doc_query = "SELECT name FROM documents WHERE doc_identifier = ?"
        target_doc_result = conn.execute(target_doc_query, (doc_info.target_doc_identifier,)).fetchone()
        
        source_doc_query = "SELECT name FROM documents WHERE doc_identifier = ?"
        source_doc_result = conn.execute(source_doc_query, (doc_info.source_doc_identifier,)).fetchone()
        
        if not target_doc_result or not source_doc_result:
            raise HTTPException(status_code=400, detail="Target or source document not found")
        
        prov_doc_name = f"Mapping: {target_doc_result[0]} to {source_doc_result[0]}"
        prov_doc_website = "Generated by Document Relationship Mapper"
        
        # Insert new provenance document
        insert_query = """
        INSERT INTO documents (doc_identifier, name, version, website, type)
        VALUES (?, ?, ?, ?, ?)
        """
        conn.execute(insert_query, (
            prov_doc_identifier,
            prov_doc_name,
            "1.0",
            prov_doc_website,
            'mapping_document'
        ))
        conn.commit()
        
        return {
            "provenance_doc_identifier": prov_doc_identifier,
            "provenance_doc_name": prov_doc_name,
            "message": "Provenance document created successfully"
        }
    finally:
        conn.close()


@app.post("/relationships")
async def create_relationship(relationship: RelationshipCreate):
    conn = get_db_connection()
    try:
        # Get element IDs
        source_element_query = """
        SELECT e.element_id 
        FROM elements e 
        JOIN documents d ON e.document_id = d.document_id 
        WHERE d.doc_identifier = ? AND e.element_identifier = ?
        """
        source_result = conn.execute(source_element_query, 
                                   (relationship.source_doc_identifier, relationship.source_element_identifier)).fetchone()
        
        dest_element_query = """
        SELECT e.element_id 
        FROM elements e 
        JOIN documents d ON e.document_id = d.document_id 
        WHERE d.doc_identifier = ? AND e.element_identifier = ?
        """
        dest_result = conn.execute(dest_element_query, 
                                 (relationship.dest_doc_identifier, relationship.dest_element_identifier)).fetchone()
        
        # Get relationship type ID
        rel_type_query = "SELECT type_id FROM relationship_types WHERE relationship_identifier = ?"
        rel_type_result = conn.execute(rel_type_query, (relationship.relationship_identifier,)).fetchone()
        
        if not all([source_result, dest_result, rel_type_result]):
            raise HTTPException(status_code=400, detail="Invalid identifiers provided")
        
        return {
            "source_element_id": source_result[0],
            "dest_element_id": dest_result[0], 
            "relationship_type_id": rel_type_result[0],
            "message": "Relationship validated successfully"
        }
    finally:
        conn.close()


@app.post("/relationships/bulk")
async def create_bulk_relationships(relationships_data: dict):
    """Create multiple relationships with a single provenance document"""
    conn = get_db_connection()
    try:
        provenance_doc_id = relationships_data.get("provenance_doc_id")
        relationships = relationships_data.get("relationships", [])
        
        if not provenance_doc_id or not relationships:
            raise HTTPException(status_code=400, detail="Missing provenance document ID or relationships")
        
        success_count = 0
        
        for rel_data in relationships:
            try:
                # Insert relationship
                insert_query = """
                INSERT INTO relationships (source_id, dest_id, prov_doc_id, relationship_type)
                VALUES (?, ?, ?, ?)
                """
                conn.execute(insert_query, (
                    rel_data["source_element_id"],
                    rel_data["dest_element_id"],
                    provenance_doc_id,
                    rel_data["relationship_type_id"]
                ))
                success_count += 1
            except sqlite3.IntegrityError:
                # Skip duplicate relationships
                continue
        
        conn.commit()
        
        return {
            "message": f"{success_count} relationships created successfully",
            "success_count": success_count,
            "total_attempted": len(relationships)
        }
    finally:
        conn.close()


@app.get("/relationships/export")
async def export_relationships(
    format: str = Query("excel", regex="^(excel|csv)$"),
    provenance_docs: Optional[str] = Query(None, description="Comma-separated list of provenance document identifiers to filter by")
):
    from fastapi.responses import StreamingResponse
    conn = get_db_connection()
    try:
        base_query = """
        SELECT 
            se.element_identifier as source_element,
            sd.doc_identifier as source_document,
            se.title as source_title,
            de.element_identifier as dest_element,
            dd.doc_identifier as dest_document,
            de.title as dest_title,
            rt.relationship_identifier as relationship_type,
            pd.doc_identifier as provenance_document
        FROM relationships r
        JOIN elements se ON r.source_id = se.element_id
        JOIN documents sd ON se.document_id = sd.document_id
        JOIN elements de ON r.dest_id = de.element_id
        JOIN documents dd ON de.document_id = dd.document_id
        JOIN documents pd ON r.prov_doc_id = pd.document_id
        JOIN relationship_types rt ON r.relationship_type = rt.type_id
        """
        
        params = []
        
        # Add filtering if provenance documents are specified
        if provenance_docs:
            prov_doc_list = [doc.strip() for doc in provenance_docs.split(',') if doc.strip()]
            if prov_doc_list:
                placeholders = ','.join(['?' for _ in prov_doc_list])
                base_query += f" WHERE pd.doc_identifier IN ({placeholders})"
                params.extend(prov_doc_list)
        
        base_query += " ORDER BY sd.doc_identifier, se.element_identifier"
        
        results = conn.execute(base_query, params).fetchall()
        df = pd.DataFrame([dict(row) for row in results])
        
        if df.empty:
            raise HTTPException(status_code=404, detail="No relationships found")
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "excel":
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Relationships', index=False)
            output.seek(0)
            
            return StreamingResponse(
                io.BytesIO(output.getvalue()),
                media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                headers={"Content-Disposition": f"attachment; filename=relationships_{timestamp}.xlsx"}
            )
        else:  # CSV
            output = io.StringIO()
            df.to_csv(output, index=False)
            
            return StreamingResponse(
                io.StringIO(output.getvalue()),
                media_type='text/csv',
                headers={"Content-Disposition": f"attachment; filename=relationships_{timestamp}.csv"}
            )
    finally:
        conn.close()
