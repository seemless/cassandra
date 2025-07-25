// Document Relationship Mapper Application

class DocumentMapper {
    constructor() {
        this.documents = [];
        this.targetElements = [];
        this.sourceElements = [];
        this.currentElementIndex = 0;
        this.mappedElements = [];
        this.relationshipTypes = [];
        this.sessionProvenanceDocuments = [];
        
        this.init();
    }

    async init() {
        await this.loadDocuments();
        await this.loadRelationshipTypes();
        this.setupEventListeners();
        this.setupDragAndDrop();
        
        // Show loading state initially
        this.hideAllSections();
    }

    // API Methods
    async apiCall(url, options = {}) {
        this.showLoading();
        try {
            const response = await fetch(url, {
                headers: {
                    'Content-Type': 'application/json',
                    ...options.headers
                },
                ...options
            });
            
            if (!response.ok) {
                throw new Error(`API call failed: ${response.statusText}`);
            }
            
            return await response.json();
        } catch (error) {
            this.showToast('Error', error.message, 'error');
            throw error;
        } finally {
            this.hideLoading();
        }
    }

    async loadDocuments() {
        try {
            const data = await this.apiCall('/documents');
            this.documents = data.documents;
            this.populateDocumentSelects();
        } catch (error) {
            console.error('Failed to load documents:', error);
        }
    }

    async loadRelationshipTypes() {
        try {
            // Get relationship types from any document (they're the same across all)
            if (this.documents.length > 0) {
                const data = await this.apiCall(`/getDocument?document_identifier=${this.documents[0].doc_identifier}`);
                this.relationshipTypes = data.relationship_types;
                this.populateRelationshipTypeSelect();
            }
        } catch (error) {
            console.error('Failed to load relationship types:', error);
        }
    }

    async loadDocumentElements(docIdentifier) {
        try {
            const data = await this.apiCall(`/documents/${docIdentifier}/elements`);
            return data.elements;
        } catch (error) {
            console.error('Failed to load elements:', error);
            return [];
        }
    }

    async searchSourceElements(docIdentifier, searchTerm = '') {
        try {
            const url = searchTerm ? 
                `/documents/${docIdentifier}/elements?search=${encodeURIComponent(searchTerm)}` :
                `/documents/${docIdentifier}/elements`;
            const data = await this.apiCall(url);
            return data.elements;
        } catch (error) {
            console.error('Failed to search elements:', error);
            return [];
        }
    }

    async validateRelationship(relationship) {
        try {
            const result = await this.apiCall('/relationships', {
                method: 'POST',
                body: JSON.stringify(relationship)
            });
            return result;
        } catch (error) {
            console.error('Failed to validate relationship:', error);
            return null;
        }
    }



    // UI Population Methods
    populateDocumentSelects() {
        const targetSelect = document.getElementById('targetDocument');
        const sourceSelect = document.getElementById('sourceDocument');

        // Clear existing options
        [targetSelect, sourceSelect].forEach(select => {
            while (select.children.length > 1) {
                select.removeChild(select.lastChild);
            }
        });

        // Add document options
        this.documents.forEach(doc => {

            const option = document.createElement('option');
            option.value = doc.doc_identifier;
            option.textContent = `${doc.name} (${doc.version})`;

            targetSelect.appendChild(option.cloneNode(true));
            sourceSelect.appendChild(option.cloneNode(true));

        });
    }

    populateRelationshipTypeSelect() {
        const select = document.getElementById('relationshipTypeSelect');
        
        // Clear existing options
        while (select.children.length > 1) {
            select.removeChild(select.lastChild);
        }

        this.relationshipTypes.forEach(type => {
            const option = document.createElement('option');
            option.value = type.relationship_identifier;
            option.textContent = `${type.relationship_identifier} - ${type.description}`;
            select.appendChild(option);
        });
    }

    // Element Display Methods
    displayCurrentTargetElement() {
        const container = document.getElementById('currentTargetElement');
        
        if (this.targetElements.length === 0) {
            container.innerHTML = '<p class="text-muted">No target elements available</p>';
            return;
        }

        const element = this.targetElements[this.currentElementIndex];
        container.innerHTML = `
            <div class="target-element">
                <div class="element-id">${element.element_identifier}</div>
                <div class="element-type">${element.element_type}</div>
                <div class="element-title">${element.title}</div>
                <div class="element-text">${element.text}</div>
            </div>
        `;

        this.updateNavigationButtons();
        this.updateProgress();
    }

