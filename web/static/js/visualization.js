/**
 * Site Structure Visualization
 * Uses Cytoscape.js for interactive graph visualization
 */

let cy = null;  // Cytoscape instance
let graphData = { nodes: [], edges: [] };  // Current graph data
let currentLayout = 'cose';  // Current layout algorithm
let currentFilter = 'all';  // Current filter

/**
 * Initialize the visualization when tab is opened
 */
function initVisualization() {
    if (cy) {
        return; // Already initialized
    }

    const container = document.getElementById('cy');
    if (!container) {
        console.error('Graph container not found');
        return;
    }

    // Hide placeholder
    const placeholder = container.querySelector('.graph-placeholder');
    if (placeholder) {
        placeholder.style.display = 'none';
    }

    // Initialize Cytoscape
    cy = cytoscape({
        container: container,
        elements: [],
        style: [
            {
                selector: 'node',
                style: {
                    'background-color': 'data(color)',
                    'label': 'data(label)',
                    'width': 'data(size)',
                    'height': 'data(size)',
                    'font-size': '12px',
                    'color': '#e5e7eb',
                    'text-outline-color': '#1f2937',
                    'text-outline-width': 2,
                    'text-valign': 'bottom',
                    'text-halign': 'center',
                    'text-margin-y': 5,
                    'overlay-opacity': 0,
                    'border-width': 2,
                    'border-color': '#374151'
                }
            },
            {
                selector: 'node:selected',
                style: {
                    'border-color': '#8b5cf6',
                    'border-width': 3,
                    'overlay-opacity': 0
                }
            },
            {
                selector: 'edge',
                style: {
                    'width': 2,
                    'line-color': '#4b5563',
                    'target-arrow-color': '#4b5563',
                    'target-arrow-shape': 'triangle',
                    'curve-style': 'bezier',
                    'arrow-scale': 1,
                    'opacity': 0.6
                }
            },
            {
                selector: 'edge:selected',
                style: {
                    'line-color': '#8b5cf6',
                    'target-arrow-color': '#8b5cf6',
                    'width': 3,
                    'opacity': 1
                }
            }
        ],
        layout: {
            name: 'preset'  // Use preset (no auto-layout on init)
        },
        wheelSensitivity: 0.2,
        minZoom: 0.1,
        maxZoom: 3
    });

    // Add interaction handlers
    setupInteractions();

    // Load initial data
    loadVisualizationData();
}

/**
 * Setup mouse interactions and tooltips
 */
function setupInteractions() {
    if (!cy) return;

    let tooltip = null;

    // Create tooltip element
    function createTooltip() {
        if (!tooltip) {
            tooltip = document.createElement('div');
            tooltip.className = 'cy-tooltip';
            tooltip.style.display = 'none';
            document.body.appendChild(tooltip);
        }
        return tooltip;
    }

    // Show tooltip on hover
    cy.on('mouseover', 'node', function(event) {
        const node = event.target;
        const data = node.data();
        const tooltip = createTooltip();

        // Build tooltip content
        const statusClass = getStatusClass(data.status_code);
        tooltip.innerHTML = `
            <div class="tooltip-url">${truncateUrl(data.url)}</div>
            <div class="tooltip-info">
                <div><strong>Title:</strong> ${data.title || 'N/A'}</div>
                <div class="tooltip-status ${statusClass}">Status: ${data.status_code}</div>
            </div>
        `;

        tooltip.style.display = 'block';
    });

    // Move tooltip with mouse
    cy.on('mousemove', 'node', function(event) {
        const tooltip = createTooltip();
        tooltip.style.left = (event.originalEvent.pageX + 10) + 'px';
        tooltip.style.top = (event.originalEvent.pageY + 10) + 'px';
    });

    // Hide tooltip when mouse leaves
    cy.on('mouseout', 'node', function() {
        const tooltip = createTooltip();
        tooltip.style.display = 'none';
    });

    // Double-click to open URL in new tab
    cy.on('dblclick', 'node', function(event) {
        const node = event.target;
        const url = node.data('url');
        if (url) {
            window.open(url, '_blank');
        }
    });

    // Click to highlight connected nodes
    cy.on('tap', 'node', function(event) {
        const node = event.target;

        // Reset all nodes and edges
        cy.elements().removeClass('highlighted').removeClass('dimmed');

        // Highlight the selected node and its neighbors
        const neighborhood = node.neighborhood().add(node);
        neighborhood.addClass('highlighted');

        // Dim everything else
        cy.elements().not(neighborhood).addClass('dimmed');
    });

    // Click on background to reset
    cy.on('tap', function(event) {
        if (event.target === cy) {
            cy.elements().removeClass('highlighted').removeClass('dimmed');
        }
    });
}

