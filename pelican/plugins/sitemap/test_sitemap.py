import importlib.resources
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp
import unittest

from pelican import Pelican
from pelican.settings import read_settings

from . import sitemap

BASE_DIR = importlib.resources.files(__package__)
TEST_DATA = BASE_DIR / "test_data"


class TestSitemap(unittest.TestCase):
    """Test class for Sitemap plugin."""

    def setUp(self):
        self.output_path = mkdtemp(prefix="pelican-plugins-sitemap-tests-")

    def tearDown(self):
        rmtree(self.output_path)

    def _run_pelican(self, sitemap_format):
        settings = read_settings(
            override={
                "PATH": TEST_DATA,
                "CACHE_CONTENT": False,
                "SITEURL": "http://localhost",
                "OUTPUT_PATH": self.output_path,
                "PLUGINS": [sitemap],
                "SITEMAP": {
                    "format": sitemap_format,
                },
            }
        )
        pelican = Pelican(settings=settings)
        pelican.run()

    def test_txt(self):
        self._run_pelican(sitemap_format="txt")
        with open(Path(self.output_path) / "sitemap.txt") as fd:
            contents = fd.read()
        expected = """\
http://localhost/
http://localhost/archives.html
http://localhost/authors.html
http://localhost/categories.html
http://localhost/category/test.html
http://localhost/pages/about-us.html
http://localhost/tag/bar.html
http://localhost/tag/foo.html
http://localhost/tag/foobar.html
http://localhost/tags.html
http://localhost/test-post-daily.html
http://localhost/test-post.html
http://localhost/translated-post-fr.html
http://localhost/translated-post.html
"""
        self.assertEqual(expected, contents)

    def test_xml(self):
        self._run_pelican(sitemap_format="xml")
        with open(Path(self.output_path) / "sitemap.xml") as fd:
            contents = fd.read()
        needle = """\
<url>
<loc>http://localhost/test-post.html</loc>
<lastmod>2023-07-12T13:00:00+00:00</lastmod>
<changefreq>monthly</changefreq>
<priority>0.5</priority>
</url>
"""
        self.assertIn(needle, contents)

        needle = """\
<url>
<loc>http://localhost/test-post-daily.html</loc>
<lastmod>2023-07-12T13:00:00+00:00</lastmod>
<changefreq>daily</changefreq>
<priority>0.3</priority>
</url>
"""
        self.assertIn(needle, contents)

    def test_custom_article_url(self):
        """Test that custom ARTICLE_URL settings are respected in sitemap."""
        settings = read_settings(
            override={
                "PATH": TEST_DATA,
                "CACHE_CONTENT": False,
                "SITEURL": "http://localhost",
                "OUTPUT_PATH": self.output_path,
                "PLUGINS": [sitemap],
                "SITEMAP": {
                    "format": "txt",
                },
                # Custom URL settings like a user might have
                "ARTICLE_URL": "blog/{slug}/",
                "ARTICLE_SAVE_AS": "{slug}/index.html",
            }
        )
        pelican = Pelican(settings=settings)
        pelican.run()

        with open(Path(self.output_path) / "sitemap.txt") as fd:
            contents = fd.read()

        # Articles should use ARTICLE_URL (blog/{slug}/),
        # not ARTICLE_SAVE_AS ({slug}/index.html)
        self.assertIn("http://localhost/blog/test-post/", contents)
        self.assertIn("http://localhost/blog/test-post-daily/", contents)
        # Should NOT contain the filesystem paths
        self.assertNotIn("http://localhost/test-post/", contents)
        self.assertNotIn("http://localhost/test-post-daily/", contents)

    def test_translations_in_sitemap(self):
        """Test that translation links use trans.url and appear in sitemap."""
        self._run_pelican(sitemap_format="xml")
        with open(Path(self.output_path) / "sitemap.xml") as fd:
            contents = fd.read()

        # Verify translation alternate links exist
        self.assertIn('<xhtml:link rel="alternate"', contents)
        # Verify they reference the correct translated article URLs
        self.assertIn('hreflang="en"', contents)
        self.assertIn('hreflang="fr"', contents)
        # Verify translated articles are in the sitemap
        self.assertIn("http://localhost/translated-post.html", contents)
        self.assertIn("http://localhost/translated-post-fr.html", contents)

    def test_translations_with_custom_article_url(self):
        """Test translation links respect custom ARTICLE_URL settings."""
        settings = read_settings(
            override={
                "PATH": TEST_DATA,
                "CACHE_CONTENT": False,
                "SITEURL": "http://localhost",
                "OUTPUT_PATH": self.output_path,
                "PLUGINS": [sitemap],
                "SITEMAP": {
                    "format": "xml",
                },
                # Custom URL settings
                "ARTICLE_URL": "blog/{slug}/",
                "ARTICLE_SAVE_AS": "{slug}/index.html",
            }
        )
        pelican = Pelican(settings=settings)
        pelican.run()

        with open(Path(self.output_path) / "sitemap.xml") as fd:
            contents = fd.read()

        # Verify translation link for English uses custom ARTICLE_URL
        self.assertIn('ref="http://localhost/blog/translated-post/"', contents)
        # Verify the French translation is also in sitemap
        # (French uses ARTICLE_LANG_URL which defaults differently)
        self.assertIn("translated-post-fr", contents)

    def test_custom_page_url(self):
        """Test that custom PAGE_URL settings are respected in sitemap."""
        settings = read_settings(
            override={
                "PATH": TEST_DATA,
                "CACHE_CONTENT": False,
                "SITEURL": "http://localhost",
                "OUTPUT_PATH": self.output_path,
                "PLUGINS": [sitemap],
                "SITEMAP": {
                    "format": "txt",
                },
                # Custom URL settings for pages
                "PAGE_URL": "pages/{slug}/",
                "PAGE_SAVE_AS": "p/{slug}/index.html",
            }
        )
        pelican = Pelican(settings=settings)
        pelican.run()

        with open(Path(self.output_path) / "sitemap.txt") as fd:
            contents = fd.read()

        # Pages should use PAGE_URL (pages/{slug}/),
        # not PAGE_SAVE_AS (p/{slug}/index.html)
        self.assertIn("http://localhost/pages/about-us/", contents)
        # Should NOT contain the filesystem path
        self.assertNotIn("http://localhost/p/about-us/", contents)
