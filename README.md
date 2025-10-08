# LibreCrawl

A web-based multi-tenant crawler for SEO analysis and website auditing.

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

### Requirements

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
python main.py
```

5. Open your browser and navigate to:
   - Local: `http://localhost:5000`
   - Network: `http://<your-ip>:5000`

### Basic usage

1. Enter a website URL in the input field
2. Click "Start" to begin crawling
3. View results in the different tabs (Overview, Internal, External, Links, Issues, PageSpeed)
4. Use "Export" to save data or "Save Crawl" to resume later
5. Customize the UI appearance in Settings > Custom CSS

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
