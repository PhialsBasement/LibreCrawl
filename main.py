import threading
import time
import csv
import json
import xml.etree.ElementTree as ET
import uuid
import webbrowser
import argparse
import secrets
import string
import os
import requests
from io import StringIO
from datetime import datetime, timedelta
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_compress import Compress
from functools import wraps
from src.crawler import WebCrawler
from src.settings_manager import SettingsManager
from src.auth_db import init_db, create_user, authenticate_user, get_user_by_id, log_guest_crawl, get_guest_crawls_last_24h, verify_user, set_user_tier, create_verification_token, verify_token, get_user_by_email, create_magic_link, verify_magic_link
from src.email_service import send_verification_email, send_welcome_email, send_magic_link_email

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# OpenAI client for AI-powered issue explanations
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
except ImportError:
    openai_client = None
    print("Warning: openai package not installed. AI explanations will be unavailable.")

# Parse command line arguments
parser = argparse.ArgumentParser(description='LibreCrawl - SEO Spider Tool')
parser.add_argument('--local', '-l', action='store_true',
                    help='Run in local mode (all users get admin tier, no rate limits)')
parser.add_argument('--disable-register', '-dr', action='store_true',
                    help='Disable new user registrations')
parser.add_argument('--disable-guest', '-dg', action='store_true',
                    help='Disable guest login')
parser.add_argument('--demo', '-dm', action='store_true',
                    help='Demo mode: 1.5GB memory limit per user, crawls auto-stop at limit')
parser.add_argument('--dangerously-skip-auth', '-dsa', action='store_true',
                    help='DANGEROUS: Allow anyone to log in as any username with no password. '
                         'The username is only used to separate per-user sessions. '
                         'Do NOT use on a public network or in production.')
args = parser.parse_args()

LOCAL_MODE = args.local
DISABLE_REGISTER = args.disable_register
DISABLE_GUEST = args.disable_guest or os.getenv('DISABLE_GUEST', '').lower() in ('true', '1', 'yes')
DEMO_MODE = args.demo or os.getenv('DEMO_MODE', '').lower() in ('true', '1', 'yes')
SKIP_AUTH = args.dangerously_skip_auth or os.getenv('DANGEROUSLY_SKIP_AUTH', '').lower() in ('true', '1', 'yes')
ALLOWED_EMAIL_DOMAIN = os.getenv('ALLOWED_EMAIL_DOMAIN', '')
MAIN_APP_URL = os.getenv('MAIN_APP_URL', 'http://localhost:5000').rstrip('/')

app = Flask(__name__, template_folder='web/templates', static_folder='web/static')
app.secret_key = 'librecrawl-secret-key-change-in-production'  # TODO: Use environment variable in production

# Enable compression for all responses
Compress(app)

# Initialize database on startup
init_db()

def generate_random_password(length=16):
    """Generate a random password with letters, digits, and symbols"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def auto_login_local_mode():
    """Auto-login for local mode - creates or logs into 'local' admin account"""
    import sqlite3
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'users.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Check if 'local' user exists
        cursor.execute('SELECT id, username, tier FROM users WHERE username = ?', ('local',))
        user = cursor.fetchone()

        if user:
            # User exists, just log them in
            session['user_id'] = user['id']
            session['username'] = user['username']
            session['tier'] = 'admin'
            session.permanent = True
            print(f"Auto-logged in as existing 'local' user (ID: {user['id']})")
        else:
            # Create new local user with random password
            random_password = generate_random_password()
            from src.auth_db import hash_password
            password_hash = hash_password(random_password)

            cursor.execute('''
                INSERT INTO users (username, email, password_hash, verified, tier)
                VALUES (?, ?, ?, 1, 'admin')
            ''', ('local', 'local@localhost', password_hash))
            conn.commit()

            user_id = cursor.lastrowid

            # Log in the new user
            session['user_id'] = user_id
            session['username'] = 'local'
            session['tier'] = 'admin'
            session.permanent = True

            print(f"Created and auto-logged in as new 'local' admin user (ID: {user_id})")
            print(f"Generated password: {random_password}")

        conn.close()
        return True
    except Exception as e:
        print(f"Error in auto_login_local_mode: {e}")
        return False

def skip_auth_login(username):
    """Skip-auth login: create user record if missing, log them in.

    Each username gets its own user_id, which drives per-user crawler
    instance and settings isolation. No password is checked. Always
    grants admin tier (matches local-mode behavior).

    Returns (success, message).
    """
    import sqlite3
    try:
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'users.db'))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute('SELECT id, username FROM users WHERE username = ?', (username,))
        user = cursor.fetchone()

        if user:
            user_id = user['id']
        else:
            from src.auth_db import hash_password
            random_password = generate_random_password()
            password_hash = hash_password(random_password)
            cursor.execute('''
                INSERT INTO users (username, email, password_hash, verified, tier)
                VALUES (?, ?, ?, 1, 'admin')
            ''', (username, f'{username}@skipauth.local', password_hash))
            conn.commit()
            user_id = cursor.lastrowid

        conn.close()

        session['user_id'] = user_id
        session['username'] = username
        session['tier'] = 'admin'
        session.permanent = True

        return True, 'Logged in (authentication skipped)'
    except sqlite3.IntegrityError as e:
        # Most likely the generated email collides with an existing account
        # whose email happens to match. Fall back to a clearer message.
        return False, f'Username conflict: try a different username ({e})'
    except Exception as e:
        print(f"Error in skip_auth_login: {e}")
        return False, f'Login error: {str(e)}'

if LOCAL_MODE:
    print("=" * 60)
    print("LOCAL MODE ENABLED")
    print("All users will have admin tier access")
    print("No rate limits or tier restrictions")
    print("Auto-login enabled with 'local' admin account")
    print("=" * 60)

if DISABLE_REGISTER:
    print("=" * 60)
    print("REGISTRATION DISABLED")
    print("New user registrations are not allowed")
    print("=" * 60)

if DISABLE_GUEST:
    print("=" * 60)
    print("GUEST MODE DISABLED")
    print("Guest login is not allowed")
    print("=" * 60)

if DEMO_MODE:
    print("=" * 60)
    print("DEMO MODE ENABLED")
    print("Memory limit: 1.5GB per user")
    print("Crawls will auto-stop when limit is reached")
    print("=" * 60)

if SKIP_AUTH:
    print("=" * 60)
    print("⚠️  DANGEROUSLY SKIP AUTH ENABLED")
    print("Anyone can log in as any username with no password!")
    print("Username is used only to separate per-user sessions.")
    print("DO NOT use on a public network or production server!")
    print("=" * 60)

def get_client_ip():
    """Get the real client IP address, checking Cloudflare headers first"""
    # Check Cloudflare header first
    if 'CF-Connecting-IP' in request.headers:
        return request.headers['CF-Connecting-IP']
    # Check other common proxy headers
    if 'X-Forwarded-For' in request.headers:
        # X-Forwarded-For can contain multiple IPs, take the first one
        return request.headers['X-Forwarded-For'].split(',')[0].strip()
    if 'X-Real-IP' in request.headers:
        return request.headers['X-Real-IP']
    # Fall back to direct connection IP
    return request.remote_addr

def login_required(f):
    """Decorator to require login for routes"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # In local mode, auto-login if not already logged in
        if LOCAL_MODE and 'user_id' not in session:
            auto_login_local_mode()
        elif 'user_id' not in session:
            # Not in local mode and not logged in
            if request.path.startswith('/api/'):
                return jsonify({'success': False, 'error': 'Authentication required'}), 401
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function

