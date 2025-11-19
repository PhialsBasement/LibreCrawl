/**
 * E-E-A-T Analyzer Plugin for LibreCrawl
 * Analyzes Experience, Expertise, Authoritativeness, Trust signals on crawled pages
 *
 * @author LibreCrawl Community
 * @version 1.0.0
 */

LibreCrawlPlugin.register({
    // Plugin metadata
    id: 'e-e-a-t',
    name: 'E-E-A-T Analyzer',
    version: '1.0.0',
    author: 'LibreCrawl Community',
    description: 'Analyzes Experience, Expertise, Authoritativeness, Trust (E-E-A-T) signals on your website',

    // Tab configuration
    tab: {
        label: 'E-E-A-T',
        icon: '🎓',
        position: 'end' // Appears after all built-in tabs
    },

    // Plugin initialization
    onLoad() {
        console.log('📊 E-E-A-T Analyzer loaded');
    },

    // Called when tab becomes active
    onTabActivate(container, data) {
        console.log('🎓 E-E-A-T tab activated with', data.urls.length, 'URLs');
        this.render(container, data);
    },

    // Called during live crawls when data updates
    onDataUpdate(data) {
        if (this.isActive && this.container) {
            this.render(this.container, data);
        }
    },

    // Called when crawl completes
    onCrawlComplete(data) {
        console.log('✅ E-E-A-T analysis complete for', data.urls.length, 'URLs');
        if (this.isActive && this.container) {
            this.render(this.container, data);
        }
    },

    // Main render function
    render(container, data) {
        const { urls, links } = data;

        if (!urls || urls.length === 0) {
            container.innerHTML = this.renderEmptyState();
            return;
        }

        // Analyze E-E-A-T signals
        const analysis = this.analyzeEEAT(urls, links);

        // Render the analysis
        container.innerHTML = `
            <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                ${this.renderHeader(analysis)}
                ${this.renderScoreCards(analysis)}
                ${this.renderSignalsBreakdown(analysis)}
                ${this.renderTopPages(analysis)}
                ${this.renderRecommendations(analysis)}
            </div>
        `;
    },

    // Render header section
    renderHeader(analysis) {
        return `
            <div class="plugin-header" style="margin-bottom: 32px;">
                <h2 style="font-size: 28px; font-weight: 700; margin-bottom: 8px; color: #e5e7eb;">
                    🎓 E-E-A-T Analysis
                </h2>
                <p style="color: #9ca3af; font-size: 14px;">
                    Experience, Expertise, Authoritativeness, and Trust signals across your website
                </p>
            </div>
        `;
    },

    // Render score cards
    renderScoreCards(analysis) {
        const scoreClass = this.getScoreClass(analysis.overallScore);
        const scoreColor = this.getScoreColor(analysis.overallScore);

        return `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 20px; margin-bottom: 32px;">
                <div class="stat-card" style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                    <div style="font-size: 14px; color: #9ca3af; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px;">
                        Overall E-E-A-T Score
                    </div>
                    <div style="font-size: 48px; font-weight: 700; color: ${scoreColor}; margin-bottom: 8px;">
                        ${analysis.overallScore}
                    </div>
                    <div style="font-size: 13px; color: #6b7280;">
                        Out of 100
                    </div>
                </div>

                <div class="stat-card" style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                    <div style="font-size: 14px; color: #9ca3af; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px;">
                        Pages with Author Info
                    </div>
                    <div style="font-size: 48px; font-weight: 700; color: #10b981; margin-bottom: 8px;">
                        ${analysis.pagesWithAuthor}
                    </div>
                    <div style="font-size: 13px; color: #6b7280;">
                        ${this.getPercentage(analysis.pagesWithAuthor, analysis.totalPages)}% of pages
                    </div>
                </div>

                <div class="stat-card" style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                    <div style="font-size: 14px; color: #9ca3af; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px;">
                        Pages with Schema Markup
                    </div>
                    <div style="font-size: 48px; font-weight: 700; color: #3b82f6; margin-bottom: 8px;">
                        ${analysis.pagesWithSchema}
                    </div>
                    <div style="font-size: 13px; color: #6b7280;">
                        ${this.getPercentage(analysis.pagesWithSchema, analysis.totalPages)}% of pages
                    </div>
                </div>

                <div class="stat-card" style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                    <div style="font-size: 14px; color: #9ca3af; margin-bottom: 12px; text-transform: uppercase; letter-spacing: 1px;">
                        External Citations
                    </div>
                    <div style="font-size: 48px; font-weight: 700; color: #f59e0b; margin-bottom: 8px;">
                        ${analysis.externalCitations}
                    </div>
                    <div style="font-size: 13px; color: #6b7280;">
                        Average ${analysis.avgExternalLinks.toFixed(1)} per page
                    </div>
                </div>
            </div>
        `;
    },

    // Render signals breakdown
    renderSignalsBreakdown(analysis) {
        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                    Trust Signals Breakdown
                </h3>
                <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px;">
                    ${this.renderSignalItem('✍️', 'Author Attribution', analysis.pagesWithAuthor, analysis.totalPages)}
                    ${this.renderSignalItem('📊', 'Structured Data', analysis.pagesWithSchema, analysis.totalPages)}
                    ${this.renderSignalItem('🔗', 'External Links', analysis.pagesWithExternalLinks, analysis.totalPages)}
                    ${this.renderSignalItem('🏷️', 'Open Graph Tags', analysis.pagesWithOGTags, analysis.totalPages)}
                    ${this.renderSignalItem('🔒', 'HTTPS Secure', analysis.securePages, analysis.totalPages)}
                    ${this.renderSignalItem('📝', 'Sufficient Content', analysis.pagesWithGoodContent, analysis.totalPages)}
                </div>
            </div>
        `;
    },

    // Render individual signal item
    renderSignalItem(icon, label, count, total) {
        const percentage = this.getPercentage(count, total);
        const barColor = percentage >= 75 ? '#10b981' : percentage >= 50 ? '#f59e0b' : '#ef4444';

        return `
            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border: 1px solid #1e293b;">
                <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 12px;">
                    <span style="font-size: 20px;">${icon}</span>
                    <div style="font-size: 13px; color: #cbd5e1; font-weight: 500;">${label}</div>
                </div>
                <div style="font-size: 24px; font-weight: 700; color: #e5e7eb; margin-bottom: 8px;">
                    ${count}/${total}
                </div>
                <div style="background: #1e293b; height: 6px; border-radius: 3px; overflow: hidden; margin-bottom: 6px;">
                    <div style="background: ${barColor}; height: 100%; width: ${percentage}%; transition: width 0.3s;"></div>
                </div>
                <div style="font-size: 12px; color: #6b7280;">
                    ${percentage}%
                </div>
            </div>
        `;
    },

    // Render top pages by E-E-A-T score
    renderTopPages(analysis) {
        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151; margin-bottom: 32px;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                    Top Pages by E-E-A-T Score
                </h3>
                <div style="overflow-x: auto;">
                    <table class="data-table" style="width: 100%; border-collapse: collapse;">
                        <thead>
                            <tr style="border-bottom: 1px solid #374151;">
                                <th style="padding: 12px; text-align: left; color: #9ca3af; font-size: 13px; font-weight: 600;">URL</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Score</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Author</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Schema</th>
                                <th style="padding: 12px; text-align: center; color: #9ca3af; font-size: 13px; font-weight: 600;">Ext. Links</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${analysis.topPages.slice(0, 10).map(page => this.renderPageRow(page)).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;
    },

    // Render individual page row
    renderPageRow(page) {
        const scoreColor = this.getScoreColor(page.score);
        return `
            <tr style="border-bottom: 1px solid #374151;">
                <td style="padding: 12px; color: #cbd5e1; font-size: 13px; max-width: 400px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${this.utils.escapeHtml(page.url)}
                </td>
                <td style="padding: 12px; text-align: center; font-weight: 600; font-size: 14px; color: ${scoreColor};">
                    ${page.score}
                </td>
                <td style="padding: 12px; text-align: center; font-size: 20px;">
                    ${page.hasAuthor ? '✅' : '❌'}
                </td>
                <td style="padding: 12px; text-align: center; font-size: 20px;">
                    ${page.hasSchema ? '✅' : '❌'}
                </td>
                <td style="padding: 12px; text-align: center; color: #cbd5e1; font-size: 13px;">
                    ${page.externalLinks}
                </td>
            </tr>
        `;
    },

    // Render recommendations
    renderRecommendations(analysis) {
        const recommendations = this.generateRecommendations(analysis);

        return `
            <div style="background: #1f2937; padding: 24px; border-radius: 12px; border: 1px solid #374151;">
                <h3 style="font-size: 18px; font-weight: 600; margin-bottom: 20px; color: #e5e7eb;">
                    💡 Recommendations to Improve E-E-A-T
                </h3>
                <div style="display: flex; flex-direction: column; gap: 12px;">
                    ${recommendations.map(rec => this.renderRecommendation(rec)).join('')}
                </div>
            </div>
        `;
    },

    // Render individual recommendation
    renderRecommendation(rec) {
        const priorityColors = {
            high: '#ef4444',
            medium: '#f59e0b',
            low: '#3b82f6'
        };

        return `
            <div style="background: #0f172a; padding: 16px; border-radius: 8px; border-left: 4px solid ${priorityColors[rec.priority]};">
                <div style="display: flex; align-items: start; gap: 12px;">
                    <span style="font-size: 24px;">${rec.icon}</span>
                    <div style="flex: 1;">
                        <div style="font-weight: 600; color: #e5e7eb; margin-bottom: 4px; font-size: 14px;">
                            ${rec.title}
                        </div>
                        <div style="color: #9ca3af; font-size: 13px; line-height: 1.6;">
                            ${rec.description}
                        </div>
                    </div>
                    <div style="background: ${priorityColors[rec.priority]}20; color: ${priorityColors[rec.priority]}; padding: 4px 12px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase;">
                        ${rec.priority}
                    </div>
                </div>
            </div>
        `;
    },

    // Empty state
    renderEmptyState() {
        return `
            <div style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
                <div class="empty-state" style="text-align: center; padding: 60px 20px;">
                    <div style="font-size: 64px; margin-bottom: 20px;">🎓</div>
                    <h3 style="font-size: 24px; font-weight: 600; color: #e5e7eb; margin-bottom: 12px;">
                        No Data Yet
                    </h3>
                    <p style="color: #9ca3af; font-size: 14px;">
                        Start crawling to analyze E-E-A-T signals on your website
                    </p>
                </div>
            </div>
        `;
    },

    // Analyze E-E-A-T signals across all URLs
    analyzeEEAT(urls, links) {
        let totalScore = 0;
        let pagesWithAuthor = 0;
        let pagesWithSchema = 0;
        let pagesWithExternalLinks = 0;
        let pagesWithOGTags = 0;
        let securePages = 0;
        let pagesWithGoodContent = 0;
        let externalCitations = 0;
        const pageScores = [];

        urls.forEach(url => {
            let score = 0;
            const urlData = {
                url: url.url,
                score: 0,
                hasAuthor: false,
                hasSchema: false,
                externalLinks: url.external_links || 0
            };

            // Check for HTTPS (10 points)
            if (url.url && url.url.startsWith('https://')) {
                score += 10;
                securePages++;
            }

            // Check for author information (20 points)
            if (url.meta_author || (url.og_tags && url.og_tags.author)) {
                score += 20;
                pagesWithAuthor++;
                urlData.hasAuthor = true;
            }

            // Check for structured data/schema markup (25 points)
            if (url.json_ld && url.json_ld.length > 0) {
                score += 25;
                pagesWithSchema++;
                urlData.hasSchema = true;
            }

            // Check for external links/citations (15 points)
            const extLinks = url.external_links || 0;
            if (extLinks > 0) {
                score += Math.min(15, extLinks * 3); // Up to 15 points
                pagesWithExternalLinks++;
                externalCitations += extLinks;
            }

            // Check for Open Graph tags (10 points)
            if (url.og_tags && url.og_tags.title) {
                score += 10;
                pagesWithOGTags++;
            }

            // Check for sufficient content (20 points)
            const wordCount = url.word_count || 0;
            if (wordCount >= 300) {
                score += 20;
                pagesWithGoodContent++;
            } else if (wordCount >= 150) {
                score += 10;
            }

            urlData.score = Math.min(100, score);
            totalScore += urlData.score;
            pageScores.push(urlData);
        });

        // Sort pages by score
        pageScores.sort((a, b) => b.score - a.score);

        return {
            totalPages: urls.length,
            overallScore: urls.length > 0 ? Math.round(totalScore / urls.length) : 0,
            pagesWithAuthor,
            pagesWithSchema,
            pagesWithExternalLinks,
            pagesWithOGTags,
            securePages,
            pagesWithGoodContent,
            externalCitations,
            avgExternalLinks: urls.length > 0 ? externalCitations / urls.length : 0,
            topPages: pageScores
        };
    },

    // Generate recommendations based on analysis
    generateRecommendations(analysis) {
        const recommendations = [];
        const total = analysis.totalPages;

        // Author attribution
        if (analysis.pagesWithAuthor < total * 0.5) {
            recommendations.push({
                icon: '✍️',
                title: 'Add Author Information',
                description: `Only ${analysis.pagesWithAuthor} out of ${total} pages have author information. Add author bylines with credentials to demonstrate expertise.`,
                priority: 'high'
            });
        }

        // Schema markup
        if (analysis.pagesWithSchema < total * 0.3) {
            recommendations.push({
                icon: '📊',
                title: 'Implement Structured Data',
                description: `${analysis.pagesWithSchema} pages have schema markup. Add JSON-LD structured data (Article, Person, Organization schemas) to improve E-E-A-T.`,
                priority: 'high'
            });
        }

        // External citations
        if (analysis.avgExternalLinks < 2) {
            recommendations.push({
                icon: '🔗',
                title: 'Add External Citations',
                description: `Average of ${analysis.avgExternalLinks.toFixed(1)} external links per page. Link to authoritative sources to support your claims and demonstrate research.`,
                priority: 'medium'
            });
        }

        // Content depth
        if (analysis.pagesWithGoodContent < total * 0.7) {
            recommendations.push({
                icon: '📝',
                title: 'Improve Content Depth',
                description: `${analysis.pagesWithGoodContent} pages have sufficient content (300+ words). Create comprehensive, in-depth content to demonstrate expertise.`,
                priority: 'medium'
            });
        }

        // HTTPS
        if (analysis.securePages < total) {
            recommendations.push({
                icon: '🔒',
                title: 'Enable HTTPS Everywhere',
                description: `${total - analysis.securePages} pages are not using HTTPS. Ensure all pages use HTTPS for trust and security.`,
                priority: 'high'
            });
        }

        // If no recommendations, add a positive message
        if (recommendations.length === 0) {
            recommendations.push({
                icon: '🎉',
                title: 'Great E-E-A-T Signals!',
                description: 'Your website demonstrates strong Experience, Expertise, Authoritativeness, and Trust signals. Keep up the good work!',
                priority: 'low'
            });
        }

        return recommendations;
    },

    // Helper: Get score class
    getScoreClass(score) {
        if (score >= 80) return 'score-good';
        if (score >= 60) return 'score-needs-improvement';
        return 'score-poor';
    },

    // Helper: Get score color
    getScoreColor(score) {
        if (score >= 80) return '#10b981';
        if (score >= 60) return '#f59e0b';
        return '#ef4444';
    },

    // Helper: Get percentage
    getPercentage(count, total) {
        return total > 0 ? Math.round((count / total) * 100) : 0;
    }
});

console.log('✅ E-E-A-T Analyzer plugin registered');
