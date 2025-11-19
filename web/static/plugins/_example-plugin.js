/**
 * Example Plugin Template for LibreCrawl
 * Copy this file and customize it to create your own plugin!
 *
 * This file starts with _ so it won't be loaded automatically.
 * To use it: rename to something like 'my-plugin.js' and add it to the plugin loader.
 */

LibreCrawlPlugin.register({
    // ==========================================
    // REQUIRED CONFIGURATION
    // ==========================================

    // Unique identifier for your plugin (use kebab-case)
    id: 'example-plugin',

    // Display name
    name: 'Example Plugin',

    // Tab configuration
    tab: {
        label: 'Example',      // Text shown on tab button
        icon: '🔥',            // Optional emoji icon
        position: 'end'        // Position: 'end' or number (0 = first tab)
    },

    // ==========================================
    // OPTIONAL METADATA
    // ==========================================

    version: '1.0.0',
    author: 'Your Name',
    description: 'A brief description of what your plugin does',

    // ==========================================
    // LIFECYCLE HOOKS
    // ==========================================

    /**
     * Called once when the plugin loads
     * Use for initialization, setup, etc.
     */
    onLoad() {
        console.log('Example plugin loaded!');

        // You can initialize state here
        this.myCustomState = {
            lastUpdate: null,
            processedCount: 0
        };
    },

    /**
     * Called when user switches to your tab
     * @param {HTMLElement} container - The DOM element for your tab content
     * @param {Object} data - Current crawl data
     */
    onTabActivate(container, data) {
        console.log('Tab activated with', data.urls.length, 'URLs');

        // Render your plugin UI
        this.render(container, data);
    },

    /**
     * Called when user switches away from your tab
     * Use for cleanup if needed
     */
    onTabDeactivate() {
        console.log('Tab deactivated');
        // Optional: clean up event listeners, timers, etc.
    },

    /**
     * Called during live crawls when new data arrives
     * @param {Object} data - Updated crawl data
     */
    onDataUpdate(data) {
        // Only update if your tab is currently active
        if (this.isActive && this.container) {
            this.render(this.container, data);
        }
    },

    /**
     * Called when a crawl completes
     * @param {Object} data - Final crawl data
     */
    onCrawlComplete(data) {
        console.log('Crawl completed!', data.urls.length, 'URLs total');

        // Optionally show notification
        this.utils.showNotification('Analysis complete!', 'success');
    },

    // ==========================================
    // YOUR CUSTOM METHODS
    // ==========================================

    /**
     * Main render function - builds your plugin UI
     * @param {HTMLElement} container - Container to render into
     * @param {Object} data - Crawl data { urls, links, issues, stats }
     */
    render(container, data) {
        // Handle empty state
        if (!data.urls || data.urls.length === 0) {
            container.innerHTML = this.renderEmptyState();
            return;
        }

        // Process the data
        const analysis = this.analyzeData(data);

        // Build your UI
        container.innerHTML = `
            <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div class="plugin-header" style="margin-bottom: 24px;">
                    <h2 style="font-size: 24px; font-weight: 700; color: #e5e7eb;">
                        🔥 Example Analysis
                    </h2>
                    <p style="color: #9ca3af; font-size: 14px;">
                        This is an example plugin showing the basic structure
                    </p>
                </div>

                <div style="background: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #374151;">
                    <h3 style="color: #e5e7eb; margin-bottom: 16px;">Summary</h3>
                    <div style="color: #cbd5e1;">
                        <p>Total URLs: ${data.urls.length}</p>
                        <p>Total Links: ${data.links ? data.links.length : 0}</p>
                        <p>Total Issues: ${data.issues ? data.issues.length : 0}</p>
                        <p>Custom Analysis Result: ${analysis.result}</p>
                    </div>
                </div>

                <div style="margin-top: 20px; background: #1f2937; padding: 20px; border-radius: 12px; border: 1px solid #374151;">
                    <h3 style="color: #e5e7eb; margin-bottom: 16px;">URL List</h3>
                    <div style="max-height: 400px; overflow-y: auto;">
                        ${this.renderUrlList(data.urls)}
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Your custom analysis logic
     * @param {Object} data - Crawl data
     * @returns {Object} - Analysis results
     */
    analyzeData(data) {
        // Example: Count how many URLs have specific characteristics
        let count = 0;

        data.urls.forEach(url => {
            // Your custom logic here
            if (url.status_code === 200) {
                count++;
            }
        });

        return {
            result: `Found ${count} successful URLs`,
            count: count
        };
    },

    /**
     * Render a list of URLs
     * @param {Array} urls - Array of URL objects
     * @returns {string} - HTML string
     */
    renderUrlList(urls) {
        return urls.slice(0, 20).map(url => `
            <div style="padding: 12px; border-bottom: 1px solid #374151; color: #cbd5e1; font-size: 13px;">
                <div style="font-weight: 600; margin-bottom: 4px;">
                    ${this.utils.escapeHtml(url.url)}
                </div>
                <div style="color: #9ca3af; font-size: 12px;">
                    Status: ${url.status_code} | Title: ${this.utils.escapeHtml(url.title || 'N/A')}
                </div>
            </div>
        `).join('');
    },

    /**
     * Render empty state when no data
     * @returns {string} - HTML string
     */
    renderEmptyState() {
        return `
            <div style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div style="text-align: center; padding: 60px 20px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">🔥</div>
                    <h3 style="font-size: 24px; color: #e5e7eb; margin-bottom: 12px;">
                        No Data Yet
                    </h3>
                    <p style="color: #9ca3af; font-size: 14px;">
                        Start crawling to see your analysis here
                    </p>
                </div>
            </div>
        `;
    },

    // ==========================================
    // AVAILABLE DATA STRUCTURE
    // ==========================================

    /*
    The 'data' object passed to your hooks contains:

    {
        urls: [
            {
                url: "https://example.com/page",
                status_code: 200,
                title: "Page Title",
                meta_description: "Meta description text",
                h1: "H1 heading",
                word_count: 1500,
                internal_links: 10,
                external_links: 5,
                analytics: { gtag: true, ga4_id: "G-XXX" },
                og_tags: { title: "OG Title", image: "..." },
                json_ld: [...],
                images: [...],
                // ... and much more!
            }
        ],

        links: [
            {
                source_url: "https://example.com/page1",
                target_url: "https://example.com/page2",
                anchor_text: "Click here",
                is_internal: true,
                target_status: 200
            }
        ],

        issues: [
            {
                url: "https://example.com/page",
                type: "error",
                category: "SEO",
                issue: "Missing title tag",
                details: "..."
            }
        ],

        stats: {
            discovered: 100,
            crawled: 100,
            depth: 3,
            speed: 5
        }
    }
    */

    // ==========================================
    // AVAILABLE UTILITIES
    // ==========================================

    /*
    You have access to utility functions via this.utils:

    - this.utils.showNotification(message, type)
      Display a notification to the user
      Types: 'success', 'error', 'info'

    - this.utils.escapeHtml(text)
      Escape HTML to prevent XSS

    - this.utils.formatUrl(url, maxLength)
      Truncate long URLs for display
    */

    // ==========================================
    // PLUGIN STATE
    // ==========================================

    /*
    Available properties on 'this':

    - this.isActive - Boolean: is your tab currently visible?
    - this.container - HTMLElement: your tab's container
    - this.id - Your plugin ID
    - this.name - Your plugin name
    - this.version - Your plugin version

    You can also add your own properties in onLoad()
    */
});

console.log('Example plugin template registered');
