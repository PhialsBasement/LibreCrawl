/**
 * Incremental Polling Manager
 * Handles fetching only new data from the server and accumulating it locally
 * to avoid transferring massive amounts of data on every poll.
 */

class IncrementalPoller {
    constructor() {
        // Track what we've received so far
        this.lastUrlCount = 0;
        this.lastLinkCount = 0;
        this.lastIssueCount = 0;

        // Accumulated data
        this.allUrls = [];
        this.allLinks = [];
        this.allIssues = [];

        // Latest stats and status
        this.latestStats = null;
        this.latestStatus = null;
        this.latestProgress = 0;
        this.isRunningPagespeed = false;
        this.memory = null;
        this.memoryData = null;
    }

    /**
     * Reset the poller state (call when starting a new crawl)
     */
    reset() {
        this.lastUrlCount = 0;
        this.lastLinkCount = 0;
        this.lastIssueCount = 0;
        this.allUrls = [];
        this.allLinks = [];
        this.allIssues = [];
        this.latestStats = null;
        this.latestStatus = null;
        this.latestProgress = 0;
        this.isRunningPagespeed = false;
        this.memory = null;
        this.memoryData = null;
    }

    /**
     * Fetch incremental update from server
     * @returns {Promise<Object>} Full crawl data (accumulated + new)
     */
    async fetchUpdate() {
        try {
            // Request only data after our last known counts
            const params = new URLSearchParams({
                url_since: this.lastUrlCount,
                link_since: this.lastLinkCount,
                issue_since: this.lastIssueCount
            });

            const response = await fetch(`/api/crawl_status?${params}`);
            const data = await response.json();

            // Update stats and status (always sent in full)
            this.latestStats = data.stats || this.latestStats;
            this.latestStatus = data.status || this.latestStatus;
            this.latestProgress = data.progress || 0;
            this.isRunningPagespeed = data.is_running_pagespeed || false;
            this.memory = data.memory || this.memory;
            this.memoryData = data.memory_data || this.memoryData;

            // Accumulate new data
            if (data.urls && data.urls.length > 0) {
                this.allUrls.push(...data.urls);
                this.lastUrlCount = this.allUrls.length;
            }

            if (data.links && data.links.length > 0) {
                this.allLinks.push(...data.links);
                this.lastLinkCount = this.allLinks.length;
            }

            if (data.issues && data.issues.length > 0) {
                this.allIssues.push(...data.issues);
                this.lastIssueCount = this.allIssues.length;
            }

            // Return data in the same format as the old get_status
            return {
                status: this.latestStatus,
                stats: this.latestStats,
                urls: this.allUrls,
                links: this.allLinks,
                issues: this.allIssues,
                progress: this.latestProgress,
                is_running_pagespeed: this.isRunningPagespeed,
                memory: this.memory,
                memory_data: this.memoryData
            };

        } catch (error) {
            console.error('Error in incremental fetch:', error);
            throw error;
        }
    }

    /**
     * Get current accumulated data without fetching
     * @returns {Object} Current full crawl data
     */
    getCurrentData() {
        return {
            status: this.latestStatus,
            stats: this.latestStats,
            urls: this.allUrls,
            links: this.allLinks,
            issues: this.allIssues,
            progress: this.latestProgress,
            is_running_pagespeed: this.isRunningPagespeed,
            memory: this.memory,
            memory_data: this.memoryData
        };
    }
}

// Export for use in app.js
window.IncrementalPoller = IncrementalPoller;
