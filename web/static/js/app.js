// Application State
let crawlState = {
    isRunning: false,
    isPaused: false,
    startTime: null,
    baseUrl: null,
    urls: [],
    links: [],
    issues: [],
    stats: {
        discovered: 0,
        crawled: 0,
        depth: 0,
        speed: 0
    },
    filters: {
        active: null,
        issueFilter: 'all',
        linksFilter: {
            internalStatusCode: 'all',
            externalStatusCode: 'all',
            internalSearch: '',
            externalSearch: ''
        }
    }
};

// Incremental polling instance
let incrementalPoller = null;

// Virtual Scrollers
let virtualScrollers = {
    overview: null,
    internal: null,
    external: null,
    internalLinks: null,
    externalLinks: null,
    issues: null,
    extraction: null,
    ngrams: null,
    compare: null
};

// 'spider' follows links from one URL; 'list' checks a pasted list
let crawlMode = 'spider';
const MAX_LIST_URLS = 100000;

// Extractor names currently shown as Custom Extraction columns
let extractionColumns = [];

// URL table column definitions. Keeping the value/sorting logic centralized
// lets hidden columns and header sorting stay in sync with the renderers.
const TABLE_COLUMNS = {
    overview: [
        { key: 'url', label: 'Address', sortable: true },
        { key: 'status_code', label: 'Status', sortable: true },
        { key: 'title', label: 'Title', sortable: true },
        { key: 'meta_description', label: 'Meta Desc', sortable: true },
        { key: 'h1', label: 'H1', sortable: true },
        { key: 'keywords', label: 'Keywords', sortable: true },
        { key: 'word_count', label: 'Words', sortable: true },
        { key: 'response_time', label: 'Response (ms)', sortable: true },
        { key: 'analytics', label: 'Analytics', sortable: true },
        { key: 'og_tags', label: 'OG Tags', sortable: true },
        { key: 'json_ld', label: 'JSON-LD', sortable: true },
        { key: 'links', label: 'Links (Int/Ext)', sortable: true },
        { key: 'images', label: 'Images', sortable: true },
        { key: 'javascript_rendered', label: 'JS', sortable: true },
        { key: 'indexability', label: 'Indexability', sortable: true },
        { key: 'indexability_status', label: 'Indexability Status', sortable: true },
        { key: 'inlinks', label: 'Inlinks', sortable: true },
        { key: 'link_score', label: 'Link Score', sortable: true },
        { key: 'in_sitemap', label: 'In Sitemap', sortable: true },
        { key: 'details', label: 'Details', sortable: false }
    ],
    internal: [
        { key: 'url', label: 'Address', sortable: true },
        { key: 'status_code', label: 'Status', sortable: true },
        { key: 'content_type', label: 'Content Type', sortable: true },
        { key: 'size', label: 'Size', sortable: true },
        { key: 'title', label: 'Title', sortable: true },
        { key: 'indexability', label: 'Indexability', sortable: true },
        { key: 'inlinks', label: 'Inlinks', sortable: true },
        { key: 'link_score', label: 'Link Score', sortable: true }
    ],
    external: [
        { key: 'url', label: 'Address', sortable: true },
        { key: 'status_code', label: 'Status', sortable: true },
        { key: 'content_type', label: 'Content Type', sortable: true },
        { key: 'size', label: 'Size', sortable: true },
        { key: 'title', label: 'Title', sortable: true }
    ]
};

// Columns the current user has chosen to hide, and the current sort per table.
const tableHiddenColumns = {
    overview: new Set(),
    internal: new Set(),
    external: new Set()
};

const tableSortState = {
    overview: null,
    internal: null,
    external: null
};

const tableColumnMenus = {};

// Initialize application
document.addEventListener('DOMContentLoaded', async function() {
    await initializeApp();
});

async function initializeApp() {
    // Load plugins first (before tabs are initialized)
    if (window.LibreCrawlPlugin && window.LibreCrawlPlugin.loader) {
        await window.LibreCrawlPlugin.loader.loadAllPlugins();
        window.LibreCrawlPlugin.loader.initializePlugins();
    }

    // Setup event listeners
    setupEventListeners();

    // Load each user's hidden-column choices before the tables are built
    await loadTablePreferences();

    // Initialize tables
    initializeTables();

    // Load user info
    loadUserInfo();

    // DEBUG: Check sessionStorage
    console.log('DEBUG: Checking sessionStorage force_ui_refresh:', sessionStorage.getItem('force_ui_refresh'));

    // Check if we just loaded a crawl from dashboard
    if (sessionStorage.getItem('force_ui_refresh') === 'true') {
        console.log('DEBUG: Found force_ui_refresh flag, loading crawl data...');
        sessionStorage.removeItem('force_ui_refresh');

        try {
            // Fetch the loaded data immediately with FULL refresh (no incremental)
            const response = await fetch('/api/crawl_status');
            const data = await response.json();

            // DEBUG: Log the full response
            console.log('DEBUG: Full /api/crawl_status response:', JSON.stringify(data, null, 2));

            // Clear existing data first
            clearAllTables();
            resetStats();

            // Force populate all data
            crawlState.urls = [];
            crawlState.links = data.links || [];
            crawlState.issues = data.issues || [];
            crawlState.stats = data.stats || {};
            crawlState.baseUrl = data.stats?.baseUrl || '';

            // Set URL input
            if (crawlState.baseUrl) {
                document.getElementById('urlInput').value = crawlState.baseUrl;
            }

            // Add each URL to tables
            if (data.urls && data.urls.length > 0) {
                data.urls.forEach(url => addUrlToTable(url));
                refreshUrlTables();
            }

            // Load links if present
            if (data.links && data.links.length > 0) {
                crawlState.pendingLinks = data.links;
                // If links tab is active, load them immediately
                if (isLinksTabActive()) {
                    updateLinksTable(data.links);
                }
            }

            // Load issues if present
            if (data.issues && data.issues.length > 0) {
                crawlState.pendingIssues = data.issues;
                // If issues tab is active, load them immediately
                if (isIssuesTabActive()) {
                    updateIssuesTable(data.issues);
                } else {
                    // Update badge count even if tab not active
                    const issuesTabButton = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.textContent.includes('Issues'));
                    if (issuesTabButton && data.issues.length > 0) {
                        const errorCount = data.issues.filter(i => i.type === 'error').length;
                        const warningCount = data.issues.filter(i => i.type === 'warning').length;
                        let badgeColor = '#3b82f6';
                        if (errorCount > 0) badgeColor = '#ef4444';
                        else if (warningCount > 0) badgeColor = '#f59e0b';
                        issuesTabButton.innerHTML = `Issues <span style="background: ${badgeColor}; color: white; padding: 2px 6px; border-radius: 12px; font-size: 12px;">${data.issues.length}</span>`;
                    }
                }
            }

            // Update all displays
            updateStatsDisplay();
            updateFilterCounts();
            updateStatusCodesTable();
            updateCrawlButtons();

            // Check if the crawl is currently running (resumed from dashboard)
            if (data.status === 'running') {
                // Set crawl state to running
                crawlState.isRunning = true;
                crawlState.isPaused = false;
                crawlState.startTime = new Date(); // Set start time to now for timer

                // Show progress UI
                showProgress();

                // Update buttons for running state
                updateCrawlButtons();

                // Start polling for updates
                updateStatus('Crawl resumed - updating...');
                pollCrawlProgress();
            } else {
                // Crawl is not running, just loaded data
                updateStatus(`Loaded crawl: ${data.stats.crawled} URLs, ${data.links?.length || 0} links, ${data.issues?.length || 0} issues`);
            }

            console.log('Loaded crawl from database:', {
                urls: data.urls?.length || 0,
                links: data.links?.length || 0,
                issues: data.issues?.length || 0,
                stats: data.stats,
                status: data.status,
                isRunning: crawlState.isRunning
            });
        } catch (error) {
            console.error('Error loading crawl data:', error);
            updateStatus('Error loading crawl data');
        }
    }

    // Restore the crawl mode picked last time in this browser
    let savedMode = 'spider';
    try {
        savedMode = localStorage.getItem('librecrawl_crawl_mode') || 'spider';
    } catch (e) { /* storage unavailable */ }
    setCrawlMode(savedMode === 'list' ? 'list' : 'spider');

    console.log('LibreCrawl initialized');
}

function setupEventListeners() {
    // URL input enter key
    document.getElementById('urlInput').addEventListener('keypress', handleUrlKeypress);

    // Update timer every second when crawling
    setInterval(updateTimer, 1000);
}

function handleUrlKeypress(event) {
    if (event.key === 'Enter' && crawlMode === 'spider' && !crawlState.isRunning) {
        toggleCrawl();
    }
}

function toggleCrawl() {
    if (!crawlState.isRunning) {
        startCrawl();
    } else if (crawlState.isPaused) {
        resumeCrawl();
    } else {
        pauseCrawl();
    }
}

// ---- Crawl mode (Spider / List) ----

function setCrawlMode(mode) {
    if (crawlState.isRunning) return;
    crawlMode = mode === 'list' ? 'list' : 'spider';
    try {
        localStorage.setItem('librecrawl_crawl_mode', crawlMode);
    } catch (e) { /* storage unavailable */ }

    const isList = crawlMode === 'list';
    document.querySelectorAll('.mode-btn').forEach(btn => {
        const active = btn.dataset.mode === crawlMode;
        btn.classList.toggle('active', active);
        btn.setAttribute('aria-pressed', active ? 'true' : 'false');
    });
    document.getElementById('urlInput').style.display = isList ? 'none' : '';
    document.getElementById('listInputGroup').style.display = isList ? 'block' : 'none';

    const label = document.getElementById('urlInputLabel');
    label.textContent = isList ? 'URLs to Check' : 'URL to Crawl';
    label.htmlFor = isList ? 'urlListInput' : 'urlInput';

    updateListCount();
    document.getElementById(isList ? 'urlListInput' : 'urlInput').focus();
}

// Pull URLs out of pasted text or a .txt/.csv file. Accepts one
// URL per line or per CSV cell; header cells and other non-URL
// tokens are skipped. Order is kept, duplicates dropped.
function parseUrlList(text) {
    const urls = [];
    const seen = new Set();
    let skipped = 0;
    (text || '').split(/[\s,;]+/).forEach(raw => {
        const token = raw.trim().replace(/^["']+|["']+$/g, '');
        if (!token || token.startsWith('#')) return;
        const looksLikeUrl = /^https?:\/\//i.test(token) ||
            /^[^\s\/]+\.[a-z]{2,}(:\d+)?(\/|$)/i.test(token) ||
            /^localhost(:\d+)?(\/|$)/i.test(token);
        const url = looksLikeUrl ? normalizeUrl(token) : null;
        if (!url || !isValidUrl(url)) {
            skipped++;
            return;
        }
        if (!seen.has(url)) {
            seen.add(url);
            urls.push(url);
        }
    });
    return { urls, skipped };
}

function updateListCount() {
    const countEl = document.getElementById('urlListCount');
    if (!countEl) return;
    const { urls, skipped } = parseUrlList(document.getElementById('urlListInput').value);
    let text = `${urls.length.toLocaleString()} URL${urls.length === 1 ? '' : 's'}`;
    if (skipped) text += ` (${skipped.toLocaleString()} non-URL entr${skipped === 1 ? 'y' : 'ies'} ignored)`;
    if (urls.length > MAX_LIST_URLS) text += `, over the ${MAX_LIST_URLS.toLocaleString()} limit`;
    countEl.textContent = text;
    countEl.classList.toggle('list-count-over', urls.length > MAX_LIST_URLS);
}

function loadUrlListFile(event) {
    const file = event.target.files && event.target.files[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
        const textarea = document.getElementById('urlListInput');
        const existing = textarea.value.trim();
        textarea.value = existing ? existing + '\n' + reader.result : reader.result;
        updateListCount();
        showNotification(`Loaded ${file.name}`, 'success');
    };
    reader.onerror = () => showNotification(`Could not read ${file.name}`, 'error');
    reader.readAsText(file);
    // Let the same file be picked again after edits
    event.target.value = '';
}

function startCrawl() {
    if (crawlMode === 'list') {
        startListCrawl();
        return;
    }

    const urlInput = document.getElementById('urlInput');
    let url = urlInput.value.trim();

    if (!url) {
        alert('Please enter a URL to crawl');
        urlInput.focus();
        return;
    }

    // Normalize the URL - add protocol if missing
    url = normalizeUrl(url);

    if (!isValidUrl(url)) {
        alert('Please enter a valid URL or domain');
        urlInput.focus();
        return;
    }

    // Update the input field with the normalized URL
    urlInput.value = url;

    beginCrawl(url, null);
}

function startListCrawl() {
    const textarea = document.getElementById('urlListInput');
    const { urls } = parseUrlList(textarea.value);

    if (urls.length === 0) {
        alert('Paste or upload at least one URL to check');
        textarea.focus();
        return;
    }
    if (urls.length > MAX_LIST_URLS) {
        alert(`List mode accepts up to ${MAX_LIST_URLS.toLocaleString()} URLs; this list has ${urls.length.toLocaleString()}`);
        return;
    }

    beginCrawl(urls[0], urls);
}

// Shared start sequence; urlList is null for a spider crawl
function beginCrawl(url, urlList) {
    crawlState.isRunning = true;
    crawlState.isPaused = false;
    crawlState.startTime = new Date();
    crawlState.baseUrl = url;

    // Initialize incremental poller for new crawl
    if (!incrementalPoller) {
        incrementalPoller = new IncrementalPoller();
    }
    incrementalPoller.reset();

    // Update UI
    updateCrawlButtons();
    showProgress();
    updateStatus(urlList ? `Starting list check of ${urlList.length.toLocaleString()} URLs...` : 'Starting crawl...');

    // Clear previous data
    clearAllTables();
    resetStats();

    // Start the actual crawling via Python backend
    startPythonCrawl(url, urlList);
}

function pauseCrawl() {
    crawlState.isPaused = true;
    updateCrawlButtons();
    updateStatus('Crawl paused');

    // Pause Python crawler
    fetch('/api/pause_crawl', {
        method: 'POST'
    }).catch(error => {
        console.error('Error pausing crawl:', error);
    });
}

function resumeCrawl() {
    crawlState.isPaused = false;
    updateCrawlButtons();
    updateStatus('Resuming crawl...');

    // Resume Python crawler
    fetch('/api/resume_crawl', {
        method: 'POST'
    }).catch(error => {
        console.error('Error resuming crawl:', error);
    });
}

function stopCrawl() {
    crawlState.isRunning = false;
    crawlState.isPaused = false;

    // Update UI
    updateCrawlButtons();
    hideProgress();
    updateStatus('Crawl stopped');

    // Stop Python crawler
    stopPythonCrawl();
}

function clearCrawlData() {
    if (crawlState.isRunning) {
        if (!confirm('A crawl is currently running. Stop the crawl and clear all data?')) {
            return;
        }
        stopCrawl();
    }

    // Clear all data
    clearAllTables();
    resetStats();
    crawlState.urls = [];
    crawlState.links = [];
    crawlState.issues = [];
    crawlState.baseUrl = null;
    crawlState.filters.active = null;
    crawlState.pendingLinks = null;
    crawlState.pendingIssues = null;
    updateStatusCodesTable();

    // Clear issues and reset badge
    window.currentIssues = [];
    updateIssuesTable([]);  // This will also clear the badge

    // Reset issue filter counts
    document.getElementById('issues-all-count').textContent = '(0)';
    document.getElementById('issues-error-count').textContent = '(0)';
    document.getElementById('issues-warning-count').textContent = '(0)';
    document.getElementById('issues-info-count').textContent = '(0)';

    // Clear visualization
    if (typeof window.clearVisualization === 'function') {
        window.clearVisualization();
    }

    // Notify plugins of data clear (send empty data)
    if (window.LibreCrawlPlugin && window.LibreCrawlPlugin.loader) {
        window.LibreCrawlPlugin.loader.notifyDataUpdate({
            urls: [],
            links: [],
            issues: [],
            stats: { discovered: 0, crawled: 0, depth: 0, speed: 0 }
        });
    }

    // Clear filter states
    document.querySelectorAll('.filter-item').forEach(item => {
        item.classList.remove('active');
    });

    // Reset the "All Issues" filter to active
    document.querySelector('[data-filter="all"]')?.classList.add('active');

    // Update UI
    updateStatus('Data cleared');
    hideProgress();
    updateCrawlButtons(); // Update save/load button states

    // Reset URL input
    document.getElementById('urlInput').value = '';
    document.getElementById('urlInput').focus();
}

function startPythonCrawl(url, urlList) {
    const payload = urlList ? { url: url, mode: 'list', urls: urlList } : { url: url };

    // Call Python backend to start crawling
    fetch('/api/start_crawl', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            updateStatus(urlList ? 'Checking listed URLs...' : 'Crawling in progress...');
            // Refresh user info to update crawl count
            loadUserInfo();
            // Start polling for updates
            pollCrawlProgress();
        } else {
            updateStatus('Error: ' + (data.error || data.message || 'could not start'));
            stopCrawl();
        }
    })
    .catch(error => {
        console.error('Error starting crawl:', error);
        updateStatus('Error starting crawl');
        stopCrawl();
    });
}