# Multi-tenant crawler instances
crawler_instances = {}  # session_id -> {'crawler': WebCrawler, 'settings': SettingsManager, 'last_accessed': datetime}
instances_lock = threading.Lock()

def get_or_create_crawler():
    """Get or create a crawler instance for the current session"""
    # Get or create session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']
    user_id = session.get('user_id')  # Get user_id from session
    tier = session.get('tier', 'guest')  # Get tier from session

    with instances_lock:
        # Check if crawler exists for this session
        if session_id not in crawler_instances:
            print(f"Creating new crawler instance for session: {session_id}, user: {user_id}, tier: {tier}")
            crawler_instances[session_id] = {
                'crawler': WebCrawler(),
                'settings': SettingsManager(session_id=session_id, user_id=user_id, tier=tier),  # Per-user settings
                'last_accessed': datetime.now()
            }
        else:
            # Update last accessed time
            crawler_instances[session_id]['last_accessed'] = datetime.now()

        return crawler_instances[session_id]['crawler']

def get_session_settings():
    """Get the settings manager for the current session"""
    # Get or create session ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())

    session_id = session['session_id']
    user_id = session.get('user_id')  # Get user_id from session
    tier = session.get('tier', 'guest')  # Get tier from session

    with instances_lock:
        # Create instance if it doesn't exist
        if session_id not in crawler_instances:
            print(f"Creating new settings instance for session: {session_id}, user: {user_id}, tier: {tier}")
            crawler_instances[session_id] = {
                'crawler': WebCrawler(),
                'settings': SettingsManager(session_id=session_id, user_id=user_id, tier=tier),
                'last_accessed': datetime.now()
            }
        else:
            # Update last accessed time
            crawler_instances[session_id]['last_accessed'] = datetime.now()

        return crawler_instances[session_id]['settings']

def cleanup_old_instances():
    """Remove crawler instances that haven't been accessed in 1 hour"""
    timeout = timedelta(hours=1)
    now = datetime.now()

    with instances_lock:
        sessions_to_remove = []
        for session_id, instance_data in crawler_instances.items():
            if now - instance_data['last_accessed'] > timeout:
                sessions_to_remove.append(session_id)

        for session_id in sessions_to_remove:
            print(f"Cleaning up crawler instance for session: {session_id}")
            # Stop any running crawls
            try:
                crawler_instances[session_id]['crawler'].stop_crawl()
            except:
                pass
            del crawler_instances[session_id]

        if sessions_to_remove:
            print(f"Cleaned up {len(sessions_to_remove)} inactive crawler instances")

def start_cleanup_thread():
    """Start background thread to cleanup old instances"""
    def cleanup_loop():
        while True:
            time.sleep(300)  # Check every 5 minutes
            try:
                cleanup_old_instances()
            except Exception as e:
                print(f"Error in cleanup thread: {e}")

    cleanup_thread = threading.Thread(target=cleanup_loop, daemon=True)
    cleanup_thread.start()
    print("Started crawler instance cleanup thread")

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
    fieldnames = ['source_url', 'target_url', 'anchor_text', 'is_internal', 'target_domain', 'target_status', 'placement']
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for link in links:
        row = {
            'source_url': link.get('source_url', ''),
            'target_url': link.get('target_url', ''),
            'anchor_text': link.get('anchor_text', ''),
            'is_internal': 'Yes' if link.get('is_internal') else 'No',
            'target_domain': link.get('target_domain', ''),
            'target_status': link.get('target_status', 'Not crawled'),
            'placement': link.get('placement', 'body')
        }
        writer.writerow(row)

    return output.getvalue()

def generate_links_json_export(links):
    """Generate JSON export for links data"""
    return json.dumps(links, indent=2)

def filter_issues_by_exclusion_patterns(issues, exclusion_patterns):
    """Filter issues based on exclusion patterns (applies current settings to loaded crawls)"""
    from fnmatch import fnmatch
    from urllib.parse import urlparse

    if not exclusion_patterns:
        return issues

    filtered_issues = []

    for issue in issues:
        url = issue.get('url', '')
        parsed = urlparse(url)
        path = parsed.path

        # Check if URL matches any exclusion pattern
        should_exclude = False
        for pattern in exclusion_patterns:
            if not pattern.strip() or pattern.strip().startswith('#'):
                continue

            if '*' in pattern:
                if fnmatch(path, pattern):
                    should_exclude = True
                    break
            elif path == pattern or path.startswith(pattern.rstrip('*')):
                should_exclude = True
                break

        if not should_exclude:
            filtered_issues.append(issue)

    return filtered_issues

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

@app.route('/login')
def login_page():
    # In local mode, auto-login and redirect to index
    if LOCAL_MODE:
        auto_login_local_mode()
        return redirect(url_for('index'))
    # Redirect to app if already logged in
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('login.html', registration_disabled=DISABLE_REGISTER, guest_disabled=DISABLE_GUEST, skip_auth=SKIP_AUTH, allowed_domain=ALLOWED_EMAIL_DOMAIN)

@app.route('/register')
def register_page():
    # Redirect to app if already logged in
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template('register.html', registration_disabled=DISABLE_REGISTER)

@app.route('/verify')
def verify_email():
    """Email verification endpoint"""
    token = request.args.get('token')

    if not token:
        return render_template('verification_result.html',
                             success=False,
                             message='Invalid verification link',
                             app_source='main')

    # Verify the token
    success, message, app_source, user_email = verify_token(token)

    # Send welcome email if successful
    if success and user_email:
        try:
            user = get_user_by_email(user_email)
            if user:
                send_welcome_email(user_email, user['username'], app_source or 'main')
        except Exception as e:
            print(f"Error sending welcome email: {e}")

    # Determine redirect URL based on app_source
    redirect_url = None
    if success:
        if app_source == 'workshop':
            redirect_url = os.getenv('WORKSHOP_APP_URL', 'https://workshop.librecrawl.com')
        else:
            redirect_url = url_for('login_page')

    return render_template('verification_result.html',
                         success=success,
                         message=message,
                         app_source=app_source or 'main',
                         redirect_url=redirect_url)

