/**
 * Virtual Scrolling Implementation for LibreCrawl
 * Handles infinite scroll with lazy loading for massive datasets (1M+ rows)
 */

class VirtualScrollTable {
    constructor(tableId, options = {}) {
        this.tableId = tableId;
        this.tableBody = document.getElementById(tableId + 'Body');
        this.table = document.getElementById(tableId);

        // Configuration
        this.rowHeight = options.rowHeight || 50;
        this.bufferSize = options.bufferSize || 20; // Extra rows to render for smooth scrolling
        this.batchSize = options.batchSize || 100; // Rows to fetch per API call
        this.apiEndpoint = options.apiEndpoint;
        this.sessionId = options.sessionId;
        this.filters = options.filters || {};
        this.renderRow = options.renderRow; // Function to render a row

        // State
        this.totalRows = 0;
        this.loadedData = new Map(); // Map of offset -> data array
        this.visibleStart = 0;
        this.visibleEnd = 0;
        this.isLoading = false;
        this.loadingCache = new Set(); // Track which batches are loading

        // Create scroll container
        this.setupScrollContainer();
        this.attachScrollListener();
    }

    setupScrollContainer() {
        // Get the table container
        this.scrollContainer = this.table.closest('.table-container');
        if (!this.scrollContainer) {
            console.error('Table container not found');
            return;
        }

        // Create spacer elements for virtual scrolling
        this.topSpacer = document.createElement('tr');
        this.topSpacer.style.height = '0px';
        this.bottomSpacer = document.createElement('tr');
        this.bottomSpacer.style.height = '0px';

        this.tableBody.prepend(this.topSpacer);
        this.tableBody.append(this.bottomSpacer);
    }

    attachScrollListener() {
        if (!this.scrollContainer) return;

        this.scrollContainer.addEventListener('scroll', () => {
            this.handleScroll();
        });
    }

    async initialize() {
        // Load first batch
        await this.loadBatch(0);
        this.render();
    }

    async loadBatch(offset) {
        // Check if already loading this batch
        if (this.loadingCache.has(offset)) {
            return;
        }

        this.loadingCache.add(offset);
        this.isLoading = true;

        try {
            const params = new URLSearchParams({
                session_id: this.sessionId,
                offset: offset,
                limit: this.batchSize,
                ...this.filters
            });

            const response = await fetch(`${this.apiEndpoint}?${params}`);
            const data = await response.json();

            if (data.success) {
                this.loadedData.set(offset, data.urls || data.links || data.issues || []);

                // Update total on first load
                if (data.total !== undefined) {
                    this.totalRows = data.total;
                    this.updateSpacers();
                }

                return data;
            }
        } catch (error) {
            console.error('Error loading batch:', error);
        } finally {
            this.isLoading = false;
            this.loadingCache.delete(offset);
        }
    }

    handleScroll() {
        const scrollTop = this.scrollContainer.scrollTop;
        const containerHeight = this.scrollContainer.clientHeight;

        // Calculate visible range
        const startRow = Math.floor(scrollTop / this.rowHeight);
        const endRow = Math.ceil((scrollTop + containerHeight) / this.rowHeight);

        // Add buffer
        this.visibleStart = Math.max(0, startRow - this.bufferSize);
        this.visibleEnd = Math.min(this.totalRows, endRow + this.bufferSize);

        // Check if we need to load more data
        this.checkAndLoadBatches();

        // Render visible rows
        this.render();
    }

    checkAndLoadBatches() {
        const startBatch = Math.floor(this.visibleStart / this.batchSize) * this.batchSize;
        const endBatch = Math.floor(this.visibleEnd / this.batchSize) * this.batchSize;

        // Load batches that cover the visible range
        for (let offset = startBatch; offset <= endBatch; offset += this.batchSize) {
            if (!this.loadedData.has(offset) && !this.loadingCache.has(offset)) {
                this.loadBatch(offset);
            }
        }
    }

    render() {
        // Clear current rows (except spacers)
        while (this.tableBody.children.length > 2) {
            if (this.tableBody.children[1] !== this.bottomSpacer) {
                this.tableBody.removeChild(this.tableBody.children[1]);
            } else {
                break;
            }
        }

        // Render visible rows
        const fragment = document.createDocumentFragment();

        for (let i = this.visibleStart; i < this.visibleEnd; i++) {
            const batchOffset = Math.floor(i / this.batchSize) * this.batchSize;
            const batch = this.loadedData.get(batchOffset);

            if (batch) {
                const indexInBatch = i - batchOffset;
                if (indexInBatch < batch.length) {
                    const rowData = batch[indexInBatch];
                    const row = this.renderRow(rowData);
                    fragment.appendChild(row);
                }
            }
        }

        // Insert rendered rows
        this.tableBody.insertBefore(fragment, this.bottomSpacer);

        // Update spacers
        this.updateSpacers();
    }

    updateSpacers() {
        const topHeight = this.visibleStart * this.rowHeight;
        const bottomHeight = Math.max(0, (this.totalRows - this.visibleEnd) * this.rowHeight);

        this.topSpacer.style.height = `${topHeight}px`;
        this.bottomSpacer.style.height = `${bottomHeight}px`;
    }

    updateFilters(newFilters) {
        this.filters = newFilters;
        this.reset();
        this.initialize();
    }