function stopPythonCrawl() {
    fetch('/api/stop_crawl', {
        method: 'POST'
    })
    .then(response => response.json())
    .then(data => {
        console.log('Crawl stopped:', data);
    })
    .catch(error => {
        console.error('Error stopping crawl:', error);
    });
}

function pollCrawlProgress() {
    if (!crawlState.isRunning) return;

    // The poller carries its own cursor/epoch; on a fresh page it starts at
    // zero and the server replays the running crawl's events from scratch
    if (!incrementalPoller) {
        incrementalPoller = new IncrementalPoller();
    }

    incrementalPoller.fetchUpdate()
        .then(data => {
            updateCrawlData(data);

            // Update bottom status bar based on current state
            if (data.is_running_pagespeed) {
                updateStatus('Running PageSpeed analysis...');
            } else if (data.status === 'running') {
                updateStatus('Crawling in progress...');
            }

            // Update visualization if visualization tab is active
            const vizTab = document.getElementById('visualization-tab');
            if (vizTab && vizTab.classList.contains('active') && typeof loadVisualizationData === 'function') {
                loadVisualizationData();
            }

            if (data.status === 'demo_stopped' || data.demo_stopped) {
                stopCrawl();
                updateStatus('Demo limit reached — crawl data saved');
                showDemoLimitNotification();
                if (typeof loadVisualizationData === 'function') {
                    loadVisualizationData();
                }
            } else if (crawlState.isRunning && data.status !== 'completed') {
                setTimeout(pollCrawlProgress, 1000); // Poll every second
            } else if (data.status === 'completed') {
                stopCrawl();
                updateStatus('Crawl completed');
                // Update visualization one final time when crawl completes
                if (typeof loadVisualizationData === 'function') {
                    loadVisualizationData();
                }
                // Notify plugins that crawl is complete
                if (window.LibreCrawlPlugin && window.LibreCrawlPlugin.loader) {
                    window.LibreCrawlPlugin.loader.notifyCrawlComplete({
                        urls: crawlState.urls,
                        links: crawlState.links,
                        issues: crawlState.issues,
                        stats: crawlState.stats
                    });
                }
            }
        })
        .catch(error => {
            console.error('Error polling crawl status:', error);
            // Continue polling even if there's an error (common on large crawls)
            if (crawlState.isRunning) {
                setTimeout(pollCrawlProgress, 1000);
            }
        });
}

function updateCrawlData(data) {
    // Update statistics
    crawlState.stats = data.stats || crawlState.stats;
    updateStatsDisplay();

    // Update memory statistics
    if (data.memory && data.memory_data) {
        updateMemoryDisplay(data.memory, data.memory_data);
    }

    // The poller reports which collections actually changed this poll, so
    // untouched tables are left alone (a plain snapshot changes everything)
    const changed = data.changed || { urls: true, links: true, issues: true };

    // Sync URL tables from the accumulated array. Updates to existing rows
    // (linked_from, image statuses) come through as replaced objects, so the
    // tables are rebuilt from state rather than append-only.
    if (data.urls && changed.urls) {
        crawlState.urls = data.urls;
        refreshUrlTables();
    }

    // Update links tables only if Links tab is active to improve performance
    if (data.links && changed.links) {
        // Always store links data in crawlState
        crawlState.links = data.links;
        if (isLinksTabActive()) {
            updateLinksTable(data.links);
        } else {
            // Store in pendingLinks for lazy loading when switching to tab
            crawlState.pendingLinks = data.links;
        }
    }

    // Update issues table only if Issues tab is active
    if (data.issues && changed.issues) {
        // Always store issues data in crawlState
        crawlState.issues = data.issues;
        if (isIssuesTabActive()) {
            updateIssuesTable(data.issues);
        } else {
            // Store in pendingIssues for lazy loading when switching to tab
            crawlState.pendingIssues = data.issues;
        }
    }

    if (changed.urls) {
        // Update filter counts
        updateFilterCounts();

        // Update status codes table (respecting active filter)
        updateStatusCodesTable(crawlState.filters.active);
    }

    // Update progress and status text
    updateProgress(data.progress || 0);
    updateProgressText(data);

    // Update PageSpeed results if available
    if (data.stats && data.stats.pagespeed_results) {
        displayPageSpeedResults(data.stats.pagespeed_results);
    }

    // Notify plugins of data update
    if ((changed.urls || changed.links || changed.issues) &&
        window.LibreCrawlPlugin && window.LibreCrawlPlugin.loader) {
        window.LibreCrawlPlugin.loader.notifyDataUpdate({
            urls: crawlState.urls,
            links: crawlState.links,
            issues: crawlState.issues,
            stats: crawlState.stats
        });
    }
}

// Rows for external links that were only HEAD-checked (Crawl External off)
// stay out of the Overview unless the External filter is picked: those sites
// were not crawled. The External tab always lists them.
function overviewUrls() {
    return crawlState.urls.filter(url => !url.link_check_only);
}

// Rebuild the URL virtual scrollers from crawlState.urls, honoring the
// active sidebar filter if one is set
function refreshUrlTables() {
    if (isExtractionTabActive()) {
        refreshExtractionTable();
    }

    if (crawlState.filters.active) {
        applyFilter(crawlState.filters.active);
        return;
    }

    if (virtualScrollers.overview) {
        virtualScrollers.overview.setData(sortTableData(overviewUrls(), 'overview'));
    }
    if (virtualScrollers.internal) {
        virtualScrollers.internal.setData(
            sortTableData(crawlState.urls.filter(url => url.is_internal), 'internal')
        );
    }
    if (virtualScrollers.external) {
        virtualScrollers.external.setData(
            sortTableData(crawlState.urls.filter(url => !url.is_internal), 'external')
        );
    }
}

function updateProgressText(data) {
    const progressText = document.getElementById('progressText');
    if (!progressText) return;

    if (data.is_running_pagespeed) {
        progressText.textContent = 'Running PageSpeed analysis...';
    } else if (data.status === 'completed') {
        progressText.textContent = 'Crawl completed';
    } else if (data.status === 'running') {
        const stats = data.stats || crawlState.stats;
        if (stats.crawled === 0) {
            progressText.textContent = 'Starting crawl...';
        } else if (stats.discovered > stats.crawled) {
            progressText.textContent = `Crawling... (${stats.crawled}/${stats.discovered} URLs)`;
        } else {
            progressText.textContent = `Finishing up... (${stats.crawled} URLs crawled)`;
        }
    } else {
        progressText.textContent = 'Initializing...';
    }
}

function updateStatsDisplay() {
    document.getElementById('discoveredCount').textContent = crawlState.stats.discovered;
    document.getElementById('crawledCount').textContent = crawlState.stats.crawled;
    document.getElementById('crawlDepth').textContent = crawlState.stats.depth;
    document.getElementById('crawlSpeed').textContent = crawlState.stats.speed + ' URLs/sec';
}

function updateMemoryDisplay(memoryData, memoryDataSizes) {
    if (!memoryData || !memoryDataSizes) return;

    // Actual data size (deep measurement)
    const dataMB = memoryDataSizes.total_deep_mb || 0;
    document.getElementById('memCurrent').textContent = dataMB.toFixed(1) + ' MB';

    // KB per URL (actual data)
    const kbPerUrl = memoryDataSizes.avg_per_url_kb || 0;
    document.getElementById('memPeak').textContent = kbPerUrl.toFixed(1) + ' KB/URL';

    // Estimate for 1M URLs (data only)
    const estimate1M = (kbPerUrl * 1000000) / 1024; // Convert to MB
    const estimate1MDisplay = estimate1M > 1024
        ? (estimate1M / 1024).toFixed(1) + ' GB'
        : estimate1M.toFixed(0) + ' MB';
    document.getElementById('memEstimate1M').textContent = estimate1MDisplay;

    // System available
    const availableMB = memoryData.system?.available_mb || 0;
    document.getElementById('memAvailable').textContent = availableMB.toFixed(0) + ' MB';
}

function updateCrawlButtons() {
    const startBtn = document.getElementById('startBtn');
    const stopBtn = document.getElementById('stopBtn');
    const clearBtn = document.getElementById('clearBtn');
    const saveCrawlBtn = document.getElementById('saveCrawlBtn');
    const loadCrawlBtn = document.getElementById('loadCrawlBtn');

    // The crawl mode is fixed once a crawl is under way
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.disabled = crawlState.isRunning;
    });
    const listInput = document.getElementById('urlListInput');
    if (listInput) listInput.readOnly = crawlState.isRunning;

    if (crawlState.isRunning) {
        if (crawlState.isPaused) {
            startBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <path d="M8 5v14l11-7z"/>
                </svg>
                Resume
            `;
        } else {
            startBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                    <rect x="6" y="4" width="4" height="16"/>
                    <rect x="14" y="4" width="4" height="16"/>
                </svg>
                Pause
            `;
        }
        startBtn.disabled = false;
        stopBtn.disabled = false;
        clearBtn.disabled = false;
        saveCrawlBtn.disabled = true; // Disable during crawl
        loadCrawlBtn.disabled = true; // Disable during crawl
    } else {
        startBtn.innerHTML = `
            <svg width="16" height="16" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
            </svg>
            Start
        `;
        startBtn.disabled = false;
        stopBtn.disabled = true;
        clearBtn.disabled = false;

        // Save button: only enabled if crawl is completed and has data
        const hasData = crawlState.stats.crawled > 0;
        saveCrawlBtn.disabled = !hasData || isSavingCrawl;

        // Load button: only enabled if no current crawl data
        loadCrawlBtn.disabled = hasData;
    }
}

function showProgress() {
    document.getElementById('progressContainer').style.display = 'flex';
}

function hideProgress() {
    document.getElementById('progressContainer').style.display = 'none';
}

function updateProgress(percentage) {
    document.getElementById('progressFill').style.width = percentage + '%';
}

function updateStatus(message) {
    document.getElementById('statusText').textContent = message;
}

function showDemoLimitNotification() {
    // Remove existing demo notification if any
    const existing = document.getElementById('demoLimitNotification');
    if (existing) existing.remove();

    const overlay = document.createElement('div');
    overlay.id = 'demoLimitNotification';
    overlay.style.cssText = `
        position: fixed; top: 0; left: 0; right: 0; bottom: 0;
        background: rgba(0,0,0,0.6); z-index: 10000;
        display: flex; align-items: center; justify-content: center;
    `;

    const box = document.createElement('div');
    box.style.cssText = `
        background: #1a1a2e; border: 1px solid #f59e0b; border-radius: 12px;
        padding: 32px 40px; max-width: 480px; text-align: center;
        color: #e0e0e0; box-shadow: 0 8px 32px rgba(0,0,0,0.5);
    `;
    box.innerHTML = `
        <div style="font-size: 28px; margin-bottom: 12px;">&#9888;</div>
        <h2 style="color: #f59e0b; margin: 0 0 12px; font-size: 18px;">Demo Memory Limit Reached</h2>
        <p style="margin: 0 0 16px; line-height: 1.5; font-size: 14px;">
            This user has reached the 1.5 GB per-user memory limit.<br>
            Your crawl data has been saved automatically.<br><br>
            <strong>This is a free demo and is not intended for production use.</strong>
        </p>
        <button id="demoLimitDismiss" style="
            background: #f59e0b; color: #000; border: none; padding: 10px 28px;
            border-radius: 6px; font-weight: 600; cursor: pointer; font-size: 14px;
        ">OK</button>
    `;

    overlay.appendChild(box);
    document.body.appendChild(overlay);

    document.getElementById('demoLimitDismiss').addEventListener('click', function() {
        overlay.remove();
    });
}

