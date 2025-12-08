"""URL list parsing and validation utilities"""
import re
from urllib.parse import urlparse, urlunparse


def parse_url_list(text):
    """
    Parse URLs from text (one per line)
    
    Args:
        text: String containing URLs separated by newlines
        
    Returns:
        tuple: (valid_urls, invalid_urls)
            valid_urls: List of normalized valid URLs
            invalid_urls: List of invalid URL strings
    """
    if not text or not text.strip():
        return [], []
    
    lines = text.split('\n')
    valid_urls = []
    invalid_urls = []
    seen_urls = set()  # For deduplication
    
    for line in lines:
        # Strip whitespace
        line = line.strip()
        
        # Skip empty lines
        if not line:
            continue
        
        # Skip comments (lines starting with #)
        if line.startswith('#'):
            continue
        
        # Normalize and validate URL
        normalized = normalize_url(line)
        
        if validate_url(normalized):
            # Deduplicate
            if normalized not in seen_urls:
                valid_urls.append(normalized)
                seen_urls.add(normalized)
        else:
            invalid_urls.append(line)
    
    return valid_urls, invalid_urls


def validate_url(url):
    """
    Validate URL format
    
    Args:
        url: URL string to validate
        
    Returns:
        bool: True if valid, False otherwise
    """
    if not url or not isinstance(url, str):
        return False
    
    try:
        parsed = urlparse(url)
        
        # Must have scheme (http or https)
        if parsed.scheme not in ['http', 'https']:
            return False
        
        # Must have netloc (domain)
        if not parsed.netloc:
            return False
        
        # Basic domain validation (contains at least one dot or is localhost)
        if '.' not in parsed.netloc and parsed.netloc != 'localhost':
            return False
        
        return True
    except Exception:
        return False


def normalize_url(url):
    """
    Normalize URL (add scheme if missing, remove trailing slashes, etc.)
    
    Args:
        url: URL string to normalize
        
    Returns:
        str: Normalized URL
    """
    if not url or not isinstance(url, str):
        return url
    
    url = url.strip()
    
    # Add http:// if no scheme present
    if not url.startswith(('http://', 'https://')):
        # Check if it looks like a URL (contains a dot)
        if '.' in url or url.startswith('localhost'):
            url = 'http://' + url
    
    try:
        parsed = urlparse(url)
        
        # Remove trailing slash from path (except for root path)
        path = parsed.path
        if path and path != '/' and path.endswith('/'):
            path = path.rstrip('/')
        
        # Reconstruct URL
        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc.lower(),  # Lowercase domain
            path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))
        
        return normalized
    except Exception:
        return url


def parse_file_content(file_content):
    """
    Parse URLs from file content (bytes or string)
    
    Args:
        file_content: File content as bytes or string
        
    Returns:
        tuple: (valid_urls, invalid_urls)
    """
    # Convert bytes to string if needed
    if isinstance(file_content, bytes):
        try:
            text = file_content.decode('utf-8')
        except UnicodeDecodeError:
            # Try other encodings
            try:
                text = file_content.decode('latin-1')
            except Exception:
                return [], []
    else:
        text = file_content
    
    return parse_url_list(text)


def get_url_statistics(urls):
    """
    Get statistics about a list of URLs
    
    Args:
        urls: List of URLs
        
    Returns:
        dict: Statistics including total count, unique domains, etc.
    """
    if not urls:
        return {
            'total': 0,
            'unique_domains': 0,
            'domains': {}
        }
    
    domains = {}
    for url in urls:
        try:
            parsed = urlparse(url)
            domain = parsed.netloc
            domains[domain] = domains.get(domain, 0) + 1
        except Exception:
            pass
    
    return {
        'total': len(urls),
        'unique_domains': len(domains),
        'domains': domains
    }
