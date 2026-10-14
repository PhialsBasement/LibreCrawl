"""Regression tests for HTTP response and processing time."""

import unittest
from datetime import timedelta
from unittest.mock import Mock, patch

from src.crawler import WebCrawler


class ResponseTimingTests(unittest.TestCase):

    def make_crawler(self, response):
        crawler = WebCrawler.__new__(WebCrawler)

        crawler.config = {
            'retries': 0,
            'max_file_size': 0,
            'timeout': 10,
            'follow_redirects': True,
            'max_depth': 0,
            'crawl_external': False,
            'crawl_images': False,
        }

        crawler.session = Mock()
        crawler.session.get.return_value = response

        crawler.link_manager = Mock()
        crawler.link_manager.is_internal.return_value = True
        crawler.link_manager.get_source_pages.return_value = []

        crawler.seo_extractor = Mock()
        crawler.seo_extractor.create_empty_result.side_effect = (
            lambda *args, **kwargs: {
                'url': args[0],
                'status_code': 0,
                'error': str(args[3]) if len(args) > 3 else ''
            }
        )

        return crawler

    def make_response(self, elapsed_ms, redirects=None):
        response = Mock()
        response.status_code = 200
        response.url = 'https://example.com/'
        response.headers = {'content-type': 'text/plain'}
        response.content = b'Example'
        response.history = redirects or []
        response.elapsed = timedelta(milliseconds=elapsed_ms)
        return response

    def test_standard_response(self):
        crawler = self.make_crawler(self.make_response(125))

        result = crawler._crawl_url_with_requests(
            'https://example.com/', 0
        )

        self.assertEqual(result['status_code'], 200)
        self.assertEqual(result['response_time'], 125)
        self.assertGreaterEqual(result['processing_time'], 0)

    def test_redirect_chain(self):
        redirect1 = Mock(elapsed=timedelta(milliseconds=80))
        redirect2 = Mock(elapsed=timedelta(milliseconds=120))

        crawler = self.make_crawler(
            self.make_response(150, [redirect1, redirect2])
        )

        result = crawler._crawl_url_with_requests(
            'https://example.com/', 0
        )

        self.assertEqual(result['response_time'], 350)

    def test_processing_time_independent(self):
        crawler = self.make_crawler(self.make_response(45))

        original_get = crawler.session.get

        def slow_get(*args, **kwargs):
            import time
            time.sleep(0.05)
            return original_get.return_value

        crawler.session.get.side_effect = slow_get

        result = crawler._crawl_url_with_requests(
            'https://example.com/', 0
        )

        self.assertEqual(result['response_time'], 45)
        self.assertGreaterEqual(result['processing_time'], 40)


if __name__ == '__main__':
    unittest.main()
