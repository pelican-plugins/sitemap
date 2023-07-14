from pathlib import Path

from pelican.tests.support import get_context, get_settings

from . import SitemapGenerator

BASE_DIR = Path(".").resolve()
TEST_DATA = BASE_DIR / "test_data"


def test_sitemap_generator(tmp_path):
    """Test the Sitemap generator."""

    generator = SitemapGenerator()
