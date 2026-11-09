# LibreCrawl

A web-based multi-tenant crawler for SEO analysis and website auditing.

🌐 **Website**: [librecrawl.com](https://librecrawl.com)

**Demo no longer available cause people thought it was a prod environ, it isnt, it was a demo to get a taste before installing**

**API Documentation:** [https://librecrawl.com/api/docs/](https://librecrawl.com/api/docs/)

**Browse plugins other people have built, or share your own, at the [Plugin Workshop](https://workshop.librecrawl.com)**.

LibreCrawl will ***always*** be free and open source. It's built and maintained by one person, with no paid tier and no investors.

### 💼 Using LibreCrawl at an agency or company?

If LibreCrawl is replacing a $279/year Screaming Frog, Deepcrawl or Sitebulb license for each of your seats, please consider putting some of that budget toward the tool you're actually using. Sponsorship pays for new features, bug fixes and keeping the project alive.

| Tier | Suggested | You get |
|---|---|---|
| ☕ Individual | Any amount | My thanks, and a faster LibreCrawl |
| 🥈 Freelancer / small agency | $20/month | Your name in the Sponsors section below |
| 🥇 Agency | $100/month | Your logo and link in the Sponsors section below |
| 🏆 Enterprise | $500/month | Large logo at the top of this README, plus priority on your bug reports and feature requests |

**[Become a sponsor on GitHub](https://github.com/sponsors/PhialsBasement)** (monthly or one-time, and companies can pay through their GitHub billing). You can also give through [PayPal](https://www.paypal.com/donate/?business=7H9HFA3385JS8&no_recurring=0&item_name=Continue+the+development+of+LibreCrawl&currency_code=AUD). Need an invoice for your accounts team? [Open an issue](https://github.com/PhialsBasement/LibreCrawl/issues) or contact me through [librecrawl.com](https://librecrawl.com).

### ❤️ Sponsors

*No sponsors yet. Your agency's logo could be first here.*

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
- 💾 **Multiple export formats** - CSV, Excel (XLSX), JSON, or XML
- 🔍 **Issue detection** - Automated SEO issue identification
- 🧩 **N-gram analysis** - Phrase frequency across body text, headings, titles, and inlink anchor text, with a CSV export
- ⚡ **Real-time crawling progress** with live statistics

## Getting started
### Quick Start (Automatic Installation)

**The easiest way to run LibreCrawl.** The start script installs everything else and opens LibreCrawl in your browser. All you need first is **Python 3.11 or newer** (or Docker).

The first start takes a few minutes, because it downloads LibreCrawl's packages and a Chromium browser (about 200 MB). Later starts are quick. Keep the window open while you use LibreCrawl, and close it (or press `Ctrl+C`) to stop.

#### Windows

1. Install Python from [python.org/downloads](https://www.python.org/downloads/) and run the installer.
2. Download LibreCrawl: on this page click the green **Code** button, then **Download ZIP**, and unzip it.
3. Open the unzipped `LibreCrawl-main` folder and double-click **`start-librecrawl.bat`**.

#### Mac

1. Install Python from [python.org/downloads](https://www.python.org/downloads/) (the macOS installer) and click through it.
2. Download LibreCrawl: on this page click the green **Code** button, then **Download ZIP**. Double-click the ZIP in your Downloads folder to unzip it.
3. Open **Terminal** (press `Cmd+Space`, type *Terminal*, press Enter).
4. Type `cd ` (with a space after it), drag the unzipped `LibreCrawl-main` folder into the Terminal window, and press Enter.
5. Paste these two lines and press Enter:
   ```bash
   chmod +x start-librecrawl.sh
   ./start-librecrawl.sh
   ```

#### Linux

```bash
# Ubuntu/Debian: Python and its venv module
sudo apt install python3 python3-venv git

git clone https://github.com/PhialsBasement/LibreCrawl.git
cd LibreCrawl
./start-librecrawl.sh
```

**What the start script does:**
1. If Docker (with Docker Compose) is installed and running, it runs LibreCrawl in a container. If Docker is installed but not running, it tells you to start it.
2. Otherwise it uses Python 3.11+: it creates its own environment in `.venv` (so your system Python stays untouched), installs LibreCrawl's packages, and installs Chromium for JavaScript rendering.
3. It starts LibreCrawl in local mode (no login) and opens `http://localhost:5000`.

It checks the packages on every start, so updating LibreCrawl also brings in any new ones.

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
docker compose up -d

# Open browser to http://localhost:5000
```
Docker starts in **standard mode** (accounts and login) unless you set `LOCAL_MODE=true`. The start scripts above use local mode. For personal use on your own machine, set this in `.env` to skip accounts entirely:

```bash
# .env file
LOCAL_MODE=true
HOST_BINDING=127.0.0.1
REGISTRATION_DISABLED=false
```

In standard mode without email (SMTP) set up, **the first account you register becomes the admin** and can log in straight away. Accounts registered after that need approving, see [Managing accounts](#managing-accounts).

For production deployment with user authentication, edit your `.env` file:

```bash
# .env file
LOCAL_MODE=false
HOST_BINDING=0.0.0.0
REGISTRATION_DISABLED=false
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=replace-with-a-long-random-string
```

To add a **Login with Zoho** button, create a "Server-based Application" client at
[api-console.zoho.com](https://api-console.zoho.com) with the redirect URI
`https://your-host/auth/zoho/callback`, then set:

```bash
ZOHO_OAUTH_ENABLED=true
ZOHO_CLIENT_ID=...
ZOHO_CLIENT_SECRET=...
ZOHO_REDIRECT_URI=https://your-host/auth/zoho/callback
# Optional: ZOHO_ACCOUNTS_URL, ZOHO_ALLOWED_DOMAINS, ZOHO_ALLOW_SIGNUP, ZOHO_DEFAULT_TIER
```

See `.env.example` for what each option does.


#### Option 2: Python

- Python 3.11 or later
- Modern web browser (Chrome, Firefox, Safari, Edge)

### Installation

1. Clone or download this repository

2. Create a virtual environment and install dependencies (Homebrew and recent Linux Python refuse a system-wide `pip install`):
```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
python -m pip install -r requirements.txt
```

3. For JavaScript rendering support (optional):
```bash
python -m playwright install chromium
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

### Managing accounts

In standard mode, new accounts are verified by email when SMTP is configured (`SMTP_*` in `.env`). Without SMTP:

- The **first account** registered on the server becomes the **admin** and can log in immediately. If you registered before this existed, just log in: an unverified account claims admin if the server has none yet.
- Later accounts can't log in until the admin approves them.

There's no admin page yet, so use `manage.py`:

```bash
python manage.py users                       # list accounts, verified status and tier
python manage.py approve <username>          # let an account log in (tier "user")
python manage.py approve <username> --tier extra
python manage.py set-tier <username> admin   # guest, user, extra or admin

# Docker
docker compose exec librecrawl python manage.py users
```

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
- **Excel (XLSX)**: Native spreadsheet workbook
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
