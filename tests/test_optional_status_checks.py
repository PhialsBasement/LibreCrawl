"""Regression tests for optional resource status checks."""

import unittest
from unittest.mock import Mock

from src.crawler import WebCrawler


class OptionalStatusChecksTests(unittest.TestCase):

    def make_crawler(self, image_check=True, external_check=True):
        crawler = WebCrawler.__new__(WebCrawler)
        crawler.config = {
            'check_image_status': image_check,
            'check_external_links': external_check,
            'crawl_external': False,
        }
        crawler._head_check_links = Mock()
        return crawler

    def make_links(self):
        return [
            {
                'target_url': 'https://example.com/image.jpg',
                'placement': 'image',
                'is_internal': True,
                'target_status': None,
            },
            {
                'target_url': 'https://external.example.org/',
                'placement': 'content',
                'is_internal': False,
                'target_status': None,
            },
        ]

    def test_checks_disabled(self):
        crawler = self.make_crawler(False, False)
        crawler._head_check_new_links(self.make_links(), {}, 1)
        crawler._head_check_links.assert_not_called()

    def test_checks_enabled(self):
        crawler = self.make_crawler(True, True)
        crawler._head_check_new_links(self.make_links(), {}, 1)
        self.assertEqual(crawler._head_check_links.call_count, 2)

    def test_image_checks_only(self):
        crawler = self.make_crawler(True, False)
        crawler._head_check_new_links(self.make_links(), {}, 1)
        self.assertEqual(crawler._head_check_links.call_count, 1)
        self.assertEqual(
            crawler._head_check_links.call_args.args[0][0]['placement'],
            'image'
        )

    def test_external_checks_only(self):
        crawler = self.make_crawler(False, True)
        crawler._head_check_new_links(self.make_links(), {}, 1)
        self.assertEqual(crawler._head_check_links.call_count, 1)
        self.assertEqual(
            crawler._head_check_links.call_args.kwargs,
            {'link_check_only': True}
        )

    def test_legacy_defaults(self):
        crawler = self.make_crawler()
        del crawler.config['check_image_status']
        del crawler.config['check_external_links']
        crawler._head_check_new_links(self.make_links(), {}, 1)
        self.assertEqual(crawler._head_check_links.call_count, 2)


if __name__ == '__main__':
    unittest.main()
