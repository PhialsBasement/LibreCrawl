import webview
import threading
import time
import csv
import json
import xml.etree.ElementTree as ET
from io import StringIO
from flask import Flask, render_template, request, jsonify
from src.crawler import WebCrawler
from src.settings_manager import SettingsManager

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')

# Global instances
crawler = WebCrawler()
settings_manager = SettingsManager()

def generate_csv_export(urls, fields):
    """Generate CSV export content"""
    output = StringIO()
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()

    for url_data in urls:
        row = {}
        for field in fields:
            value = url_data.get(field, '')

            # Handle complex data types for CSV
            if field == 'analytics' and isinstance(value, dict):
                analytics_list = []
                if value.get('gtag') or value.get('ga4_id'): analytics_list.append('GA4')
                if value.get('google_analytics'): analytics_list.append('GA')
                if value.get('gtm_id'): analytics_list.append('GTM')
                if value.get('facebook_pixel'): analytics_list.append('FB')
                if value.get('hotjar'): analytics_list.append('HJ')
                if value.get('mixpanel'): analytics_list.append('MP')
                row[field] = ', '.join(analytics_list)
            elif field == 'og_tags' and isinstance(value, dict):
                row[field] = f"{len(value)} tags" if value else ''
            elif field == 'twitter_tags' and isinstance(value, dict):
                row[field] = f"{len(value)} tags" if value else ''
            elif field == 'json_ld' and isinstance(value, list):
                row[field] = f"{len(value)} scripts" if value else ''
            elif field == 'images' and isinstance(value, list):
                row[field] = f"{len(value)} images" if value else ''
            elif field == 'internal_links' and isinstance(value, (int, float)):
                row[field] = f"{int(value)} internal links" if value else '0 internal links'
            elif field == 'external_links' and isinstance(value, (int, float)):
                row[field] = f"{int(value)} external links" if value else '0 external links'
            elif field == 'h2' and isinstance(value, list):
                row[field] = ', '.join(value[:3]) + ('...' if len(value) > 3 else '')
            elif field == 'h3' and isinstance(value, list):
                row[field] = ', '.join(value[:3]) + ('...' if len(value) > 3 else '')
            elif isinstance(value, (dict, list)):
                row[field] = str(value)
            else:
                row[field] = value

        writer.writerow(row)

    return output.getvalue()

def generate_json_export(urls, fields):
    """Generate JSON export content"""
    filtered_urls = []
    for url_data in urls:
        filtered_data = {}
        for field in fields:
            value = url_data.get(field, '')
            # Keep complex data structures intact in JSON
            filtered_data[field] = value
        filtered_urls.append(filtered_data)

    return json.dumps({
        'export_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_urls': len(filtered_urls),
        'fields': fields,
        'data': filtered_urls
    }, indent=2, default=str)

def generate_xml_export(urls, fields):
    """Generate XML export content"""
    root = ET.Element('librecrawl_export')
    root.set('export_date', time.strftime('%Y-%m-%d %H:%M:%S'))
    root.set('total_urls', str(len(urls)))

    urls_element = ET.SubElement(root, 'urls')

    for url_data in urls:
        url_element = ET.SubElement(urls_element, 'url')
        for field in fields:
            field_element = ET.SubElement(url_element, field)
            field_element.text = str(url_data.get(field, ''))

    return ET.tostring(root, encoding='unicode')

def generate_links_csv_export(links):
    """Generate CSV export for links data"""
    output = StringIO()
    fieldnames = ['source_url', 'target_url', 'anchor_text', 'is_internal', 'target_domain', 'target_status']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for link in links:
        row = {
            'source_url': link.get('source_url', ''),
            'target_url': link.get('target_url', ''),
            'anchor_text': link.get('anchor_text', ''),
            'is_internal': 'Yes' if link.get('is_internal') else 'No',
            'target_domain': link.get('target_domain', ''),
            'target_status': link.get('target_status', 'Not crawled')
        }
        writer.writerow(row)

    return output.getvalue()

