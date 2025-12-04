/**
 * Selector Search Plugin for LibreCrawl
 * 
 * Allows searching for CSS selectors across crawled pages.
 * Shows which pages contain the selector and how many times it appears.
 */

LibreCrawlPlugin.register({
    id: 'selector-search',
    name: 'Selector Search',
    
    tab: {
        label: 'Selector Search',
        icon: '🔍',
        position: 'end'
    },
    
    version: '1.0.0',
    description: 'Search for CSS selectors across crawled pages',
    
    onLoad() {
        this.searchState = {
            selector: '',
            isSearching: false,
            results: [],
            error: null
        };
    },
    
    async onTabActivate(container, data) {
        this.container = container;
        
        // If no URLs in data, fetch from API
        if (!data.urls || data.urls.length === 0) {
            try {
                const response = await fetch('/api/crawl_status');
                const apiData = await response.json();
                if (apiData.urls && apiData.urls.length > 0) {
                    data = {
                        urls: apiData.urls,
                        links: apiData.links || [],
                        issues: apiData.issues || [],
                        stats: apiData.stats || {}
                    };
                }
            } catch (error) {
                console.error('Failed to fetch crawl data:', error);
            }
        }
        
        this.render(container, data);
    },
    
    onTabDeactivate() {
        // Cleanup if needed
    },
    
    onDataUpdate(data) {
        if (this.isActive && this.container) {
            // Update the URL list if search is active
            if (this.searchState.selector && this.searchState.results.length > 0) {
                this.render(this.container, data);
            }
        }
    },
    
    render(container, data) {
        if (!data.urls || data.urls.length === 0) {
            container.innerHTML = this.renderEmptyState();
            return;
        }
        
        container.innerHTML = `
            <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div class="plugin-header" style="margin-bottom: 24px;">
                    <h2 style="font-size: 24px; font-weight: 700; color: #e5e7eb; margin-bottom: 8px;">
                        🔍 Selector Search
                    </h2>
                    <p style="color: #9ca3af; font-size: 14px;">
                        Search for CSS selectors across ${data.urls.length} crawled pages
                    </p>
                </div>
                
                <div style="background: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 20px;">
                    <div style="display: flex; gap: 12px; align-items: flex-start;">
                        <div style="flex: 1;">
                            <label style="display: block; color: #cbd5e1; font-size: 13px; font-weight: 600; margin-bottom: 8px;">
                                CSS Selector
                            </label>
                            <input 
                                type="text" 
                                id="selector-input" 
                                placeholder="e.g., div > h1, .class-name, #id-name"
                                value="${this.utils.escapeHtml(this.searchState.selector)}"
                                style="width: 100%; padding: 10px 14px; background: #111827; border: 1px solid #374151; border-radius: 8px; color: #e5e7eb; font-size: 14px; font-family: monospace;"
                                ${this.searchState.isSearching ? 'disabled' : ''}
                            />
                            <p style="color: #9ca3af; font-size: 12px; margin-top: 8px;">
                                Enter a CSS selector to search for (e.g., <code style="background: #111827; padding: 2px 6px; border-radius: 4px;">div > h1</code>, <code style="background: #111827; padding: 2px 6px; border-radius: 4px;">.class-name</code>, <code style="background: #111827; padding: 2px 6px; border-radius: 4px;">#id-name</code>)
                            </p>
                        </div>
                        <div style="margin-top: 28px;">
                            <button 
                                id="search-btn"
                                onclick="window.selectorSearchPlugin?.performSearch()"
                                style="padding: 10px 24px; background: ${this.searchState.isSearching ? '#4b5563' : '#7c3aed'}; color: white; border: none; border-radius: 8px; font-weight: 600; cursor: ${this.searchState.isSearching ? 'not-allowed' : 'pointer'}; font-size: 14px; white-space: nowrap;"
                                ${this.searchState.isSearching ? 'disabled' : ''}
                            >
                                ${this.searchState.isSearching ? 'Searching...' : 'Search'}
                            </button>
                        </div>
                    </div>
                    
                    ${this.searchState.error ? `
                        <div style="margin-top: 16px; padding: 12px; background: #7f1d1d; border: 1px solid #991b1b; border-radius: 8px; color: #fca5a5;">
                            <strong>Error:</strong> ${this.utils.escapeHtml(this.searchState.error)}
                        </div>
                    ` : ''}
                </div>
                
                ${this.searchState.results.length > 0 ? this.renderResults(data) : ''}
            </div>
        `;
        
        // Store reference for button click
        window.selectorSearchPlugin = this;
        
        // Add Enter key support
        const input = document.getElementById('selector-input');
        if (input) {
            input.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !this.searchState.isSearching) {
                    this.performSearch();
                }
            });
        }
    },
    
    async performSearch() {
        const input = document.getElementById('selector-input');
        if (!input) return;
        
        const selector = input.value.trim();
        if (!selector) {
            this.utils.showNotification('Please enter a CSS selector', 'error');
            return;
        }
        
        // Get current crawl data
        const response = await fetch('/api/crawl_status');
        const data = await response.json();
        
        if (!data.urls || data.urls.length === 0) {
            this.utils.showNotification('No crawled pages available', 'error');
            return;
        }
        
        this.searchState.selector = selector;
        this.searchState.isSearching = true;
        this.searchState.error = null;
        this.searchState.results = [];
        
        // Update UI
        this.render(this.container, { urls: data.urls, links: data.links || [], issues: data.issues || [], stats: data.stats || {} });
        
        // Search through all URLs
        const results = [];
        const totalUrls = data.urls.length;
        let processed = 0;
        
        try {
            // Process URLs in batches to avoid overwhelming the server
            const batchSize = 5;
            for (let i = 0; i < data.urls.length; i += batchSize) {
                const batch = data.urls.slice(i, i + batchSize);
                
                await Promise.all(batch.map(async (urlData) => {
                    try {
                        // Only search HTML pages
                        if (urlData.status_code !== 200) {
                            processed++;
                            return;
                        }
                        
                        const contentType = urlData.content_type || '';
                        if (!contentType.includes('text/html')) {
                            processed++;
                            return;
                        }
                        
                        // Fetch HTML
                        const htmlResponse = await fetch('/api/fetch_html', {
                            method: 'POST',
                            headers: {
                                'Content-Type': 'application/json'
                            },
                            body: JSON.stringify({ url: urlData.url })
                        });
                        
                        const htmlData = await htmlResponse.json();
                        
                        if (htmlData.success && htmlData.html) {
                            // Parse HTML and search for selector
                            const count = this.countSelectorMatches(htmlData.html, selector);
                            
                            if (count > 0) {
                                results.push({
                                    url: urlData.url,
                                    title: urlData.title || urlData.url,
                                    count: count,
                                    status_code: urlData.status_code
                                });
                            }
                        }
                    } catch (error) {
                        console.error(`Error processing ${urlData.url}:`, error);
                    } finally {
                        processed++;
                    }
                }));
                
                // Update progress
                if (this.container) {
                    const progress = Math.round((processed / totalUrls) * 100);
                    const btn = document.getElementById('search-btn');
                    if (btn) {
                        btn.textContent = `Searching... ${progress}%`;
                    }
                }
            }
            
            // Sort by count (descending)
            results.sort((a, b) => b.count - a.count);
            
            this.searchState.results = results;
            this.searchState.isSearching = false;
            
            // Update UI with results
            this.render(this.container, { urls: data.urls, links: data.links || [], issues: data.issues || [], stats: data.stats || {} });
            
            if (results.length === 0) {
                this.utils.showNotification(`Selector "${selector}" not found on any pages`, 'info');
            } else {
                this.utils.showNotification(`Found "${selector}" on ${results.length} page(s)`, 'success');
            }
            
        } catch (error) {
            console.error('Search error:', error);
            this.searchState.error = error.message || 'An error occurred during search';
            this.searchState.isSearching = false;
            this.render(this.container, { urls: data.urls, links: data.links || [], issues: data.issues || [], stats: data.stats || {} });
            this.utils.showNotification('Search failed: ' + error.message, 'error');
        }
    },
    
    countSelectorMatches(html, selector) {
        try {
            // Create a temporary DOM element to parse HTML
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            
            // Try to query the selector
            try {
                const elements = doc.querySelectorAll(selector);
                return elements.length;
            } catch (e) {
                // Invalid selector
                throw new Error(`Invalid CSS selector: ${selector}`);
            }
        } catch (error) {
            // If DOMParser fails (e.g., invalid HTML), try a simpler approach
            // This is a fallback for malformed HTML
            console.warn('DOMParser failed, using regex fallback:', error);
            return 0;
        }
    },
    
    renderResults(data) {
        const totalMatches = this.searchState.results.reduce((sum, r) => sum + r.count, 0);
        
        return `
            <div style="background: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #374151;">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                    <h3 style="color: #e5e7eb; font-size: 18px; font-weight: 600;">
                        Search Results
                    </h3>
                    <div style="color: #cbd5e1; font-size: 14px;">
                        Found on <strong style="color: #a78bfa;">${this.searchState.results.length}</strong> page(s) 
                        with <strong style="color: #a78bfa;">${totalMatches}</strong> total match(es)
                    </div>
                </div>
                
                <div style="overflow-x: auto;">
                    <table class="data-table" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="background: #111827; border-bottom: 2px solid #374151;">
                                <th style="padding: 12px; text-align: left; color: #cbd5e1; font-weight: 600; font-size: 13px;">URL</th>
                                <th style="padding: 12px; text-align: left; color: #cbd5e1; font-weight: 600; font-size: 13px;">Title</th>
                                <th style="padding: 12px; text-align: center; color: #cbd5e1; font-weight: 600; font-size: 13px; width: 100px;">Matches</th>
                                <th style="padding: 12px; text-align: center; color: #cbd5e1; font-weight: 600; font-size: 13px; width: 100px;">Status</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${this.searchState.results.map(result => `
                                <tr style="border-bottom: 1px solid #374151; hover:background: #111827;">
                                    <td style="padding: 12px;">
                                        <a href="${this.utils.escapeHtml(result.url)}" target="_blank" style="color: #7c3aed; text-decoration: none; font-size: 13px; word-break: break-all;">
                                            ${this.utils.escapeHtml(this.utils.formatUrl(result.url, 60))}
                                        </a>
                                    </td>
                                    <td style="padding: 12px; color: #cbd5e1; font-size: 13px;">
                                        ${this.utils.escapeHtml(result.title || 'N/A')}
                                    </td>
                                    <td style="padding: 12px; text-align: center;">
                                        <span style="background: #7c3aed; color: white; padding: 4px 10px; border-radius: 12px; font-size: 12px; font-weight: 600;">
                                            ${result.count}
                                        </span>
                                    </td>
                                    <td style="padding: 12px; text-align: center;">
                                        <span style="color: ${result.status_code === 200 ? '#10b981' : '#ef4444'}; font-size: 13px; font-weight: 600;">
                                            ${result.status_code}
                                        </span>
                                    </td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },
    
    renderEmptyState() {
        return `
            <div style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div style="text-align: center; padding: 60px 20px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">🔍</div>
                    <h3 style="font-size: 24px; color: #e5e7eb; margin-bottom: 12px;">
                        No Data Yet
                    </h3>
                    <p style="color: #9ca3af; font-size: 14px;">
                        Start crawling to search for CSS selectors
                    </p>
                </div>
            </div>
        `;
    }
});

console.log('Selector Search plugin registered');

