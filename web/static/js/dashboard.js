// ========================================
// Dashboard Functions
// ========================================

async function openDashboard() {
    const modal = document.getElementById('dashboardModal');
    const content = document.getElementById('dashboardContent');

    // Show modal
    modal.style.display = 'flex';

    // Load crawls
    try {
        const response = await fetch('/api/crawls/list');
        const data = await response.json();

        if (!data.success) {
            content.innerHTML = `<p style="color: #ef4444;">Error loading crawls: ${data.error}</p>`;
            return;
        }

        const crawls = data.crawls || [];

        if (crawls.length === 0) {
            content.innerHTML = `<p style="text-align: center; color: #9ca3af;">No saved crawls found.</p>`;
            return;
        }

        // Build table
        let html = `
            <table class="data-table" style="width: 100%; table-layout: fixed;">
                <thead>
                    <tr>
                        <th style="width: 180px;">Date</th>
                        <th style="width: 200px;">Domain</th>
                        <th style="width: 80px;">URLs</th>
                        <th style="width: 100px;">Status</th>
                        <th style="width: 280px;">Actions</th>
                    </tr>
                </thead>
                <tbody>
        `;

        crawls.forEach(crawl => {
            const date = new Date(crawl.started_at).toLocaleString();
            const domain = crawl.base_domain || crawl.base_url;
            const status = crawl.status || 'unknown';
            const statusColor = status === 'completed' ? '#10b981' : status === 'running' ? '#3b82f6' : status === 'paused' ? '#f59e0b' : '#6b7280';

            html += `
                <tr>
                    <td>${date}</td>
                    <td>${domain}</td>
                    <td>${crawl.urls_crawled || 0}</td>
                    <td><span style="color: ${statusColor};">${status}</span></td>
                    <td style="white-space: nowrap;">
                        <button class="btn btn-primary" style="margin-right: 5px; padding: 6px 12px; font-size: 13px;" onclick="loadCrawlFromDashboard(${crawl.id})">Load</button>
                        <button class="btn btn-secondary" style="margin-right: 5px; padding: 6px 12px; font-size: 13px;" onclick="resumeCrawlFromDashboard(${crawl.id})">Resume</button>
                        <button class="btn btn-danger" style="padding: 6px 12px; font-size: 13px;" onclick="deleteCrawlFromDashboard(${crawl.id})">Delete</button>
                    </td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        content.innerHTML = html;

    } catch (error) {
        console.error('Error loading dashboard:', error);
        content.innerHTML = `<p style="color: #ef4444;">Error loading crawls.</p>`;
    }
}

function closeDashboard() {
    document.getElementById('dashboardModal').style.display = 'none';
}

async function loadCrawlFromDashboard(crawlId) {
    if (!confirm('Load this crawl? Any unsaved current data will be lost.')) return;

    try {
        // Call backend to load data into current crawler
        const response = await fetch(`/api/crawls/${crawlId}/load`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!data.success) {
            alert('Error: ' + (data.error || data.message));
            return;
        }

        // Close dashboard
        closeDashboard();

        // Fetch the loaded data
        const statusResponse = await fetch('/api/crawl_status');
        const statusData = await statusResponse.json();

        // Clear UI
        clearAllTables();
        resetStats();

        // Populate data
        crawlState.urls = [];
        crawlState.links = statusData.links || [];
        crawlState.issues = statusData.issues || [];
        crawlState.stats = statusData.stats || {};
        crawlState.baseUrl = statusData.stats?.baseUrl || '';

        // Set URL input
        if (crawlState.baseUrl) {
            document.getElementById('urlInput').value = crawlState.baseUrl;
        }

        // Add URLs to tables
        if (statusData.urls && statusData.urls.length > 0) {
            statusData.urls.forEach(url => addUrlToTable(url));
        }

        // Load links
        if (statusData.links && statusData.links.length > 0) {
            crawlState.pendingLinks = statusData.links;
        }

        // Load issues
        if (statusData.issues && statusData.issues.length > 0) {
            crawlState.pendingIssues = statusData.issues;
        }

        // Update displays
        updateStatsDisplay();
        updateFilterCounts();
        updateStatusCodesTable();
        updateCrawlButtons();
        updateStatus(`Loaded: ${statusData.urls?.length || 0} URLs`);

        showNotification('Crawl loaded successfully', 'success');

    } catch (error) {
        console.error('Error loading crawl:', error);
        alert('Error loading crawl');
    }
}

async function resumeCrawlFromDashboard(crawlId) {
    if (!confirm('Resume this crawl? Any unsaved current data will be lost.')) return;

    try {
        // Call backend to resume
        const response = await fetch(`/api/crawls/${crawlId}/resume`, {
            method: 'POST'
        });
        const data = await response.json();

        if (!data.success) {
            alert('Error: ' + (data.error || data.message));
            return;
        }

        // Close dashboard
        closeDashboard();

        // Fetch the loaded data
        const statusResponse = await fetch('/api/crawl_status');
        const statusData = await statusResponse.json();

        // Clear UI
        clearAllTables();
        resetStats();

        // Populate data
        crawlState.urls = [];
        crawlState.links = statusData.links || [];
        crawlState.issues = statusData.issues || [];
        crawlState.stats = statusData.stats || {};
        crawlState.baseUrl = statusData.stats?.baseUrl || '';

        // Set URL input
        if (crawlState.baseUrl) {
            document.getElementById('urlInput').value = crawlState.baseUrl;
        }

        // Add URLs to tables
        if (statusData.urls && statusData.urls.length > 0) {
            statusData.urls.forEach(url => addUrlToTable(url));
        }

        // Load links
        if (statusData.links && statusData.links.length > 0) {
            crawlState.pendingLinks = statusData.links;
        }

        // Load issues
        if (statusData.issues && statusData.issues.length > 0) {
            crawlState.pendingIssues = statusData.issues;
        }

        // Set crawl as running
        if (statusData.status === 'running') {
            crawlState.isRunning = true;
            crawlState.isPaused = false;
            crawlState.startTime = new Date();
            showProgress();
            updateCrawlButtons();
            pollCrawlProgress();
        }

        // Update displays
        updateStatsDisplay();
        updateFilterCounts();
        updateStatusCodesTable();
        updateStatus('Crawl resumed');

        showNotification('Crawl resumed successfully', 'success');

    } catch (error) {
        console.error('Error resuming crawl:', error);
        alert('Error resuming crawl');
    }
}

async function deleteCrawlFromDashboard(crawlId) {
    if (!confirm('Delete this crawl permanently? This cannot be undone.')) return;

    try {
        const response = await fetch(`/api/crawls/${crawlId}/delete`, {
            method: 'DELETE'
        });
        const data = await response.json();

        if (data.success) {
            showNotification('Crawl deleted', 'success');
            // Reload dashboard
            openDashboard();
        } else {
            alert('Error deleting crawl: ' + data.error);
        }
    } catch (error) {
        console.error('Error deleting crawl:', error);
        alert('Error deleting crawl');
    }
}
