"""Offline tests for the APOD to Overflight wallpaper list generator.

Run: python3 -m unittest discover -s tests -v
"""

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir))

import apod_wallpapers as aw  # noqa: E402

FIXTURE = os.path.join(HERE, "fixtures", "apod-basic-page.json")


def page():
    with open(FIXTURE) as f:
        return json.load(f)


def post(date, *, html="", hdurl="", media_type="image", copyright="", credit=""):
    return {
        "date": date,
        "title": f"APOD {date}",
        "media_type": media_type,
        "basic_html": html,
        "hdurl": hdurl,
        "url": "https://science.nasa.gov/image-article/apod-x/",
        "copyright": copyright,
        "credit": credit,
    }


DAM = "https://assets.science.nasa.gov/content/dam/science/cds/apod/2026/november/x.jpg"
HTML_WITH_IMG = f'<html><img src="{DAM}" /></html>'
MISSIONS = "https://assets.science.nasa.gov/dynamicimage/assets/science/missions/webb/2026/10/x.jpg"


class TestImageExtraction(unittest.TestCase):
    def test_hdurl_is_primary(self):
        p = post("2026-11-01", html=HTML_WITH_IMG, hdurl=MISSIONS)
        self.assertEqual(aw.pick_image(p), MISSIONS)

    def test_hdurl_query_stripped(self):
        p = post("2026-11-02", hdurl=DAM + "?w=1008&h=861&fit=clip")
        self.assertEqual(aw.pick_image(p), DAM)

    def test_hdurl_placeholder_rejected(self):
        p = post(
            "1995-06-20",
            html=HTML_WITH_IMG,
            hdurl="https://assets.science.nasa.gov/dynamicimage/a/news-thumbnail.png?w=594",
        )
        self.assertEqual(aw.pick_image(p), DAM)

    def test_html_fallback_when_hdurl_empty(self):
        p = post("2026-11-03", html=HTML_WITH_IMG)
        self.assertEqual(aw.pick_image(p), DAM)

    def test_missions_subtree_flows_through(self):
        # Regression: images outside science/cds/apod/ must still resolve and resize.
        p = post("2026-11-11", html="<p>no image here</p>", hdurl=MISSIONS)
        self.assertEqual(aw.pick_image(p), MISSIONS)
        self.assertEqual(aw.resize_image(aw.pick_image(p), 1920), MISSIONS + "?w=1920")

    def test_skips_video_and_iframe(self):
        for mt in ("video", "iframe"):
            self.assertIsNone(aw.pick_image(post("2026-11-04", html=HTML_WITH_IMG, media_type=mt)))

    def test_skips_posts_without_image(self):
        self.assertIsNone(aw.pick_image(post("2026-11-05")))


class TestResize(unittest.TestCase):
    def test_resize_rewrites_host(self):
        self.assertEqual(
            aw.resize_image(DAM, 1920),
            "https://assets.science.nasa.gov/dynamicimage/assets/science/cds/apod/2026/november/x.jpg?w=1920",
        )

    def test_resize_strips_existing_query(self):
        capped = DAM + "?w=1008&h=861&fit=clip"
        out = aw.resize_image(capped, 1920)
        self.assertEqual(out.count("?"), 1)
        self.assertTrue(out.endswith("?w=1920"))

    def test_resize_keeps_absolute_non_cdn_url(self):
        other = "https://example.org/pic.jpg"
        self.assertEqual(aw.resize_image(other, 1920), other)


class TestBuildEntries(unittest.TestCase):
    def setUp(self):
        self.posts = page()

    def test_output_schema(self):
        entries = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="t")
        self.assertTrue(entries)
        for e in entries:
            self.assertEqual(set(e), {"location", "title", "author", "url_img"})
            self.assertTrue(e["url_img"].startswith("https://"))
            self.assertTrue(e["url_img"].endswith("?w=1920"))
            self.assertEqual(e["location"], aw.LOCATION)

    def test_output_capped_at_100(self):
        many = [post(f"2025-{1 + i // 28:02d}-{1 + i % 28:02d}", html=HTML_WITH_IMG) for i in range(300)]
        entries = aw.build_entries(many, width=1920, count=100, newest_count=7, seed="t")
        self.assertEqual(len(entries), 100)

    def test_newest_seven_included(self):
        entries = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="t")
        newest = [p["title"] for p in self.posts if p["media_type"] == "image"][:7]
        got = [e["title"] for e in entries]
        for title in newest:
            self.assertIn(title, got)

    def test_no_duplicate_dates(self):
        entries = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="t")
        titles = [e["title"] for e in entries]
        self.assertEqual(len(titles), len(set(titles)))

    def test_seed_reproducible(self):
        a = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="2026-11-23")
        b = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="2026-11-23")
        self.assertEqual(a, b)

    def test_author_markup_stripped(self):
        posts = [
            post(
                "2026-11-11",
                html=HTML_WITH_IMG,
                copyright='<a href="https://x.test">David Cruz</a>',
            ),
            post(
                "2026-11-05",
                html=HTML_WITH_IMG,
                copyright='<a href="https://nasa.gov">NASA</a>, <a href="https://esa.int">ESA</a>',
            ),
        ]
        entries = aw.build_entries(posts, width=1920, count=100, newest_count=2, seed="t")
        authors = [e["author"] for e in entries]
        self.assertEqual(authors[0], "David Cruz")
        self.assertEqual(authors[1], "NASA, ESA")
        for a in authors:
            self.assertNotIn("<", a)

    def test_author_fallback(self):
        posts = [
            post("2026-11-10", html=HTML_WITH_IMG, copyright="Jane Doe"),
            post("2026-11-09", html=HTML_WITH_IMG, credit="NASA/JPL"),
            post("2026-11-08", html=HTML_WITH_IMG),
        ]
        entries = aw.build_entries(posts, width=1920, count=100, newest_count=3, seed="t")
        authors = {e["title"]: e["author"] for e in entries}
        self.assertEqual(authors["APOD 2026-11-10"], "Jane Doe")
        self.assertEqual(authors["APOD 2026-11-09"], "NASA/JPL")
        self.assertEqual(authors["APOD 2026-11-08"], "")

    def test_json_parses_as_plugin_media(self):
        entries = aw.build_entries(self.posts, width=1920, count=100, newest_count=7, seed="t")
        text = json.dumps(entries)
        back = json.loads(text)
        self.assertIsInstance(back, list)
        self.assertTrue(all(isinstance(x, dict) for x in back))


if __name__ == "__main__":
    unittest.main()
