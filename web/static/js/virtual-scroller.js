/**
 * Virtual Scrolling implementation for large table datasets
 * Only renders visible rows + buffer for smooth scrolling
 */

class VirtualScroller {
    constructor(container, options = {}) {
        this.container = container;
        this.tableBody = container.querySelector('tbody');
        this.data = [];

        // Configuration
        this.rowHeight = options.rowHeight || 40; // px per row
        this.buffer = options.buffer || 10; // extra rows to render above/below viewport
        this.columnCount = options.columnCount || 1;
        this.renderRow = options.renderRow || this.defaultRenderRow.bind(this);

        // State
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.visibleStart = 0;
        this.visibleEnd = 0;

        // Create virtual scrolling structure
        this.setupVirtualScroll();

        // Bind scroll handler
        this.handleScroll = this.handleScroll.bind(this);
        this.container.addEventListener('scroll', this.handleScroll, { passive: true });

        // Observe container size changes
        this.resizeObserver = new ResizeObserver(() => this.updateViewport());
        this.resizeObserver.observe(this.container);
    }

    setupVirtualScroll() {
        // Get column count from table header
        const table = this.tableBody.parentElement;
        const headerRow = table.querySelector('thead tr');
        const columnCount = headerRow ? headerRow.children.length : 1;

        // Create spacer rows for virtual scrolling (top and bottom padding)
        this.topSpacer = document.createElement('tr');
        const topCell = document.createElement('td');
        topCell.colSpan = columnCount;
        topCell.style.height = '0px';
        topCell.style.padding = '0';
        topCell.style.border = 'none';
        topCell.style.pointerEvents = 'none';
        this.topSpacer.appendChild(topCell);

        this.bottomSpacer = document.createElement('tr');
        const bottomCell = document.createElement('td');
        bottomCell.colSpan = columnCount;
        bottomCell.style.height = '0px';
        bottomCell.style.padding = '0';
        bottomCell.style.border = 'none';
        bottomCell.style.pointerEvents = 'none';
        this.bottomSpacer.appendChild(bottomCell);

        // Insert spacers at top and bottom of tbody
        this.tableBody.insertBefore(this.topSpacer, this.tableBody.firstChild);
        this.tableBody.appendChild(this.bottomSpacer);

        // Ensure container can scroll
        this.container.style.overflowY = 'auto';
        this.container.style.position = 'relative';

        console.log('VirtualScroller initialized with', columnCount, 'columns');
    }

    setData(data) {
        this.data = data;
        this.updateScrollHeight();
        this.render();
    }

    appendData(newData) {
        this.data.push(...newData);
        this.updateScrollHeight();
        this.render();
    }

    updateScrollHeight() {
        // Total height is set via spacer rows, not needed here
        // The spacers will be adjusted during render
    }

    updateViewport() {
        this.containerHeight = this.container.clientHeight;
        this.render();
    }

    handleScroll() {
        this.scrollTop = this.container.scrollTop;
        this.render();
    }

    getVisibleRange() {
        const start = Math.floor(this.scrollTop / this.rowHeight);
        const visibleCount = Math.ceil(this.containerHeight / this.rowHeight);

        // Add buffer
        const bufferedStart = Math.max(0, start - this.buffer);
        const bufferedEnd = Math.min(this.data.length, start + visibleCount + this.buffer);

        return { start: bufferedStart, end: bufferedEnd };
    }

    render() {
        if (!this.data.length) {
            // Clear all rows except spacers
            const existingRows = Array.from(this.tableBody.children).filter(
                child => child !== this.topSpacer && child !== this.bottomSpacer
            );
            existingRows.forEach(row => row.remove());

            if (this.topSpacer && this.topSpacer.firstChild) {
                this.topSpacer.firstChild.style.height = '0px';
            }
            if (this.bottomSpacer && this.bottomSpacer.firstChild) {
                this.bottomSpacer.firstChild.style.height = '0px';
            }
            return;
        }

        const { start, end } = this.getVisibleRange();

        // Only re-render if range changed significantly
        if (start === this.visibleStart && end === this.visibleEnd) {
            return;
        }

        this.visibleStart = start;
        this.visibleEnd = end;

        // Calculate spacer heights
        const topHeight = start * this.rowHeight;
        const bottomHeight = (this.data.length - end) * this.rowHeight;

        // Update spacers (set height on the TD cells)
        this.topSpacer.firstChild.style.height = topHeight + 'px';
        this.bottomSpacer.firstChild.style.height = bottomHeight + 'px';

        // Remove existing data rows (keep spacers)
        const existingRows = Array.from(this.tableBody.children).filter(
            child => child !== this.topSpacer && child !== this.bottomSpacer
        );
        existingRows.forEach(row => row.remove());

        // Create and insert new rows
        const fragment = document.createDocumentFragment();
        for (let i = start; i < end; i++) {
            const row = this.createRow(this.data[i], i);
            fragment.appendChild(row);
        }

        // Insert rows between spacers
        this.tableBody.insertBefore(fragment, this.bottomSpacer);
    }

    createRow(rowData, index) {
        const row = document.createElement('tr');
        row.dataset.index = index;

        // Use custom render function
        this.renderRow(row, rowData, index);

        return row;
    }

    defaultRenderRow(row, rowData, index) {
        // Default: assume rowData is array of cell values
        if (Array.isArray(rowData)) {
            rowData.forEach(cellData => {
                const cell = document.createElement('td');
                if (typeof cellData === 'string' && cellData.includes('<button')) {
                    cell.innerHTML = cellData;
                } else {
                    cell.textContent = cellData;
                }
                row.appendChild(cell);
            });
        } else {
            // Single cell with stringified data
            const cell = document.createElement('td');
            cell.textContent = JSON.stringify(rowData);
            row.appendChild(cell);
        }
    }

    clear() {
        this.data = [];
        this.visibleStart = 0;
        this.visibleEnd = 0;

        // Remove all rows except spacers
        const existingRows = Array.from(this.tableBody.children).filter(
            child => child !== this.topSpacer && child !== this.bottomSpacer
        );
        existingRows.forEach(row => row.remove());

        // Reset spacer heights
        if (this.topSpacer && this.topSpacer.firstChild) {
            this.topSpacer.firstChild.style.height = '0px';
        }
        if (this.bottomSpacer && this.bottomSpacer.firstChild) {
            this.bottomSpacer.firstChild.style.height = '0px';
        }

        console.log('Virtual scroller cleared');
    }

    destroy() {
        this.container.removeEventListener('scroll', this.handleScroll);
        this.resizeObserver.disconnect();
    }
}

// Export for use in app.js
window.VirtualScroller = VirtualScroller;