function updateTimer() {
    if (crawlState.isRunning && crawlState.startTime) {
        const elapsed = new Date() - crawlState.startTime;
        const minutes = Math.floor(elapsed / 60000);
        const seconds = Math.floor((elapsed % 60000) / 1000);
        document.getElementById('crawlTime').textContent =
            `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
    }
}

// ------------------------------------------------------------------
// Per-user column visibility + header sorting for the URL tables
// ------------------------------------------------------------------

const TABLE_NAMES = ['overview', 'internal', 'external'];

async function loadTablePreferences() {
    let preferences = {};
    try {
        const response = await fetch('/api/ui/preferences');
        if (response.ok) {
            const data = await response.json();
            if (data.success && data.preferences) {
                preferences = data.preferences;
            }
        }
    } catch (error) {
        console.warn('Could not load table column preferences:', error);
    }

    TABLE_NAMES.forEach(tableName => {
        const entry = preferences[tableName];
        const hidden = entry && Array.isArray(entry.hidden) ? entry.hidden : [];
        const validKeys = new Set(TABLE_COLUMNS[tableName].map(column => column.key));
        const hiddenSet = new Set(hidden.filter(key => validKeys.has(key)));

        // Never hide every column - the table would become unusable.
        if (hiddenSet.size === TABLE_COLUMNS[tableName].length) {
            hiddenSet.delete(TABLE_COLUMNS[tableName][0].key);
        }
        tableHiddenColumns[tableName] = hiddenSet;
    });
}

async function saveTablePreferences() {
    const preferences = {};
    TABLE_NAMES.forEach(tableName => {
        preferences[tableName] = {
            hidden: Array.from(tableHiddenColumns[tableName])
        };
    });

    try {
        const response = await fetch('/api/ui/preferences', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ preferences })
        });
        const data = await response.json();
        if (!data.success) {
            showNotification('Column preferences could not be saved', 'warning');
        }
    } catch (error) {
        console.error('Could not save table column preferences:', error);
        showNotification('Column preferences could not be saved', 'warning');
    }
}

function rawOverviewValue(urlData, key) {
    switch (key) {
        case 'url': return urlData.url || '';
        case 'status_code': return urlData.status_code;
        case 'title': return urlData.title || '';
        case 'meta_description': return urlData.meta_description || '';
        case 'h1': return urlData.h1 || '';
        case 'keywords': return urlData.keywords || '';
        case 'word_count': return Number(urlData.word_count || 0);
        case 'response_time': return Number(urlData.response_time || 0);
        case 'analytics': return formatAnalyticsInfo(urlData.analytics || {});
        case 'og_tags': return Object.keys(urlData.og_tags || {}).length;
        case 'json_ld': return (urlData.json_ld || []).length;
        case 'links': return Number(urlData.internal_links || 0) + Number(urlData.external_links || 0);
        case 'images': return (urlData.images || []).length;
        case 'javascript_rendered': return urlData.javascript_rendered ? 1 : 0;
        default: return rawAnalysisValue(urlData, key);
    }
}

// Unique inlinks. The exact count arrives with the end-of-crawl analysis;
// until then the live linked_from length is a close stand-in (O(1), as
// this runs inside sort comparators).
function inlinkCount(urlData) {
    if (typeof urlData.inlinks === 'number') return urlData.inlinks;
    if (!urlData.is_internal) return null;
    return (urlData.linked_from || []).length;
}

// Columns shared by the Overview and Internal tables
function rawAnalysisValue(urlData, key) {
    switch (key) {
        case 'indexability': return urlData.indexability || '';
        case 'indexability_status': return urlData.indexability_status || '';
        case 'inlinks': return inlinkCount(urlData);
        case 'link_score': return typeof urlData.link_score === 'number' ? urlData.link_score : null;
        case 'in_sitemap':
            if (urlData.in_sitemap === true) return 'Yes';
            if (urlData.in_sitemap === false) return 'No';
            return '';
        default: return '';
    }
}

function rawUrlValue(urlData, key) {
    switch (key) {
        case 'url': return urlData.url || '';
        case 'status_code': return urlData.status_code;
        case 'content_type': return urlData.content_type || '';
        case 'size': return Number(urlData.size || 0);
        case 'title': return urlData.title || '';
        default: return rawAnalysisValue(urlData, key);
    }
}

function rawColumnValue(tableName, urlData, key) {
    if (tableName === 'overview') {
        return rawOverviewValue(urlData, key);
    }
    return rawUrlValue(urlData, key);
}

function displayColumnValue(tableName, urlData, key) {
    const raw = rawColumnValue(tableName, urlData, key);

    if (tableName === 'overview') {
        if (key === 'meta_description') {
            return raw.length > 50 ? raw.substring(0, 50) + '...' : raw;
        }
        if (key === 'og_tags') return raw ? `${raw} tags` : '';
        if (key === 'json_ld') return raw ? `${raw} scripts` : '';
        if (key === 'links') {
            return `${urlData.internal_links || 0}/${urlData.external_links || 0}`;
        }
        if (key === 'images') return raw ? `${raw} images` : '';
        if (key === 'javascript_rendered') return raw ? '✅ JS' : '';
    }

    if (raw === null || raw === undefined) return '';
    return String(raw);
}

function sortTableData(data, tableName) {
    const sort = tableSortState[tableName];
    if (!sort) return data;

    const column = TABLE_COLUMNS[tableName].find(c => c.key === sort.key);
    if (!column || !column.sortable) return data;

    const direction = sort.direction === 'desc' ? -1 : 1;

    return data.slice().sort((a, b) => {
        const aValue = rawColumnValue(tableName, a, sort.key);
        const bValue = rawColumnValue(tableName, b, sort.key);

        if (aValue == null && bValue == null) {
            return String(a.url || '').localeCompare(String(b.url || '')) * direction;
        }
        if (aValue == null) return 1;
        if (bValue == null) return -1;

        let result;
        if (typeof aValue === 'number' && typeof bValue === 'number') {
            result = aValue - bValue;
        } else {
            result = String(aValue).localeCompare(String(bValue), undefined, { sensitivity: 'base' });
        }

        if (result === 0) {
            result = String(a.url || '').localeCompare(String(b.url || ''));
        }
        return result * direction;
    });
}

function setupTableHeader(tableName) {
    const table = document.getElementById(`${tableName}Table`);
    if (!table) return;

    const headers = table.querySelectorAll('thead th');
    headers.forEach((th, index) => {
        const column = TABLE_COLUMNS[tableName][index];
        if (!column) return;

        th.dataset.col = column.key;

        if (column.sortable) {
            th.classList.add('sortable');
            th.addEventListener('click', event => {
                if (event.target.classList.contains('column-resize-grip')) return;
                handleTableSort(tableName, column.key);
            });

            const indicator = document.createElement('span');
            indicator.className = 'sort-indicator';
            indicator.setAttribute('aria-hidden', 'true');
            th.appendChild(indicator);
        }

        if (tableHiddenColumns[tableName].has(column.key)) {
            th.classList.add('column-hidden');
        }
    });
}

function createTableColumnToolbar(tableName) {
    const pane = document.getElementById(`${tableName}-tab`);
    if (!pane) return;

    const container = pane.querySelector('.table-container');
    if (!container) return;

    const toolbar = document.createElement('div');
    toolbar.className = 'table-toolbar';

    const row = document.createElement('div');
    row.className = 'table-toolbar-row';

    const left = document.createElement('div');
    left.className = 'table-toolbar-left';

    const columnsButton = document.createElement('button');
    columnsButton.type = 'button';
    columnsButton.className = 'column-toggle-btn';
    columnsButton.setAttribute('aria-haspopup', 'true');
    columnsButton.setAttribute('aria-expanded', 'false');
    columnsButton.innerHTML =
        '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">' +
        '<rect x="1.75" y="2.75" width="12.5" height="10.5" rx="1.5"/><path d="M6 2.75v10.5M10 2.75v10.5"/></svg>' +
        '<span>Columns</span>' +
        '<svg class="caret" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.75" aria-hidden="true">' +
        '<path d="M4.5 6.5 8 10l3.5-3.5"/></svg>';

    const hint = document.createElement('span');
    hint.className = 'table-toolbar-hint';
    hint.textContent = 'Click a column header to sort ascending/descending';

    const menu = document.createElement('div');
    menu.className = 'column-menu';
    menu.hidden = true;

    left.appendChild(columnsButton);
    left.appendChild(menu);
    row.appendChild(left);
    row.appendChild(hint);

    TABLE_COLUMNS[tableName].forEach(column => {
        const label = document.createElement('label');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.dataset.col = column.key;
        checkbox.checked = !tableHiddenColumns[tableName].has(column.key);

        checkbox.addEventListener('change', () => {
            if (checkbox.checked) {
                tableHiddenColumns[tableName].delete(column.key);
            } else {
                tableHiddenColumns[tableName].add(column.key);
            }

            // Keep at least one visible column.
            if (tableHiddenColumns[tableName].size === TABLE_COLUMNS[tableName].length) {
                tableHiddenColumns[tableName].delete(column.key);
                checkbox.checked = true;
            }

            applyColumnVisibility(tableName);
            saveTablePreferences();
        });

        label.appendChild(checkbox);
        label.appendChild(document.createTextNode(' ' + column.label));
        menu.appendChild(label);
    });

    const resetButton = document.createElement('button');
    resetButton.type = 'button';
    resetButton.className = 'column-menu-reset';
    resetButton.textContent = 'Show all columns';
    resetButton.addEventListener('click', () => {
        tableHiddenColumns[tableName].clear();
        menu.querySelectorAll('input[type="checkbox"]').forEach(cb => {
            cb.checked = true;
        });
        applyColumnVisibility(tableName);
        saveTablePreferences();
    });
    menu.appendChild(resetButton);

    const setMenuOpen = open => {
        menu.hidden = !open;
        columnsButton.setAttribute('aria-expanded', String(open));
    };

    columnsButton.addEventListener('click', () => {
        setMenuOpen(menu.hidden);
    });

    // Close the dropdown on outside click or Escape.
    document.addEventListener('click', event => {
        if (!menu.hidden && !left.contains(event.target)) setMenuOpen(false);
    });
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && !menu.hidden) setMenuOpen(false);
    });

    toolbar.appendChild(row);
    pane.insertBefore(toolbar, container);
    tableColumnMenus[tableName] = menu;
}

function setupTableColumnControls() {
    TABLE_NAMES.forEach(tableName => {
        setupTableHeader(tableName);
        createTableColumnToolbar(tableName);
    });

    TABLE_NAMES.forEach(tableName => {
        applyColumnVisibility(tableName);
    });
}

function applyColumnVisibility(tableName) {
    const table = document.getElementById(`${tableName}Table`);
    if (!table) return;

    const hidden = tableHiddenColumns[tableName];

    table.querySelectorAll('thead th[data-col]').forEach(th => {
        th.classList.toggle('column-hidden', hidden.has(th.dataset.col));
    });

    table.querySelectorAll('tbody td[data-col]').forEach(cell => {
        cell.classList.toggle('column-hidden', hidden.has(cell.dataset.col));
    });

    updateScrollerColumnCount(tableName);
}

function updateScrollerColumnCount(tableName) {
    const scroller = virtualScrollers[tableName];
    if (!scroller) return;

    const visibleCount = TABLE_COLUMNS[tableName].filter(
        column => !tableHiddenColumns[tableName].has(column.key)
    ).length || 1;

    if (scroller.topSpacer && scroller.topSpacer.firstChild) {
        scroller.topSpacer.firstChild.colSpan = visibleCount;
    }
    if (scroller.bottomSpacer && scroller.bottomSpacer.firstChild) {
        scroller.bottomSpacer.firstChild.colSpan = visibleCount;
    }
}

function handleTableSort(tableName, key) {
    const column = TABLE_COLUMNS[tableName].find(c => c.key === key);
    if (!column || !column.sortable) return;

    const current = tableSortState[tableName];
    if (current && current.key === key) {
        tableSortState[tableName] = {
            key,
            direction: current.direction === 'asc' ? 'desc' : 'asc'
        };
    } else {
        tableSortState[tableName] = { key, direction: 'asc' };
    }

    updateSortIndicators(tableName);
    refreshUrlTables();
}

function updateSortIndicators(tableName) {
    const table = document.getElementById(`${tableName}Table`);
    if (!table) return;

    const sort = tableSortState[tableName];
    table.querySelectorAll('thead th').forEach(th => {
        const indicator = th.querySelector('.sort-indicator');
        if (!indicator) return;

        const active = sort && sort.key === th.dataset.col;
        indicator.textContent = active
            ? (sort.direction === 'asc' ? ' ↑' : ' ↓')
            : '';
        th.classList.toggle('sorted', active);
    });
}

// Table Management
function initializeTables() {
    // Clear any existing data first
    clearAllTables();
    // Initialize virtual scrollers for all tables
    initializeVirtualScrollers();
    // Attach column controls and sorting to the URL tables
    setupTableColumnControls();
    // Initialize column resizers after virtual scrollers
    setTimeout(() => {
        if (window.initializeColumnResizers) {
            initializeColumnResizers();
        }
    }, 100);
}

function initializeVirtualScrollers() {
    try {
        // Overview table
        const overviewContainer = document.querySelector('#overview-tab .table-container');
        if (overviewContainer && overviewContainer.querySelector('tbody')) {
            virtualScrollers.overview = new VirtualScroller(overviewContainer, {
                rowHeight: 100,
                buffer: 25,
                renderRow: renderOverviewRow
            });
            console.log('Overview virtual scroller initialized');
        }

        // Internal URLs table
        const internalContainer = document.querySelector('#internal-tab .table-container');
        if (internalContainer && internalContainer.querySelector('tbody')) {
            virtualScrollers.internal = new VirtualScroller(internalContainer, {
                rowHeight: 80,
                buffer: 25,
                renderRow: renderInternalRow
            });
            console.log('Internal virtual scroller initialized');
        }

        // External URLs table
        const externalContainer = document.querySelector('#external-tab .table-container');
        if (externalContainer && externalContainer.querySelector('tbody')) {
            virtualScrollers.external = new VirtualScroller(externalContainer, {
                rowHeight: 80,
                buffer: 25,
                renderRow: renderExternalRow
            });
            console.log('External virtual scroller initialized');
        }

        // Internal Links table
        const internalLinksContainer = document.querySelector('#links-tab .internal-links-container');
        if (internalLinksContainer && internalLinksContainer.querySelector('tbody')) {
            virtualScrollers.internalLinks = new VirtualScroller(internalLinksContainer, {
                rowHeight: 80,
                buffer: 25,
                renderRow: renderInternalLinkRow
            });
            console.log('Internal links virtual scroller initialized');
        }

        // External Links table
        const externalLinksContainer = document.querySelector('#links-tab .external-links-container');
        if (externalLinksContainer && externalLinksContainer.querySelector('tbody')) {
            virtualScrollers.externalLinks = new VirtualScroller(externalLinksContainer, {
                rowHeight: 80,
                buffer: 25,
                renderRow: renderExternalLinkRow
            });
            console.log('External links virtual scroller initialized');
        }

        // Custom extraction table (columns follow the extractors)
        const extractionContainer = document.querySelector('#extraction-tab .table-container');
        if (extractionContainer && extractionContainer.querySelector('tbody')) {
            virtualScrollers.extraction = new VirtualScroller(extractionContainer, {
                rowHeight: 60,
                buffer: 25,
                renderRow: renderExtractionRow
            });
        }

        // N-grams table
        const ngramsContainer = document.querySelector('#ngrams-tab .table-container');
        if (ngramsContainer && ngramsContainer.querySelector('tbody')) {
            virtualScrollers.ngrams = new VirtualScroller(ngramsContainer, {
                rowHeight: 60,
                buffer: 25,
                renderRow: renderNgramRow
            });
            console.log('N-grams virtual scroller initialized');
        }

        // Crawl comparison table
        const compareContainer = document.querySelector('#compare-tab .table-container');
        if (compareContainer && compareContainer.querySelector('tbody')) {
            virtualScrollers.compare = new VirtualScroller(compareContainer, {
                rowHeight: 60,
                buffer: 25,
                renderRow: renderCompareRow
            });
        }

        // Issues table
        const issuesContainer = document.querySelector('#issues-tab .table-container');
        if (issuesContainer && issuesContainer.querySelector('tbody')) {
            virtualScrollers.issues = new VirtualScroller(issuesContainer, {
                rowHeight: 80,
                buffer: 25,
                renderRow: renderIssueRow
            });
            console.log('Issues virtual scroller initialized');
        }
    } catch (error) {
        console.error('Error initializing virtual scrollers:', error);
    }
}

function isLinksTabActive() {
    const linksTab = document.getElementById('links-tab');
    return linksTab && linksTab.classList.contains('active');
}

function isExtractionTabActive() {
    const tab = document.getElementById('extraction-tab');
    return tab && tab.classList.contains('active');
}

// Rows with extraction results; the table only redraws while its
// tab is showing, and catches up when the tab is opened
function refreshExtractionTable() {
    const scroller = virtualScrollers.extraction;
    if (!scroller) return;

    const rows = crawlState.urls.filter(u => u.custom_extraction);
    const names = [];
    const seen = new Set();
    rows.forEach(u => Object.keys(u.custom_extraction).forEach(name => {
        if (!seen.has(name)) {
            seen.add(name);
            names.push(name);
        }
    }));

    if (names.join('\u0000') !== extractionColumns.join('\u0000')) {
        extractionColumns = names;
        rebuildExtractionHeader();
    }

    const empty = document.getElementById('extractionEmpty');
    if (empty) empty.style.display = rows.length ? 'none' : 'block';
    scroller.setData(rows);
}

function rebuildExtractionHeader() {
    const headerRow = document.getElementById('extractionHeaderRow');
    if (!headerRow) return;
    headerRow.innerHTML = '';
    ['Address', 'Status', ...extractionColumns].forEach(label => {
        const th = document.createElement('th');
        th.textContent = label;
        headerRow.appendChild(th);
    });

    // Spacer rows span the whole table
    const scroller = virtualScrollers.extraction;
    if (scroller) {
        scroller.topSpacer.firstChild.colSpan = extractionColumns.length + 2;
        scroller.bottomSpacer.firstChild.colSpan = extractionColumns.length + 2;
    }
    if (window.ColumnResizer) {
        new ColumnResizer(document.getElementById('extractionTable'));
    }
}

function renderExtractionRow(row, urlData) {
    const status = urlData.status_code ||
        getStatusCodeText(0, urlData.error_type);
    row.appendChild(makeTextCell(urlData.url, 'break-all'));
    row.appendChild(makeTextCell(status));

    const extracted = urlData.custom_extraction || {};
    extractionColumns.forEach(name => {
        const values = extracted[name] || [];
        const full = values.join(' | ');
        const shown = full.length > 300 ? full.substring(0, 300) + '…' : full;
        const cell = makeTextCell(shown, 'break-word');
        if (shown !== full) cell.title = full;
        if (values.length > 1) cell.dataset.count = values.length;
        row.appendChild(cell);
    });
}

// TIL: Its n-gram not engram. Thanks Cyberpunk
// N-gram analysis
let ngramRows = [];

function isNgramsTabActive() {
    const tab = document.getElementById('ngrams-tab');
    return tab && tab.classList.contains('active');
}

async function loadNgrams() {
    const sizeSelect = document.getElementById('ngramSize');
    const urlFilter = document.getElementById('ngramUrlFilter');
    const statusEl = document.getElementById('ngramStatus');
    const n = sizeSelect ? parseInt(sizeSelect.value, 10) : 1;
    const activeFilter = crawlState.filters.active;

    statusEl.textContent = 'Analyzing…';
    const params = new URLSearchParams({ n: String(n) });
    if (activeFilter) {
        params.set('filter', activeFilter);
    }
    if (urlFilter && urlFilter.value.trim()) {
        params.set('url', urlFilter.value.trim());
    }

    try {
        const response = await fetch('/api/ngrams?' + params.toString());
        const data = await response.json();
        if (!data.success) {
            statusEl.textContent = data.error || 'N-gram analysis failed';
            return;
        }
        ngramRows = data.ngrams || [];
        statusEl.textContent = `${data.url_count} URL(s), ${ngramRows.length} n-gram(s)`
            + (activeFilter ? ` [filter: ${activeFilter}]` : '');
        renderNgrams(ngramRows);
    } catch (error) {
        statusEl.textContent = 'N-gram analysis failed';
    }
}

function renderNgrams(rows) {
    const scroller = virtualScrollers.ngrams;
    const empty = document.getElementById('ngramsEmptyState');
    if (!scroller) return;

    if (!rows.length) {
        empty.style.display = 'block';
        scroller.setData([]);
        return;
    }
    empty.style.display = 'none';
    scroller.setData(rows);
}

function renderNgramRow(row, ngram) {
    row.appendChild(makeTextCell(ngram.gram, 'break-word'));
    row.appendChild(makeTextCell(ngram.body));
    row.appendChild(makeTextCell(ngram.density + '%'));
    row.appendChild(makeTextCell(ngram.body_unlinked));
    row.appendChild(makeTextCell(ngram.headings));
    row.appendChild(makeTextCell(ngram.title));
    row.appendChild(makeTextCell(ngram.inlinks_anchor));
    row.appendChild(makeTextCell(ngram.inlinks_alt));
    row.appendChild(makeTextCell(ngram.total));
}

function filterNgrams() {
    const query = document.getElementById('ngramSearch').value.trim().toLowerCase();
    renderNgrams(query ? ngramRows.filter(r => r.gram.toLowerCase().includes(query)) : ngramRows);
}

function exportNgrams() {
    if (!ngramRows.length) return;
    const headers = ['gram', 'body', 'density', 'body_unlinked', 'headings', 'title', 'inlinks_anchor', 'inlinks_alt', 'total', 'url_count'];
    const lines = [headers.join(',')];
    ngramRows.forEach(row => {
        lines.push(headers.map(key => {
            const value = row[key] === undefined ? '' : String(row[key]);
            return '"' + value.replace(/"/g, '""') + '"';
        }).join(','));
    });
    const blob = new Blob([lines.join('\n')], { type: 'text/csv' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'ngrams.csv';
    link.click();
    URL.revokeObjectURL(link.href);
}

// ========================================
// Crawl comparison
// ========================================
let compareResult = null;
let compareKindFilter = 'all';
let compareLabels = {};
const compareState = { currentId: null, previousId: null };

async function loadCompareOptions() {
    const select = document.getElementById('compareCrawlSelect');
    const statusEl = document.getElementById('compareStatus');
    if (!select) return;

    try {
        const [statusResponse, listResponse] = await Promise.all([
            fetch('/api/crawl_status?stats_only=1'),
            fetch('/api/crawls/list?limit=200')
        ]);
        const status = await statusResponse.json();
        const list = await listResponse.json();
        const currentId = status.crawl_id;
        compareState.currentId = currentId;

        if (!list.success) {
            statusEl.textContent = list.error || 'Could not load saved crawls';
            return;
        }

        const current = (list.crawls || []).find(c => c.id === currentId);
        const currentDomain = current ? current.base_domain : null;
        const others = (list.crawls || []).filter(c => c.id !== currentId);
        // Same site first, newest first within each group (the list is
        // already newest first)
        others.sort((a, b) => (b.base_domain === currentDomain) - (a.base_domain === currentDomain));

        const previous = select.value;
        select.innerHTML = '';
        if (!currentId) {
            statusEl.textContent = 'Run or load a crawl first; it becomes the "current" side.';
        } else if (!others.length) {
            statusEl.textContent = 'No other saved crawls to compare with yet.';
        } else {
            statusEl.textContent = '';
        }
        others.forEach(c => {
            const option = document.createElement('option');
            option.value = c.id;
            const when = c.started_at ? String(c.started_at).replace('T', ' ').slice(0, 16) : '';
            option.textContent = `#${c.id} ${c.base_url} · ${when} · ${c.urls_crawled || 0} URLs` +
                (c.status && c.status !== 'completed' ? ` (${c.status})` : '');
            select.appendChild(option);
        });
        if (previous && others.some(c => String(c.id) === previous)) {
            select.value = previous;
        }
    } catch (error) {
        statusEl.textContent = 'Could not load saved crawls';
    }
}