    displaySourceElements(elements) {
        const container = document.getElementById('sourceElements');
        
        if (elements.length === 0) {
            container.innerHTML = '<p class="text-muted">No elements found</p>';
            return;
        }

        container.innerHTML = elements.map(element => `
            <div class="source-element" draggable="true" data-element='${JSON.stringify(element)}'>
                <div class="element-type">${element.element_type}</div>
                <div class="element-id">${element.element_identifier}</div>
                <div class="element-title">${element.title}</div>
                <div class="element-text">${element.text}</div>
            </div>
        `).join('');

        // Re-attach drag event listeners
        this.attachDragListeners();
    }

    displayMappedElements() {
        const container = document.getElementById('mappingArea');
        
        if (this.mappedElements.length === 0) {
            container.innerHTML = `
                <div class="mapping-placeholder">
                    <i class="fas fa-hand-paper"></i>
                    <p>Drag source elements here to create relationships</p>
                </div>
            `;
            return;
        }

        container.innerHTML = this.mappedElements.map((element, index) => `
            <div class="mapped-element">
                <button class="remove-mapping" onclick="app.removeMappedElement(${index})">
                    <i class="fas fa-times"></i>
                </button>
                <div class="element-id">${element.element_identifier}</div>
                <div class="element-title">${element.title}</div>
                <div class="element-text">${element.text}</div>
            </div>
        `).join('');

        this.updateSaveButton();
    }

    // Navigation Methods
    updateNavigationButtons() {
        const prevBtn = document.getElementById('prevElement');
        const nextBtn = document.getElementById('nextElement');
        
        prevBtn.disabled = this.currentElementIndex === 0;
        nextBtn.disabled = this.currentElementIndex >= this.targetElements.length - 1;
    }

    updateProgress() {
        const progressText = document.getElementById('progressText');
        const progressBar = document.getElementById('progressBar');
        
        const completed = this.currentElementIndex;
        const total = this.targetElements.length;
        const percentage = total > 0 ? Math.round((completed / total) * 100) : 0;
        
        progressText.textContent = `${completed} of ${total} elements completed`;
        progressBar.style.width = `${percentage}%`;
    }

    updateSaveButton() {
        const saveBtn = document.getElementById('saveRelationships');
        saveBtn.disabled = this.mappedElements.length === 0;
    }

    // Event Handlers
    setupEventListeners() {
        // Document selection
        document.getElementById('targetDocument').addEventListener('change', async (e) => {
            if (e.target.value) {
                this.targetElements = await this.loadDocumentElements(e.target.value);
                this.currentElementIndex = 0;
                this.mappedElements = [];
                this.sessionProvenanceDocuments = []; // Reset session tracking
                this.displayCurrentTargetElement();
                this.displayMappedElements();
                this.checkIfInterfaceReady();
            }
        });

        document.getElementById('sourceDocument').addEventListener('change', async (e) => {
            if (e.target.value) {
                await this.loadAndDisplaySourceElements(e.target.value);
                this.checkIfInterfaceReady();
            }
        });

        // Search functionality
        document.getElementById('searchInput').addEventListener('input', this.debounce(async (e) => {
            const sourceDoc = document.getElementById('sourceDocument').value;
            if (sourceDoc) {
                this.sourceElements = await this.searchSourceElements(sourceDoc, e.target.value);
                this.displaySourceElements(this.sourceElements);
            }
        }, 300));

        // Navigation
        document.getElementById('prevElement').addEventListener('click', () => {
            if (this.currentElementIndex > 0) {
                this.currentElementIndex--;
                this.mappedElements = [];
                this.displayCurrentTargetElement();
                this.displayMappedElements();
            }
        });

        document.getElementById('nextElement').addEventListener('click', () => {
            if (this.currentElementIndex < this.targetElements.length - 1) {
                this.currentElementIndex++;
                this.mappedElements = [];
                this.displayCurrentTargetElement();
                this.displayMappedElements();
            }
        });

        // Mapping area actions
        document.getElementById('clearMappings').addEventListener('click', () => {
            this.mappedElements = [];
            this.displayMappedElements();
        });

        document.getElementById('saveRelationships').addEventListener('click', () => {
            this.showRelationshipModal();
        });

        // Modal actions
        document.getElementById('confirmRelationship').addEventListener('click', () => {
            this.createRelationships();
        });

        // Export actions
        document.getElementById('exportExcel').addEventListener('click', () => {
            this.exportRelationships('excel');
        });

        document.getElementById('exportCSV').addEventListener('click', () => {
            this.exportRelationships('csv');
        });
    }

    async loadAndDisplaySourceElements(docIdentifier) {
        this.sourceElements = await this.loadDocumentElements(docIdentifier);
        this.displaySourceElements(this.sourceElements);
        document.getElementById('searchInput').value = '';
    }

    checkIfInterfaceReady() {
        const targetDoc = document.getElementById('targetDocument').value;
        const sourceDoc = document.getElementById('sourceDocument').value;
        
        if (targetDoc && sourceDoc) {
            this.showMappingInterface();
        }
    }

