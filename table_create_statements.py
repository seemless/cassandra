create_statements_map = {"documents": '''
                        CREATE TABLE documents (
                            document_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            doc_identifier VARCHAR(20),
                            name VARCHAR(255),
                            version VARCHAR(10),
                            version_minor VARCHAR(10),
                            website VARCHAR(255),
                            type VARCHAR(255),
                            UNIQUE(doc_identifier)
                        );
                            ''',
                         "elements": '''
                        CREATE TABLE elements (
                            element_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            document_id INTEGER,
                            element_type VARCHAR(255),
                            element_identifier VARCHAR(255),
                            title VARCHAR(255),
                            text VARCHAR(255),
                            UNIQUE(document_id,element_identifier,title,text),
                            FOREIGN KEY (document_id)
                                REFERENCES documents(document_id)
                                ON DELETE CASCADE
                        );
                            ''',
                         "relationship_types": '''
                        CREATE TABLE relationship_types (
                            type_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            relationship_identifier VARCHAR(40),
                            description VARCHAR(255),
                            value VARCHAR(255),
                            UNIQUE(relationship_identifier)
                        );
                            ''',
                         "relationships": '''
                        CREATE TABLE relationships (
                            source_id INTEGER,
                            dest_id INTEGER,
                            prov_doc_id INTEGER,
                            relationship_type INTEGER,
                            comment VARCHAR(255),
                            UNIQUE(source_id, dest_id, prov_doc_id, relationship_type),
                            FOREIGN KEY (source_id)
                                REFERENCES elements(element_id)
                                ON DELETE CASCADE,
                            FOREIGN KEY (dest_id)
                                REFERENCES elements(element_id)
                                ON DELETE CASCADE,
                            FOREIGN KEY (prov_doc_id)
                                REFERENCES documents(document_id)
                                ON DELETE CASCADE,
                            FOREIGN KEY (relationship_type)
                                REFERENCES relationship_types(type_id)
                                ON DELETE CASCADE
                        );
                            '''
                         }
