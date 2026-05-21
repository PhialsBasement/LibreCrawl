/**
 * Page Diagnostics Plugin for LibreCrawl
 * Broad health summary, issues table with fixes, meta tag matrix, performance analysis
 *
 * @author LibreCrawl Community
 * @version 1.0.0
 */

const ISSUE_KNOWLEDGE = {
    // ── SEO ──────────────────────────────────────────────────────────────────
    'Missing Title Tag': {
        fix: 'Add a <title> tag inside <head> with 30–60 characters. Use your primary keyword near the front.',
        priority: 'high'
    },
    'Title Too Long': {
        fix: 'Shorten to under 60 characters. Google truncates longer titles in SERPs, hiding your message.',
        priority: 'medium'
    },
    'Title Too Short': {
        fix: 'Expand to at least 30 characters. Short titles miss keyword and context opportunities.',
        priority: 'low'
    },
    'Missing Meta Description': {
        fix: 'Add <meta name="description" content="..."> with 120–160 characters summarising the page.',
        priority: 'high'
    },
    'Meta Description Too Long': {
        fix: 'Trim to under 160 characters. Google will truncate it anyway, so make every word count.',
        priority: 'low'
    },
    'Meta Description Too Short': {
        fix: 'Expand to at least 120 characters. Use this space to drive click-through with a clear value statement.',
        priority: 'low'
    },
    'Missing H1 Tag': {
        fix: 'Add one <h1> heading that matches the page topic and includes your primary keyword.',
        priority: 'high'
    },

    // ── Content ───────────────────────────────────────────────────────────────
    'Thin Content': {
        fix: 'Expand content. Minimums by page type: homepage 500 words, service page 800, blog post 1,500, product page 300. Focus on original insight, not filler.',
        priority: 'medium'
    },
    'Duplicate Content Detected': {
        fix: 'Add a canonical tag pointing to the preferred version, or 301-redirect duplicates to the primary URL.',
        priority: 'medium'
    },

    // ── Technical ─────────────────────────────────────────────────────────────
    '[4xx] Client Error': {
        fix: 'Update or remove internal links pointing here. If the page moved, add a 301 redirect to the new URL.',
        priority: 'high'
    },
    '[5xx] Server Error': {
        fix: 'Investigate the server-side error. Check application logs, database connections, and memory limits.',
        priority: 'high'
    },
    '[3xx] Redirect': {
        fix: 'Update internal links to point directly to the final destination URL to eliminate redirect hops.',
        priority: 'low'
    },
    'Missing Canonical URL': {
        fix: 'Add <link rel="canonical" href="[this-page-url]"> to the <head> to prevent duplicate content issues.',
        priority: 'medium'
    },
    'Canonical URL Different': {
        fix: 'Verify the canonical points to the intended URL. A mismatch can signal to Google that this page is a duplicate.',
        priority: 'medium'
    },
    'DNS Not Found': {
        fix: 'The domain does not resolve. Remove or update any internal links pointing to this non-existent URL.',
        priority: 'high'
    },
    'Connection Refused': {
        fix: 'Server actively refused the connection. Verify the server is running and the port is open.',
        priority: 'high'
    },
    'Request Timeout': {
        fix: 'Server took too long to respond. Investigate server performance, queuing, and resource exhaustion.',
        priority: 'high'
    },
    'SSL/TLS Error': {
        fix: 'Fix the SSL certificate: check expiry date, verify the certificate covers this domain, and ensure the chain is complete.',
        priority: 'high'
    },

    // ── Performance ───────────────────────────────────────────────────────────
    'Slow Response Time': {
        fix: 'Server response exceeds 3s. Add edge caching or a CDN, optimise database queries, and reduce server-side computation. Target TTFB under 200ms.',
        priority: 'high'
    },
    'Moderate Response Time': {
        fix: 'Response is 1–3s. Ideal TTFB is under 200ms. Enable HTTP caching headers and move static assets to a CDN.',
        priority: 'medium'
    },
    'Large Page Size': {
        fix: 'HTML payload exceeds 3 MB. Enable Gzip/Brotli compression on the server, remove inline scripts/styles, and defer non-critical content.',
        priority: 'high'
    },
    'Moderate Page Size': {
        fix: 'HTML payload is 1–3 MB. Enable server-side compression. Every extra 10 KB uncompressed adds ~80–150 ms on mobile connections.',
        priority: 'medium'
    },

    // ── Mobile ────────────────────────────────────────────────────────────────
    'Missing Viewport Meta Tag': {
        fix: 'Add <meta name="viewport" content="width=device-width, initial-scale=1"> to <head>. Without it, mobile browsers render at desktop width.',
        priority: 'high'
    },

    // ── Accessibility ─────────────────────────────────────────────────────────
    'Missing Language Attribute': {
        fix: 'Add lang attribute to <html> (e.g. <html lang="en">). Required for screen readers and correct browser rendering.',
        priority: 'medium'
    },
    'Images Without Alt Text': {
        fix: 'Add descriptive alt="" to every <img>. Describe what the image shows. Use alt="" (empty) only for purely decorative images.',
        priority: 'medium'
    },

    // ── Content (images) ──────────────────────────────────────────────────────
    'Broken Image (No Response)': {
        fix: 'Image URL returned no response. If the image was deleted, replace it with a working image or remove the <img> tag entirely.',
        priority: 'high'
    },
    'Broken Image': {
        fix: 'Image URL returned an error status. Check the URL is correct; if deleted, replace or remove the <img> tag.',
        priority: 'high'
    },

    // ── Social ────────────────────────────────────────────────────────────────
    'Missing OpenGraph Tags': {
        fix: 'Add og:title, og:description, and og:image meta tags. These control how your page appears when shared on social media.',
        priority: 'medium'
    },
    'Missing Twitter Card Tags': {
        fix: 'Add twitter:card, twitter:title, twitter:description, and twitter:image meta tags for rich previews on X/Twitter.',
        priority: 'low'
    },

    // ── Structured Data ───────────────────────────────────────────────────────
    'No Structured Data': {
        fix: 'Add JSON-LD schema markup (Article, Organization, Product, or BreadcrumbList) in a <script type="application/ld+json"> block to improve rich result eligibility.',
        priority: 'medium'
    },

    // ── Indexability ──────────────────────────────────────────────────────────
    'Noindex Tag Present': {
        fix: 'The page has a noindex directive. Confirm this is intentional. If the page should be indexed, remove the noindex from meta robots or the X-Robots-Tag header.',
        priority: 'high'
    },
    'Nofollow Tag Present': {
        fix: 'The page has a nofollow directive. This prevents link equity from passing to linked pages. Remove if unintentional.',
        priority: 'medium'
    },

    // ── Fallback ──────────────────────────────────────────────────────────────
    '_default': {
        fix: 'Review the issue details above and consult the relevant documentation for your CMS or framework.',
        priority: 'low'
    }
};

