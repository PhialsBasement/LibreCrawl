/**
 * Virtual Scrolling implementation for large table datasets
 * Only renders visible rows + buffer for smooth scrolling
 *
 * The row height passed in options is only an initial estimate: rows with
 * wrapping text render taller or shorter, so after each render the scroller
 * measures what actually got painted and adapts its estimate. That keeps
 * the spacer math (and therefore the scrollbar) from drifting away from
 * reality on long lists.
 */

class VirtualScroller {
    constructor(container, options = {}) {
        this.container = container;
        this.tableBody = container.querySelector('tbody');
        this.data = [];

        // Configuration
        this.rowHeight = options.rowHeight || 40; // px per row (adaptive estimate)
        this.buffer = options.buffer || 10; // extra rows to render above/below viewport
        this.renderRow = options.renderRow || this.defaultRenderRow.bind(this);

        // State
        this.scrollTop = 0;
        this.containerHeight = 0;
        this.visibleStart = -1;
        this.visibleEnd = -1;
        this.renderedLength = -1;
        this.rafPending = false;

        // Create virtual scrolling structure
        this.setupVirtualScroll();

        // Bind scroll handler (rAF-throttled so fast scrolling doesn't
        // rebuild the DOM more than once per frame)
        this.handleScroll = this.handleScroll.bind(this);
        this.container.addEventListener('scroll', this.handleScroll, { passive: true });

        // Observe container size changes
        this.resizeObserver = new ResizeObserver(() => {
            this.containerHeight = this.container.clientHeight;
            this.scheduleRender();
        });
        this.resizeObserver.observe(this.container);
    }

    setupVirtualScroll() {
        // Get column count from table header
        const table = this.tableBody.parentElement;
        const headerRow = table.querySelector('thead tr');
        const columnCount = headerRow ? headerRow.children.length : 1;

        // Create spacer rows for virtual scrolling (top and bottom padding)
        this.topSpacer = this.createSpacer(columnCount);
        this.bottomSpacer = this.createSpacer(columnCount);

        // Insert spacers at top and bottom of tbody
        this.tableBody.insertBefore(this.topSpacer, this.tableBody.firstChild);
        this.tableBody.appendChild(this.bottomSpacer);

        // Ensure container can scroll
        this.container.style.overflowY = 'auto';
        this.container.style.overflowX = 'auto';
        this.container.style.position = 'relative';
    }

    createSpacer(columnCount) {
        const row = document.createElement('tr');
        const cell = document.createElement('td');
        cell.colSpan = columnCount;
        cell.style.height = '0px';
        cell.style.padding = '0';
        cell.style.border = 'none';
        cell.style.pointerEvents = 'none';
        row.appendChild(cell);
        return row;
    }

    setData(data) {
        this.data = data;
        // Force a full re-render and clamp the scroll position in case the
        // new data is shorter than where the user had scrolled to
        this.visibleStart = -1;
        this.visibleEnd = -1;
        this.renderedLength = -1;

        const maxScroll = Math.max(0, this.data.length * this.rowHeight - this.containerHeight);
        if (this.scrollTop > maxScroll) {
            this.container.scrollTop = maxScroll;
            this.scrollTop = maxScroll;
        }

        this.render();
    }

    appendData(newData) {
        this.data.push(...newData);
        this.render();
    }

    handleScroll() {
        this.scrollTop = this.container.scrollTop;
        this.scheduleRender();
    }

    scheduleRender() {
        if (this.rafPending) return;
        this.rafPending = true;
        requestAnimationFrame(() => {
            this.rafPending = false;
            this.render();
        });
    }

    removeDataRows() {
        const existingRows = Array.from(this.tableBody.children).filter(
            child => child !== this.topSpacer && child !== this.bottomSpacer
        );
        existingRows.forEach(row => row.remove());
    }

    setSpacerHeights(start, end) {
        this.topSpacer.firstChild.style.height = Math.max(0, start * this.rowHeight) + 'px';
        this.bottomSpacer.firstChild.style.height = Math.max(0, (this.data.length - end) * this.rowHeight) + 'px';
    }

    render() {
        const total = this.data.length;

        if (!this.containerHeight) {
            this.containerHeight = this.container.clientHeight;
        }

        if (total === 0) {
            this.removeDataRows();
            this.setSpacerHeights(0, 0);
            this.visibleStart = -1;
            this.visibleEnd = -1;
            this.renderedLength = 0;
            return;
        }

        const firstVisible = Math.floor(this.scrollTop / this.rowHeight);
        const visibleCount = Math.max(1, Math.ceil(this.containerHeight / this.rowHeight));
        const start = Math.max(0, firstVisible - this.buffer);
        const end = Math.min(total, firstVisible + visibleCount + this.buffer);

        if (start === this.visibleStart && end === this.visibleEnd) {
            // Rendered window unchanged. If rows streamed in below it, just
            // grow the bottom spacer so the scrollbar tracks the data —
            // no need to rebuild the visible rows
            if (total !== this.renderedLength) {
                this.renderedLength = total;
                this.setSpacerHeights(start, end);
            }
            return;
        }

        this.visibleStart = start;
        this.visibleEnd = end;
        this.renderedLength = total;
        this.setSpacerHeights(start, end);

        // Rebuild the visible window
        this.removeDataRows();
        const fragment = document.createDocumentFragment();
        for (let i = start; i < end; i++) {
            fragment.appendChild(this.createRow(this.data[i], i));
        }
        this.tableBody.insertBefore(fragment, this.bottomSpacer);

        this.measureRows();
    }

    measureRows() {
        // Adapt the row-height estimate to what actually rendered, so rows
        // that wrap to multiple lines don't make the scroll math drift
        const rows = Array.from(this.tableBody.children).filter(
            child => child !== this.topSpacer && child !== this.bottomSpacer
        );
        if (!rows.length) return;

        let sum = 0;
        for (const row of rows) {
            sum += row.offsetHeight;
        }
        const measured = sum / rows.length;

        if (measured > 0 && Math.abs(measured - this.rowHeight) > 1) {
            // Damped update: converge without jumping around on outlier rows
            this.rowHeight = this.rowHeight * 0.5 + measured * 0.5;
            this.setSpacerHeights(this.visibleStart, this.visibleEnd);
        }
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
        this.visibleStart = -1;
        this.visibleEnd = -1;
        this.renderedLength = 0;
        this.removeDataRows();
        this.setSpacerHeights(0, 0);
    }

    destroy() {
        this.container.removeEventListener('scroll', this.handleScroll);
        this.resizeObserver.disconnect();
    }
}

// Export for use in app.js
window.VirtualScroller = VirtualScroller;
