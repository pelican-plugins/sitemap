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
                "PATH": BASE_DIR,
                "CACHE_CONTENT": False,
                "SITEURL": "http://localhost",
                "CONTENT": TEST_DATA,
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
http://localhost/tag/bar.html
http://localhost/tag/foo.html
http://localhost/tag/foobar.html
http://localhost/tags.html
http://localhost/test-post-daily.html
http://localhost/test-post.html
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
