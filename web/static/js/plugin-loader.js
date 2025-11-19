/**
 * LibreCrawl Plugin Loader
 * Automatically discovers and loads plugins from /static/plugins/
 */

class PluginLoader {
    constructor() {
        this.plugins = [];
        this.loadedPluginIds = new Set();
        this.activePluginId = null;
    }

    /**
     * Load all plugins from the plugins directory
     */
    async loadAllPlugins() {
        try {
            // List of plugins to load
            // In the future, this could come from a backend API or auto-discovery
            const pluginFiles = await this.discoverPlugins();

            console.log(`📦 Discovered ${pluginFiles.length} plugin(s)`);

            // Load each plugin script
            for (const pluginFile of pluginFiles) {
                await this.loadPluginScript(pluginFile);
            }

            console.log(`✅ Loaded ${this.plugins.length} plugin(s)`);

        } catch (error) {
            console.error('❌ Failed to load plugins:', error);
        }
    }

    /**
     * Discover available plugins
     * Currently uses a simple file list, but could be extended to:
     * - Fetch from backend API
     * - Parse directory listing
     * - Use manifest file
     */
    async discoverPlugins() {
        // For now, we'll manually list plugins here
        // Users can add their plugin filenames to this array
        const manualPlugins = [
            // Add your plugin files here, e.g.:
            'e-e-a-t.js',
            // 'content-quality.js',
        ];

        // Filter out disabled plugins (starting with _)
        return manualPlugins.filter(file => !file.startsWith('_'));
    }

    /**
     * Load a single plugin script
     */
    async loadPluginScript(pluginFile) {
        return new Promise((resolve, reject) => {
            const script = document.createElement('script');
            script.src = `/static/plugins/${pluginFile}`;
            script.async = false; // Load in order

            script.onload = () => {
                console.log(`✓ Loaded: ${pluginFile}`);
                resolve();
            };

            script.onerror = () => {
                console.error(`✗ Failed to load: ${pluginFile}`);
                reject(new Error(`Failed to load ${pluginFile}`));
            };

            document.head.appendChild(script);
        });
    }

    /**
     * Register a plugin (called by plugin files via LibreCrawlPlugin.register())
     */
    registerPlugin(pluginConfig) {
        // Validate required fields
        const validation = this.validatePlugin(pluginConfig);
        if (!validation.valid) {
            console.error('❌ Plugin validation failed:', validation.errors);
            return false;
        }

        // Check for duplicate ID
        if (this.loadedPluginIds.has(pluginConfig.id)) {
            console.error(`❌ Plugin ID "${pluginConfig.id}" already registered`);
            return false;
        }

        // Create plugin instance
        const plugin = this.createPluginInstance(pluginConfig);

        // Store plugin
        this.plugins.push(plugin);
        this.loadedPluginIds.add(pluginConfig.id);

        console.log(`✅ Registered plugin: ${plugin.name} (${plugin.id})`);

        // Call onLoad hook if present
        if (typeof plugin.onLoad === 'function') {
            try {
                plugin.onLoad.call(plugin);
            } catch (error) {
                console.error(`Error in ${plugin.name}.onLoad():`, error);
            }
        }

        return true;
    }

    /**
     * Validate plugin configuration
     */
    validatePlugin(config) {
        const errors = [];

        if (!config.id || typeof config.id !== 'string') {
            errors.push('Plugin must have a valid "id" (string)');
        }

        if (!config.name || typeof config.name !== 'string') {
            errors.push('Plugin must have a valid "name" (string)');
        }

        if (!config.tab || typeof config.tab !== 'object') {
            errors.push('Plugin must have a "tab" configuration object');
        } else {
            if (!config.tab.label || typeof config.tab.label !== 'string') {
                errors.push('Plugin tab must have a valid "label" (string)');
            }
        }

        if (typeof config.onTabActivate !== 'function') {
            errors.push('Plugin must have an "onTabActivate" function');
        }

        return {
            valid: errors.length === 0,
            errors: errors
        };
    }

    /**
     * Create a plugin instance with utilities and lifecycle management
     */
    createPluginInstance(config) {
        const plugin = {
            // Plugin metadata
            id: config.id,
            name: config.name,
            version: config.version || '1.0.0',
            author: config.author || 'Unknown',
            description: config.description || '',

            // Tab configuration
            tab: {
                label: config.tab.label,
                icon: config.tab.icon || '',
                position: config.tab.position || 'end'
            },

            // Lifecycle hooks
            onLoad: config.onLoad,
            onTabActivate: config.onTabActivate,
            onTabDeactivate: config.onTabDeactivate,
            onDataUpdate: config.onDataUpdate,
            onCrawlComplete: config.onCrawlComplete,

            // Custom methods
            ...config,

            // Plugin state
            isActive: false,
            container: null,

            // Utilities
            utils: {
                showNotification: (message, type = 'info') => {
                    if (typeof window.showNotification === 'function') {
                        window.showNotification(message, type);
                    }
                },

                escapeHtml: (text) => {
                    if (typeof window.escapeHtml === 'function') {
                        return window.escapeHtml(text);
                    }
                    if (!text) return text;
                    const div = document.createElement('div');
                    div.textContent = text;
                    return div.innerHTML;
                },

                formatUrl: (url, maxLength = 60) => {
                    if (!url || url.length <= maxLength) return url;
                    return url.substring(0, maxLength - 3) + '...';
                }
            }
        };

        return plugin;
    }

