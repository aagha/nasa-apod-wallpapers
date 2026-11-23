"""Opt-in live checks against science.nasa.gov. Skipped unless APOD_LIVE=1.

    APOD_LIVE=1 python3 -m unittest tests.test_live -v
"""

import os
import sys
import unittest
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))

import apod_wallpapers as aw  # noqa: E402

LIVE = os.environ.get("APOD_LIVE") == "1"


@unittest.skipUnless(LIVE, "set APOD_LIVE=1 to run live checks")
class TestLive(unittest.TestCase):
    def test_live_fetch_recent(self):
        posts = aw.fetch_posts(pages=1)
        self.assertEqual(len(posts), aw.PER_PAGE)
        self.assertGreaterEqual(len([p for p in posts if p.get("date")]), aw.PER_PAGE - 1)

    def test_live_images_head_ok(self):
        entries = aw.build_entries(aw.fetch_posts(pages=2), width=1920, count=10, newest_count=7)
        self.assertTrue(entries)
        for e in entries[:10]:
            req = urllib.request.Request(e["url_img"], method="HEAD")
            with urllib.request.urlopen(req, timeout=30) as resp:
                self.assertEqual(resp.status, 200)
                self.assertTrue(resp.headers["Content-Type"].startswith("image/"), e["url_img"])

    def test_live_oldest_boundary(self):
        def count(date_to):
            url = f"{aw.BASE}?per_page=25&date_from=950101&date_to={date_to}"
            return len(aw.fetch_json(url))

        self.assertEqual(count("950615"), 0)
        self.assertGreaterEqual(count("950616"), 1)


if __name__ == "__main__":
    unittest.main()
