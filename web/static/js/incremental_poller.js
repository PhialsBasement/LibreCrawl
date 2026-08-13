/**
 * Incremental Polling Manager
 *
 * Syncs crawl data from the server through its event log. Each poll sends
 * the last sequence number the client has seen (plus the data epoch) and
 * receives only the events after it — including updates to rows the client
 * already holds (link status backfills, linked_from updates), which the old
 * count-based array slicing could never deliver.
 *
 * When the server's data generation changes (new crawl, loaded crawl,
 * resume), the epoch changes and the server sets `reset: true`; the poller
 * drops its accumulated state and rebuilds from the replayed stream.
 */

class IncrementalPoller {
    constructor() {
        this.reset();
    }

    /**
     * Reset the poller state (call when starting a new crawl)
     */
    reset() {
        this.resetData();
        this.latestStats = null;
        this.latestStatus = null;
        this.latestProgress = 0;
        this.isRunningPagespeed = false;
        this.memory = null;
        this.memoryData = null;
    }

    resetData() {
        this.epoch = '';
        this.seq = 0;
        this.allUrls = [];
        this.urlIndex = new Map();      // url -> index in allUrls
        this.allLinks = [];
        this.linkIndex = new Map();     // "source|target" -> index in allLinks
        this.allIssues = [];
    }

    /**
     * Apply a batch of events to the accumulated arrays.
     * Returns which collections changed, so the UI can skip untouched tables.
     */
    applyEvents(events) {
        const changed = { urls: false, links: false, issues: false };

        for (const ev of events) {
            const d = ev.data;
            switch (ev.kind) {
                case 'url':
                case 'url_update': {
                    const i = this.urlIndex.get(d.url);
                    if (i === undefined) {
                        this.urlIndex.set(d.url, this.allUrls.length);
                        this.allUrls.push(d);
                    } else {
                        this.allUrls[i] = d;
                    }
                    changed.urls = true;
                    break;
                }
                case 'link':
                case 'link_update': {
                    const key = d.source_url + '|' + d.target_url;
                    const i = this.linkIndex.get(key);
                    if (i === undefined) {
                        this.linkIndex.set(key, this.allLinks.length);
                        this.allLinks.push(d);
                    } else {
                        this.allLinks[i] = d;
                    }
                    changed.links = true;
                    break;
                }
                case 'issue':
                    this.allIssues.push(d);
                    changed.issues = true;
                    break;
            }
        }

        return changed;
    }

    /**
     * Fetch incremental update from server
     * @returns {Promise<Object>} Full crawl data (accumulated + new)
     */
    async fetchUpdate() {
        try {
            const params = new URLSearchParams({
                since_seq: this.seq,
                epoch: this.epoch
            });

            const response = await fetch(`/api/crawl_status?${params}`);
            const data = await response.json();

            // Stale epoch: the server has a new data generation — drop
            // everything and rebuild from the replayed events
            if (data.reset) {
                this.resetData();
            }

            this.epoch = data.epoch || this.epoch;
            this.seq = typeof data.latest_seq === 'number' ? data.latest_seq : this.seq;

            const changed = this.applyEvents(data.events || []);
            if (data.reset) {
                changed.urls = changed.links = changed.issues = true;
            }

            // Status and stats are always sent in full
            this.latestStats = data.stats || this.latestStats;
            this.latestStatus = data.status || this.latestStatus;
            this.latestProgress = data.progress || 0;
            this.isRunningPagespeed = data.is_running_pagespeed || false;
            this.memory = data.memory || this.memory;
            this.memoryData = data.memory_data || this.memoryData;

            return {
                status: this.latestStatus,
                stats: this.latestStats,
                urls: this.allUrls,
                links: this.allLinks,
                issues: this.allIssues,
                progress: this.latestProgress,
                is_running_pagespeed: this.isRunningPagespeed,
                memory: this.memory,
                memory_data: this.memoryData,
                demo_stopped: data.demo_stopped || false,
                demo_mode: data.demo_mode || false,
                changed: changed
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