@app.route('/api/request-magic-link', methods=['POST'])
def request_magic_link():
    data = request.get_json() or {}
    email = (data.get('email') or '').strip().lower()

    if not email or '@' not in email:
        return jsonify({'success': False, 'message': 'A valid email address is required.'})

    if ALLOWED_EMAIL_DOMAIN and not email.endswith(f'@{ALLOWED_EMAIL_DOMAIN}'):
        return jsonify({'success': False, 'message': f'Only @{ALLOWED_EMAIL_DOMAIN} addresses are allowed.'})

    token = create_magic_link(email)
    if not token:
        return jsonify({'success': False, 'message': 'Failed to generate login link. Please try again.'})

    magic_url = f"{MAIN_APP_URL}/auth/magic?token={token}"
    send_magic_link_email(email, magic_url)
    return jsonify({'success': True, 'message': 'Check your email for a login link.'})


@app.route('/auth/magic', methods=['GET'])
def magic_link_auth():
    token = request.args.get('token', '').strip()
    if not token:
        return redirect(url_for('login_page', error='invalid'))

    success, user_id, message = verify_magic_link(token)

    if not success:
        return redirect(url_for('login_page', error='invalid'))

    user = get_user_by_id(user_id)
    session['user_id'] = user_id
    session['username'] = user['username']
    session['tier'] = 'admin' if LOCAL_MODE else user['tier']
    session.permanent = True
    return redirect(url_for('index'))


@app.route('/api/register', methods=['POST'])
def register():
    return jsonify({'success': False, 'message': 'Registration is not available. Use magic link login.'}), 410

@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    username = (data.get('username') or '').strip()
    password = data.get('password') or ''

    # Dangerously skip auth: accept any username with no password.
    if SKIP_AUTH:
        if not username:
            return jsonify({'success': False, 'message': 'Username required'})
        if len(username) > 50:
            return jsonify({'success': False, 'message': 'Username must be 50 characters or less'})
        success, message = skip_auth_login(username)
        return jsonify({'success': success, 'message': message})

    return jsonify({'success': False, 'message': 'Password login is not available. Use OTP login.'}), 410

@app.route('/api/guest-login', methods=['POST'])
def guest_login():
    """Login as a guest user (no account required, limited to 3 crawls/24h)"""
    if DISABLE_GUEST:
        return jsonify({'success': False, 'message': 'Guest login is disabled'})

    # Create a guest session with no user_id but with tier='guest'
    # In local mode, guests also get admin tier
    session['user_id'] = None
    session['username'] = 'Guest'
    session['tier'] = 'admin' if LOCAL_MODE else 'guest'
    session.permanent = False  # Don't persist guest sessions

    return jsonify({'success': True, 'message': 'Logged in as guest'})

@app.route('/api/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return jsonify({'success': True, 'message': 'Logged out successfully'})

@app.route('/api/user/info')
@login_required
def user_info():
    """Get current user info including tier"""
    from src.auth_db import get_crawls_last_24h
    user_id = session.get('user_id')
    tier = session.get('tier', 'guest')
    username = session.get('username')

    # Get crawl count
    crawls_today = 0
    if tier == 'guest':
        # For guests, count from IP address
        client_ip = get_client_ip()
        crawls_today = get_guest_crawls_last_24h(client_ip)
    else:
        # For registered users, count from database
        crawls_today = get_crawls_last_24h(user_id)

    return jsonify({
        'success': True,
        'user': {
            'id': user_id,
            'username': username,
            'tier': tier,
            'crawls_today': crawls_today,
            'crawls_remaining': max(0, 3 - crawls_today) if tier == 'guest' else -1
        }
    })

@app.route('/')
def index():
    # In local mode, auto-login if not already logged in
    if LOCAL_MODE and 'user_id' not in session:
        auto_login_local_mode()
    elif 'user_id' not in session:
        # Not in local mode and not logged in, redirect to login
        return redirect(url_for('login_page'))
    return render_template('index.html')

@app.route('/dashboard')
@login_required
def dashboard():
    """Crawl history dashboard"""
    return render_template('dashboard.html')

@app.route('/debug/memory')
@login_required
def debug_memory_page():
    """Debug page with nice UI for memory monitoring"""
    return render_template('debug_memory.html')

@app.route('/api/start_crawl', methods=['POST'])
@login_required
def start_crawl():
    from src.auth_db import get_crawls_last_24h, log_crawl_start

    data = request.get_json()
    url = data.get('url')

    if not url:
        return jsonify({'success': False, 'error': 'URL is required'})

    user_id = session.get('user_id')
    session_id = session.get('session_id')
    tier = session.get('tier', 'guest')

    # Check guest limits (IP-based) - skip in local mode
    if tier == 'guest' and not LOCAL_MODE:
        client_ip = get_client_ip()
        crawls_from_ip = get_guest_crawls_last_24h(client_ip)

        if crawls_from_ip >= 3:
            return jsonify({
                'success': False,
                'error': 'Guest limit reached: 3 crawls per 24 hours from your IP address. Please register for unlimited crawls.'
            })

        # Log this guest crawl
        log_guest_crawl(client_ip)

    # Get or create crawler for this session
    crawler = get_or_create_crawler()
    settings_manager = get_session_settings()

    # Apply current settings to crawler before starting
    try:
        crawler_config = settings_manager.get_crawler_config()
        crawler.update_config(crawler_config)
    except Exception as e:
        print(f"Warning: Could not apply settings: {e}")

    # Enforce demo mode limits
    if DEMO_MODE:
        crawler.config['demo_mode'] = True
        crawler.config['demo_memory_limit_bytes'] = int(1.5 * 1024 * 1024 * 1024)  # 1.5GB

    # Pass user_id and session_id for database persistence
    success, message = crawler.start_crawl(url, user_id=user_id, session_id=session_id)

    # Store crawl_id in session
    if success and crawler.crawl_id:
        session['current_crawl_id'] = crawler.crawl_id
        # Also log to old crawl_history for compatibility
        log_crawl_start(user_id, url)

    return jsonify({'success': success, 'message': message, 'crawl_id': crawler.crawl_id})

@app.route('/api/stop_crawl', methods=['POST'])
@login_required
def stop_crawl():
    crawler = get_or_create_crawler()
    success, message = crawler.stop_crawl()
    return jsonify({'success': success, 'message': message})

@app.route('/api/crawl_status')
@login_required
def crawl_status():
    crawler = get_or_create_crawler()
    settings_manager = get_session_settings()

    # Check for incremental update parameters
    url_since = request.args.get('url_since', type=int)
    link_since = request.args.get('link_since', type=int)
    issue_since = request.args.get('issue_since', type=int)

    # Get full status data
    status_data = crawler.get_status()

    # Ensure baseUrl is in stats (needed for UI to work correctly)
    if crawler.base_url and 'stats' in status_data:
        status_data['stats']['baseUrl'] = crawler.base_url

    # Check if we need to force a full refresh (after loading from DB)
    force_full = session.pop('force_full_refresh', False)

    # If incremental parameters provided AND not forcing full refresh, slice the arrays
    if not force_full:
        if url_since is not None:
            status_data['urls'] = status_data.get('urls', [])[url_since:]
        if link_since is not None:
            status_data['links'] = status_data.get('links', [])[link_since:]
        if issue_since is not None:
            status_data['issues'] = status_data.get('issues', [])[issue_since:]

    # Apply current issue exclusion patterns to displayed issues
    issues = status_data.get('issues', [])
    if issues:
        current_settings = settings_manager.get_settings()
        exclusion_patterns_text = current_settings.get('issueExclusionPatterns', '')
        exclusion_patterns = [p.strip() for p in exclusion_patterns_text.split('\n') if p.strip()]
        filtered_issues = filter_issues_by_exclusion_patterns(issues, exclusion_patterns)
        status_data['issues'] = filtered_issues

    return jsonify(status_data)

@app.route('/api/visualization_data')
@login_required
def visualization_data():
    """Get graph data for site structure visualization"""
    try:
        crawler = get_or_create_crawler()
        status_data = crawler.get_status()

        # Get URLs from the status data
        crawled_pages = status_data.get('urls', [])
        all_links = status_data.get('links', [])

        # Build nodes and edges for the graph
        nodes = []
        edges = []
        url_to_id = {}

        # Create nodes from crawled pages (limit to prevent lag)
        max_nodes = 500  # Optimization: limit nodes for performance
        pages_to_visualize = crawled_pages[:max_nodes]

        for idx, page in enumerate(pages_to_visualize):
            url = page.get('url', '')
            status_code = page.get('status_code', 0)

            # Assign color based on status code
            if 200 <= status_code < 300:
                color = '#10b981'  # Green for 2xx
            elif 300 <= status_code < 400:
                color = '#3b82f6'  # Blue for 3xx
            elif 400 <= status_code < 500:
                color = '#f59e0b'  # Orange for 4xx
            elif 500 <= status_code < 600:
                color = '#ef4444'  # Red for 5xx
            else:
                color = '#6b7280'  # Gray for other

            # Create node
            node = {
                'data': {
                    'id': f'node-{idx}',
                    'label': url.split('/')[-1] or url.split('//')[-1],  # Use last path segment or domain
                    'url': url,
                    'status_code': status_code,
                    'title': page.get('title', ''),
                    'color': color,
                    'size': 30 if idx == 0 else 20,  # Make root node larger
                    'depth': page.get('depth', 0)
                }
            }
            nodes.append(node)
            url_to_id[url] = f'node-{idx}'

        # Create edges from links data
        # Links are stored as: {'source_url': url, 'target_url': url, 'is_internal': bool, ...}
        edges_set = set()  # Use set to avoid duplicate edges
        for link in all_links:
            if link.get('is_internal'):  # Only use internal links
                source_url = link.get('source_url', '')
                target_url = link.get('target_url', '')

                source_id = url_to_id.get(source_url)
                target_id = url_to_id.get(target_url)

                if source_id and target_id and source_id != target_id:
                    edge_key = f'{source_id}-{target_id}'
                    if edge_key not in edges_set:
                        edges_set.add(edge_key)
                        edge = {
                            'data': {
                                'id': f'edge-{edge_key}',
                                'source': source_id,
                                'target': target_id
                            }
                        }
                        edges.append(edge)

        return jsonify({
            'success': True,
            'nodes': nodes,
            'edges': edges,
            'total_pages': len(crawled_pages),
            'visualized_pages': len(nodes),
            'truncated': len(crawled_pages) > max_nodes
        })

    except Exception as e:
        print(f"Error generating visualization data: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': str(e),
            'nodes': [],
            'edges': []
        })