def generate_links_json_export(links):
    """Generate JSON export for links data"""
    return json.dumps(links, indent=2)

def generate_issues_csv_export(issues):
    """Generate CSV export for issues data"""
    output = StringIO()
    fieldnames = ['url', 'type', 'category', 'issue', 'details']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for issue in issues:
        row = {
            'url': issue.get('url', ''),
            'type': issue.get('type', ''),
            'category': issue.get('category', ''),
            'issue': issue.get('issue', ''),
            'details': issue.get('details', '')
        }
        writer.writerow(row)

    return output.getvalue()

def generate_issues_json_export(issues):
    """Generate JSON export for issues data"""
    # Group issues by URL for better organization
    issues_by_url = {}
    for issue in issues:
        url = issue.get('url', '')
        if url not in issues_by_url:
            issues_by_url[url] = []
        issues_by_url[url].append({
            'type': issue.get('type', ''),
            'category': issue.get('category', ''),
            'issue': issue.get('issue', ''),
            'details': issue.get('details', '')
        })

    return json.dumps({
        'export_date': time.strftime('%Y-%m-%d %H:%M:%S'),
        'total_issues': len(issues),
        'total_urls_with_issues': len(issues_by_url),
        'issues_by_url': issues_by_url,
        'all_issues': issues
    }, indent=2)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start_crawl', methods=['POST'])
def start_crawl():
    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'error': 'URL is required'})

    # Apply current settings to crawler before starting
    try:
        crawler_config = settings_manager.get_crawler_config()
        crawler.update_config(crawler_config)
    except Exception as e:
        print(f"Warning: Could not apply settings: {e}")

    success, message = crawler.start_crawl(url)
    return jsonify({'success': success, 'message': message})

@app.route('/api/stop_crawl', methods=['POST'])
def stop_crawl():
    success, message = crawler.stop_crawl()
    return jsonify({'success': success, 'message': message})

@app.route('/api/crawl_status')
def crawl_status():
    return jsonify(crawler.get_status())

@app.route('/api/get_settings')
def get_settings():
    try:
        settings = settings_manager.get_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    try:
        data = request.get_json()
        success, message = settings_manager.save_settings(data)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_settings', methods=['POST'])
def reset_settings():
    try:
        success, message = settings_manager.reset_settings()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_crawler_settings', methods=['POST'])
