# LibreCrawl

A desktop web crawler for SEO analysis and website auditing.

<img width="1408" height="736" alt="img" src="https://github.com/user-attachments/assets/ed091b73-2551-44e2-9286-ebfc166cabf7" />

## What it does

LibreCrawl crawls websites and gives you detailed information about pages, links, SEO elements, and performance. It's built as a desktop app using Python and a web interface.

## Features

<img width="1920" height="1037" alt="z1" src="https://github.com/user-attachments/assets/8a9b2445-8938-44da-b8f2-2451bcb90bdf" />

- Crawl websites with configurable depth and limits
- Extract SEO data (titles, meta descriptions, headings, etc.)
- Analyze internal and external links
- Track analytics and social media tags
- PageSpeed Insights integration
- Export data to CSV, JSON, or XML
- Save and load crawl sessions
- Real-time crawling progress

## Getting started

<img width="1920" height="1037" alt="z2" src="https://github.com/user-attachments/assets/6f9cbf84-3338-47b1-b1dc-e8860eac44e8" />


### Requirements

- Python 3.8 or later
- Windows, macOS, or Linux

### Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python main.py
```

The app will open in a desktop window.

### Basic usage


<img width="1920" height="1037" alt="z3" src="https://github.com/user-attachments/assets/5375bf78-be25-41af-8b5d-0fa72d2d0d8d" />

1. Enter a website URL in the input field
2. Click "Start" to begin crawling
3. View results in the different tabs (Overview, Internal, External, etc.)
4. Use "Export" to save data or "Save Crawl" to resume later

## Configuration

Click "Settings" to configure:

- **Crawler settings**: depth, URL limits, delays
- **Request settings**: user agent, timeouts, proxy
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
- Some dynamic content requires JavaScript (not currently supported)

## Files

- `main.py` - Main application and Flask server
- `src/crawler.py` - Core crawling engine
- `src/settings_manager.py` - Configuration management
- `web/` - Frontend interface files

## License

MIT License - see LICENSE file for details.