@app.route('/api/debug/memory')
@login_required
def debug_memory():
    """Debug endpoint showing memory stats for all active crawler instances"""
    with instances_lock:
        memory_stats = {
            'total_instances': len(crawler_instances),
            'instances': []
        }

        for session_id, instance_data in crawler_instances.items():
            crawler = instance_data['crawler']
            stats = crawler.memory_monitor.get_stats()

            memory_stats['instances'].append({
                'session_id': session_id[:8] + '...',  # Truncate for privacy
                'last_accessed': instance_data['last_accessed'].isoformat(),
                'urls_crawled': len(crawler.crawl_results),
                'memory': stats,
                'data_sizes': crawler.user_memory.get_stats()
            })

        return jsonify(memory_stats)

@app.route('/api/debug/memory/profile')
@login_required
def debug_memory_profile():
    """Detailed memory profiling - what's actually using the RAM"""
    from src.core.memory_profiler import MemoryProfiler

    with instances_lock:
        profiles = []

        for session_id, instance_data in crawler_instances.items():
            crawler = instance_data['crawler']

            # Get object breakdown
            breakdown = MemoryProfiler.get_object_memory_breakdown()

            profiles.append({
                'session_id': session_id[:8] + '...',
                'urls_crawled': len(crawler.crawl_results),
                'object_breakdown': breakdown,
                'data_sizes': crawler.user_memory.get_stats()
            })

        return jsonify({
            'total_instances': len(crawler_instances),
            'profiles': profiles
        })

@app.route('/api/filter_issues', methods=['POST'])
@login_required
def filter_issues():
    try:
        data = request.get_json()
        issues = data.get('issues', [])
        settings_manager = get_session_settings()

        # Get current exclusion patterns
        current_settings = settings_manager.get_settings()
        exclusion_patterns_text = current_settings.get('issueExclusionPatterns', '')
        exclusion_patterns = [p.strip() for p in exclusion_patterns_text.split('\n') if p.strip()]

        # Filter issues
        filtered_issues = filter_issues_by_exclusion_patterns(issues, exclusion_patterns)

        return jsonify({'success': True, 'issues': filtered_issues})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/get_settings')
@login_required
def get_settings():
    try:
        settings_manager = get_session_settings()
        settings = settings_manager.get_settings()
        return jsonify({'success': True, 'settings': settings})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/save_settings', methods=['POST'])
@login_required
def save_settings():
    try:
        data = request.get_json()
        settings_manager = get_session_settings()
        success, message = settings_manager.save_settings(data)
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/reset_settings', methods=['POST'])
@login_required
def reset_settings():
    try:
        settings_manager = get_session_settings()
        success, message = settings_manager.reset_settings()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/update_crawler_settings', methods=['POST'])