/**
 * Load visualization data from backend
 */
async function loadVisualizationData() {
    try {
        const response = await fetch('/api/visualization_data');
        const data = await response.json();

        if (!data.success) {
            console.error('Failed to load visualization data:', data.error);
            return;
        }

        graphData = {
            nodes: data.nodes || [],
            edges: data.edges || []
        };

        // Show warning if data was truncated
        if (data.truncated) {
            console.warn(`Showing ${data.visualized_pages} of ${data.total_pages} pages for performance`);
        }

        // Update the graph
        updateGraph();

    } catch (error) {
        console.error('Error loading visualization data:', error);
    }
}

/**
 * Update the graph with current data and filters
 */
function updateGraph() {
    if (!cy) {
        initVisualization();
        return;
    }

    // Filter data based on current filter
    let filteredNodes = graphData.nodes;
    let filteredEdges = graphData.edges;

    if (currentFilter !== 'all') {
        filteredNodes = graphData.nodes.filter(node => {
            const statusCode = node.data.status_code;

            switch (currentFilter) {
                case 'html':
                    // Only show HTML pages (typically 2xx with no file extension or .html)
                    const url = node.data.url;
                    return statusCode >= 200 && statusCode < 300 &&
                           (url.endsWith('/') || url.endsWith('.html') || url.endsWith('.htm') || !url.includes('.'));
                case '2xx':
                    return statusCode >= 200 && statusCode < 300;
                case '3xx':
                    return statusCode >= 300 && statusCode < 400;
                case '4xx':
                    return statusCode >= 400 && statusCode < 500;
                case '5xx':
                    return statusCode >= 500 && statusCode < 600;
                default:
                    return true;
            }
        });

        // Filter edges to only include edges where both nodes are present
        const nodeIds = new Set(filteredNodes.map(n => n.data.id));
        filteredEdges = graphData.edges.filter(edge =>
            nodeIds.has(edge.data.source) && nodeIds.has(edge.data.target)
        );
    }

    // Update graph
    cy.elements().remove();
    cy.add([...filteredNodes, ...filteredEdges]);

    // Apply layout
    applyLayout(currentLayout);
}

/**
 * Apply a layout algorithm to the graph
 */
function applyLayout(layoutName) {
    if (!cy) return;

    const layoutConfig = {
        name: layoutName,
        animate: 'end',  // Animate to end result, not during iterations
        animationDuration: 500,
        fit: true,
        padding: 50,
        boundingBox: undefined,
        avoidOverlap: true
    };

    // Add specific config for certain layouts
    if (layoutName === 'cose') {
        // More balanced values that won't cause numerical instability
        layoutConfig.nodeRepulsion = 400000;
        layoutConfig.nodeOverlap = 20;
        layoutConfig.idealEdgeLength = 100;
        layoutConfig.edgeElasticity = 100;
        layoutConfig.nestingFactor = 5;
        layoutConfig.gravity = 80;
        layoutConfig.numIter = 1000;
        layoutConfig.initialTemp = 200;
        layoutConfig.coolingFactor = 0.95;
        layoutConfig.minTemp = 1.0;
        layoutConfig.randomize = true;
        layoutConfig.componentSpacing = 200;      // Space between disconnected components
    } else if (layoutName === 'breadthfirst') {
        layoutConfig.directed = true;
        layoutConfig.spacingFactor = 1.5;
    } else if (layoutName === 'concentric') {
        layoutConfig.minNodeSpacing = 100;
        layoutConfig.concentric = function(node) {
            return node.degree();
        };
        layoutConfig.levelWidth = function() {
            return 2;
        };
    }

    const layout = cy.layout(layoutConfig);
    layout.run();
}

/**
 * Change the layout algorithm
 */
function changeLayout(layoutName) {
    currentLayout = layoutName;
    applyLayout(layoutName);
}

/**
 * Filter visualization by criteria
 */
function filterVisualization(filter) {
    currentFilter = filter;
    updateGraph();
}

/**
 * Reset the view to show all nodes
 */
function resetVisualization() {
    if (!cy) return;

    cy.elements().removeClass('highlighted').removeClass('dimmed');
    cy.fit(50);
    cy.zoom(1);
}

/**
 * Export visualization as PNG image
 */
