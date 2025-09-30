# LibreCrawl

A desktop web crawler for SEO analysis and website auditing.

## What it does

LibreCrawl crawls websites and gives you detailed information about pages, links, SEO elements, and performance. It's built as a desktop app using Python and a web interface.

## Features

- Crawl websites with configurable depth and limits
- **JavaScript rendering** for dynamic content (React, Vue, Angular, etc.)
- Extract SEO data (titles, meta descriptions, headings, etc.)
- Analyze internal and external links
- Track analytics and social media tags
- PageSpeed Insights integration
- Export data to CSV, JSON, or XML
- Save and load crawl sessions
- Real-time crawling progress

## Getting started

### Requirements

- Python 3.8 or later
- Windows, macOS, or Linux

### Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```
***IMPORTANT: YOU MUST INSTALL pywebview==4.4.1 AND NOT ANY VERSION PAST 5.0, THE AUTHOR OF THE LIBRARY HAS CAUSED SOME ISSUES IN REGARDS TO DOWNLOADS***

3. For JavaScript rendering support (optional):
```bash
playwright install chromium
```

4. Run the application:
```bash
python main.py
```

The app will open in a desktop window.

### Basic usage

1. Enter a website URL in the input field
2. Click "Start" to begin crawling
3. View results in the different tabs (Overview, Internal, External, etc.)
4. Use "Export" to save data or "Save Crawl" to resume later

## Configuration

Click "Settings" to configure:

- **Crawler settings**: depth, URL limits, delays
- **Request settings**: user agent, timeouts, proxy
- **JavaScript rendering**: browser engine, wait times, viewport size
- **Filters**: file types to include/exclude
- **Export options**: formats and fields to export

For PageSpeed analysis, you can add a Google API key in Settings > Requests for higher rate limits.

## Export formats

- **CSV**: Spreadsheet-friendly format
- **JSON**: Structured data with all details
- **XML**: Markup format for other tools

## Known limitations

- PageSpeed API has rate limits (works better with API key)
- Large sites may take time to crawl completely
- JavaScript rendering is slower than HTTP-only crawling

## Files

- `main.py` - Main application and Flask server
- `src/crawler.py` - Core crawling engine
- `src/settings_manager.py` - Configuration management
- `web/` - Frontend interface files

## License

MIT License - see LICENSE file for details.