@login_required
def update_crawler_settings():
    try:
        crawler = get_or_create_crawler()
        settings_manager = get_session_settings()
        # Get current settings and update crawler configuration
        crawler_config = settings_manager.get_crawler_config()
        crawler.update_config(crawler_config)
        return jsonify({'success': True, 'message': 'Crawler settings updated'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/pause_crawl', methods=['POST'])
@login_required
def pause_crawl():
    try:
        crawler = get_or_create_crawler()
        success, message = crawler.pause_crawl()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/resume_crawl', methods=['POST'])
@login_required
def resume_crawl():
    try:
        crawler = get_or_create_crawler()
        success, message = crawler.resume_crawl()
        return jsonify({'success': success, 'message': message})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crawls/list')
@login_required
def list_crawls():
    """Get all crawls for current user"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import get_user_crawls, get_crawl_count

        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        status_filter = request.args.get('status')

        crawls = get_user_crawls(user_id, limit=limit, offset=offset, status_filter=status_filter)
        total_count = get_crawl_count(user_id)

        return jsonify({
            'success': True,
            'crawls': crawls,
            'total': total_count
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crawls/<int:crawl_id>')
@login_required
def get_crawl(crawl_id):
    """Get complete crawl data by ID"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import get_crawl_by_id, load_crawled_urls, load_crawl_links, load_crawl_issues

        # Get crawl metadata
        crawl = get_crawl_by_id(crawl_id)
        if not crawl:
            return jsonify({'success': False, 'error': 'Crawl not found'}), 404

        # Check ownership (guests have user_id = None)
        if user_id and crawl.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        # Load all data
        urls = load_crawled_urls(crawl_id)
        links = load_crawl_links(crawl_id)
        issues = load_crawl_issues(crawl_id)

        return jsonify({
            'success': True,
            'crawl': crawl,
            'urls': urls,
            'links': links,
            'issues': issues
        })
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/crawls/<int:crawl_id>/load', methods=['POST'])
@login_required
def load_crawl_into_session(crawl_id):
    """Load a historical crawl into the current session"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import get_crawl_by_id, load_crawled_urls, load_crawl_links, load_crawl_issues

        # Get crawl metadata
        crawl = get_crawl_by_id(crawl_id)
        if not crawl:
            return jsonify({'success': False, 'error': 'Crawl not found'}), 404

        # Check ownership
        if user_id and crawl.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        # Get current crawler instance
        crawler = get_or_create_crawler()

        # Stop any running crawl
        if crawler.is_running:
            crawler.stop_crawl()

        # Load all data from database
        urls = load_crawled_urls(crawl_id)
        links = load_crawl_links(crawl_id)
        issues = load_crawl_issues(crawl_id)

        # Inject into current crawler instance
        with crawler.results_lock:
            crawler.crawl_results = urls
            crawler.stats['crawled'] = len(urls)
            crawler.stats['discovered'] = len(urls)
            crawler.base_url = crawl['base_url']
            crawler.base_domain = crawl['base_domain']

        # Load links into link manager
        if crawler.link_manager:
            crawler.link_manager.all_links = links
            # Rebuild links_set
            crawler.link_manager.links_set.clear()
            for link in links:
                link_key = f"{link['source_url']}|{link['target_url']}"
                crawler.link_manager.links_set.add(link_key)

        # Load issues into issue detector
        if crawler.issue_detector:
            crawler.issue_detector.detected_issues = issues

        # Rebuild per-user memory tracker for loaded data
        crawler.user_memory.reset()
        crawler._demo_limit_reached = False
        for url_data in urls:
            crawler.user_memory.track_url(url_data)
        if links:
            crawler.user_memory.track_links(links)
        if issues:
            crawler.user_memory.track_issues(issues)

        # Set Flask session flag for force full refresh
        session['force_full_refresh'] = True

        return jsonify({
            'success': True,
            'message': f'Loaded {len(urls)} URLs, {len(links)} links, {len(issues)} issues',
            'urls_count': len(urls),
            'links_count': len(links),
            'issues_count': len(issues),
            'should_refresh_ui': True
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/crawls/<int:crawl_id>/resume', methods=['POST'])
@login_required
def resume_crawl_endpoint(crawl_id):
    """Resume an interrupted crawl"""
    try:
        user_id = session.get('user_id')
        session_id = session.get('session_id')

        # Get crawler for this session
        crawler = get_or_create_crawler()

        # Enforce demo mode limits on resumed crawls
        if DEMO_MODE:
            crawler.config['demo_mode'] = True
            crawler.config['demo_memory_limit_bytes'] = int(1.5 * 1024 * 1024 * 1024)

        # Resume from database
        success, message = crawler.resume_from_database(crawl_id, user_id=user_id, session_id=session_id)

        if success:
            session['current_crawl_id'] = crawl_id

        return jsonify({'success': success, 'message': message})
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crawls/<int:crawl_id>/delete', methods=['DELETE'])
@login_required
def delete_crawl_endpoint(crawl_id):
    """Delete a crawl and all associated data"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import delete_crawl, get_crawl_by_id

        # Verify ownership
        crawl = get_crawl_by_id(crawl_id)
        if not crawl:
            return jsonify({'success': False, 'error': 'Crawl not found'}), 404

        if user_id and crawl.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        success = delete_crawl(crawl_id)
        return jsonify({'success': success, 'message': 'Crawl deleted successfully' if success else 'Failed to delete crawl'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crawls/<int:crawl_id>/archive', methods=['POST'])
@login_required
def archive_crawl(crawl_id):
    """Archive crawl (mark as archived but keep data)"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import set_crawl_status, get_crawl_by_id

        # Verify ownership
        crawl = get_crawl_by_id(crawl_id)
        if not crawl:
            return jsonify({'success': False, 'error': 'Crawl not found'}), 404

        if user_id and crawl.get('user_id') != user_id:
            return jsonify({'success': False, 'error': 'Unauthorized'}), 403

        success = set_crawl_status(crawl_id, 'archived')
        return jsonify({'success': success, 'message': 'Crawl archived successfully' if success else 'Failed to archive crawl'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/crawls/stats')
@login_required
def crawl_stats():
    """Get statistics about user's crawls"""
    try:
        user_id = session.get('user_id')
        from src.crawl_db import get_crawl_count, get_database_size_mb
        import sqlite3

        # Get counts by status
        conn = sqlite3.connect(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'users.db'))
        cursor = conn.cursor()

        cursor.execute('''
            SELECT status, COUNT(*) as count
            FROM crawls
            WHERE user_id = ?
            GROUP BY status
        ''', (user_id,))

        status_counts = {row[0]: row[1] for row in cursor.fetchall()}
        conn.close()

        return jsonify({
            'success': True,
            'total_crawls': get_crawl_count(user_id),
            'by_status': status_counts,
            'database_size_mb': get_database_size_mb()
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/export_data', methods=['POST'])
@login_required
def export_data():
    try:
        data = request.get_json()
        export_format = data.get('format', 'csv')
        export_fields = data.get('fields', ['url', 'status_code', 'title'])
        local_data = data.get('localData', {})

        # Use local data if provided (from loaded crawl), otherwise get from crawler
        if local_data and local_data.get('urls'):
            urls = local_data.get('urls', [])
            links = local_data.get('links', [])
            issues = local_data.get('issues', [])
        else:
            # Get current crawl results
            crawler = get_or_create_crawler()
            crawl_data = crawler.get_status()
            urls = crawl_data.get('urls', [])
            links = crawl_data.get('links', [])
            issues = crawl_data.get('issues', [])

        if not urls:
            return jsonify({'success': False, 'error': 'No data to export'})

        # Update link statuses from crawled URLs (fixes missing status codes in exports)
        if links and urls:
            status_lookup = {url_data['url']: url_data.get('status_code') for url_data in urls}
            for link in links:
                target_url = link.get('target_url')
                if target_url in status_lookup:
                    link['target_status'] = status_lookup[target_url]

        # Apply current issue exclusion patterns (works for loaded crawls too)
        if issues:
            settings_manager = get_session_settings()
            current_settings = settings_manager.get_settings()
            exclusion_patterns_text = current_settings.get('issueExclusionPatterns', '')
            exclusion_patterns = [p.strip() for p in exclusion_patterns_text.split('\n') if p.strip()]
            issues = filter_issues_by_exclusion_patterns(issues, exclusion_patterns)
            print(f"DEBUG: After exclusion filter, {len(issues)} issues remain")

        # Collect files to export based on special field selections
        files_to_export = []

        # Check for special export fields and prepare them as separate files
        has_issues_export = 'issues_detected' in export_fields
        has_links_export = 'links_detailed' in export_fields

        # Remove special fields from regular export fields
        regular_fields = [f for f in export_fields if f not in ['issues_detected', 'links_detailed']]

        # Debug logging
        print(f"DEBUG: export_fields = {export_fields}")
        print(f"DEBUG: has_issues_export = {has_issues_export}")
        print(f"DEBUG: has_links_export = {has_links_export}")
        print(f"DEBUG: regular_fields = {regular_fields}")
        print(f"DEBUG: len(urls) = {len(urls)}")
        print(f"DEBUG: len(links) = {len(links)}")
        print(f"DEBUG: len(issues) = {len(issues)}")

        # Generate issues export if requested
        if has_issues_export:
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

            files_to_export.append({
                'content': issues_content,
                'mimetype': issues_mimetype,
                'filename': issues_filename
            })

        # Generate links export if requested
        if has_links_export:
            if export_format == 'csv':
                links_content = generate_links_csv_export(links)
                links_mimetype = 'text/csv'
                links_filename = f'librecrawl_links_{int(time.time())}.csv'
            elif export_format == 'json':
                links_content = generate_links_json_export(links)
                links_mimetype = 'application/json'
                links_filename = f'librecrawl_links_{int(time.time())}.json'
            else:
                links_content = generate_links_csv_export(links)
                links_mimetype = 'text/csv'
                links_filename = f'librecrawl_links_{int(time.time())}.csv'

            files_to_export.append({
                'content': links_content,
                'mimetype': links_mimetype,
                'filename': links_filename
            })

        # Generate regular export if there are regular fields
        if regular_fields:
            if export_format == 'csv':
                regular_content = generate_csv_export(urls, regular_fields)
                regular_mimetype = 'text/csv'
                regular_filename = f'librecrawl_export_{int(time.time())}.csv'
            elif export_format == 'json':
                regular_content = generate_json_export(urls, regular_fields)
                regular_mimetype = 'application/json'
                regular_filename = f'librecrawl_export_{int(time.time())}.json'
            elif export_format == 'xml':
                regular_content = generate_xml_export(urls, regular_fields)
                regular_mimetype = 'application/xml'
                regular_filename = f'librecrawl_export_{int(time.time())}.xml'
            else:
                return jsonify({'success': False, 'error': 'Unsupported export format'})

            files_to_export.append({
                'content': regular_content,
                'mimetype': regular_mimetype,
                'filename': regular_filename
            })

        # Handle special case where only special fields are selected but no data
        if not files_to_export:
            if has_issues_export and not issues:
                return jsonify({'success': False, 'error': 'No issues data to export'})
            elif has_links_export and not links:
                return jsonify({'success': False, 'error': 'No links data to export'})
            else:
                return jsonify({'success': False, 'error': 'No data to export'})

        # Return multiple files if we have more than one, otherwise single file
        if len(files_to_export) > 1:
            return jsonify({
                'success': True,
                'multiple_files': True,
                'files': files_to_export
            })
        else:
            # Single file
            file_data = files_to_export[0]
            return jsonify({
                'success': True,
                'content': file_data['content'],
                'mimetype': file_data['mimetype'],
                'filename': file_data['filename']
            })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

def recover_crashed_crawls():
    """Check for and recover any crashed crawls on startup"""
    try:
        from src.crawl_db import get_crashed_crawls, set_crawl_status

        crashed = get_crashed_crawls()

        if crashed:
            print("\n" + "=" * 60)
            print("CRASH RECOVERY")
            print("=" * 60)
            for crawl in crashed:
                set_crawl_status(crawl['id'], 'failed')
                print(f"Found crashed crawl: {crawl['base_url']} (ID: {crawl['id']})")
                print(f"  → Marked as failed. User can resume from dashboard.")
            print("=" * 60 + "\n")
    except Exception as e:
        print(f"Error during crash recovery: {e}")

def graceful_shutdown(signum, frame):
    """Save all active crawls before shutdown"""
    print("\n" + "=" * 60)
    print("GRACEFUL SHUTDOWN")
    print("=" * 60)
    print("Saving all active crawls...")

    try:
        with instances_lock:
            for session_id, instance_data in list(crawler_instances.items()):
                crawler = instance_data['crawler']
                if crawler.is_running and crawler.crawl_id and crawler.db_save_enabled:
                    print(f"  → Saving crawl {crawler.crawl_id}...")
                    try:
                        crawler._save_batch_to_db(force=True)
                        crawler._save_queue_checkpoint()
                        from src.crawl_db import set_crawl_status
                        set_crawl_status(crawler.crawl_id, 'paused')
                    except Exception as e:
                        print(f"    Error saving crawl {crawler.crawl_id}: {e}")

        print("All crawls saved successfully")
        print("=" * 60)
    except Exception as e:
        print(f"Error during shutdown: {e}")

    print("Goodbye!")
    import sys
    sys.exit(0)

CATEGORY_ROLE_MAP = {
    'Technical':        'Web Developer',
    'Performance':      'Web Developer',
    'SEO':              'Webmaster',
    'Content':          'Copywriter / Content Editor',
    'Accessibility':    'Web Developer / Designer',
    'Mobile':           'Web Developer / Designer',
    'Social':           'Copywriter / Content Editor',
    'Structured Data':  'Webmaster',
    'Indexability':     'Webmaster',
}

@app.route('/api/explain_issue', methods=['POST'])
@login_required
def explain_issue():
    """Generate AI-powered explanation and fix for a crawl issue using OpenAI"""
    try:
        # Check if OpenAI client is available
        if openai_client is None:
            return jsonify({
                'success': False,
                'error': 'OpenAI package not installed. Run: pip install openai>=1.0.0'
            }), 400

        # Check if API key is configured
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return jsonify({
                'success': False,
                'error': 'OPENAI_API_KEY not configured in .env file'
            }), 400

        data = request.get_json()
        url = data.get('url', '')
        issue = data.get('issue', '')
        category = data.get('category', '')
        details = data.get('details', '')
        page_context = data.get('page_context', {})

        # Build context string from page data
        context_parts = []
        if page_context.get('title'):
            context_parts.append(f"Page title: {page_context['title']}")
        if page_context.get('word_count'):
            context_parts.append(f"Word count: {page_context['word_count']}")
        if page_context.get('meta_description'):
            context_parts.append(f"Meta description: {page_context['meta_description'][:100]}")
        if page_context.get('h1'):
            context_parts.append(f"H1: {page_context['h1']}")

        context_str = '\n'.join(context_parts) if context_parts else 'No additional context available'

        # Build the prompt for OpenAI
        prompt = f"""You are an SEO expert providing actionable advice. Analyze this specific issue:

URL: {url}
Issue: {issue}
Category: {category}
Details: {details}

Page Context:
{context_str}

Provide a JSON response with exactly this structure:
{{
    "explanation": "2-3 sentence explanation of why this issue matters for SEO and user experience",
    "how_to_fix": "Step-by-step fix instructions (3-5 bullet points, use markdown formatting with • for bullets)",
    "priority": "high/medium/low based on SEO impact",
    "role": "Most suitable role from this list only: Webmaster (SEO config, robots.txt, sitemaps, schema markup, indexability), Copywriter / Content Editor (written content, meta descriptions, social tags, OG metadata), Web Developer (code, performance, accessibility implementation, responsive design, ARIA), Designer (visual design, color contrast, typography, layout, UX)"
}}

Keep the explanation concise but specific to this URL. Use SEMRush-style actionable language."""

        # Call OpenAI API
        response = openai_client.chat.completions.create(
            model='gpt-3.5-turbo',
            messages=[
                {'role': 'system', 'content': 'You are an SEO expert. Always respond with valid JSON.'},
                {'role': 'user', 'content': prompt}
            ],
            max_tokens=500,
            temperature=0.3,
            response_format={'type': 'json_object'}
        )

        # Parse response
        ai_response = json.loads(response.choices[0].message.content)

        # Log token usage (optional, for cost tracking)
        usage = response.usage
        print(f"AI Explain - Tokens used: {usage.total_tokens} (in: {usage.prompt_tokens}, out: {usage.completion_tokens})")

        return jsonify({
            'success': True,
            'explanation': ai_response.get('explanation', ''),
            'how_to_fix': ai_response.get('how_to_fix', ''),
            'priority': ai_response.get('priority', 'medium'),
            'role': ai_response.get('role', ''),
            'tokens_used': usage.total_tokens,
            'model': 'gpt-3.5-turbo'
        })

    except Exception as e:
        print(f"AI Explain Error: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/create_devops_ticket', methods=['POST'])
@login_required
def create_devops_ticket():
    """Create an Azure DevOps Product Backlog Item from a Page Diagnostics issue"""
    import base64
    from urllib.parse import urlparse, quote

    org      = os.getenv('AZURE_DEVOPS_ORG')
    pat      = os.getenv('AZURE_DEVOPS_PAT')
    sm_email = os.getenv('AZURE_DEVOPS_SM_EMAIL')

    missing = [k for k, v in {
        'AZURE_DEVOPS_ORG':      org,
        'AZURE_DEVOPS_PAT':      pat,
        'AZURE_DEVOPS_SM_EMAIL': sm_email,
    }.items() if not v]
    if missing:
        return jsonify({'success': False, 'error': f'Missing .env variables: {", ".join(missing)}'}), 400

    data        = request.get_json()
    url         = data.get('url', '')
    issue       = data.get('issue', '')
    category    = data.get('category', '')
    issue_type  = data.get('issue_type', 'warning')
    ai_exp      = data.get('ai_explanation', '')
    ai_fix      = data.get('ai_how_to_fix', '')
    ai_priority = data.get('ai_priority', 'medium')

    project   = data.get('project_override') or os.getenv('AZURE_DEVOPS_PROJECT', '')
    parent_id = data.get('parent_id_override') or os.getenv('AZURE_DEVOPS_PARENT_ID', '')

    if not project:
        return jsonify({'success': False, 'error': 'No Azure project selected. Use the Project dropdown next to the Clear button.'}), 400
    if not parent_id:
        return jsonify({'success': False, 'error': 'No Feature selected. Use the Feature dropdown next to the Clear button.'}), 400

    if issue_type == 'error':
        az_priority, sup_label, moscow = (1, 'Critical', 'Must') if ai_priority == 'high' else (2, 'High', 'Should')
    elif issue_type == 'warning':
        az_priority, sup_label, moscow = 3, 'Warning', 'Could'
    else:
        az_priority, sup_label, moscow = 4, 'Informational', "Won't"

    valid_roles = {'Webmaster', 'Copywriter / Content Editor', 'Web Developer', 'Designer'}
    ai_role = data.get('ai_role', '')
    role = ai_role if ai_role in valid_roles else CATEGORY_ROLE_MAP.get(category, 'Web Developer')
    fix_items = [p.strip() for p in ai_fix.split('•') if p.strip()]
    fix_html  = '<ul>' + ''.join(f'<li>{item}</li>' for item in fix_items) + '</ul>' \
                if fix_items else f'<p>{ai_fix}</p>'

    parsed    = urlparse(url)
    short_url = (parsed.path.rstrip('/') or parsed.netloc)[-60:]

    description_html = (
        f'<h3>🧩 Summary</h3>'
        f'<p>{ai_exp} This issue was detected by LibreCrawl on '
        f'<a href="{url}">{url}</a>. '
        f'Category: {category}. Severity: {sup_label} — Priority {az_priority} ({moscow}).</p>'
        f'<h3>👥 Responsibility</h3>'
        f'<ul><li>{role} — required</li>'
        f'<li>Scrum Master to review and delegate based on role above</li></ul>'
        f'<h3>⚙️ Implementation Direction</h3>'
        f'{fix_html}'
    )

    ac_html = (
        f'<ul>'
        f'<li>Issue "{issue}" should no longer be detected by LibreCrawl on {url}</li>'
        f'<li>Page should pass {category} validation in the next scheduled crawl</li>'
        f'<li>Verified and closed within sprint by Scrum Master</li>'
        f'</ul>'
    )

    title     = f'[{category}] {issue} — {short_url}'
    token     = base64.b64encode(f':{pat}'.encode()).decode()
    work_type = quote('Product Backlog Item')
    api_url   = f'https://dev.azure.com/{org}/{quote(project)}/_apis/wit/workitems/${work_type}?api-version=7.1'

    headers = {
        'Content-Type': 'application/json-patch+json',
        'Authorization': f'Basic {token}',
    }
    body = [
        {'op': 'add', 'path': '/fields/System.Title',                             'value': title},
        {'op': 'add', 'path': '/fields/System.Description',                       'value': description_html},
        {'op': 'add', 'path': '/fields/Microsoft.VSTS.Common.Priority',           'value': az_priority},
        {'op': 'add', 'path': '/fields/System.AssignedTo',                        'value': sm_email},
        {'op': 'add', 'path': '/fields/Microsoft.VSTS.Common.AcceptanceCriteria', 'value': ac_html},
        {'op': 'add', 'path': '/fields/System.AreaPath',                            'value': f'{project}\\{os.environ.get("AZURE_AREA_SUFFIX")}'},
        {'op': 'add', 'path': '/relations/-', 'value': {
            'rel': 'System.LinkTypes.Hierarchy-Reverse',
            'url': f'https://dev.azure.com/{org}/_apis/wit/workitems/{parent_id}',
            'attributes': {'comment': 'Created by LibreCrawl Page Diagnostics'}
        }},
    ]

    try:
        resp = requests.post(api_url, headers=headers, json=body, timeout=10)
        resp.raise_for_status()
        ticket_id  = resp.json()['id']
        ticket_url = f'https://dev.azure.com/{org}/{quote(project)}/_workitems/edit/{ticket_id}'
        from src.crawl_db import save_devops_ticket
        save_devops_ticket(url, issue, category, ticket_id, ticket_url, user_id=session.get('user_id'))
        return jsonify({'success': True, 'ticket_id': ticket_id, 'ticket_url': ticket_url, 'title': title})
    except requests.exceptions.HTTPError:
        return jsonify({'success': False, 'error': f'Azure DevOps {resp.status_code}: {resp.text}'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/devops_tickets/check', methods=['POST'])
@login_required
def check_devops_tickets():
    try:
        from src.crawl_db import get_tickets_for_issues
        data = request.get_json()
        pairs = data.get('pairs', [])
        tickets = get_tickets_for_issues(pairs)
        return jsonify({'success': True, 'tickets': tickets})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/devops/projects', methods=['GET'])
@login_required
def devops_projects():
    import base64
    from urllib.parse import quote
    org = os.getenv('AZURE_DEVOPS_ORG')
    pat = os.getenv('AZURE_DEVOPS_PAT')
    if not org or not pat:
        return jsonify({'success': False, 'error': 'AZURE_DEVOPS_ORG or AZURE_DEVOPS_PAT not configured'}), 400
    token   = base64.b64encode(f':{pat}'.encode()).decode()
    api_url = f'https://dev.azure.com/{org}/_apis/projects?api-version=7.1&$top=100'
    try:
        resp = requests.get(api_url, headers={'Authorization': f'Basic {token}'}, timeout=10)
        resp.raise_for_status()
        projects = [{'id': p['id'], 'name': p['name']} for p in resp.json().get('value', [])]
        return jsonify({'success': True, 'projects': projects})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/devops/features', methods=['GET'])
@login_required
def devops_features():
    import base64
    from urllib.parse import quote
    org     = os.getenv('AZURE_DEVOPS_ORG')
    pat     = os.getenv('AZURE_DEVOPS_PAT')
    project = request.args.get('project', '')
    if not org or not pat:
        return jsonify({'success': False, 'error': 'AZURE_DEVOPS_ORG or AZURE_DEVOPS_PAT not configured'}), 400
    if not project:
        return jsonify({'success': False, 'error': 'project query param required'}), 400
    token    = base64.b64encode(f':{pat}'.encode()).decode()
    headers  = {'Authorization': f'Basic {token}', 'Content-Type': 'application/json'}
    wiql_url = f'https://dev.azure.com/{org}/{quote(project)}/_apis/wit/wiql?api-version=7.1&$top=200'
    wiql_body = {'query': (
        "SELECT [System.Id] FROM WorkItems "
        "WHERE [System.WorkItemType] IN ('Epic', 'Feature') "
        "AND [System.TeamProject] = @project "
        "AND [System.State] <> 'Removed' "
        "ORDER BY [System.Title]"
    )}
    try:
        wiql_resp = requests.post(wiql_url, headers=headers, json=wiql_body, timeout=10)
        wiql_resp.raise_for_status()
        ids = [str(item['id']) for item in wiql_resp.json().get('workItems', [])][:200]
        if not ids:
            return jsonify({'success': True, 'features': []})
        batch_url  = (
            f'https://dev.azure.com/{org}/{quote(project)}/_apis/wit/workitems'
            f'?ids={",".join(ids)}&fields=System.Id,System.Title,System.WorkItemType&api-version=7.1'
        )
        batch_resp = requests.get(batch_url, headers=headers, timeout=10)
        batch_resp.raise_for_status()
        features = [
            {
                'id':   item['id'],
                'name': item['fields']['System.Title'],
                'type': item['fields'].get('System.WorkItemType', '')
            }
            for item in batch_resp.json().get('value', [])
        ]
        return jsonify({'success': True, 'features': features})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


def main():
    import signal

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, graceful_shutdown)
    signal.signal(signal.SIGTERM, graceful_shutdown)

    # Recover any crashed crawls from previous session
    recover_crashed_crawls()

    # Start cleanup thread for old crawler instances
    start_cleanup_thread()

    print("=" * 60)
    print("LibreCrawl - SEO Spider")
    print("=" * 60)
    print(f"\n🚀 Server starting on http://0.0.0.0:5000")
    print(f"🌐 Access from browser: http://localhost:5000")
    print(f"📱 Access from network: http://<your-ip>:5000")
    print(f"\n✨ Multi-tenancy enabled - each browser session is isolated")
    print(f"💾 Settings stored in browser localStorage")
    print(f"\nPress Ctrl+C to stop the server\n")
    print("=" * 60 + "\n")

    # Open browser in a separate thread after short delay
    def open_browser():
        time.sleep(1.5)  # Wait for Flask to start
        webbrowser.open('http://localhost:5000')

    browser_thread = threading.Thread(target=open_browser, daemon=True)
    browser_thread.start()

    # Run Flask server with Waitress (production-grade WSGI server)
    from waitress import serve
    print("Starting LibreCrawl on http://localhost:5000")
    print("Using Waitress WSGI server with multi-threading support")
    serve(app, host='0.0.0.0', port=5000, threads=8)

if __name__ == '__main__':
    main()