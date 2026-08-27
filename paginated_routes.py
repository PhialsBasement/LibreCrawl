"""Paginated crawl-serve routes for LibreCrawl.

Adds bounded-memory endpoints that serve crawled URLs and links one page at a
time. The single-shot GET /api/crawls/<id> loads every url + link + issue and
jsonifies the whole payload before responding, which spikes past 8GB and OOM
kills the crawler for large crawls (15k+ pages). These routes only ever load
and serialize `limit` rows per request.

The row dicts returned here come from the same src.crawl_db loaders that
GET /api/crawls/<id> uses, so the shapes are byte-identical from the API's
point of view. Registered onto the Flask app by main.py right before serve()
is called (see the Dockerfile patch).
"""
import sys

from flask import jsonify, request

DEFAULT_PAGE_LIMIT = 500
MAX_PAGE_LIMIT = 2000
MIN_PAGE_LIMIT = 1


def _resolve_login_required():
    """Reuse main.py's login_required decorator so auth stays identical.

    register() runs from main.py right before serve(), by which point the
    decorator is already defined on the running __main__ module. Reusing it
    (instead of re-implementing the session / local-mode logic) guarantees
    these routes authenticate exactly like the other /api/crawls routes.
    """
    main_module = sys.modules.get('__main__')
    login_required = getattr(main_module, 'login_required', None)
    if login_required is None:
        raise RuntimeError(
            'paginated_routes.register: login_required not found on __main__; '
            'register(app) must be called from main.py after login_required is defined'
        )
    return login_required


def _clamp_limit(raw):
    """Force limit into [MIN, MAX]. Never 0/None — a falsy limit makes the
    src.crawl_db loaders skip pagination and return the whole table."""
    if raw is None:
        return DEFAULT_PAGE_LIMIT
    if raw < MIN_PAGE_LIMIT:
        return MIN_PAGE_LIMIT
    if raw > MAX_PAGE_LIMIT:
        return MAX_PAGE_LIMIT
    return raw


def _clamp_offset(raw):
    if raw is None or raw < 0:
        return 0
    return raw


def register(app):
    """Add the paginated crawl-serve routes to the Flask app."""
    login_required = _resolve_login_required()

    @app.route('/api/crawls/<int:crawl_id>/urls')
    @login_required
    def get_crawl_urls_paginated(crawl_id):
        """Serve one bounded page of crawled URLs."""
        try:
            from src.crawl_db import load_crawled_urls

            limit = _clamp_limit(request.args.get('limit', type=int))
            offset = _clamp_offset(request.args.get('offset', type=int))
            urls = load_crawled_urls(crawl_id, limit, offset)

            return jsonify({
                'success': True,
                'urls': urls,
                'offset': offset,
                'limit': limit,
                'count': len(urls)
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500

    @app.route('/api/crawls/<int:crawl_id>/links')
    @login_required
    def get_crawl_links_paginated(crawl_id):
        """Serve one bounded page of crawl links."""
        try:
            from src.crawl_db import load_crawl_links

            limit = _clamp_limit(request.args.get('limit', type=int))
            offset = _clamp_offset(request.args.get('offset', type=int))
            links = load_crawl_links(crawl_id, limit, offset)

            return jsonify({
                'success': True,
                'links': links,
                'offset': offset,
                'limit': limit,
                'count': len(links)
            })
        except Exception as e:
            import traceback
            traceback.print_exc()
            return jsonify({'success': False, 'error': str(e)}), 500