async function runCompare() {
    const select = document.getElementById('compareCrawlSelect');
    const statusEl = document.getElementById('compareStatus');
    if (!select || !select.value) {
        statusEl.textContent = 'Pick a crawl to compare with.';
        return;
    }

    statusEl.textContent = 'Comparing…';
    const params = new URLSearchParams({ previous: select.value });
    try {
        const response = await fetch('/api/crawls/compare?' + params.toString());
        const data = await response.json();
        if (!data.success) {
            statusEl.textContent = data.error || 'Comparison failed';
            return;
        }
        compareResult = data;
        compareLabels = {};
        data.change_kinds.forEach(kind => { compareLabels[kind.key] = kind.label; });
        compareState.previousId = data.previous.id;
        compareState.currentId = data.current.id;
        compareKindFilter = 'all';

        const filter = document.getElementById('compareChangeFilter');
        filter.innerHTML = '<option value="all">All changes</option>';
        data.change_kinds.forEach(kind => {
            const option = document.createElement('option');
            option.value = kind.key;
            option.textContent = `${kind.label} (${data.summary.changes[kind.key] || 0})`;
            filter.appendChild(option);
        });

        statusEl.textContent = `#${data.previous.id} → #${data.current.id}: ` +
            `${data.total_changes.toLocaleString()} change(s)` +
            (data.truncated ? ` (showing the first ${data.changes.length.toLocaleString()}; export CSV for all)` : '');
        renderCompareSummary(data);
        filterCompareChanges();
    } catch (error) {
        statusEl.textContent = 'Comparison failed';
    }
}

function renderCompareSummary(data) {
    const container = document.getElementById('compareSummary');
    container.innerHTML = '';

    const cards = document.createElement('div');
    cards.className = 'compare-cards';

    const totals = document.createElement('div');
    totals.className = 'compare-card';
    totals.style.cursor = 'default';
    const strong = document.createElement('strong');
    strong.textContent = `${data.summary.previous_urls.toLocaleString()} → ${data.summary.current_urls.toLocaleString()}`;
    totals.appendChild(strong);
    totals.appendChild(document.createTextNode('URLs'));
    cards.appendChild(totals);

    data.change_kinds.forEach(kind => {
        const count = data.summary.changes[kind.key] || 0;
        const card = document.createElement('button');
        card.type = 'button';
        card.className = 'compare-card' + (count ? '' : ' zero');
        card.dataset.kind = kind.key;
        const value = document.createElement('strong');
        value.textContent = count.toLocaleString();
        card.appendChild(value);
        card.appendChild(document.createTextNode(kind.label));
        card.addEventListener('click', () => {
            const filter = document.getElementById('compareChangeFilter');
            filter.value = filter.value === kind.key ? 'all' : kind.key;
            filterCompareChanges();
        });
        cards.appendChild(card);
    });
    container.appendChild(cards);

    // Only issue types whose count moved; unchanged ones are noise here
    const movedIssues = (data.issue_changes || []).filter(change => change.delta !== 0);
    if (movedIssues.length) {
        const wrap = document.createElement('div');
        wrap.className = 'compare-issues';
        const table = document.createElement('table');
        const head = table.createTHead().insertRow();
        ['Issue', 'Type', 'Previous', 'Current', 'Change'].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            head.appendChild(th);
        });
        const body = table.createTBody();
        movedIssues.forEach(change => {
            const row = body.insertRow();
            [change.issue, change.type, change.previous, change.current].forEach(value => {
                row.insertCell().textContent = value;
            });
            const delta = row.insertCell();
            delta.textContent = change.delta > 0 ? `+${change.delta}` : String(change.delta);
            if (change.delta > 0) delta.className = 'compare-delta-up';
            else if (change.delta < 0) delta.className = 'compare-delta-down';
        });
        wrap.appendChild(table);
        container.appendChild(wrap);
    }
}

function filterCompareChanges() {
    const scroller = virtualScrollers.compare;
    const empty = document.getElementById('compareEmptyState');
    if (!scroller) return;
    if (!compareResult) {
        scroller.setData([]);
        return;
    }

    compareKindFilter = document.getElementById('compareChangeFilter').value;
    const query = document.getElementById('compareSearch').value.trim().toLowerCase();

    let rows = compareResult.changes;
    if (compareKindFilter !== 'all') {
        rows = rows.filter(c => c.change === compareKindFilter);
    }
    if (query) {
        rows = rows.filter(c =>
            c.url.toLowerCase().includes(query) ||
            String(c.previous).toLowerCase().includes(query) ||
            String(c.current).toLowerCase().includes(query));
    }

    document.querySelectorAll('#compareSummary .compare-card[data-kind]').forEach(card => {
        card.classList.toggle('active', card.dataset.kind === compareKindFilter);
    });

    if (empty) {
        empty.style.display = rows.length ? 'none' : 'flex';
        const title = empty.querySelector('h3');
        const text = empty.querySelector('p');
        if (title) title.textContent = 'No Changes';
        if (text) text.textContent = compareResult.total_changes
            ? 'Nothing matches the current filter.'
            : 'These two crawls match on every compared field.';
    }
    scroller.setData(rows);
}

function exportCompareCsv() {
    if (!compareState.previousId || !compareState.currentId) {
        showNotification('Run a comparison first', 'warning');
        return;
    }
    const params = new URLSearchParams({
        previous: compareState.previousId,
        current: compareState.currentId,
        format: 'csv'
    });
    window.location.href = '/api/crawls/compare?' + params.toString();
}

function renderCompareRow(row, change) {
    const urlCell = makeTextCell(change.url, 'break-all');
    urlCell.title = change.url;
    row.appendChild(urlCell);
    row.appendChild(makeTextCell(compareLabels[change.change] || change.change));
    const previous = makeTextCell(change.previous, 'break-word');
    previous.title = change.previous;
    row.appendChild(previous);
    const current = makeTextCell(change.current, 'break-word');
    current.title = change.current;
    row.appendChild(current);
}

function isIssuesTabActive() {
    const issuesTab = document.getElementById('issues-tab');
    return issuesTab && issuesTab.classList.contains('active');
}

function updateLinksTable(links) {
    // Create a lookup map of URL statuses from crawled URLs
    const urlStatusMap = new Map();
    if (crawlState.urls && crawlState.urls.length > 0) {
        crawlState.urls.forEach(url => {
            urlStatusMap.set(url.url, url.status_code);
        });
    }

    // Remove duplicates from links array (extra safety check)
    const uniqueLinks = [];
    const seenLinks = new Set();
    links.forEach(link => {
        const key = `${link.source_url}|${link.target_url}`;
        if (!seenLinks.has(key)) {
            seenLinks.add(key);

            // Update target status with actual crawled status if available
            const crawledStatus = urlStatusMap.get(link.target_url);
            if (crawledStatus) {
                link.target_status = crawledStatus;
            }

            uniqueLinks.push(link);
        }
    });

    // Store unfiltered links in crawlState
    crawlState.links = uniqueLinks;

    // Apply filters and update virtual scrollers
    applyLinksFilter();

    console.log(`Links loaded: ${crawlState.links.filter(l => l.is_internal).length} internal, ${crawlState.links.filter(l => !l.is_internal).length} external`);
}

function applyLinksFilter() {
    if (!crawlState.links || crawlState.links.length === 0) return;

    // Separate internal and external links
    let internalLinks = crawlState.links.filter(link => link.is_internal);
    let externalLinks = crawlState.links.filter(link => !link.is_internal);

    // Apply status code filter for internal links
    const internalStatusFilter = crawlState.filters.linksFilter.internalStatusCode;
    if (internalStatusFilter && internalStatusFilter !== 'all') {
        internalLinks = internalLinks.filter(link => {
            if (!link.target_status) return false;
            const status = parseInt(link.target_status);
            switch (internalStatusFilter) {
                case '2xx': return status >= 200 && status < 300;
                case '3xx': return status >= 300 && status < 400;
                case '4xx': return status >= 400 && status < 500;
                case '5xx': return status >= 500;
                default: return true;
            }
        });
    }

    // Apply search filter for internal links
    const internalSearch = crawlState.filters.linksFilter.internalSearch.toLowerCase();
    if (internalSearch) {
        internalLinks = internalLinks.filter(link =>
            link.source_url.toLowerCase().includes(internalSearch) ||
            link.target_url.toLowerCase().includes(internalSearch) ||
            (link.anchor_text && link.anchor_text.toLowerCase().includes(internalSearch))
        );
    }

    // Apply status code filter for external links
    const externalStatusFilter = crawlState.filters.linksFilter.externalStatusCode;
    if (externalStatusFilter && externalStatusFilter !== 'all') {
        externalLinks = externalLinks.filter(link => {
            if (!link.target_status) return false;
            const status = parseInt(link.target_status);
            switch (externalStatusFilter) {
                case '2xx': return status >= 200 && status < 300;
                case '3xx': return status >= 300 && status < 400;
                case '4xx': return status >= 400 && status < 500;
                case '5xx': return status >= 500;
                default: return true;
            }
        });
    }

    // Apply search filter for external links
    const externalSearch = crawlState.filters.linksFilter.externalSearch.toLowerCase();
    if (externalSearch) {
        externalLinks = externalLinks.filter(link =>
            link.source_url.toLowerCase().includes(externalSearch) ||
            link.target_url.toLowerCase().includes(externalSearch) ||
            (link.target_domain && link.target_domain.toLowerCase().includes(externalSearch))
        );
    }

    // Update virtual scrollers with filtered data
    if (virtualScrollers.internalLinks) {
        virtualScrollers.internalLinks.setData(internalLinks);
    }

    if (virtualScrollers.externalLinks) {
        virtualScrollers.externalLinks.setData(externalLinks);
    }
}