    reset() {
        this.loadedData.clear();
        this.loadingCache.clear();
        this.visibleStart = 0;
        this.visibleEnd = 0;
        this.totalRows = 0;
        this.scrollContainer.scrollTop = 0;
    }

    destroy() {
        // Clean up
        this.loadedData.clear();
        this.loadingCache.clear();
    }
}

// Helper functions for rendering rows

function renderOverviewRow(urlData) {
    const row = document.createElement('tr');

    const analyticsInfo = formatAnalyticsInfo(urlData.analytics || {});
    const ogTagsCount = Object.keys(urlData.og_tags || {}).length;
    const jsonLdCount = (urlData.json_ld || []).length;
    const linksInfo = `${urlData.internal_links || 0}/${urlData.external_links || 0}`;
    const imagesCount = (urlData.images || []).length;
    const jsRendered = urlData.javascript_rendered ? '✅ JS' : '';

    row.innerHTML = `
        <td title="${urlData.url}">${urlData.url}</td>
        <td>${urlData.status_code}</td>
        <td title="${urlData.title || ''}">${urlData.title || ''}</td>
        <td title="${urlData.meta_description || ''}">${(urlData.meta_description || '').substring(0, 50)}${urlData.meta_description && urlData.meta_description.length > 50 ? '...' : ''}</td>
        <td>${urlData.h1 || ''}</td>
        <td>${urlData.word_count || 0}</td>
        <td>${urlData.response_time || 0}</td>
        <td>${analyticsInfo}</td>
        <td>${ogTagsCount > 0 ? `${ogTagsCount} tags` : ''}</td>
        <td>${jsonLdCount > 0 ? `${jsonLdCount} scripts` : ''}</td>
        <td>${linksInfo}</td>
        <td>${imagesCount > 0 ? `${imagesCount} images` : ''}</td>
        <td>${jsRendered}</td>
        <td><button class="details-btn" onclick="showUrlDetails('${urlData.url}')">📊 Details</button></td>
    `;

    return row;
}

function renderInternalRow(urlData) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td title="${urlData.url}">${urlData.url}</td>
        <td>${urlData.status_code}</td>
        <td>${urlData.content_type || ''}</td>
        <td>${urlData.size || 0}</td>
        <td title="${urlData.title || ''}">${urlData.title || ''}</td>
    `;
    return row;
}

function renderExternalRow(urlData) {
    const row = document.createElement('tr');
    row.innerHTML = `
        <td title="${urlData.url}">${urlData.url}</td>
        <td>${urlData.status_code}</td>
        <td>${urlData.content_type || ''}</td>
        <td>${urlData.size || 0}</td>
        <td title="${urlData.title || ''}">${urlData.title || ''}</td>
    `;
    return row;
}

function renderInternalLinkRow(linkData) {
    const row = document.createElement('tr');
    const status = linkData.target_status || 'Not crawled';
    const placement = linkData.placement || 'body';

    row.innerHTML = `
        <td title="${linkData.source_url}">${linkData.source_url}</td>
        <td title="${linkData.target_url}">${linkData.target_url}</td>
        <td title="${linkData.anchor_text}">${linkData.anchor_text}</td>
        <td>${status}</td>
        <td>${placement}</td>
    `;
    return row;
}

function renderExternalLinkRow(linkData) {
    const row = document.createElement('tr');
    const placement = linkData.placement || 'body';

    row.innerHTML = `
        <td title="${linkData.source_url}">${linkData.source_url}</td>
        <td title="${linkData.target_url}">${linkData.target_url}</td>
        <td title="${linkData.anchor_text}">${linkData.anchor_text}</td>
        <td>${linkData.target_domain}</td>
        <td>${placement}</td>
    `;
    return row;
}

function renderIssueRow(issueData) {
    const row = document.createElement('tr');
    row.setAttribute('data-issue-type', issueData.type);

    // Set row style based on issue type
    if (issueData.type === 'error') {
        row.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
    } else if (issueData.type === 'warning') {
        row.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
    } else {
        row.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
    }

    // Create type indicator
    let typeIcon = '';
    let typeColor = '';
    if (issueData.type === 'error') {
        typeIcon = '❌';
        typeColor = '#ef4444';
    } else if (issueData.type === 'warning') {
        typeIcon = '⚠️';
        typeColor = '#f59e0b';
    } else {
        typeIcon = 'ℹ️';
        typeColor = '#3b82f6';
    }

    row.innerHTML = `
        <td style="word-break: break-all;" title="${issueData.url}">${issueData.url}</td>
        <td><span style="color: ${typeColor};">${typeIcon}</span> ${issueData.type}</td>
        <td>${issueData.category}</td>
        <td>${issueData.issue}</td>
        <td style="word-break: break-word;" title="${issueData.details}">${issueData.details}</td>
    `;

    return row;
}

// Export for use in other modules
window.VirtualScrollTable = VirtualScrollTable;
window.renderOverviewRow = renderOverviewRow;
window.renderInternalRow = renderInternalRow;
window.renderExternalRow = renderExternalRow;
window.renderInternalLinkRow = renderInternalLinkRow;
window.renderExternalLinkRow = renderExternalLinkRow;
window.renderIssueRow = renderIssueRow;