def update_crawler_settings():
    try:
        # Get current settings and update crawler configuration
        crawler_config = settings_manager.get_crawler_config()
        crawler.update_config(crawler_config)
        return jsonify({'success': True, 'message': 'Crawler settings updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/pause_crawl', methods=['POST'])
def pause_crawl():
    try:
        success, message = crawler.pause_crawl()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resume_crawl', methods=['POST'])
def resume_crawl():
    try:
        success, message = crawler.resume_crawl()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export_data', methods=['POST'])
def export_data():
    try:
        data = request.get_json()
        export_format = data.get('format', 'csv')
        export_fields = data.get('fields', ['url', 'status_code', 'title'])

        # Get current crawl results
        crawl_data = crawler.get_status()
        urls = crawl_data.get('urls', [])
        links = crawl_data.get('links', [])
        issues = crawl_data.get('issues', [])

        if not urls:
            return jsonify({'success': False, 'error': 'No data to export'})

        # Check if issues_detected export is requested (SEPARATE FILE)
        if 'issues_detected' in export_fields:
            # Remove it from the regular export fields
            export_fields = [f for f in export_fields if f != 'issues_detected']

            # Export issues data as a COMPLETELY SEPARATE file
            if issues:
                # Prepare issues export
                if export_format == 'csv':
                    issues_content = generate_issues_csv_export(issues)
                    issues_mimetype = 'text/csv'
                    issues_filename = f'librecrawl_issues_{int(time.time())}.csv'
                elif export_format == 'json':
                    issues_content = generate_issues_json_export(issues)
                    issues_mimetype = 'application/json'
                    issues_filename = f'librecrawl_issues_{int(time.time())}.json'
                else:
                    issues_content = generate_issues_csv_export(issues)
                    issues_mimetype = 'text/csv'
                    issues_filename = f'librecrawl_issues_{int(time.time())}.csv'

                # If no other fields selected, return just the issues
                if not export_fields:
                    return jsonify({
                        'success': True,
                        'content': issues_content,
                        'mimetype': issues_mimetype,
                        'filename': issues_filename
                    })

                # Otherwise, return BOTH files
                # Generate regular export for the remaining fields
                if export_format == 'csv':
                    regular_content = generate_csv_export(urls, export_fields)
                    regular_mimetype = 'text/csv'
                    regular_filename = f'librecrawl_export_{int(time.time())}.csv'
                elif export_format == 'json':
                    regular_content = generate_json_export(urls, export_fields)
                    regular_mimetype = 'application/json'
                    regular_filename = f'librecrawl_export_{int(time.time())}.json'
                elif export_format == 'xml':
                    regular_content = generate_xml_export(urls, export_fields)
                    regular_mimetype = 'application/xml'
                    regular_filename = f'librecrawl_export_{int(time.time())}.xml'
                else:
                    regular_content = generate_csv_export(urls, export_fields)
                    regular_mimetype = 'text/csv'
                    regular_filename = f'librecrawl_export_{int(time.time())}.csv'

                # Return both files data
                return jsonify({
                    'success': True,
                    'multiple_files': True,
                    'files': [
                        {
                            'content': regular_content,
                            'mimetype': regular_mimetype,
                            'filename': regular_filename
                        },
                        {
                            'content': issues_content,
                            'mimetype': issues_mimetype,
                            'filename': issues_filename
                        }
                    ]
                })

        # Check if links_detailed export is requested
        elif 'links_detailed' in export_fields:
            # Export links data separately
            if not links:
                return jsonify({'success': False, 'error': 'No links data to export'})

            if export_format == 'csv':
                content = generate_links_csv_export(links)
                mimetype = 'text/csv'
                filename = f'librecrawl_links_{int(time.time())}.csv'
            elif export_format == 'json':
                content = generate_links_json_export(links)
                mimetype = 'application/json'
                filename = f'librecrawl_links_{int(time.time())}.json'
            else:
                content = generate_links_csv_export(links)
                mimetype = 'text/csv'
                filename = f'librecrawl_links_{int(time.time())}.csv'
        else:
            # Generate regular export content
            if export_format == 'csv':
                content = generate_csv_export(urls, export_fields)
                mimetype = 'text/csv'
                filename = f'librecrawl_export_{int(time.time())}.csv'
            elif export_format == 'json':
                content = generate_json_export(urls, export_fields)
                mimetype = 'application/json'
                filename = f'librecrawl_export_{int(time.time())}.json'
            elif export_format == 'xml':
                content = generate_xml_export(urls, export_fields)
                mimetype = 'application/xml'
                filename = f'librecrawl_export_{int(time.time())}.xml'
            else:
                return jsonify({'success': False, 'error': 'Unsupported export format'})

        return jsonify({
            'success': True,
            'content': content,
            'mimetype': mimetype,
            'filename': filename
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def start_flask():
    app.run(host='127.0.0.1', port=5000, debug=False, use_reloader=False)

def main():
    # Start Flask in a separate thread
    flask_thread = threading.Thread(target=start_flask, daemon=True)
    flask_thread.start()

    # Give Flask a moment to start
    import time
    time.sleep(1)

    # Create webview window
    webview.create_window(
        title='LibreCrawl - SEO Spider',
        url='http://127.0.0.1:5000',
        width=1400,
        height=900,
        min_size=(1000, 600),
        resizable=True
    )

    # Start webview (this will block until window is closed)
    webview.start(debug=False)

if __name__ == '__main__':
    main()