function filterInternalLinks(filterType) {
    crawlState.filters.linksFilter.internalStatusCode = filterType;
    applyLinksFilter();
}

function filterExternalLinks(filterType) {
    crawlState.filters.linksFilter.externalStatusCode = filterType;
    applyLinksFilter();
}

function searchInternalLinks(searchText) {
    crawlState.filters.linksFilter.internalSearch = searchText;
    applyLinksFilter();
}

function searchExternalLinks(searchText) {
    crawlState.filters.linksFilter.externalSearch = searchText;
    applyLinksFilter();
}

function updateIssuesTable(issues) {
    if (!issues || !Array.isArray(issues)) {
        issues = [];
    }

    // Store issues globally for filtering
    window.currentIssues = issues;

    const emptyState = document.getElementById('issuesEmptyState');
    const issuesTable = document.getElementById('issuesTable');

    // Count by type
    let errorCount = 0;
    let warningCount = 0;
    let infoCount = 0;

    issues.forEach(issue => {
        if (issue.type === 'error') errorCount++;
        else if (issue.type === 'warning') warningCount++;
        else if (issue.type === 'info') infoCount++;
    });

    // Update filter counts
    document.getElementById('issues-all-count').textContent = `(${issues.length})`;
    document.getElementById('issues-error-count').textContent = `(${errorCount})`;
    document.getElementById('issues-warning-count').textContent = `(${warningCount})`;
    document.getElementById('issues-info-count').textContent = `(${infoCount})`;

    // Show/hide empty state
    if (issues.length === 0) {
        if (emptyState) emptyState.style.display = 'block';
        if (issuesTable) issuesTable.style.display = 'none';
    } else {
        if (emptyState) emptyState.style.display = 'none';
        if (issuesTable) issuesTable.style.display = 'table';

        // Use virtual scroller for issues
        if (virtualScrollers.issues) {
            virtualScrollers.issues.setData(issues);
        }
    }

    // Update issue count in tab button (find the button, not the tab content)
    const issuesTabButton = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.textContent.includes('Issues'));
    if (issuesTabButton) {
        const totalIssues = issues.length;
        if (totalIssues > 0) {
            let badgeColor = '#3b82f6';
            if (errorCount > 0) badgeColor = '#ef4444';
            else if (warningCount > 0) badgeColor = '#f59e0b';

            issuesTabButton.innerHTML = `Issues <span style="background: ${badgeColor}; color: white; padding: 2px 6px; border-radius: 12px; font-size: 12px;">${totalIssues}</span>`;
        } else {
            issuesTabButton.innerHTML = 'Issues';
        }
    }
}

function clearAllTables() {
    // Clear virtual scrollers if they exist
    if (virtualScrollers.overview) {
        virtualScrollers.overview.clear();
    }
    if (virtualScrollers.internal) {
        virtualScrollers.internal.clear();
    }
    if (virtualScrollers.external) {
        virtualScrollers.external.clear();
    }
    if (virtualScrollers.internalLinks) {
        virtualScrollers.internalLinks.clear();
    }
    if (virtualScrollers.externalLinks) {
        virtualScrollers.externalLinks.clear();
    }
    if (virtualScrollers.issues) {
        virtualScrollers.issues.clear();
    }
    if (virtualScrollers.extraction) {
        virtualScrollers.extraction.clear();
    }
    if (extractionColumns.length) {
        extractionColumns = [];
        rebuildExtractionHeader();
    }
    const extractionEmpty = document.getElementById('extractionEmpty');
    if (extractionEmpty) extractionEmpty.style.display = 'block';

    ngramRows = [];
    if (virtualScrollers.ngrams) {
        virtualScrollers.ngrams.clear();
    }

    // A new crawl changes the "current" side, so a shown diff is stale
    compareResult = null;
    compareState.previousId = null;
    if (virtualScrollers.compare) {
        virtualScrollers.compare.clear();
    }
    const compareSummary = document.getElementById('compareSummary');
    if (compareSummary) compareSummary.innerHTML = '';
    const compareStatus = document.getElementById('compareStatus');
    if (compareStatus) compareStatus.textContent = '';
    const ngramEmpty = document.getElementById('ngramsEmptyState');
    if (ngramEmpty) ngramEmpty.style.display = 'block';

    // Clear status codes table (not virtualized)
    const statusCodesBody = document.getElementById('statusCodesTableBody');
    if (statusCodesBody) statusCodesBody.innerHTML = '';

    crawlState.urls = [];

    console.log('All tables cleared');
}

function formatAnalyticsInfo(analytics) {
    const detected = [];
    if (analytics.gtag || analytics.ga4_id) detected.push('GA4');
    if (analytics.google_analytics) detected.push('GA');
    if (analytics.gtm_id) detected.push('GTM');
    if (analytics.facebook_pixel) detected.push('FB');
    if (analytics.hotjar) detected.push('HJ');
    if (analytics.mixpanel) detected.push('MP');

    return detected.length > 0 ? detected.join(', ') : '';
}

function addUrlToTable(urlData) {
    // Check if URL already exists to prevent duplicates
    const existingUrl = crawlState.urls.find(u => u.url === urlData.url);
    if (existingUrl) {
        return; // Skip duplicate
    }

    crawlState.urls.push(urlData);

    // Update virtual scrollers with new data
    if (virtualScrollers.overview && !urlData.link_check_only) {
        virtualScrollers.overview.appendData([urlData]);
    }

    if (urlData.is_internal && virtualScrollers.internal) {
        virtualScrollers.internal.appendData([urlData]);
    } else if (!urlData.is_internal && virtualScrollers.external) {
        virtualScrollers.external.appendData([urlData]);
    }

    // Reapply current filter if one is active
    if (crawlState.filters.active) {
        applyFilter(crawlState.filters.active);
    }
}

function addRowToTable(tableBodyId, rowData) {
    const tbody = document.getElementById(tableBodyId);
    const row = tbody.insertRow();

    rowData.forEach(cellData => {
        const cell = row.insertCell();
        // Check if cellData contains HTML (specifically our button)
        if (typeof cellData === 'string' && cellData.includes('<button')) {
            cell.innerHTML = cellData;
        } else {
            cell.textContent = cellData;
        }
    });
}

// Tab Management
function switchTab(tabName) {
    // Remove active class from all tabs and panes
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('active'));

    // Add active class to selected tab and pane
    event.target.classList.add('active');
    document.getElementById(tabName + '-tab').classList.add('active');

    // Load pending links data if switching to Links tab
    if (tabName === 'links' && crawlState.pendingLinks) {
        updateLinksTable(crawlState.pendingLinks);
        crawlState.pendingLinks = null; // Clear pending data
    }

    if (tabName === 'extraction') {
        refreshExtractionTable();
    }

    if (tabName === 'ngrams') {
        loadNgrams();
    }

    if (tabName === 'compare') {
        loadCompareOptions();
    }

    // Load pending issues data if switching to Issues tab
    if (tabName === 'issues' && crawlState.pendingIssues) {
        updateIssuesTable(crawlState.pendingIssues);
        crawlState.pendingIssues = null; // Clear pending data
    }

    // Initialize visualization if switching to Visualization tab
    if (tabName === 'visualization' && typeof initVisualization === 'function') {
        // Small delay to ensure the tab is visible before initializing
        setTimeout(() => {
            initVisualization();
        }, 100);
    }

    // Handle plugin tabs
    const pluginTab = document.getElementById(`${tabName}-tab`);
    if (pluginTab && pluginTab.classList.contains('plugin-tab')) {
        handlePluginTabSwitch(tabName);
    }
}

// Handle plugin tab activation
function handlePluginTabSwitch(tabName) {
    if (!window.LibreCrawlPlugin || !window.LibreCrawlPlugin.loader) {
        return;
    }

    const loader = window.LibreCrawlPlugin.loader;

    // Deactivate previously active plugin
    if (loader.activePluginId && loader.activePluginId !== tabName) {
        loader.deactivatePlugin(loader.activePluginId);
    }

    // Activate the new plugin
    loader.activatePlugin(tabName, {
        urls: crawlState.urls,
        links: crawlState.links,
        issues: crawlState.issues,
        stats: crawlState.stats
    });
}

// Issue Filtering
function filterIssues(filterType) {
    // Store the active filter
    crawlState.filters.issueFilter = filterType;

    // Update active button state and colors
    document.querySelectorAll('#issues-tab .filter-item').forEach(btn => {
        btn.classList.remove('active');
        const filter = btn.getAttribute('data-filter');

        if (filter === filterType) {
            btn.classList.add('active');
            // Set active state colors
            if (filter === 'all') {
                btn.style.background = '#374151';
                btn.style.borderColor = '#4b5563';
                btn.style.color = 'white';
            } else if (filter === 'error') {
                btn.style.background = 'rgba(239, 68, 68, 0.2)';
                btn.style.borderColor = 'rgba(239, 68, 68, 0.5)';
            } else if (filter === 'warning') {
                btn.style.background = 'rgba(245, 158, 11, 0.2)';
                btn.style.borderColor = 'rgba(245, 158, 11, 0.5)';
            } else if (filter === 'info') {
                btn.style.background = 'rgba(59, 130, 246, 0.2)';
                btn.style.borderColor = 'rgba(59, 130, 246, 0.5)';
            }
        } else {
            // Reset inactive state colors
            if (filter === 'all') {
                btn.style.background = 'transparent';
                btn.style.borderColor = '#4b5563';
                btn.style.color = '#9ca3af';
            } else if (filter === 'error') {
                btn.style.background = 'rgba(239, 68, 68, 0.1)';
                btn.style.borderColor = 'rgba(239, 68, 68, 0.3)';
            } else if (filter === 'warning') {
                btn.style.background = 'rgba(245, 158, 11, 0.1)';
                btn.style.borderColor = 'rgba(245, 158, 11, 0.3)';
            } else if (filter === 'info') {
                btn.style.background = 'rgba(59, 130, 246, 0.1)';
                btn.style.borderColor = 'rgba(59, 130, 246, 0.3)';
            }
        }
    });

    // Filter issues data and update virtual scroller
    if (window.currentIssues && virtualScrollers.issues) {
        let filteredIssues = window.currentIssues;

        if (filterType !== 'all') {
            filteredIssues = window.currentIssues.filter(issue => issue.type === filterType);
        }

        virtualScrollers.issues.setData(filteredIssues);
    }
}

// Filter Management
function toggleFilter(filterType) {
    const filterItems = document.querySelectorAll('.filter-item');
    filterItems.forEach(item => item.classList.remove('active'));

    event.currentTarget.classList.add('active');
    crawlState.filters.active = filterType;

    // Apply filter to tables
    applyFilter(filterType);
}

function applyFilter(filterType) {
    // Set current filter as active
    crawlState.filters.active = filterType;

    // Filter the data arrays and update virtual scrollers
    filterVirtualScrollerData('overview', filterType);
    filterVirtualScrollerData('internal', filterType);
    filterVirtualScrollerData('external', filterType);

    // Update Status Codes table with filtered data
    updateStatusCodesTable(filterType);

    if (isNgramsTabActive()) {
        loadNgrams();
    }

    console.log('Applied filter:', filterType);
}

function clearActiveFilters() {
    crawlState.filters.active = null;

    // Reset all virtual scrollers to show full data
    if (virtualScrollers.overview) {
        virtualScrollers.overview.setData(sortTableData(overviewUrls(), 'overview'));
    }
    if (virtualScrollers.internal) {
        const internalUrls = crawlState.urls.filter(url => url.is_internal);
        virtualScrollers.internal.setData(sortTableData(internalUrls, 'internal'));
    }
    if (virtualScrollers.external) {
        const externalUrls = crawlState.urls.filter(url => !url.is_internal);
        virtualScrollers.external.setData(sortTableData(externalUrls, 'external'));
    }

    // Reset Status Codes table to show all data
    updateStatusCodesTable();

    if (isNgramsTabActive()) {
        loadNgrams();
    }
}

function filterVirtualScrollerData(scrollerName, filterType) {
    const scroller = virtualScrollers[scrollerName];
    if (!scroller) return;

    let filteredData = crawlState.urls;

    // Apply base filter for internal/external tables
    if (scrollerName === 'overview' && filterType !== 'external') {
        filteredData = overviewUrls();
    } else if (scrollerName === 'internal') {
        filteredData = filteredData.filter(url => url.is_internal);
    } else if (scrollerName === 'external') {
        filteredData = filteredData.filter(url => !url.is_internal);
    }

    // Apply user-selected filter
    if (filterType) {
        filteredData = filteredData.filter(url => {
            switch (filterType) {
                case 'internal':
                    return isInternalURL(url.url);
                case 'external':
                    return !isInternalURL(url.url);
                case '2xx':
                    return url.status_code >= 200 && url.status_code < 300;
                case '3xx':
                    return url.status_code >= 300 && url.status_code < 400;
                case '4xx':
                    return url.status_code >= 400 && url.status_code < 500;
                case '5xx':
                    return url.status_code >= 500;
                case 'no_response':
                    return (url.status_code === 0 || url.status_code === null || url.status_code === undefined)
                        && url.error_type !== 'file_too_large';
                case 'html':
                    return (url.content_type || '').toLowerCase().includes('html');
                case 'css':
                    return (url.content_type || '').toLowerCase().includes('css');
                case 'js':
                    return (url.content_type || '').toLowerCase().includes('javascript');
                case 'images':
                    return (url.content_type || '').toLowerCase().includes('image');
                case 'indexable':
                    return url.indexability === 'Indexable';
                case 'non_indexable':
                    return url.indexability === 'Non-Indexable';
                default:
                    return true;
            }
        });
    }

    scroller.setData(sortTableData(filteredData, scrollerName));
}

// Legacy function - kept for compatibility but no longer used
function filterTable(tableBodyId, filterType) {
    // This function is deprecated in favor of filterVirtualScrollerData
    // Kept for backwards compatibility only
}

function isInternalURL(url) {
    if (!url || !crawlState.baseUrl) return false;
    try {
        const urlObj = new URL(url);
        const baseObj = new URL(crawlState.baseUrl);

        // Normalize domains by removing www prefix for comparison
        const urlDomain = urlObj.hostname.replace('www.', '');
        const baseDomain = baseObj.hostname.replace('www.', '');

        return urlDomain === baseDomain;
    } catch (e) {
        return false;
    }
}