    // Drag and Drop Setup
    setupDragAndDrop() {
        const mappingArea = document.getElementById('mappingArea');

        mappingArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            mappingArea.classList.add('drag-over');
        });

        mappingArea.addEventListener('dragleave', (e) => {
            if (!mappingArea.contains(e.relatedTarget)) {
                mappingArea.classList.remove('drag-over');
            }
        });

        mappingArea.addEventListener('drop', (e) => {
            e.preventDefault();
            mappingArea.classList.remove('drag-over');
            
            const elementData = e.dataTransfer.getData('text/plain');
            if (elementData) {
                try {
                    const element = JSON.parse(elementData);
                    this.addMappedElement(element);
                } catch (error) {
                    console.error('Error parsing dropped element:', error);
                }
            }
        });
    }

    attachDragListeners() {
        const sourceElements = document.querySelectorAll('.source-element');
        
        sourceElements.forEach(element => {
            element.addEventListener('dragstart', (e) => {
                e.dataTransfer.setData('text/plain', element.dataset.element);
                element.classList.add('dragging');
            });

            element.addEventListener('dragend', (e) => {
                element.classList.remove('dragging');
            });
        });
    }

    addMappedElement(element) {
        // Check if element is already mapped
        const isAlreadyMapped = this.mappedElements.some(mapped => 
            mapped.element_identifier === element.element_identifier
        );

        if (!isAlreadyMapped) {
            this.mappedElements.push(element);
            this.displayMappedElements();
            this.showToast('Success', 'Element added to mapping area', 'success');
        } else {
            this.showToast('Warning', 'Element is already mapped', 'warning');
        }
    }

    removeMappedElement(index) {
        this.mappedElements.splice(index, 1);
        this.displayMappedElements();
    }

    async createProvenanceDocument(targetDoc, sourceDoc) {
        try {
            const result = await this.apiCall('/provenance-documents', {
                method: 'POST',
                body: JSON.stringify({
                    target_doc_identifier: targetDoc,
                    source_doc_identifier: sourceDoc
                })
            });
            return result;
        } catch (error) {
            console.error('Failed to create provenance document:', error);
            return null;
        }
    }

    async saveBulkRelationships(provenanceDocId, relationships) {
        try {
            const result = await this.apiCall('/relationships/bulk', {
                method: 'POST',
                body: JSON.stringify({
                    provenance_doc_id: provenanceDocId,
                    relationships: relationships
                })
            });
            return result;
        } catch (error) {
            console.error('Failed to save bulk relationships:', error);
            return null;
        }
    }

    // Relationship Management
    showRelationshipModal() {
        const modal = new bootstrap.Modal(document.getElementById('relationshipModal'));
        modal.show();
    }

    async createRelationships() {
        const relationshipType = document.getElementById('relationshipTypeSelect').value;
        const targetDoc = document.getElementById('targetDocument').value;
        const sourceDoc = document.getElementById('sourceDocument').value;

        if (!relationshipType) {
            this.showToast('Error', 'Please select relationship type', 'error');
            return;
        }

        const targetElement = this.targetElements[this.currentElementIndex];
        
        // First, validate all relationships and get their IDs
        const validatedRelationships = [];
        
        for (const sourceElement of this.mappedElements) {
            const relationship = {
                source_element_identifier: targetElement.element_identifier,
                source_doc_identifier: targetDoc,
                dest_element_identifier: sourceElement.element_identifier,
                dest_doc_identifier: sourceDoc,
                relationship_identifier: relationshipType
            };

            const validated = await this.validateRelationship(relationship);
            if (validated) {
                validatedRelationships.push(validated);
            }
        }

        if (validatedRelationships.length === 0) {
            this.showToast('Error', 'No valid relationships to create', 'error');
            return;
        }

        // Create provenance document
        const provenanceDoc = await this.createProvenanceDocument(targetDoc, sourceDoc);
        if (!provenanceDoc) {
            this.showToast('Error', 'Failed to create provenance document', 'error');
            return;
        }

        // Show provenance document info in modal
        document.getElementById('provenanceDocumentInfo').style.display = 'block';
        document.getElementById('provenanceDocumentName').textContent = provenanceDoc.provenance_doc_name;

        // Get provenance document ID
        const provenanceDocIdData = await this.getDocumentId(provenanceDoc.provenance_doc_identifier);
        
        if (!provenanceDocIdData) {
            this.showToast('Error', 'Failed to retrieve provenance document ID', 'error');
            return;
        }

        // Create bulk relationships
        const result = await this.saveBulkRelationships(provenanceDocIdData.document_id, validatedRelationships);
        
        if (result && result.success_count > 0) {
            // Track the provenance document for this session
            this.sessionProvenanceDocuments.push(provenanceDoc.provenance_doc_identifier);
            
            this.showToast('Success', `${result.success_count} relationships created successfully with new provenance document`, 'success');
            this.mappedElements = [];
            this.displayMappedElements();
            
            // Move to next element if available
            if (this.currentElementIndex < this.targetElements.length - 1) {
                this.currentElementIndex++;
                this.displayCurrentTargetElement();
            }
            
            // Update export section with session info
            this.updateExportSection();
        } else {
            this.showToast('Error', 'Failed to create relationships', 'error');
        }

        // Hide modal after a short delay to show the provenance document info
        setTimeout(() => {
            bootstrap.Modal.getInstance(document.getElementById('relationshipModal')).hide();
        }, 2000);
        
        // Show export section if we have relationships
        this.showExportSection();
    }

    async getDocumentId(docIdentifier) {
        try {
            const data = await this.apiCall(`/documents/${docIdentifier}/id`);
            return data;
        } catch (error) {
            console.error('Failed to get document ID:', error);
            return null;
        }
    }

    // Export functionality
    async exportRelationships(format) {
        try {
            this.showLoading();
            
            // Build URL with session provenance documents filter
            let url = `/relationships/export?format=${format}`;
            if (this.sessionProvenanceDocuments.length > 0) {
                const provenanceDocs = this.sessionProvenanceDocuments.join(',');
                url += `&provenance_docs=${encodeURIComponent(provenanceDocs)}`;
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error('Export failed');
            }

            const blob = await response.blob();
            const downloadUrl = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = downloadUrl;
            a.download = response.headers.get('Content-Disposition')?.split('filename=')[1] || `relationships.${format === 'excel' ? 'xlsx' : 'csv'}`;
            document.body.appendChild(a);
            a.click();
            window.URL.revokeObjectURL(downloadUrl);
            document.body.removeChild(a);
            
            const exportType = this.sessionProvenanceDocuments.length > 0 ? 'session' : 'all';
            this.showToast('Success', `${exportType} relationships exported to ${format.toUpperCase()}`, 'success');
        } catch (error) {
            this.showToast('Error', 'Failed to export relationships', 'error');
        } finally {
            this.hideLoading();
        }
    }

    // UI State Management
    hideAllSections() {
        document.getElementById('progressSection').style.display = 'none';
        document.getElementById('mappingInterface').style.display = 'none';
        document.getElementById('exportSection').style.display = 'none';
    }

    showMappingInterface() {
        document.getElementById('progressSection').style.display = 'block';
        document.getElementById('mappingInterface').style.display = 'flex';
    }

    showExportSection() {
        document.getElementById('exportSection').style.display = 'block';
        this.updateExportSection();
    }

    updateExportSection() {
        // Update export section with session information
        const exportSection = document.getElementById('exportSection');
        if (exportSection && this.sessionProvenanceDocuments.length > 0) {
            // Find or create session info element
            let sessionInfo = document.getElementById('sessionExportInfo');
            if (!sessionInfo) {
                sessionInfo = document.createElement('div');
                sessionInfo.id = 'sessionExportInfo';
                sessionInfo.className = 'alert alert-info mt-2';
                exportSection.querySelector('.card-body').appendChild(sessionInfo);
            }
            
            const sessionCount = this.sessionProvenanceDocuments.length;
            sessionInfo.innerHTML = `
                <i class="fas fa-info-circle"></i>
                <strong>Session Export:</strong> Export will include relationships from ${sessionCount} 
                provenance document${sessionCount > 1 ? 's' : ''} created in this mapping session.
            `;
        }
    }

    showLoading() {
        document.getElementById('loadingSpinner').style.display = 'flex';
    }

    hideLoading() {
        document.getElementById('loadingSpinner').style.display = 'none';
    }

    showToast(title, message, type = 'info') {
        const toast = document.getElementById('notificationToast');
        const toastTitle = document.getElementById('toastTitle');
        const toastMessage = document.getElementById('toastMessage');
        const toastIcon = document.getElementById('toastIcon');

        toastTitle.textContent = title;
        toastMessage.textContent = message;

        // Set icon and color based on type
        const iconMap = {
            success: 'fas fa-check-circle text-success',
            error: 'fas fa-exclamation-circle text-danger',
            warning: 'fas fa-exclamation-triangle text-warning',
            info: 'fas fa-info-circle text-info'
        };

        toastIcon.className = iconMap[type] || iconMap.info;

        const bsToast = new bootstrap.Toast(toast);
        bsToast.show();
    }

    // Utility Methods
    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
}

// Initialize application when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.app = new DocumentMapper();
});