    /**
     * Initialize all loaded plugins (create tabs)
     */
    initializePlugins() {
        console.log(`🎨 Initializing ${this.plugins.length} plugin tab(s)...`);

        this.plugins.forEach(plugin => {
            this.createPluginTab(plugin);
        });
    }

    /**
     * Create a tab for a plugin
     */
    createPluginTab(plugin) {
        const tabHeader = document.querySelector('.tab-header');
        const tabContent = document.querySelector('.tab-content');

        if (!tabHeader || !tabContent) {
            console.error('Tab containers not found');
            return;
        }

        // Create tab button
        const tabBtn = document.createElement('button');
        tabBtn.className = 'tab-btn';
        tabBtn.setAttribute('data-plugin-id', plugin.id);

        const icon = plugin.tab.icon ? `${plugin.tab.icon} ` : '';
        tabBtn.textContent = `${icon}${plugin.tab.label}`;

        tabBtn.onclick = () => {
            if (typeof window.switchTab === 'function') {
                window.switchTab(plugin.id);
            }
        };

        // Insert tab button at appropriate position
        if (plugin.tab.position === 'end' || typeof plugin.tab.position !== 'number') {
            tabHeader.appendChild(tabBtn);
        } else {
            const children = Array.from(tabHeader.children);
            const insertBefore = children[plugin.tab.position];
            if (insertBefore) {
                tabHeader.insertBefore(tabBtn, insertBefore);
            } else {
                tabHeader.appendChild(tabBtn);
            }
        }

        // Create tab pane
        const tabPane = document.createElement('div');
        tabPane.id = `${plugin.id}-tab`;
        tabPane.className = 'tab-pane plugin-tab';
        tabPane.setAttribute('data-plugin-id', plugin.id);

        tabContent.appendChild(tabPane);

        console.log(`  ✓ Created tab: ${plugin.tab.label}`);
    }

    /**
     * Get a plugin by ID
     */
    getPlugin(pluginId) {
        return this.plugins.find(p => p.id === pluginId);
    }

    /**
     * Activate a plugin tab
     */
    activatePlugin(pluginId, data) {
        const plugin = this.getPlugin(pluginId);
        if (!plugin) return;

        const container = document.getElementById(`${pluginId}-tab`);
        if (!container) return;

        // Store container and mark as active
        plugin.container = container;
        plugin.isActive = true;
        this.activePluginId = pluginId;

        // Call onTabActivate hook
        if (typeof plugin.onTabActivate === 'function') {
            try {
                plugin.onTabActivate.call(plugin, container, data);
            } catch (error) {
                console.error(`Error in ${plugin.name}.onTabActivate():`, error);
                container.innerHTML = `
                    <div class="empty-state">
                        <h3>Plugin Error</h3>
                        <p>Failed to load plugin content. Check console for details.</p>
                    </div>
                `;
            }
        }
    }

    /**
     * Deactivate a plugin tab
     */
    deactivatePlugin(pluginId) {
        const plugin = this.getPlugin(pluginId);
        if (!plugin) return;

        plugin.isActive = false;

        if (this.activePluginId === pluginId) {
            this.activePluginId = null;
        }

        // Call onTabDeactivate hook
        if (typeof plugin.onTabDeactivate === 'function') {
            try {
                plugin.onTabDeactivate.call(plugin);
            } catch (error) {
                console.error(`Error in ${plugin.name}.onTabDeactivate():`, error);
            }
        }
    }

    /**
     * Notify all plugins of data update
     */
    notifyDataUpdate(data) {
        this.plugins.forEach(plugin => {
            if (typeof plugin.onDataUpdate === 'function') {
                try {
                    plugin.onDataUpdate.call(plugin, data);
                } catch (error) {
                    console.error(`Error in ${plugin.name}.onDataUpdate():`, error);
                }
            }
        });
    }

    /**
     * Notify all plugins that crawl is complete
     */
    notifyCrawlComplete(data) {
        this.plugins.forEach(plugin => {
            if (typeof plugin.onCrawlComplete === 'function') {
                try {
                    plugin.onCrawlComplete.call(plugin, data);
                } catch (error) {
                    console.error(`Error in ${plugin.name}.onCrawlComplete():`, error);
                }
            }
        });
    }

    /**
     * Get all loaded plugins
     */
    getAllPlugins() {
        return this.plugins;
    }
}

// Global plugin API
window.LibreCrawlPlugin = {
    loader: new PluginLoader(),

    /**
     * Register a new plugin
     * @param {Object} config - Plugin configuration
     */
    register(config) {
        return this.loader.registerPlugin(config);
    },

    /**
     * Get the plugin loader instance
     */
    getLoader() {
        return this.loader;
    }
};

console.log('🔌 LibreCrawl Plugin System loaded');