function isStatusCodeRange(statusText, min, max) {
    const status = parseInt(statusText);
    return status >= min && status <= max;
}

function isContentType(contentType, type) {
    if (!contentType) return false;
    return contentType.toLowerCase().includes(type.toLowerCase());
}

function updateFilterCounts() {
    // Count URLs by type and update filter counts
    const counts = {
        internal: 0,
        external: 0,
        '2xx': 0,
        '3xx': 0,
        '4xx': 0,
        '5xx': 0,
        no_response: 0,
        html: 0,
        css: 0,
        js: 0,
        images: 0,
        indexable: 0,
        non_indexable: 0
    };

    crawlState.urls.forEach(url => {
        // Count by internal/external using corrected logic
        if (isInternalURL(url.url)) counts.internal++;
        else counts.external++;

        // The other filters match what the Overview shows under them
        if (url.link_check_only) return;

        // Count by status code
        const statusCode = parseInt(url.status_code);
        if (statusCode >= 200 && statusCode < 300) counts['2xx']++;
        else if (statusCode >= 300 && statusCode < 400) counts['3xx']++;
        else if (statusCode >= 400 && statusCode < 500) counts['4xx']++;
        else if (statusCode >= 500) counts['5xx']++;
        else if ((url.status_code === 0 || isNaN(statusCode)) && url.error_type !== 'file_too_large') counts.no_response++;

        // Count by content type
        const contentType = url.content_type || '';
        if (contentType.includes('html')) counts.html++;
        else if (contentType.includes('css')) counts.css++;
        else if (contentType.includes('javascript')) counts.js++;
        else if (contentType.includes('image')) counts.images++;

        if (url.indexability === 'Indexable') counts.indexable++;
        else if (url.indexability === 'Non-Indexable') counts.non_indexable++;
    });

    // Update DOM
    Object.keys(counts).forEach(key => {
        const element = document.getElementById(key + '-count');
        if (element) {
            element.textContent = counts[key];
        }
    });
}

function updateStatusCodesTable(filterType = null) {
    const tbody = document.getElementById('statusCodesTableBody');
    if (!tbody) return;

    // Count status codes, respecting current filter
    const statusCounts = {};
    let filteredUrls = filterType === 'external' ? crawlState.urls : overviewUrls();

    // Apply filter if specified
    if (filterType === 'internal') {
        filteredUrls = filteredUrls.filter(url => isInternalURL(url.url));
    } else if (filterType === 'external') {
        filteredUrls = filteredUrls.filter(url => !isInternalURL(url.url));
    } else if (filterType === '2xx') {
        filteredUrls = filteredUrls.filter(url => {
            const status = parseInt(url.status_code);
            return status >= 200 && status < 300;
        });
    } else if (filterType === '3xx') {
        filteredUrls = filteredUrls.filter(url => {
            const status = parseInt(url.status_code);
            return status >= 300 && status < 400;
        });
    } else if (filterType === '4xx') {
        filteredUrls = filteredUrls.filter(url => {
            const status = parseInt(url.status_code);
            return status >= 400 && status < 500;
        });
    } else if (filterType === '5xx') {
        filteredUrls = filteredUrls.filter(url => {
            const status = parseInt(url.status_code);
            return status >= 500;
        });
    } else if (filterType === 'no_response') {
        filteredUrls = filteredUrls.filter(url =>
            (url.status_code === 0 || url.status_code === null || url.status_code === undefined)
            && url.error_type !== 'file_too_large'
        );
    } else if (filterType === 'html') {
        filteredUrls = filteredUrls.filter(url => (url.content_type || '').includes('html'));
    } else if (filterType === 'css') {
        filteredUrls = filteredUrls.filter(url => (url.content_type || '').includes('css'));
    } else if (filterType === 'js') {
        filteredUrls = filteredUrls.filter(url => (url.content_type || '').includes('javascript'));
    } else if (filterType === 'images') {
        filteredUrls = filteredUrls.filter(url => (url.content_type || '').includes('image'));
    } else if (filterType === 'indexable') {
        filteredUrls = filteredUrls.filter(url => url.indexability === 'Indexable');
    } else if (filterType === 'non_indexable') {
        filteredUrls = filteredUrls.filter(url => url.indexability === 'Non-Indexable');
    }

    let totalUrls = filteredUrls.length;

    filteredUrls.forEach(url => {
        // Group status_code=0 rows by error_type so DNS / timeout / refused
        // show as distinct rows instead of collapsing into a single "0".
        const isZero = url.status_code === 0 || url.status_code === null || url.status_code === undefined;
        const key = isZero ? `0|${url.error_type || 'unknown'}` : String(url.status_code);
        statusCounts[key] = (statusCounts[key] || 0) + 1;
    });

    // Clear existing rows
    tbody.innerHTML = '';

    // Sort: real HTTP codes first (numeric), then no-response variants
    const keys = Object.keys(statusCounts).sort((a, b) => {
        const aIsZero = a.startsWith('0|');
        const bIsZero = b.startsWith('0|');
        if (aIsZero && !bIsZero) return 1;
        if (!aIsZero && bIsZero) return -1;
        if (aIsZero && bIsZero) return a.localeCompare(b);
        return parseInt(a) - parseInt(b);
    });

    keys.forEach(key => {
        const count = statusCounts[key];
        const percentage = totalUrls > 0 ? ((count / totalUrls) * 100).toFixed(1) : 0;
        let displayCode, statusText;
        if (key.startsWith('0|')) {
            const errorType = key.slice(2);
            displayCode = '0';
            statusText = getStatusCodeText(0, errorType);
        } else {
            displayCode = key;
            statusText = getStatusCodeText(parseInt(key));
        }

        addRowToTable('statusCodesTableBody', [
            displayCode,
            statusText,
            count,
            percentage + '%'
        ]);
    });
}

function getStatusCodeText(statusCode, errorType) {
    if (statusCode >= 200 && statusCode < 300) {
        return 'Success';
    } else if (statusCode >= 300 && statusCode < 400) {
        return 'Redirect';
    } else if (statusCode >= 400 && statusCode < 500) {
        return 'Client Error';
    } else if (statusCode >= 500) {
        return 'Server Error';
    } else if (statusCode === 0) {
        switch (errorType) {
            case 'dns_not_found':       return 'DNS Not Found';
            case 'connection_refused':  return 'Connection Refused';
            case 'timeout':             return 'Timeout';
            case 'ssl_error':           return 'SSL/TLS Error';
            case 'connection_error':    return 'Connection Error';
            case 'file_too_large':      return 'Skipped (file too large)';
            case 'blocked_by_robots':   return 'Blocked by robots.txt';
            default:                    return 'No Response';
        }
    } else {
        return 'Unknown';
    }
}

function resetStats() {
    crawlState.stats = {
        discovered: 0,
        crawled: 0,
        depth: 0,
        speed: 0
    };
    updateStatsDisplay();
}

// Utility Functions
function normalizeUrl(input) {
    // Remove any whitespace
    input = input.trim();

    // If it already has a protocol, return as-is
    if (input.match(/^https?:\/\//i)) {
        return input;
    }

    // If it looks like a domain or IP, add https://
    if (input.match(/^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]*\.([a-zA-Z]{2,}|[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3})/) ||
        input.match(/^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}/) ||
        input.match(/^localhost(:[0-9]+)?$/i) ||
        input.match(/^[a-zA-Z0-9-]+\.(com|org|net|edu|gov|mil|int|co|io|dev|app|tech|info|biz|name|pro|museum|aero|coop|travel|jobs|mobi|tel|asia|cat|post|xxx|local|test)$/i)) {
        return 'https://' + input;
    }

    // If it doesn't match common patterns, try adding https:// anyway
    return 'https://' + input;
}

function isValidUrl(string) {
    try {
        const url = new URL(string);
        // Check if it has a valid protocol and hostname
        return (url.protocol === 'http:' || url.protocol === 'https:') && url.hostname.length > 0;
    } catch (_) {
        return false;
    }
}

// This is defined in settings.js - no need to redefine here

async function logout() {
    try {
        const response = await fetch('/api/logout', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const data = await response.json();

        if (data.success) {
            // Redirect to login page
            window.location.href = '/login';
        } else {
            console.error('Logout failed:', data.message);
            // Still redirect even if logout fails
            window.location.href = '/login';
        }
    } catch (error) {
        console.error('Logout error:', error);
        // Redirect anyway
        window.location.href = '/login';
    }
}

async function loadUserInfo() {
    try {
        const response = await fetch('/api/user/info');
        const data = await response.json();

        if (data.success && data.user) {
            const user = data.user;
            const userInfoElement = document.getElementById('userInfo');

            if (user.tier === 'guest') {
                // Show crawls remaining for guests
                const remaining = user.crawls_remaining;
                userInfoElement.textContent = `Guest (${remaining}/3 crawls remaining)`;
                userInfoElement.style.color = remaining === 0 ? '#dc2626' : '#6b7280';
            } else {
                // Show username and tier for registered users
                userInfoElement.textContent = `${user.username} (${user.tier})`;
                userInfoElement.style.color = '#6b7280';
            }
        }
    } catch (error) {
        console.error('Error loading user info:', error);
    }
}

async function exportData() {
    const exportBtn = document.getElementById('exportBtn');
    if (exportBtn) {
        if (exportBtn.disabled) return; // Already exporting
        exportBtn.disabled = true;
        exportBtn.textContent = 'Exporting...';
    }
    try {
        // Export with the settings this browser is showing. settings.js keeps
        // them in localStorage and syncs to the server in the background; the
        // server copy can lag (a failed sync, a busy database), which used to
        // make exports ignore the format picked in Settings. Only fall back to
        // the server copy when nothing is loaded here.
        let settings = (typeof currentSettings !== 'undefined' && currentSettings
                        && Object.keys(currentSettings).length) ? currentSettings : null;
        if (!settings) {
            const settingsResponse = await fetch('/api/get_settings');
            const settingsData = await settingsResponse.json();

            if (!settingsData.success) {
                showNotification('Failed to get export settings', 'error');
                return;
            }
            settings = settingsData.settings;
        }

        const exportFormat = settings.exportFormat || 'csv';
        const exportFields = settings.exportFields || ['url', 'status_code', 'title', 'meta_description', 'h1'];

        // Check where the exportable data lives: the server (active or resumed
        // crawl) or only this browser (crawl loaded from a saved file)
        let serverHasData = false;
        try {
            // Lightweight check — stats only, no data arrays
            const status = await fetch('/api/crawl_status?stats_only=1');
            const statusData = await status.json();
            serverHasData = !!(statusData.stats && statusData.stats.crawled > 0);
        } catch (e) {
            console.log('Status check failed, assuming local-only data:', e);
        }
        const localHasData = crawlState.urls && crawlState.urls.length > 0;

        if (!serverHasData && !localHasData) {
            showNotification('No crawl data to export', 'error');
            return;
        }

        showNotification('Preparing export...', 'info');

        if (!serverHasData) {
            // File-loaded crawls exist only in the browser — the streaming
            // endpoint can't see them, so use the legacy export endpoint
            await legacyExportData(exportFormat, exportFields);
            return;
        }

        // Determine which data types to export based on settings
        const hasIssues = exportFields.includes('issues_detected');
        const hasLinks = exportFields.includes('links_detailed');
        const hasNgrams = exportFields.includes('ngrams');
        const regularFields = exportFields.filter(
            f => f !== 'issues_detected' && f !== 'links_detailed' && f !== 'ngrams'
        );

        // Use streaming endpoint — downloads directly, no memory blow-up
        const downloads = [];

        if (regularFields.length > 0) {
            const params = new URLSearchParams({
                format: exportFormat,
                fields: regularFields.join(','),
                type: 'urls'
            });
            downloads.push('/api/export_stream?' + params.toString());
        }

        if (hasLinks) {
            const params = new URLSearchParams({
                format: exportFormat,
                type: 'links'
            });
            downloads.push('/api/export_stream?' + params.toString());
        }

        if (hasIssues) {
            const params = new URLSearchParams({
                format: exportFormat,
                type: 'issues'
            });
            downloads.push('/api/export_stream?' + params.toString());
        }

        if (hasNgrams) {
            const params = new URLSearchParams({
                format: exportFormat,
                type: 'ngrams'
            });
            if (crawlState.filters.active) {
                params.set('filter', crawlState.filters.active);
            }
            downloads.push('/api/export_stream?' + params.toString());
        }

        if (downloads.length === 0) {
            showNotification('No fields selected for export', 'error');
            return;
        }

        // Trigger each download
        downloads.forEach((url, index) => {
            setTimeout(() => {
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = '';
                document.body.appendChild(a);
                a.click();
                document.body.removeChild(a);
            }, index * 500);
        });

        const fileWord = downloads.length === 1 ? 'file' : 'files';
        showNotification('Exporting ' + downloads.length + ' ' + fileWord + '...', 'success');

    } catch (error) {
        console.error('Export error:', error);
        showNotification('Export failed', 'error');
    } finally {
        if (exportBtn) {
            exportBtn.disabled = false;
            exportBtn.textContent = 'Export';
        }
    }
}

// Legacy in-memory export via POST /api/export_data — used for crawls loaded
// from a saved file, where the data exists only in browser state
async function legacyExportData(exportFormat, exportFields) {
    const exportResponse = await fetch('/api/export_data', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            format: exportFormat,
            fields: exportFields,
            localData: {
                urls: crawlState.urls || [],
                links: crawlState.links || [],
                issues: crawlState.issues || window.currentIssues || []
            }
        })
    });

    const exportData = await exportResponse.json();

    if (!exportData.success) {
        showNotification(exportData.error || 'Export failed', 'error');
        return;
    }

    // Binary formats (xlsx) arrive base64-encoded; text formats as-is
    const toBlob = (file) => {
        if (file.encoding === 'base64') {
            const bytes = Uint8Array.from(atob(file.content), c => c.charCodeAt(0));
            return new Blob([bytes], { type: file.mimetype });
        }
        return new Blob([file.content], { type: file.mimetype });
    };

    if (exportData.multiple_files && exportData.files) {
        exportData.files.forEach((file, index) => {
            setTimeout(() => {
                const blob = toBlob(file);
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.style.display = 'none';
                a.href = url;
                a.download = file.filename;
                document.body.appendChild(a);
                a.click();
                window.URL.revokeObjectURL(url);
                document.body.removeChild(a);
            }, index * 500); // Delay between downloads to avoid browser blocking
        });

        showNotification(`Exporting ${exportData.files.length} files...`, 'success');
    } else {
        const blob = toBlob(exportData);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = exportData.filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification(`Export complete: ${exportData.filename}`, 'success');
    }
}

