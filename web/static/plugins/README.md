# LibreCrawl Plugins

Drop your custom plugin files here! Each `.js` file will automatically create a new tab in LibreCrawl.

## 🔌 Quick Start

1. Create a new `.js` file in this folder (e.g., `my-plugin.js`)
2. Register your plugin using the LibreCrawl Plugin API
3. Refresh the app - your new tab appears automatically!

## 📝 Example Plugin Structure

```javascript
LibreCrawlPlugin.register({
  // Required: Unique ID (used for tab identification)
  id: 'my-plugin',

  // Required: Display name
  name: 'My Plugin',

  // Required: Tab configuration
  tab: {
    label: 'My Tab',
    icon: '🔥', // Optional emoji
  },

  // Called when your tab is activated
  onTabActivate(container, data) {
    // data contains: { urls, links, issues, stats }
    container.innerHTML = `
      <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
        <h2>My Custom Analysis</h2>
        <p>Found ${data.urls.length} URLs!</p>
      </div>
    `;
  },

  // Optional: Called during live crawls when data updates
  onDataUpdate(data) {
    if (this.isActive) {
      // Update your UI
    }
  }
});
```

## 🎯 Available Data

Your plugin receives the same data as built-in tabs:

- **`urls`** - Array of all crawled URLs with full metadata
- **`links`** - All discovered links (internal/external)
- **`issues`** - Detected SEO issues
- **`stats`** - Crawl statistics (discovered, crawled, depth, speed)

## 📚 Full API Reference

### Plugin Configuration

```javascript
{
  id: string,              // Unique identifier
  name: string,            // Display name
  version: string,         // Optional version
  author: string,          // Optional author
  description: string,     // Optional description

  tab: {
    label: string,         // Tab button text
    icon: string,          // Optional emoji/icon
    position: number       // Optional position (default: append to end)
  }
}
```

### Lifecycle Hooks

- `onLoad()` - Called when plugin loads
- `onTabActivate(container, data)` - Called when tab becomes active
- `onTabDeactivate()` - Called when user switches away
- `onDataUpdate(data)` - Called during live crawls
- `onCrawlComplete(data)` - Called when crawl finishes

### Utilities

Access built-in utilities via `this.utils`:

```javascript
this.utils.showNotification(message, type) // 'success', 'error', 'info'
this.utils.formatUrl(url)
this.utils.escapeHtml(text)
```

## 🎨 Styling

Use these CSS classes to match LibreCrawl's design:

- `.plugin-content` - Main container
- `.plugin-header` - Header section
- `.data-table` - Tables (auto-styled)
- `.stat-card` - Statistic cards
- `.score-good` / `.score-needs-improvement` / `.score-poor` - Score indicators

**Important:** Always add these styles to your main plugin container for proper scrolling:

```javascript
container.innerHTML = `
  <div class="plugin-content" style="padding: 20px; overflow-y: auto; max-height: calc(100vh - 280px);">
    <!-- Your content here -->
  </div>
`;
```

The `max-height: calc(100vh - 280px)` ensures your content scrolls properly within the tab pane.

## 🔥 Example Plugins

Check out these example plugins to get started:

- `_example-plugin.js` - Basic template (ignored by loader)
- `e-e-a-t.js` - E-E-A-T analyzer example
- `content-quality.js` - Content quality scorer example

Happy plugin development! 🚀
