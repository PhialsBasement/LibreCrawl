import json
import os
from pathlib import Path

class SettingsManager:
    def __init__(self):
        self.settings_file = Path.home() / '.librecrawl' / 'settings.json'
        self.settings_dir = self.settings_file.parent

        # Load default settings
        self.default_settings = self._get_default_settings()
        self.current_settings = self.load_settings()

    def _get_default_settings(self):
        """Get fresh default settings"""
        return {
            # Crawler settings
            'maxDepth': 3,
            'maxUrls': 1000,
            'crawlDelay': 1,
            'followRedirects': True,
            'crawlExternalLinks': False,

            # Request settings
            'userAgent': 'LibreCrawl/1.0 (Web Crawler)',
            'timeout': 10,
            'retries': 3,
            'acceptLanguage': 'en-US,en;q=0.9',
            'respectRobotsTxt': True,
            'allowCookies': True,
            'discoverSitemaps': True,
            'enablePageSpeed': False,
            'googleApiKey': '',

            # Filter settings
            'includeExtensions': 'html,htm,php,asp,aspx,jsp',
            'excludeExtensions': 'pdf,doc,docx,zip,exe,dmg',
            'includePatterns': '',
            'excludePatterns': '',
            'maxFileSize': 50,

            # Export settings
            'exportFormat': 'csv',
            'exportFields': ['url', 'status_code', 'title', 'meta_description', 'h1'],

            # Advanced settings
            'concurrency': 5,
            'memoryLimit': 512,
            'logLevel': 'INFO',
            'saveSession': False,
            'enableProxy': False,
            'proxyUrl': '',
            'customHeaders': '',

            # JavaScript rendering settings
            'enableJavaScript': False,
            'jsWaitTime': 3,
            'jsTimeout': 30,
            'jsBrowser': 'chromium',
            'jsHeadless': True,
            'jsUserAgent': 'LibreCrawl/1.0 (Web Crawler with JavaScript)',
            'jsViewportWidth': 1920,
            'jsViewportHeight': 1080,
            'jsMaxConcurrentPages': 3,

            # Issue exclusion patterns
            'issueExclusionPatterns': '''# WordPress admin & system paths
/wp-admin/*
/wp-content/plugins/*
/wp-content/themes/*
/wp-content/uploads/*
/wp-includes/*
/wp-login.php
/wp-cron.php
/xmlrpc.php
/wp-json/*
/wp-activate.php
/wp-signup.php
/wp-trackback.php

# Auth & user management pages
/login*
/signin*
/sign-in*
/log-in*
/auth/*
/authenticate/*
/register*
/signup*
/sign-up*
/registration/*
/logout*
/signout*
/sign-out*
/log-out*
/forgot-password*
/reset-password*
/password-reset*
/recover-password*
/change-password*
/account/password/*
/user/password/*
/activate/*
/verification/*
/verify/*
/confirm/*

# Admin panels & dashboards
/admin/*
/administrator/*
/_admin/*
/backend/*
/dashboard/*
/cpanel/*
/phpmyadmin/*
/pma/*
/webmail/*
/plesk/*
/control-panel/*
/manage/*
/manager/*

# E-commerce checkout & cart
/checkout/*
/cart/*
/basket/*
/payment/*
/billing/*
/order/*
/orders/*
/purchase/*

# User account pages
/account/*
/profile/*
/settings/*
/preferences/*
/my-account/*
/user/*
/member/*
/members/*

# CGI & server scripts
/cgi-bin/*
/cgi/*
/fcgi-bin/*

# Version control & config
/.git/*
/.svn/*
/.hg/*
/.bzr/*
/.cvs/*
/.env
/.env.*
/.htaccess
/.htpasswd
/web.config
/app.config
/composer.json
/package.json

# Development & build artifacts
/node_modules/*
/vendor/*
/bower_components/*
/jspm_packages/*
/includes/*
/lib/*
/libs/*
/src/*
/dist/*
/build/*
/builds/*
/_next/*
/.next/*
/out/*
/_nuxt/*
/.nuxt/*

# Testing & development
/test/*
/tests/*
/spec/*
/specs/*
/__tests__/*
/debug/*
/dev/*
/development/*
/staging/*

# API internal endpoints
/api/internal/*
/api/admin/*
/api/private/*

# System & internal
/private/*
/system/*
/core/*
/internal/*
/tmp/*
/temp/*
/cache/*
/logs/*
/log/*
/backup/*
/backups/*
/old/*
/archive/*
/archives/*
/config/*
/configs/*
/configuration/*

# Media upload forms
/upload/*
/uploads/*
/uploader/*
/file-upload/*

# Search & filtering (often noisy for SEO)
/search*
*/search/*
?s=*
?search=*
*/filter/*
?filter=*
*/sort/*
?sort=*

# Printer-friendly & special views
/print/*
?print=*
/preview/*
?preview=*
/embed/*
?embed=*
/amp/*
/amp

# Feed URLs
/feed/*
/feeds/*
/rss/*
*.rss
/atom/*
*.atom

# Common file types to exclude from issues
*.json
*.xml
*.yaml
*.yml
*.toml
*.ini
*.conf
*.log
*.txt
*.csv
*.sql
*.db
*.bak
*.backup
*.old
*.orig
*.tmp
*.swp
*.map
*.min.js
*.min.css'''
        }

    def ensure_settings_dir(self):
        """Ensure the settings directory exists"""
        self.settings_dir.mkdir(parents=True, exist_ok=True)

    def load_settings(self):
        """Load settings from file or return defaults"""
        try:
            if self.settings_file.exists():
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    saved_settings = json.load(f)
                    # Merge with defaults to ensure all keys are present
                    settings = {**self.default_settings}
                    settings.update(saved_settings)
                    return settings
            else:
                return self.default_settings.copy()
        except Exception as e:
            print(f"Error loading settings: {e}")
            return self.default_settings.copy()

    def save_settings(self, settings):
        """Save settings to file"""
        try:
            self.ensure_settings_dir()

            # Validate settings before saving
            if not self.validate_settings(settings):
                return False, "Invalid settings provided"

            # Update current settings
            self.current_settings = {**self.default_settings}
            self.current_settings.update(settings)

            # Save to file
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)

            return True, "Settings saved successfully"

        except Exception as e:
            return False, f"Error saving settings: {str(e)}"

    def get_settings(self):
        """Get current settings"""
        return self.current_settings.copy()

    def get_setting(self, key, default=None):
        """Get a specific setting value"""
        return self.current_settings.get(key, default)

    def update_setting(self, key, value):
        """Update a specific setting"""
        if key in self.default_settings:
            self.current_settings[key] = value
            return self.save_settings(self.current_settings)
        return False, f"Unknown setting key: {key}"

    def reset_settings(self):
        """Reset settings to defaults"""
        # Get fresh defaults from the method to ensure latest patterns are used
        fresh_defaults = self._get_default_settings()
        return self.save_settings(fresh_defaults)

    def validate_settings(self, settings):
        """Validate settings values"""
        try:
            # Check required keys exist
            for key in self.default_settings:
                if key not in settings:
                    return False

            # Validate numeric ranges
            numeric_validations = {
                'maxDepth': (1, 10),
                'maxUrls': (1, 50000),
                'crawlDelay': (0, 60),
                'timeout': (1, 120),
                'retries': (0, 10),
                'maxFileSize': (1, 1000),
                'concurrency': (1, 50),
                'memoryLimit': (64, 4096),
                'jsWaitTime': (0, 30),
                'jsTimeout': (5, 120),
                'jsViewportWidth': (800, 4000),
                'jsViewportHeight': (600, 3000),
                'jsMaxConcurrentPages': (1, 10)
            }

            for key, (min_val, max_val) in numeric_validations.items():
                if key in settings:
                    value = settings[key]
                    if not isinstance(value, (int, float)) or value < min_val or value > max_val:
                        return False

            # Validate string fields are not empty where required
            required_strings = ['userAgent']
            for key in required_strings:
                if key in settings and not settings[key].strip():
                    return False

            # Validate export fields is a list
            if 'exportFields' in settings and not isinstance(settings['exportFields'], list):
                return False

            # Validate proxy URL if proxy is enabled
            if settings.get('enableProxy') and settings.get('proxyUrl'):
                try:
                    from urllib.parse import urlparse
                    result = urlparse(settings['proxyUrl'])
                    if not all([result.scheme, result.netloc]):
                        return False
                except:
                    return False

            return True

        except Exception:
            return False

    def get_crawler_config(self):
        """Get settings formatted for the crawler"""
        settings = self.get_settings()

        return {
            'max_depth': settings['maxDepth'],
            'max_urls': settings['maxUrls'],
            'delay': settings['crawlDelay'],
            'follow_redirects': settings['followRedirects'],
            'crawl_external': settings['crawlExternalLinks'],
            'user_agent': settings['userAgent'],
            'timeout': settings['timeout'],
            'retries': settings['retries'],
            'accept_language': settings['acceptLanguage'],
            'respect_robots': settings['respectRobotsTxt'],
            'allow_cookies': settings['allowCookies'],
            'include_extensions': [ext.strip() for ext in settings['includeExtensions'].split(',') if ext.strip()],
            'exclude_extensions': [ext.strip() for ext in settings['excludeExtensions'].split(',') if ext.strip()],
            'include_patterns': [p.strip() for p in settings['includePatterns'].split('\n') if p.strip()],
            'exclude_patterns': [p.strip() for p in settings['excludePatterns'].split('\n') if p.strip()],
            'max_file_size': settings['maxFileSize'] * 1024 * 1024,  # Convert MB to bytes
            'concurrency': settings['concurrency'],
            'memory_limit': settings['memoryLimit'] * 1024 * 1024,  # Convert MB to bytes
            'log_level': settings['logLevel'],
            'enable_proxy': settings['enableProxy'],
            'proxy_url': settings['proxyUrl'] if settings['enableProxy'] else None,
            'custom_headers': self._parse_custom_headers(settings['customHeaders']),
            'discover_sitemaps': settings['discoverSitemaps'],
            'enable_pagespeed': settings['enablePageSpeed'],
            'google_api_key': settings['googleApiKey'],
            'enable_javascript': settings['enableJavaScript'],
            'js_wait_time': settings['jsWaitTime'],
            'js_timeout': settings['jsTimeout'],
            'js_browser': settings['jsBrowser'],
            'js_headless': settings['jsHeadless'],
            'js_user_agent': settings['jsUserAgent'],
            'js_viewport_width': settings['jsViewportWidth'],
            'js_viewport_height': settings['jsViewportHeight'],
            'js_max_concurrent_pages': settings['jsMaxConcurrentPages'],
            'issue_exclusion_patterns': [p.strip() for p in settings['issueExclusionPatterns'].split('\n') if p.strip()]
        }

    def _parse_custom_headers(self, headers_text):
        """Parse custom headers from text format"""
        headers = {}
        if headers_text:
            for line in headers_text.split('\n'):
                line = line.strip()
                if ':' in line:
                    key, value = line.split(':', 1)
                    headers[key.strip()] = value.strip()
        return headers

    def export_settings(self, file_path):
        """Export settings to a file"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.current_settings, f, indent=2, ensure_ascii=False)
            return True, "Settings exported successfully"
        except Exception as e:
            return False, f"Error exporting settings: {str(e)}"

    def import_settings(self, file_path):
        """Import settings from a file"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_settings = json.load(f)

            if self.validate_settings(imported_settings):
                return self.save_settings(imported_settings)
            else:
                return False, "Invalid settings file format"

        except Exception as e:
            return False, f"Error importing settings: {str(e)}"