// Helper function to escape HTML for safe display
function escapeHtml(text) {
    if (!text) return text;
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showUrlDetails(url) {
    // Find the URL data
    const urlData = crawlState.urls.find(u => u.url === url);
    if (!urlData) {
        showNotification('URL data not found', 'error');
        return;
    }

    // Escape all user-controlled text fields to prevent HTML injection
    const safeUrl = escapeHtml(url);
    const safeTitle = escapeHtml(urlData.title) || 'N/A';
    const safeH1 = escapeHtml(urlData.h1) || 'N/A';
    const safeMetaDesc = escapeHtml(urlData.meta_description) || 'N/A';
    const safeLang = escapeHtml(urlData.lang) || 'N/A';
    const safeCharset = escapeHtml(urlData.charset) || 'N/A';
    const safeCanonical = escapeHtml(urlData.canonical_url) || 'N/A';
    const safeRobots = escapeHtml(urlData.robots) || 'N/A';
    const safeContentType = escapeHtml(urlData.content_type) || 'N/A';
    const safeGa4Id = escapeHtml(urlData.analytics?.ga4_id) || 'N/A';
    const safeGtmId = escapeHtml(urlData.analytics?.gtm_id) || 'N/A';

    // Create modal content
    const modalContent = `
        <div class="details-modal-overlay" onclick="closeUrlDetails()">
            <div class="details-modal" onclick="event.stopPropagation()">
                <div class="details-header">
                    <h3>Comprehensive URL Analysis</h3>
                    <button class="close-btn" onclick="closeUrlDetails()">×</button>
                </div>
                <div class="details-content">
                    <div class="details-url">${safeUrl}</div>

                    <div class="details-sections">
                        <div class="details-section">
                            <h4>🔍 Basic SEO</h4>
                            <div class="details-grid">
                                <div><strong>Title:</strong> ${safeTitle}</div>
                                <div><strong>H1:</strong> ${safeH1}</div>
                                <div><strong>Meta Description:</strong> ${safeMetaDesc}</div>
                                <div><strong>Keywords:</strong> ${escapeHtml(urlData.keywords) || 'N/A'}</div>
                                <div><strong>Word Count:</strong> ${urlData.word_count || 0}</div>
                                <div><strong>Language:</strong> ${safeLang}</div>
                                <div><strong>Charset:</strong> ${safeCharset}</div>
                                <div><strong>Canonical URL:</strong> ${safeCanonical}</div>
                                <div><strong>Robots Meta:</strong> ${safeRobots}</div>
                                ${urlData.h1_count > 1 ? `<div><strong>H1 Count:</strong> ${urlData.h1_count}</div>` : ''}
                                ${urlData.title_count > 1 ? `<div><strong>Title Tags:</strong> ${urlData.title_count}</div>` : ''}
                                ${urlData.canonical_header ? `<div><strong>Canonical (Link header):</strong> ${escapeHtml(urlData.canonical_header)}</div>` : ''}
                            </div>
                            ${urlData.canonical_count > 1 ? `
                                <div class="details-subsection">
                                    <h5>${urlData.canonical_count} canonical declarations:</h5>
                                    ${(urlData.canonicals || []).map(href =>
                                        `<div style="word-break: break-all;">${escapeHtml(href) || '<span style="color:#9ca3af">(empty href)</span>'}</div>`
                                    ).join('')}
                                </div>
                            ` : ''}
                        </div>

                        <div class="details-section">
                            <h4>🧭 Indexability</h4>
                            <div class="details-grid">
                                <div><strong>Indexability:</strong> ${escapeHtml(urlData.indexability) || 'N/A'}${urlData.indexability_status ? ' (' + escapeHtml(urlData.indexability_status) + ')' : ''}</div>
                                <div><strong>X-Robots-Tag:</strong> ${escapeHtml(urlData.x_robots_tag) || 'N/A'}</div>
                                <div><strong>Unique Inlinks:</strong> ${inlinkCount(urlData) ?? 'N/A'}</div>
                                <div><strong>Internal Outlinks:</strong> ${typeof urlData.outlinks === 'number' ? urlData.outlinks : 'N/A'}</div>
                                <div><strong>Link Score:</strong> ${typeof urlData.link_score === 'number' ? urlData.link_score + ' / 100' : 'N/A'}</div>
                                <div><strong>In Sitemap:</strong> ${urlData.in_sitemap === true ? 'Yes' : urlData.in_sitemap === false ? 'No' : 'No sitemap found'}</div>
                            </div>
                            ${(urlData.redirects && urlData.redirects.length) ? `
                                <div class="details-subsection">
                                    <h5>Redirect chain (${urlData.redirects.length} hop${urlData.redirects.length !== 1 ? 's' : ''}):</h5>
                                    ${urlData.redirects.map(hop =>
                                        `<div style="word-break: break-all;">${escapeHtml(String(hop.status_code || '3xx'))} ${escapeHtml(hop.url)}</div>`
                                    ).join('')}
                                    <div style="word-break: break-all;">→ ${escapeHtml(urlData.redirected_to || '')} (${escapeHtml(String(urlData.status_code))})</div>
                                </div>
                            ` : ''}
                        </div>

                        <div class="details-section">
                            <h4>📊 Analytics & Tracking</h4>
                            <div class="details-grid">
                                <div><strong>Google Analytics:</strong> ${urlData.analytics?.google_analytics ? '✅ Yes' : '❌ No'}</div>
                                <div><strong>GA4/Gtag:</strong> ${urlData.analytics?.gtag ? '✅ Yes' : '❌ No'}</div>
                                <div><strong>GA4 ID:</strong> ${safeGa4Id}</div>
                                <div><strong>GTM ID:</strong> ${safeGtmId}</div>
                                <div><strong>Facebook Pixel:</strong> ${urlData.analytics?.facebook_pixel ? '✅ Yes' : '❌ No'}</div>
                                <div><strong>Hotjar:</strong> ${urlData.analytics?.hotjar ? '✅ Yes' : '❌ No'}</div>
                                <div><strong>Mixpanel:</strong> ${urlData.analytics?.mixpanel ? '✅ Yes' : '❌ No'}</div>
                            </div>
                        </div>

                        <div class="details-section">
                            <h4>📱 Social Media</h4>
                            <div class="details-grid">
                                <div><strong>OpenGraph Tags:</strong> ${Object.keys(urlData.og_tags || {}).length} found</div>
                                <div><strong>Twitter Cards:</strong> ${Object.keys(urlData.twitter_tags || {}).length} found</div>
                            </div>
                            ${Object.keys(urlData.og_tags || {}).length > 0 ? `
                                <div class="details-subsection">
                                    <h5>OpenGraph Tags:</h5>
                                    ${Object.entries(urlData.og_tags || {}).map(([key, value]) =>
                                        `<div><strong>og:${escapeHtml(key)}:</strong> ${escapeHtml(value)}</div>`
                                    ).join('')}
                                </div>
                            ` : ''}
                            ${Object.keys(urlData.twitter_tags || {}).length > 0 ? `
                                <div class="details-subsection">
                                    <h5>Twitter Cards:</h5>
                                    ${Object.entries(urlData.twitter_tags || {}).map(([key, value]) =>
                                        `<div><strong>twitter:${escapeHtml(key)}:</strong> ${escapeHtml(value)}</div>`
                                    ).join('')}
                                </div>
                            ` : ''}
                        </div>

                        <div class="details-section">
                            <h4>🔗 Links & Structure</h4>
                            <div class="details-grid">
                                <div><strong>Internal Links:</strong> ${urlData.internal_links || 0}</div>
                                <div><strong>External Links:</strong> ${urlData.external_links || 0}</div>
                                <div><strong>Images:</strong> ${(urlData.images || []).length}</div>
                                <div><strong>H2 Tags:</strong> ${(urlData.h2 || []).length}</div>
                                <div><strong>H3 Tags:</strong> ${(urlData.h3 || []).length}</div>
                            </div>
                        </div>

                        <div class="details-section">
                            <h4>⚡ Performance</h4>
                            <div class="details-grid">
                                <div><strong>Status Code:</strong> ${urlData.status_code}${urlData.error_type ? ' (' + escapeHtml(getStatusCodeText(parseInt(urlData.status_code) || 0, urlData.error_type)) + ')' : ''}</div>
                                <div><strong>Response Time:</strong> ${urlData.response_time || 0}ms</div>
                                ${urlData.render_time ? `<div><strong>Render Time:</strong> ${urlData.render_time}ms <span style="color:#9ca3af">(includes the JS render wait)</span></div>` : ''}
                                <div><strong>Content Type:</strong> ${safeContentType}</div>
                                <div><strong>Size:</strong> ${urlData.size || 0} bytes</div>
                                ${urlData.error ? `<div><strong>Error:</strong> ${escapeHtml(urlData.error)}</div>` : ''}
                            </div>
                        </div>

                        ${urlData.custom_extraction && Object.keys(urlData.custom_extraction).length ? `
                        <div class="details-section">
                            <h4>🧩 Custom Extraction</h4>
                            <div class="details-grid">
                                ${Object.entries(urlData.custom_extraction).map(([name, values]) => `
                                    <div><strong>${escapeHtml(name)}:</strong> ${(values && values.length)
                                        ? values.map(v => `<span class="extract-value">${escapeHtml(v)}</span>`).join(' ')
                                        : '<span style="color:#9ca3af">no match</span>'}</div>
                                `).join('')}
                            </div>
                        </div>
                        ` : ''}

                        ${(urlData.linked_from && urlData.linked_from.length > 0) ? `
                        <div class="details-section">
                            <h4>🔗 Linked From</h4>
                            <div class="details-grid">
                                <div><strong>Found on ${urlData.linked_from.length} page${urlData.linked_from.length !== 1 ? 's' : ''}:</strong></div>
                            </div>
                            <div class="details-subsection">
                                <ul style="list-style: none; padding: 0; margin: 10px 0;">
                                    ${urlData.linked_from.slice(0, 20).map(sourceUrl => {
                                        const escapedUrl = escapeHtml(sourceUrl);
                                        return `<li style="padding: 5px 0; word-break: break-all;"><a href="${escapedUrl}" target="_blank" style="color: #8b5cf6; text-decoration: none;">${escapedUrl}</a></li>`;
                                    }).join('')}
                                    ${urlData.linked_from.length > 20 ? `<li style="padding: 5px 0; font-style: italic; color: #9ca3af;">... and ${urlData.linked_from.length - 20} more</li>` : ''}
                                </ul>
                            </div>
                        </div>
                        ` : ''}

                        <div class="details-section">
                            <h4>🏗️ Structured Data</h4>
                            <div class="details-grid">
                                <div><strong>JSON-LD Scripts:</strong> ${(urlData.json_ld || []).length}</div>
                                <div><strong>Schema.org Items:</strong> ${(urlData.schema_org || []).length}</div>
                            </div>
                            ${(urlData.json_ld || []).length > 0 ? `
                                <div class="details-subsection">
                                    <h5>JSON-LD Data:</h5>
                                    <pre class="json-preview">${escapeHtml(JSON.stringify(urlData.json_ld, null, 2))}</pre>
                                </div>
                            ` : ''}
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    // Add modal to page
    document.body.insertAdjacentHTML('beforeend', modalContent);
}

function closeUrlDetails() {
    const modal = document.querySelector('.details-modal-overlay');
    if (modal) {
        modal.remove();
    }
}

function displayPageSpeedResults(results) {
    const container = document.getElementById('pagespeedResults');
    if (!container || !results || results.length === 0) {
        return;
    }

    container.innerHTML = '';

    results.forEach(pageResult => {
        const pageCard = document.createElement('div');
        pageCard.className = 'pagespeed-page-card';

        const mobile = pageResult.mobile || {};
        const desktop = pageResult.desktop || {};

        pageCard.innerHTML = `
            <div class="pagespeed-page-header">
                <h4 class="pagespeed-page-url">${pageResult.url}</h4>
                <span class="pagespeed-analysis-date">Analyzed: ${pageResult.analysis_date}</span>
            </div>

            <div class="pagespeed-results-grid">
                <div class="pagespeed-device-result">
                    <h5>📱 Mobile</h5>
                    ${mobile.success ? `
                        <div class="pagespeed-score ${getScoreClass(mobile.performance_score)}">
                            ${mobile.performance_score || 'N/A'}
                        </div>
                        <div class="pagespeed-metrics">
                            <div class="metric">
                                <span class="metric-label">FCP:</span>
                                <span class="metric-value">${mobile.metrics?.first_contentful_paint || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">LCP:</span>
                                <span class="metric-value">${mobile.metrics?.largest_contentful_paint || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">CLS:</span>
                                <span class="metric-value">${mobile.metrics?.cumulative_layout_shift || 'N/A'}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">SI:</span>
                                <span class="metric-value">${mobile.metrics?.speed_index || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">TTI:</span>
                                <span class="metric-value">${mobile.metrics?.time_to_interactive || 'N/A'}s</span>
                            </div>
                        </div>
                    ` : `
                        <div class="pagespeed-error">
                            Error: ${mobile.error || 'Analysis failed'}
                        </div>
                    `}
                </div>

                <div class="pagespeed-device-result">
                    <h5>🖥️ Desktop</h5>
                    ${desktop.success ? `
                        <div class="pagespeed-score ${getScoreClass(desktop.performance_score)}">
                            ${desktop.performance_score || 'N/A'}
                        </div>
                        <div class="pagespeed-metrics">
                            <div class="metric">
                                <span class="metric-label">FCP:</span>
                                <span class="metric-value">${desktop.metrics?.first_contentful_paint || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">LCP:</span>
                                <span class="metric-value">${desktop.metrics?.largest_contentful_paint || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">CLS:</span>
                                <span class="metric-value">${desktop.metrics?.cumulative_layout_shift || 'N/A'}</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">SI:</span>
                                <span class="metric-value">${desktop.metrics?.speed_index || 'N/A'}s</span>
                            </div>
                            <div class="metric">
                                <span class="metric-label">TTI:</span>
                                <span class="metric-value">${desktop.metrics?.time_to_interactive || 'N/A'}s</span>
                            </div>
                        </div>
                    ` : `
                        <div class="pagespeed-error">
                            Error: ${desktop.error || 'Analysis failed'}
                        </div>
                    `}
                </div>
            </div>
        `;

        container.appendChild(pageCard);
    });
}

function getScoreClass(score) {
    if (!score) return 'score-unknown';
    if (score >= 90) return 'score-good';
    if (score >= 50) return 'score-needs-improvement';
    return 'score-poor';
}

// Save/Load Crawl Functions
let isSavingCrawl = false;

// Browsers cap one string near 512 MB, and a big crawl's JSON
// exceeds it. Save files are built and read a row at a time.
const SAVE_BATCH_ROWS = 5000;

// Returns Blob parts forming {...meta, key: [rows], ...}.
async function buildCrawlFileParts(meta, arrays) {
    const head = JSON.stringify(meta);
    const parts = [head.slice(0, -1)];
    for (const [key, rows] of Object.entries(arrays)) {
        parts.push(`,${JSON.stringify(key)}:[`);
        for (let i = 0; i < rows.length; i += SAVE_BATCH_ROWS) {
            const end = Math.min(i + SAVE_BATCH_ROWS, rows.length);
            let chunk = '';
            for (let j = i; j < end; j++) {
                chunk += (j ? ',' : '') + (JSON.stringify(rows[j]) ?? 'null');
            }
            parts.push(chunk);
            // Yield so the page stays responsive
            await new Promise(resolve => setTimeout(resolve, 0));
        }
        parts.push(']');
    }
    parts.push('}');
    return parts;
}

// Incremental parser for a saved crawl: a top-level object
// whose array values are parsed one element at a time.
class CrawlFileParser {
    constructor() {
        this.data = {};
        this.state = 'start';
        this.depth = 0;
        this.inString = false;
        this.escaped = false;
        this.key = null;
        this.rows = null;
        this.capturing = false;
        this.capStart = 0;
        this.buf = '';
    }

    begin(i) {
        this.capturing = true;
        this.capStart = i;
        this.buf = '';
    }

    take(chunk, end) {
        const text = this.buf + chunk.slice(this.capStart, end);
        this.capturing = false;
        this.buf = '';
        return text;
    }

    flushRow(chunk, i) {
        if (this.capturing) this.rows.push(JSON.parse(this.take(chunk, i)));
    }

    push(chunk) {
        for (let i = 0; i < chunk.length; i++) {
            const c = chunk[i];
            if (this.inString) {
                if (this.escaped) {
                    this.escaped = false;
                } else if (c === '\\') {
                    this.escaped = true;
                } else if (c === '"') {
                    this.inString = false;
                    if (this.state === 'key') {
                        this.key = JSON.parse(this.take(chunk, i + 1));
                        this.state = 'colon';
                    }
                }
                continue;
            }
            if (c === ' ' || c === '\n' || c === '\r' || c === '\t') continue;

            switch (this.state) {
                case 'start':
                    if (c !== '{') throw new Error('Not a crawl file');
                    this.depth = 1;
                    this.state = 'key';
                    break;
                case 'key':
                    if (c === '"') {
                        this.begin(i);
                        this.inString = true;
                    } else if (c === '}') {
                        this.state = 'done';
                    } else if (c !== ',') {
                        throw new Error('Malformed crawl file');
                    }
                    break;
                case 'colon':
                    if (c !== ':') throw new Error('Malformed crawl file');
                    this.state = 'value';
                    break;
                case 'value':
                    if (c === '[') {
                        this.rows = [];
                        this.depth = 2;
                        this.state = 'array';
                    } else {
                        this.state = 'scalar';
                        this.begin(i);
                        this.track(c);
                    }
                    break;
                case 'array':
                    if (this.depth === 2 && c === ',') {
                        this.flushRow(chunk, i);
                    } else if (this.depth === 2 && c === ']') {
                        this.flushRow(chunk, i);
                        this.data[this.key] = this.rows;
                        this.rows = null;
                        this.depth = 1;
                        this.state = 'key';
                    } else {
                        if (!this.capturing) this.begin(i);
                        this.track(c);
                    }
                    break;
                case 'scalar':
                    if (this.depth === 1 && (c === ',' || c === '}')) {
                        this.data[this.key] = JSON.parse(this.take(chunk, i));
                        this.state = c === '}' ? 'done' : 'key';
                    } else {
                        this.track(c);
                    }
                    break;
                default:
                    throw new Error('Unexpected data after end of crawl file');
            }
        }
        if (this.capturing) {
            this.buf += chunk.slice(this.capStart);
            this.capStart = 0;
        }
    }

    track(c) {
        if (c === '"') this.inString = true;
        else if (c === '{' || c === '[') this.depth++;
        else if (c === '}' || c === ']') this.depth--;
    }

    finish() {
        if (this.state !== 'done') throw new Error('Crawl file is truncated');
        return this.data;
    }
}

async function readCrawlFile(file) {
    const parser = new CrawlFileParser();
    const reader = file.stream().pipeThrough(new TextDecoderStream()).getReader();
    for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        parser.push(value);
    }
    return parser.finish();
}

async function saveCrawl() {
    const saveCrawlBtn = document.getElementById('saveCrawlBtn');
    if (isSavingCrawl || (saveCrawlBtn && saveCrawlBtn.disabled)) return;
    isSavingCrawl = true;
    if (saveCrawlBtn) {
        saveCrawlBtn.disabled = true;
        saveCrawlBtn.textContent = 'Saving...';
    }
    try {
        if (crawlState.stats.crawled === 0) {
            showNotification('No crawl data to save', 'error');
            return;
        }

        // The poller keeps the rows current. Only stats are refreshed,
        // for PageSpeed results that land after the crawl finishes.
        let stats = crawlState.stats;
        try {
            const status = await fetch('/api/crawl_status?stats_only=1');
            const light = await status.json();
            if (light.stats && light.stats.crawled === stats.crawled) {
                stats = light.stats;
            }
        } catch (e) {
            console.log('Using local stats for save:', e);
        }

        const meta = {
            timestamp: new Date().toISOString(),
            baseUrl: crawlState.baseUrl,
            stats: stats,
            version: '1.1'
        };
        const parts = await buildCrawlFileParts(meta, {
            urls: crawlState.urls || [],
            links: crawlState.links || [],
            issues: crawlState.issues || []
        });

        const blob = new Blob(parts, { type: 'application/json' });
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;

        // Generate filename with domain and timestamp
        const domain = crawlState.baseUrl ? new URL(crawlState.baseUrl).hostname : 'crawl';
        const timestamp = new Date().toISOString().slice(0, 19).replace(/:/g, '-');
        a.download = `librecrawl_${domain}_${timestamp}.json`;

        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);

        showNotification('Crawl saved successfully', 'success');

    } catch (error) {
        console.error('Save error:', error);
        showNotification(`Failed to save crawl: ${error.message}`, 'error');
    } finally {
        isSavingCrawl = false;
        if (saveCrawlBtn) {
            saveCrawlBtn.textContent = 'Save Crawl';
        }
        updateCrawlButtons(); // Restore correct enabled/disabled state
    }
}

function loadCrawl() {
    // Create file input
    const fileInput = document.createElement('input');
    fileInput.type = 'file';
    fileInput.accept = '.json';
    fileInput.style.display = 'none';

    fileInput.addEventListener('change', async function(event) {
        const file = event.target.files[0];
        if (!file) return;

        const loadCrawlBtn = document.getElementById('loadCrawlBtn');
        if (loadCrawlBtn) loadCrawlBtn.textContent = 'Loading...';
        try {
            const saveData = await readCrawlFile(file);

            // Validate save data
            if (!saveData.version || !saveData.urls || !saveData.stats) {
                showNotification('Invalid crawl file format', 'error');
                return;
            }

            // Clear current data
            clearAllTables();
            resetStats();

            // Load the data
            crawlState.baseUrl = saveData.baseUrl;
            crawlState.stats = saveData.stats;
            crawlState.urls = [];
            crawlState.links = saveData.links || [];
            crawlState.issues = saveData.issues || [];

            // Update UI
            document.getElementById('urlInput').value = saveData.baseUrl || '';
            updateStatsDisplay();

            // Populate tables with loaded data
            if (saveData.urls && saveData.urls.length > 0) {
                console.log(`Loading ${saveData.urls.length} URLs...`);

                // Clear crawlState.urls first to avoid duplicate check issues
                crawlState.urls = [];

                // Add URLs to tables (addUrlToTable will handle adding to crawlState.urls)
                saveData.urls.forEach(url => {
                    // Debug: check if url has is_internal flag
                    if (url.is_internal === undefined) {
                        console.warn('URL missing is_internal flag:', url.url);
                        // Try to determine is_internal based on domain
                        if (crawlState.baseUrl) {
                            try {
                                const urlDomain = new URL(url.url).hostname.replace('www.', '');
                                const baseDomain = new URL(crawlState.baseUrl).hostname.replace('www.', '');
                                url.is_internal = urlDomain === baseDomain;
                            } catch (e) {
                                url.is_internal = false;
                            }
                        }
                    }
                    addUrlToTable(url);
                });

                console.log(`Added ${crawlState.urls.length} URLs to state`);
                console.log('Sample URL data:', crawlState.urls[0]);
            }

            // Load links data
            if (saveData.links && saveData.links.length > 0) {
                console.log(`Loading ${saveData.links.length} links...`);
                crawlState.pendingLinks = saveData.links;
                // If Links tab is currently active, load them immediately
                if (isLinksTabActive()) {
                    updateLinksTable(saveData.links);
                }
            }

            // Load issues data if present - filter them based on current exclusion settings
            if (saveData.issues && saveData.issues.length > 0) {
                console.log(`Loading ${saveData.issues.length} issues...`);

                // Filter issues using current exclusion patterns
                try {
                    const filterResponse = await fetch('/api/filter_issues', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ issues: saveData.issues })
                    });
                    const filterData = await filterResponse.json();

                    const filteredIssues = filterData.success ? filterData.issues : saveData.issues;
                    console.log(`Filtered to ${filteredIssues.length} issues after exclusions`);

                    crawlState.issues = filteredIssues;
                    crawlState.pendingIssues = filteredIssues;

                    // If Issues tab is currently active, load them immediately
                    if (isIssuesTabActive()) {
                        updateIssuesTable(filteredIssues);
                    } else {
                        // Update the badge count even if tab is not active
                        const issuesTabButton = Array.from(document.querySelectorAll('.tab-btn')).find(btn => btn.textContent.includes('Issues'));
                        if (issuesTabButton) {
                            const errorCount = filteredIssues.filter(i => i.type === 'error').length;
                            const warningCount = filteredIssues.filter(i => i.type === 'warning').length;
                            let badgeColor = '#3b82f6';
                            if (errorCount > 0) badgeColor = '#ef4444';
                            else if (warningCount > 0) badgeColor = '#f59e0b';
                            issuesTabButton.innerHTML = `Issues <span style="background: ${badgeColor}; color: white; padding: 2px 6px; border-radius: 12px; font-size: 12px;">${filteredIssues.length}</span>`;
                        }
                    }
                } catch (error) {
                    console.error('Failed to filter issues:', error);
                    // Fall back to unfiltered issues if filtering fails
                    crawlState.issues = saveData.issues;
                    crawlState.pendingIssues = saveData.issues;
                    if (isIssuesTabActive()) {
                        updateIssuesTable(saveData.issues);
                    }
                }
            }

            // Update all secondary data
            updateFilterCounts();
            updateStatusCodesTable();
            updateCrawlButtons();

            // Display PageSpeed results if available
            if (saveData.stats && saveData.stats.pagespeed_results) {
                console.log(`Loading ${saveData.stats.pagespeed_results.length} PageSpeed results...`);
                displayPageSpeedResults(saveData.stats.pagespeed_results);
            }

            // Force refresh of all tables
            setTimeout(() => {
                console.log('Force refreshing tables...');
                const overviewCount = document.getElementById('overviewTableBody').children.length;
                const internalCount = document.getElementById('internalTableBody').children.length;
                const externalCount = document.getElementById('externalTableBody').children.length;
                console.log(`Table counts - Overview: ${overviewCount}, Internal: ${internalCount}, External: ${externalCount}`);
            }, 100);

            // Update visualization if it exists and has been initialized
            if (typeof window.updateVisualizationFromLoadedData === 'function') {
                window.updateVisualizationFromLoadedData(saveData.urls, saveData.links);
            }

            // Notify plugins of loaded data
            if (window.LibreCrawlPlugin && window.LibreCrawlPlugin.loader) {
                window.LibreCrawlPlugin.loader.notifyDataUpdate({
                    urls: crawlState.urls,
                    links: crawlState.links,
                    issues: crawlState.issues,
                    stats: crawlState.stats
                });
            }

            showNotification(`Crawl loaded: ${saveData.stats.crawled} URLs from ${new Date(saveData.timestamp).toLocaleDateString()}`, 'success');

        } catch (error) {
            console.error('Load error:', error);
            showNotification(`Failed to load crawl file: ${error.message}`, 'error');
        } finally {
            if (loadCrawlBtn) loadCrawlBtn.textContent = 'Load Crawl';
        }
    });

    // Trigger file selection
    document.body.appendChild(fileInput);
    fileInput.click();
    document.body.removeChild(fileInput);
}

// ========================================
// Virtual Scroller Render Functions
// ========================================

function renderOverviewRow(row, urlData, index) {
    TABLE_COLUMNS.overview.forEach(column => {
        const cell = document.createElement('td');
        cell.dataset.col = column.key;

        if (tableHiddenColumns.overview.has(column.key)) {
            cell.classList.add('column-hidden');
        }

        if (column.key === 'details') {
            const button = document.createElement('button');
            button.className = 'details-btn';
            button.textContent = '📊 Details';
            button.addEventListener('click', () => showUrlDetails(urlData.url));
            cell.appendChild(button);
        } else {
            cell.textContent = displayColumnValue('overview', urlData, column.key);
        }

        row.appendChild(cell);
    });
}

function renderUrlRow(row, urlData, tableName) {
    TABLE_COLUMNS[tableName].forEach(column => {
        const cell = document.createElement('td');
        cell.dataset.col = column.key;

        if (tableHiddenColumns[tableName].has(column.key)) {
            cell.classList.add('column-hidden');
        }

        cell.textContent = displayColumnValue(tableName, urlData, column.key);
        row.appendChild(cell);
    });
}

function renderInternalRow(row, urlData, index) {
    renderUrlRow(row, urlData, 'internal');
}

function renderExternalRow(row, urlData, index) {
    renderUrlRow(row, urlData, 'external');
}

// Build a <td> with text set via textContent so crawled-page content
// (anchor text, URLs, issue details) can never inject markup
function makeTextCell(text, wordBreak) {
    const cell = document.createElement('td');
    if (wordBreak) cell.style.wordBreak = wordBreak;
    cell.textContent = text;
    return cell;
}

function makeStatusBadgeCell(targetStatus) {
    const cell = document.createElement('td');
    if (targetStatus) {
        const badge = document.createElement('span');
        badge.className = `status-badge status-${Math.floor(targetStatus / 100)}xx`;
        badge.textContent = targetStatus;
        cell.appendChild(badge);
    }
    return cell;
}

function renderInternalLinkRow(row, link, index) {
    const placement = link.placement ? link.placement.charAt(0).toUpperCase() + link.placement.slice(1) : 'Unknown';

    row.appendChild(makeTextCell(link.source_url, 'break-all'));
    row.appendChild(makeTextCell(link.target_url, 'break-all'));
    row.appendChild(makeStatusBadgeCell(link.target_status));
    row.appendChild(makeTextCell(link.anchor_text || ''));
    row.appendChild(makeTextCell(placement));
}

function renderExternalLinkRow(row, link, index) {
    const placement = link.placement ? link.placement.charAt(0).toUpperCase() + link.placement.slice(1) : 'Unknown';

    row.appendChild(makeTextCell(link.source_url, 'break-all'));
    row.appendChild(makeTextCell(link.target_url, 'break-all'));
    row.appendChild(makeStatusBadgeCell(link.target_status));
    row.appendChild(makeTextCell(link.target_domain || ''));
    row.appendChild(makeTextCell(placement));
}

function renderIssueRow(row, issue, index) {
    row.setAttribute('data-issue-type', issue.type);

    // Set row style based on issue type
    let typeIcon, typeColor;
    if (issue.type === 'error') {
        row.style.backgroundColor = 'rgba(239, 68, 68, 0.1)';
        typeIcon = '❌';
        typeColor = '#ef4444';
    } else if (issue.type === 'warning') {
        row.style.backgroundColor = 'rgba(245, 158, 11, 0.1)';
        typeIcon = '⚠️';
        typeColor = '#f59e0b';
    } else {
        row.style.backgroundColor = 'rgba(59, 130, 246, 0.1)';
        typeIcon = 'ℹ️';
        typeColor = '#3b82f6';
    }

    const urlCell = makeTextCell(issue.url, 'break-all');
    urlCell.title = issue.url;
    row.appendChild(urlCell);

    const typeCell = document.createElement('td');
    const icon = document.createElement('span');
    icon.style.color = typeColor;
    icon.textContent = typeIcon;
    typeCell.appendChild(icon);
    typeCell.appendChild(document.createTextNode(' ' + issue.type));
    row.appendChild(typeCell);

    row.appendChild(makeTextCell(issue.category));
    row.appendChild(makeTextCell(issue.issue));

    const detailsCell = makeTextCell(issue.details, 'break-word');
    detailsCell.title = issue.details;
    row.appendChild(detailsCell);
}