function exportVisualizationImage() {
    if (!cy) return;

    const png = cy.png({
        output: 'blob',
        bg: '#1a1d29',
        full: true,
        scale: 2
    });

    const url = URL.createObjectURL(png);
    const link = document.createElement('a');
    link.href = url;
    link.download = 'site-structure-visualization.png';
    link.click();
    URL.revokeObjectURL(url);
}

/**
 * Helper: Get status class for tooltip
 */
function getStatusClass(statusCode) {
    if (statusCode >= 200 && statusCode < 300) return 'status-2xx';
    if (statusCode >= 300 && statusCode < 400) return 'status-3xx';
    if (statusCode >= 400 && statusCode < 500) return 'status-4xx';
    if (statusCode >= 500 && statusCode < 600) return 'status-5xx';
    return 'status-other';
}

/**
 * Helper: Truncate URL for display
 */
function truncateUrl(url, maxLength = 60) {
    if (url.length <= maxLength) return url;
    return url.substring(0, maxLength - 3) + '...';
}

/**
 * Clear the visualization
 */
function clearVisualization() {
    // Clear graph data
    graphData = { nodes: [], edges: [] };

    // Clear the cytoscape graph if it exists
    if (cy) {
        cy.elements().remove();
        cy.fit();
    }

    // Show placeholder
    const container = document.getElementById('cy');
    if (container) {
        const placeholder = container.querySelector('.graph-placeholder');
        if (placeholder) {
            placeholder.style.display = 'block';
        }
    }

    console.log('Visualization cleared');
}

/**
 * Update visualization from loaded crawl data (not from backend)
 */
function updateVisualizationFromLoadedData(urls, links) {
    if (!urls || urls.length === 0) {
        console.log('No URL data to visualize');
        return;
    }

    console.log(`Building visualization from ${urls.length} URLs and ${links ? links.length : 0} links`);

    // Build nodes from URLs
    const nodes = [];
    const url_to_id = {};
    const max_nodes = 500;
    const pages_to_visualize = urls.slice(0, max_nodes);

    for (let idx = 0; idx < pages_to_visualize.length; idx++) {
        const page = pages_to_visualize[idx];
        const url = page.url || '';
        const status_code = page.status_code || 0;

        // Assign color based on status code
        let color = '#6b7280';
        if (status_code >= 200 && status_code < 300) color = '#10b981';
        else if (status_code >= 300 && status_code < 400) color = '#3b82f6';
        else if (status_code >= 400 && status_code < 500) color = '#f59e0b';
        else if (status_code >= 500 && status_code < 600) color = '#ef4444';

        const node = {
            data: {
                id: `node-${idx}`,
                label: url.split('/').pop() || url.split('//').pop() || url,
                url: url,
                status_code: status_code,
                title: page.title || '',
                color: color,
                size: idx === 0 ? 30 : 20
            }
        };
        nodes.push(node);
        url_to_id[url] = `node-${idx}`;
    }

    // Build edges from links
    const edges = [];
    const edges_set = new Set();

    if (links && links.length > 0) {
        for (const link of links) {
            if (link.is_internal) {
                const source_url = link.source_url || '';
                const target_url = link.target_url || '';

                const source_id = url_to_id[source_url];
                const target_id = url_to_id[target_url];

                if (source_id && target_id && source_id !== target_id) {
                    const edge_key = `${source_id}-${target_id}`;
                    if (!edges_set.has(edge_key)) {
                        edges_set.add(edge_key);
                        edges.push({
                            data: {
                                id: `edge-${edge_key}`,
                                source: source_id,
                                target: target_id
                            }
                        });
                    }
                }
            }
        }
    }

    console.log(`Built ${nodes.length} nodes and ${edges.length} edges from loaded data`);

    // Update global graph data
    graphData = { nodes, edges };

    // Hide placeholder
    const container = document.getElementById('cy');
    if (container) {
        const placeholder = container.querySelector('.graph-placeholder');
        if (placeholder) {
            placeholder.style.display = 'none';
        }
    }

    // If visualization is already initialized, update it
    if (cy) {
        updateGraph();
    }
}

// Export functions to global scope
window.initVisualization = initVisualization;
window.changeLayout = changeLayout;
window.filterVisualization = filterVisualization;
window.resetVisualization = resetVisualization;
window.exportVisualizationImage = exportVisualizationImage;
window.loadVisualizationData = loadVisualizationData;
window.updateVisualizationFromLoadedData = updateVisualizationFromLoadedData;
window.clearVisualization = clearVisualization;