LibreCrawlPlugin.register({
    id: 'page-diagnostics',
    name: 'Page Diagnostics',
    version: '1.0.0',
    author: 'LibreCrawl Community',
    description: 'Broad health diagnostics: broken links, missing meta tags, performance issues, and fix guidance',

    tab: {
        label: 'Diagnostics',
        icon: '🔍',
        position: 'end'
    },

    onLoad() {
        console.log('🔍 Page Diagnostics plugin loaded');
    },

    onTabActivate(container, data) {
        console.log('🔍 Page Diagnostics tab activated');
        this.render(container, data);
    },

    onDataUpdate(data) {
        if (this.isActive && this.container) {
            this.render(this.container, data);
        }
    },

    onCrawlComplete(data) {
        console.log('✅ Page Diagnostics complete');
        if (this.isActive && this.container) {
            this.render(this.container, data);
        }
    },

    render(container, data) {
        if (!data || !data.urls || data.urls.length === 0) {
            container.innerHTML = this.renderEmptyState();
            return;
        }

        const { urls, issues, links } = data;
        const internalUrls = urls.filter(u => u.is_internal !== false);

        container.innerHTML = `
            <div class="plugin-content" style="padding: 20px; overflow-y: auto; overflow-x: hidden; max-height: calc(100vh - 280px);">
                ${this.renderHeader()}
                ${this.renderSummaryCards(issues, internalUrls, links)}
                ${this.renderIssuesTable(issues)}
                ${this.renderMetaTagMatrix(internalUrls)}
                ${this.renderPerformanceAnalysis(internalUrls)}
            </div>
        `;

        // Attach filter event listeners (category + URL search)
        const filterSelect = container.querySelector('#pd-category-filter');
        const urlSearchInput = container.querySelector('#pd-url-search');

        const applyFilters = () => {
            const selected = filterSelect ? filterSelect.value : 'All';
            const urlQuery = urlSearchInput ? urlSearchInput.value.trim().toLowerCase() : '';
            const table = container.querySelector('#pd-issues-table');
            if (!table) return;
            table.querySelectorAll('tbody tr').forEach(row => {
                const categoryMatch = selected === 'All' || row.dataset.category === selected;
                const urlAnchor = row.querySelector('a');
                const urlMatch = !urlQuery || (urlAnchor && urlAnchor.getAttribute('href').toLowerCase().includes(urlQuery));
                row.style.display = (categoryMatch && urlMatch) ? '' : 'none';
            });
        };

        if (filterSelect) filterSelect.addEventListener('change', applyFilters);
        if (urlSearchInput) urlSearchInput.addEventListener('input', applyFilters);

        // Attach "Ask AI" button event listeners with localStorage caching
        const aiButtons = container.querySelectorAll('.ai-btn');
        aiButtons.forEach(btn => {
            btn.addEventListener('click', async (e) => {
                e.preventDefault();
                const url = btn.dataset.url;
                const issue = btn.dataset.issue;
                const category = btn.dataset.category;
                const details = btn.dataset.details;
                const cacheKey = btn.dataset.cacheKey;
                const row = btn.closest('tr');
                const responseDiv = row.querySelector(`.ai-response[data-cache-key="${cacheKey}"]`);
                const staticFixDiv = row.querySelector('.static-fix');

                if (!responseDiv) return;

                // Check localStorage cache first
                const cached = localStorage.getItem(cacheKey);
                if (cached) {
                    const cachedData = JSON.parse(cached);
                    this.displayAIResponse(responseDiv, staticFixDiv, cachedData, btn);
                    return;
                }

                // Show loading state
                btn.disabled = true;
                btn.innerHTML = '🤔 Thinking...';
                btn.style.opacity = '0.6';
                responseDiv.style.display = 'block';
                responseDiv.innerHTML = `
                    <div style="color: #f59e0b; font-size: 12px;">
                        <span style="display: inline-block; animation: pulse 1.5s infinite;">●</span> AI is analyzing...
                    </div>
                `;

                // Find page context from data
                const pageData = urls.find(u => u.url === url) || {};

                try {
                    const resp = await fetch('/api/explain_issue', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            url: url,
                            issue: issue,
                            category: category,
                            details: details,
                            page_context: {
                                title: pageData.title || '',
                                word_count: pageData.word_count || 0,
                                meta_description: pageData.meta_description || '',
                                h1: pageData.h1 || ''
                            }
                        })
                    });

                    const result = await resp.json();

                    if (result.success) {
                        // Cache in localStorage
                        localStorage.setItem(cacheKey, JSON.stringify(result));
                        this.displayAIResponse(responseDiv, staticFixDiv, result, btn);
                    } else {
                        // API failed — fallback to static ISSUE_KNOWLEDGE
                        responseDiv.innerHTML = `
                            <div style="color: #ef4444; font-size: 12px; margin-bottom: 8px;">
                                ⚠️ AI unavailable. Showing built-in advice:
                            </div>
                            <div style="color: #cbd5e1;">
                                ${this.utils.escapeHtml((ISSUE_KNOWLEDGE[issue] || ISSUE_KNOWLEDGE['_default']).fix)}
                            </div>
                        `;
                        responseDiv.style.display = 'block';
                        btn.disabled = false;
                        btn.innerHTML = '✨ Ask AI';
                        btn.style.opacity = '1';
                    }
                } catch (err) {
                    responseDiv.innerHTML = `
                        <div style="color: #ef4444; font-size: 12px;">
                            ❌ Error: ${this.utils.escapeHtml(err.message)}
                        </div>
                    `;
                    responseDiv.style.display = 'block';
                    btn.disabled = false;
                    btn.innerHTML = '✨ Ask AI';
                    btn.style.opacity = '1';
                }
            });
        });

        // Attach "Create Ticket" button event listeners
        const ticketButtons = container.querySelectorAll('.ticket-btn');
        ticketButtons.forEach(btn => {
            btn.addEventListener('click', async () => {
                const cacheKey = btn.dataset.cacheKey;
                const row = btn.closest('tr');
                const ticketResult = row.querySelector(`.ticket-result[data-cache-key="${cacheKey}"]`);

                // Use cached AI response if available, otherwise fall back to static knowledge
                const cached = localStorage.getItem(cacheKey);
                let aiExp = '', aiHowToFix = '', aiPriority = 'medium', aiRole = '';
                if (cached) {
                    const c = JSON.parse(cached);
                    aiExp       = c.explanation  || '';
                    aiHowToFix  = c.how_to_fix   || '';
                    aiPriority  = c.priority      || 'medium';
                    aiRole      = c.role          || '';
                } else {
                    const knowledge = ISSUE_KNOWLEDGE[btn.dataset.issue] || ISSUE_KNOWLEDGE['_default'];
                    aiHowToFix = knowledge.fix;
                    aiPriority = knowledge.priority;
                }

                btn.disabled = true;
                btn.innerHTML = '⏳ Creating...';

                try {
                    const ctx = window.devopsContext || {};
                    const resp = await fetch('/api/create_devops_ticket', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            url:              btn.dataset.url,
                            issue:            btn.dataset.issue,
                            category:         btn.dataset.category,
                            issue_type:       btn.dataset.issueType,
                            ai_explanation:   aiExp,
                            ai_how_to_fix:    aiHowToFix,
                            ai_priority:      aiPriority,
                            ai_role:          aiRole,
                            project_override:   ctx.project  || '',
                            parent_id_override: ctx.parentId || ''
                        })
                    });
                    const result = await resp.json();

                    if (result.success) {
                        btn.innerHTML = '✅ Ticket Created';
                        btn.style.opacity = '0.6';
                        btn.style.cursor = 'default';
                        if (ticketResult) {
                            ticketResult.style.display = 'block';
                            ticketResult.innerHTML = `
                                <div style="color:#6b7280; margin-bottom:3px;">Azure title: <em>${this.utils.escapeHtml(result.title || '')}</em></div>
                                <a href="${result.ticket_url}" target="_blank" style="color:#3b82f6; text-decoration:none;">View PBI #${result.ticket_id} in Azure Boards →</a>
                            `;
                        }
                    } else {
                        btn.disabled = false;
                        btn.innerHTML = '🎫 Create Ticket';
                        if (ticketResult) {
                            ticketResult.style.display = 'block';
                            ticketResult.innerHTML = `<span style="color: #ef4444;">❌ ${this.utils.escapeHtml(result.error)}</span>`;
                        }
                    }
                } catch (err) {
                    btn.disabled = false;
                    btn.innerHTML = '🎫 Create Ticket';
                    if (ticketResult) {
                        ticketResult.style.display = 'block';
                        ticketResult.innerHTML = `<span style="color: #ef4444;">❌ ${this.utils.escapeHtml(err.message)}</span>`;
                    }
                }
            });
        });

        const issuePairs = (issues || [])
            .filter(i => (i.type || 'info') !== 'info')
            .map(i => ({
                url: i.url,
                issue: i.issue,
                cache_key: 'ai_' + btoa(unescape(encodeURIComponent(i.url + '|' + i.issue))).replace(/[=+/]/g, '')
            }));

        if (issuePairs.length > 0) {
            fetch('/api/devops_tickets/check', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pairs: issuePairs })
            })
            .then(r => r.json())
            .then(result => {
                if (!result.success) return;
                Object.entries(result.tickets).forEach(([cacheKey, ticket]) => {
                    const btn = container.querySelector(`.ticket-btn[data-cache-key="${cacheKey}"]`);
                    if (!btn) return;
                    const row = btn.closest('tr');
                    btn.style.display = 'flex';
                    btn.disabled = true;
                    btn.innerHTML = '✅ Ticket Exists';
                    btn.style.opacity = '0.6';
                    btn.style.cursor = 'default';
                    const ticketResult = row.querySelector(`.ticket-result[data-cache-key="${cacheKey}"]`);
                    if (ticketResult) {
                        ticketResult.style.display = 'block';
                        ticketResult.innerHTML = `<a href="${ticket.ticket_url}" target="_blank" style="color: #3b82f6; text-decoration: none;">View PBI #${ticket.ticket_id} in Azure Boards →</a>`;
                    }
                });
            })
            .catch(() => {});
        }
    },

    displayAIResponse(responseDiv, staticFixDiv, data, btn) {
        const explanation = data.explanation || '';
        const howToFix = data.how_to_fix || '';
        const priority = data.priority || 'medium';
        const tokensUsed = data.tokens_used || 0;

        const priorityColor = priority === 'high' ? '#ef4444' : priority === 'medium' ? '#f59e0b' : '#10b981';

        responseDiv.innerHTML = `
            <div style="margin-bottom: 8px;">
                <div style="color: #e5e7eb; font-weight: 600; margin-bottom: 6px;">🤖 Why it matters</div>
                <div style="color: #cbd5e1; font-size: 12px; line-height: 1.6;">${this.utils.escapeHtml(explanation)}</div>
            </div>
            <div style="margin-bottom: 8px;">
                <div style="color: #e5e7eb; font-weight: 600; margin-bottom: 6px;">🔧 How to fix</div>
                <div style="color: #cbd5e1; font-size: 12px; line-height: 1.6;">${howToFix.replace(/•/g, '•')}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 8px; margin-top: 8px;">
                <span style="background: ${priorityColor}20; color: ${priorityColor}; padding: 2px 8px; border-radius: 10px; font-size: 10px; font-weight: 600; text-transform: uppercase;">${priority} priority</span>
                <span style="color: #6b7280; font-size: 10px;">${tokensUsed} tokens used</span>
                <button class="regenerate-btn" style="margin-left: auto; background: none; border: 1px solid #374151; color: #9ca3af; padding: 2px 8px; border-radius: 4px; font-size: 10px; cursor: pointer;">🔄 Regenerate</button>
            </div>
                   
        `;

        // Hide static fix text
        if (staticFixDiv) staticFixDiv.style.display = 'none';

        // Update button
        btn.disabled = false;
        btn.innerHTML = '✅ AI Ready';
        btn.style.opacity = '0.6';
        btn.style.cursor = 'default';

        // Reveal Create Ticket button now that AI analysis is ready
        const row = btn.closest('tr');
        if (row) {
            const ticketBtn = row.querySelector('.ticket-btn');
            if (ticketBtn) {
                ticketBtn.style.display = 'flex';
            }
        }

        // Regenerate button handler
        const regenBtn = responseDiv.querySelector('.regenerate-btn');
        if (regenBtn) {
            regenBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                // Clear cache and trigger button click again
                const cacheKey = btn.dataset.cacheKey;
                localStorage.removeItem(cacheKey);
                btn.disabled = false;
                btn.innerHTML = '✨ Ask AI';
                btn.style.opacity = '1';
                btn.style.cursor = 'pointer';
                btn.click();
            });
        }

    },

    renderHeader() {
        return `
            <div class="plugin-header" style="margin-bottom: 32px;">
                <h2 style="font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #e5e7eb;">
                    🔍 Page Diagnostics
                </h2>
                <p style="color: #9ca3af; font-size: 14px;">
                    Health summary, issue diagnosis, and fix guidance across your website
                </p>
            </div>
        `;
    },

    renderEmptyState() {
        return `
            <div style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div class="empty-state" style="text-align: center; padding: 60px 20px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">🔍</div>
                    <h3 style="font-size: 24px; font-weight: 600; color: #e5e7eb; margin-bottom: 12px;">
                        No Data Yet
                    </h3>
                    <p style="color: #9ca3af; font-size: 14px;">
                        Start crawling to see page diagnostics
                    </p>
                </div>
            </div>
        `;
    },

    // ── Section 1: Summary Cards ────────────────────────────────────────────

    renderSummaryCards(issues, internalUrls, links) {
        const criticalErrors = issues.filter(i => i.type === 'error').length;

        const brokenLinksAndImages = internalUrls.filter(u =>
            u.status_code && u.status_code >= 400
        ).length + issues.filter(i =>
            i.issue && i.issue.includes('Broken Image')
        ).length;

        const missingMetaUrls = new Set(issues
            .filter(i => i.category === 'SEO' || i.category === 'Social')
            .map(i => i.url)
        ).size;

        const perfProblems = internalUrls.filter(u =>
            (u.response_time && u.response_time > 1000) ||
            (u.size && u.size > 102400)
        ).length;

        return `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 32px;">
                ${this.renderCard('Critical Errors', criticalErrors, '#ef4444', 'error')}
                ${this.renderCard('Broken Links & Images', brokenLinksAndImages, '#f59e0b', 'warning')}
                ${this.renderCard('Missing Meta Tags', missingMetaUrls, '#3b82f6', 'info')}
                ${this.renderCard('Performance Problems', perfProblems, '#ef4444', 'error')}
            </div>
        `;
    },

    renderCard(label, value, color, type) {
        return `
            <div class="stat-card" style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                <div style="font-size: 14px; color: #9ca3af; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px;">
                    ${label}
                </div>
                <div style="font-size: 48px; font-weight: 700; color: ${color}; margin-bottom: 8px;">
                    ${value}
                </div>
                <div style="font-size: 13px; color: #6b7280;">
                    ${type === 'error' ? 'Needs immediate attention' : type === 'warning' ? 'Should be reviewed' : 'Check affected pages'}
                </div>
            </div>
        `;
    },

    // ── Section 2: Issues Table ─────────────────────────────────────────────

    renderIssuesTable(issues) {
        if (!issues || issues.length === 0) {
            return `
                <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                    <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                        Issues Table
                    </h3>
                    <p style="color: #9ca3af; font-size: 14px;">No issues found. Great job!</p>
                </div>
            `;
        }

        const categories = ['All', 'SEO', 'Technical', 'Performance', 'Content', 'Mobile', 'Accessibility', 'Social', 'Structured Data', 'Indexability'];
        const typeOrder = { error: 0, warning: 1, info: 2 };
        const sortedIssues = [...issues].sort((a, b) => {
            if (typeOrder[a.type] !== typeOrder[b.type]) return typeOrder[a.type] - typeOrder[b.type];
            return (a.url || '').localeCompare(b.url || '');
        });

        const categoryOptions = categories.map(c =>
            `<option value="${c}">${c}</option>`
        ).join('');

        const rows = sortedIssues.map(issue => this.renderIssueRow(issue)).join('');

        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                    Issues Table
                </h3>
                <div style="margin-bottom: 16px; display: flex; align-items: center; flex-wrap: wrap; gap: 8px;">
                    <label style="font-size: 13px; color: #9ca3af; margin-right: 4px;">Filter by category:</label>
                    <select id="pd-category-filter" style="background: #0f172a; color: #e5e7eb; border: 1px solid #374151; padding: 6px 12px; border-radius: 6px; font-size: 13px;">
                        ${categoryOptions}
                    </select>
                    <input
                        id="pd-url-search"
                        type="text"
                        placeholder="Search URL…"
                        style="background: #0f172a; color: #e5e7eb; border: 1px solid #374151; padding: 6px 12px; border-radius: 6px; font-size: 13px; margin-left: auto; width: 260px;"
                    />
                </div>
                <div style="overflow-x: auto;">
                    <table class="data-table" style="width: 100%; border-collapse: collapse;" id="pd-issues-table">
                        <thead>
                            <tr style="border-bottom: 1px solid #374151;">
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">URL</th>
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">Category</th>
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">About the Issue</th>
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">How to Fix</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },

    renderIssueRow(issue) {
        const url = this.utils.escapeHtml(issue.url || '');
        const shortUrl = this.utils.formatUrl(issue.url, 60);
        const category = issue.category || 'Other';
        const categoryColor = this.getCategoryColor(category);
        const about = this.utils.escapeHtml(
            (issue.issue || '') + (issue.details ? ' — ' + issue.details : '')
        );
        const fix = this.utils.escapeHtml(
            (ISSUE_KNOWLEDGE[issue.issue] || ISSUE_KNOWLEDGE['_default']).fix
        );

        // Create a unique cache key for this issue
        const cacheKey = 'ai_' + btoa(unescape(encodeURIComponent(issue.url + '|' + issue.issue))).replace(/[=+/]/g, '');

        return `
            <tr style="border-bottom: 1px solid #374151;" data-category="${category}" data-cache-key="${cacheKey}">
                <td style="padding: 12px; color: #cbd5e1; font-size: 13px; max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <a href="${url}" target="_blank" style="color: #3b82f6; text-decoration: none;">${shortUrl}</a>
                </td>
                <td style="padding: 12px;">
                    <span style="background: ${categoryColor}20; color: ${categoryColor}; padding: 4px 10px; border-radius: 12px; font-size: 11px; font-weight: 600;">
                        ${category}
                    </span>
                </td>
                <td style="padding: 12px; color: #cbd5e1; font-size: 13px; line-height: 1.5; white-space: normal; word-break: break-word;">
                    ${about}
                </td>
                <td style="padding: 12px; color: #cbd5e1; font-size: 13px; line-height: 1.5; white-space: normal; word-break: break-word; min-width: 250px;">
                    <div class="static-fix">${fix}</div>
                    <div style="display: flex; gap: 6px; margin-top: 8px; flex-wrap: wrap;">
                        <button class="ai-btn" data-url="${url}" data-issue="${this.utils.escapeHtml(issue.issue || '')}" data-category="${this.utils.escapeHtml(category)}" data-details="${this.utils.escapeHtml(issue.details || '')}" data-cache-key="${cacheKey}" data-issue-type="${this.utils.escapeHtml(issue.type || 'info')}" style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; display: flex; align-items: center; gap: 4px; transition: opacity 0.2s;" onmouseover="this.style.opacity=0.8" onmouseout="this.style.opacity=1">
                            ✨ Ask AI
                        </button>
                        ${(issue.type || 'info') !== 'info' ? `
                        <button class="ticket-btn" data-url="${url}" data-issue="${this.utils.escapeHtml(issue.issue || '')}" data-category="${this.utils.escapeHtml(category)}" data-issue-type="${this.utils.escapeHtml(issue.type || 'info')}" data-cache-key="${cacheKey}" style="display: none; background: linear-gradient(135deg, #0ea5e9 0%, #2563eb 100%); color: white; border: none; padding: 6px 12px; border-radius: 6px; font-size: 11px; cursor: pointer; align-items: center; gap: 4px; transition: opacity 0.2s;" onmouseover="this.style.opacity=0.8" onmouseout="this.style.opacity=1">
                            🎫 Create Ticket
                        </button>` : ''}
                    </div>
                    <div class="ticket-result" data-cache-key="${cacheKey}" style="display: none; margin-top: 6px; font-size: 11px;"></div>
                    <div class="ai-response" data-cache-key="${cacheKey}" style="display: none; margin-top: 12px; padding: 12px; background: #0f172a; border-radius: 8px; border: 1px solid #1e293b; font-size: 12px; line-height: 1.6;"></div>
                </td>
            </tr>
        `;
    },

    getCategoryColor(category) {
        const map = {
            'Technical': '#ef4444',
            'Performance': '#ef4444',
            'SEO': '#f59e0b',
            'Content': '#f59e0b',
            'Social': '#3b82f6',
            'Accessibility': '#3b82f6'
        };
        return map[category] || '#6b7280';
    },

    // ── Section 3: Meta Tag Completeness Matrix ─────────────────────────────

    renderMetaTagMatrix(internalUrls) {
        const limit = 50;
        const showUrls = internalUrls.slice(0, limit);
        const total = internalUrls.length;

        const metaColumns = [
            { key: 'title', label: 'Title', field: 'title', tip: 'Page title tag' },
            { key: 'description', label: 'Meta Description', field: 'meta_description', tip: 'Meta description tag' },
            { key: 'h1', label: 'H1', field: 'h1', tip: 'Primary heading' },
            { key: 'canonical', label: 'Canonical', field: 'canonical_url', tip: 'Canonical URL' },
            { key: 'lang', label: 'Lang', field: 'lang', tip: 'Language attribute' },
            { key: 'viewport', label: 'Viewport', field: 'viewport', tip: 'Mobile viewport tag' },
            { key: 'og_title', label: 'OG Title', field: 'og_tags', tip: 'OpenGraph title', nested: 'title' },
            { key: 'og_image', label: 'OG Image', field: 'og_tags', tip: 'OpenGraph image', nested: 'image' },
            { key: 'twitter_card', label: 'Twitter Card', field: 'twitter_tags', tip: 'Twitter card type', nested: 'card' },
            { key: 'json_ld', label: 'JSON-LD', field: 'json_ld', tip: 'Structured data', isArray: true }
        ];

        const headerCells = metaColumns.map(col =>
            `<th style="padding: 10px 8px; text-align: center; color: #9ca3af; font-size: 12px; font-weight: 600; border-bottom: 1px solid #374151;" title="${col.tip}">
                ${col.label}
            </th>`
        ).join('');

        const rows = showUrls.map(url => {
            const urlCell = `<td style="padding: 10px 8px; color: #cbd5e1; font-size: 12px; max-width: 250px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; border-bottom: 1px solid #1e293b;">
                <a href="${this.utils.escapeHtml(url.url)}" target="_blank" style="color: #3b82f6; text-decoration: none;">${this.utils.formatUrl(url.url, 40)}</a>
            </td>`;

            const metaCells = metaColumns.map(col => {
                let present = false;
                if (col.isArray) {
                    present = url[col.field] && url[col.field].length > 0;
                } else if (col.nested) {
                    present = url[col.field] && url[col.field][col.nested];
                } else {
                    present = url[col.field];
                }
                return `<td style="padding: 10px 8px; text-align: center; border-bottom: 1px solid #1e293b; font-size: 14px;">
                    ${present ? '✅' : '❌'}
                </td>`;
            }).join('');

            return `<tr>${urlCell}${metaCells}</tr>`;
        }).join('');

        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 8px; color: #e5e7eb;">
                    Meta Tag Completeness Matrix
                </h3>
                <p style="color: #9ca3af; font-size: 13px; margin-bottom: 20px;">
                    Showing ${Math.min(limit, total)} of ${total} pages
                </p>
                <div style="overflow-x: auto;">
                    <table class="data-table" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr>
                                <th style="padding: 10px 8px; text-align: left; color: #9ca3af; font-size: 12px; font-weight: 600; border-bottom: 1px solid #374151;">URL</th>
                                ${headerCells}
                            </tr>
                        </thead>
                        <tbody>
                            ${rows}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },

    // ── Section 4: Performance & Page Weight Analysis ────────────────────────

    renderPerformanceAnalysis(internalUrls) {
        const explainer = `
            <div style="background: #0f172a; border-left: 4px solid #f59e0b; padding: 16px 20px; border-radius: 0 8px 8px 0; margin-bottom: 24px;">
                <div style="font-weight: 600; color: #e5e7eb; margin-bottom: 8px; font-size: 14px;">
                    ⚡ Why large HTML causes slow load times
                </div>
                <div style="color: #9ca3af; font-size: 13px; line-height: 1.6;">
                    Large HTML documents force the browser to download more bytes before rendering can begin. Every extra 10 KB of uncompressed HTML adds approximately 80–150 ms on a mobile connection. When a page also has a slow server response time (above 1s), the problem is compounded — the server is slow to respond AND the browser receives a heavy payload. Google's LCP metric (target: under 2.5s) is directly hurt by both.
                </div>
            </div>
        `;

        const worstOffenders = [...internalUrls]
            .sort((a, b) => (b.response_time || 0) - (a.response_time || 0))
            .slice(0, 10);

        const perfRows = worstOffenders.map(url => this.renderPerfRow(url)).join('');

        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                    Performance & Page Weight Analysis
                </h3>
                ${explainer}
                <h4 style="font-size: 15px; font-weight: 600; margin-bottom: 16px; color: #e5e7eb;">
                    Worst Offenders — Top 10 by Response Time
                </h4>
                <div style="overflow-x: auto;">
                    <table class="data-table" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 1px solid #374151;">
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">URL</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Response Time</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">HTML Size</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Issue Count</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${perfRows}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },

    renderPerfRow(url) {
        const responseTime = url.response_time || 0;
        const size = url.size || 0;
        const issueCount = (url.issues ? url.issues.length : 0);

        const rtColor = responseTime < 1000 ? '#10b981' : responseTime <= 3000 ? '#f59e0b' : '#ef4444';
        const rtLabel = responseTime < 1000 ? 'fast' : responseTime <= 3000 ? 'moderate' : 'slow';
        const sizeColor = size < 102400 ? '#10b981' : size <= 512000 ? '#f59e0b' : '#ef4444';
        const sizeKB = (size / 1024).toFixed(1);

        const shortUrl = this.utils.formatUrl(url.url, 60);
        const escapedUrl = this.utils.escapeHtml(url.url);

        return `
            <tr style="border-bottom: 1px solid #374151;">
                <td style="padding: 12px; color: #cbd5e1; font-size: 13px; max-width: 350px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    <a href="${escapedUrl}" target="_blank" style="color: #3b82f6; text-decoration: none;">${shortUrl}</a>
                </td>
                <td style="padding: 12px; text-align: center; font-weight: 600; font-size: 13px; color: ${rtColor};">
                    ${responseTime} ms <span style="font-size: 11px; color: #6b7280;">(${rtLabel})</span>
                </td>
                <td style="padding: 12px; text-align: center; font-weight: 600; font-size: 13px; color: ${sizeColor};">
                    ${sizeKB} KB
                </td>
                <td style="padding: 12px; text-align: center; color: #cbd5e1; font-size: 13px;">
                    ${issueCount}
                </td>
            </tr>
        `;
    }
});

console.log('✅ Page Diagnostics plugin registered');
