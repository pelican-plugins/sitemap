from pathlib import Path

from . import SitemapGenerator

BASE_DIR = Path(".").resolve()
TEST_DATA = BASE_DIR / "test_data"


def test_sitemap_generator(tmp_path):
    """Test the Sitemap generator."""
    SitemapGenerator()
