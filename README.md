# LibreCrawl

A web-based multi-tenant crawler for SEO analysis and website auditing.

🌐 **Website**: [librecrawl.com](https://librecrawl.com)

**Try the Live Demo:** [https://librecrawl.com/app/](https://librecrawl.com/app/)

**API Documentation:** [https://librecrawl.com/api/docs/](https://librecrawl.com/api/docs/)

**Plugin Workshop** [https://librecrawl.com/workshop/](https://librecrawl.com/workshop/)

LibreCrawl will ***always*** be free and open source. If it's replacing your $259/year Screaming Frog license, deepcrawl license or sitebulb license, [buy me a coffee](https://www.paypal.com/donate/?business=7H9HFA3385JS8&no_recurring=0&item_name=Continue+the+development+of+LibreCrawl&currency_code=AUD).

## What it does

LibreCrawl crawls websites and gives you detailed information about pages, links, SEO elements, and performance. It's built as a web application using Python Flask with a modern web interface supporting multiple concurrent users.

## Features

- 🚀 **Multi-tenancy** - Multiple users can crawl simultaneously with isolated sessions
- 🎨 **Custom CSS styling** - Personalize the UI with your own CSS themes
- 💾 **Browser localStorage persistence** - Settings saved per browser
- 🔄 **JavaScript rendering** for dynamic content (React, Vue, Angular, etc.)
- 📊 **SEO analysis** - Extract titles, meta descriptions, headings, etc.
- 🔗 **Link analysis** - Track internal and external links with detailed relationship mapping
- 📈 **PageSpeed Insights integration** - Analyze Core Web Vitals
- 💾 **Multiple export formats** - CSV, JSON, or XML
- 🔍 **Issue detection** - Automated SEO issue identification
- ⚡ **Real-time crawling progress** with live statistics

## Getting started
### Quick Start (Automatic Installation)

**The easiest way to run LibreCrawl** - just run the startup script and it handles everything:

**Windows:**
```batch
start-librecrawl.bat
```

**Linux/Mac:**
```bash
chmod +x start-librecrawl.sh
./start-librecrawl.sh
```

**What it does automatically:**
1. Checks for Docker - if found, runs LibreCrawl in a container (recommended)
2. If no Docker, checks for Python - if not found, downloads and installs it (Windows only *temporairly disabled since it causes some bat issues*)
3. Installs all dependencies automatically (`pip install -r requirements.txt`)
4. Installs Playwright browsers for JavaScript rendering
5. Starts LibreCrawl in local mode (no authentication)
6. Opens your browser to `http://localhost:5000`

### Manual Installation

If you prefer to install manually or want more control:

#### Option 1: Docker (Recommended)

**Requirements:**
- Docker and Docker Compose

**Steps:**
```bash
# Clone the repository
git clone https://github.com/PhialsBasement/LibreCrawl.git
cd LibreCrawl

# Copy environment file
cp .env.example .env

# Start LibreCrawl
docker-compose up -d

# Open browser to http://localhost:5000
```
By default, LibreCrawl runs in local mode for easy personal use. The `.env` file controls this:

```bash
# .env file
LOCAL_MODE=true
HOST_BINDING=127.0.0.1
REGISTRATION_DISABLED=false
```

For production deployment with user authentication, edit your `.env` file:

```bash
# .env file
LOCAL_MODE=false
HOST_BINDING=0.0.0.0
REGISTRATION_DISABLED=false
```


#### Option 2: Python

- Python 3.8 or later
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. Clone or download this repository

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. For JavaScript rendering support (optional):
```bash
playwright install chromium
```

4. Run the application:
```bash
# Standard mode (with authentication and tier system)
python main.py

# Local mode (all users get admin tier, no rate limits)
python main.py --local
# or
python main.py -l
```

5. Open your browser and navigate to:
   - Local: `http://localhost:5000`
   - Network: `http://<your-ip>:5000`


## LibreCrawl Plugins

Drop your custom plugin files in `/web/static/plugins/`! Each `.js` file will automatically create a new tab in LibreCrawl.

### 🔌 Quick Start

1. Create a new `.js` file in this folder (e.g., `my-plugin.js`)
2. Register your plugin using the LibreCrawl Plugin API
3. Refresh the app - your new tab appears automatically!

### 📝 Example Plugin Structure

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

### 🎯 Available Data

Your plugin receives the same data as built-in tabs:

- **`urls`** - Array of all crawled URLs with full metadata
- **`links`** - All discovered links (internal/external)
- **`issues`** - Detected SEO issues
- **`stats`** - Crawl statistics (discovered, crawled, depth, speed)

### 📚 Full API Reference

#### Plugin Configuration

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

#### Lifecycle Hooks

- `onLoad()` - Called when plugin loads
- `onTabActivate(container, data)` - Called when tab becomes active
- `onTabDeactivate()` - Called when user switches away
- `onDataUpdate(data)` - Called during live crawls
- `onCrawlComplete(data)` - Called when crawl finishes

#### Utilities

Access built-in utilities via `this.utils`:

```javascript
this.utils.showNotification(message, type) // 'success', 'error', 'info'
this.utils.formatUrl(url)
this.utils.escapeHtml(text)
```

#### 🎨 Styling

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

#### Example Plugins

Check out these example plugins to get started:

- `_example-plugin.js` - Basic template (ignored by loader)
- `e-e-a-t.js` - E-E-A-T analyzer example


### Running Modes

**Standard Mode** (default):
- Full authentication system with login/register
- Tier-based access control (Guest, User, Extra, Admin)
- Guest users limited to 3 crawls per 24 hours (IP-based)
- Ideal for public-facing demos or shared hosting

**Local Mode** (`--local` or `-l`):
- All users automatically get admin tier access
- No rate limits or tier restrictions
- Perfect for personal use or single-user self-hosting
- Recommended for local development and testing

## Configuration

Click "Settings" to configure:

- **Crawler settings**: depth (up to 5M URLs), delays, external links
- **Request settings**: user agent, timeouts, proxy, robots.txt
- **JavaScript rendering**: browser engine, wait times, viewport size
- **Filters**: file types and URL patterns to include/exclude
- **Export options**: formats and fields to export
- **Custom CSS**: personalize the UI appearance with custom styles
- **Issue exclusion**: patterns to exclude from SEO issue detection

For PageSpeed analysis, add a Google API key in Settings > Requests for higher rate limits (25k/day vs limited).

## Export formats

- **CSV**: Spreadsheet-friendly format
- **JSON**: Structured data with all details
- **XML**: Markup format for other tools

## Multi-tenancy

LibreCrawl supports multiple concurrent users with isolated sessions:

- Each browser session gets its own crawler instance and data
- Settings are stored in browser localStorage (persistent across restarts)
- Custom CSS themes are per-browser
- Sessions expire after 1 hour of inactivity
- Crawl data is isolated between users

## Known limitations

- PageSpeed API has rate limits (works better with API key)
- Large sites may take time to crawl completely
- JavaScript rendering is slower than HTTP-only crawling
- Settings stored in localStorage (cleared if browser data is cleared)

## Files

- `main.py` - Main application and Flask server
- `src/crawler.py` - Core crawling engine
- `src/settings_manager.py` - Configuration management
- `web/` - Frontend interface files

## License

MIT License - see LICENSE file for details.
