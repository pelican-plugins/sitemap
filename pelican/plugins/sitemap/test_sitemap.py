from pathlib import Path

from pelican.tests.support import get_context, get_settings

from . import SitemapGenerator

BASE_DIR = Path(".").resolve()
TEST_DATA = BASE_DIR / "test_data"


def test_sitemap_generator(tmp_path):
    """Test the Sitemap generator."""
    settings = get_settings()
    context = get_context(settings)
    theme = settings["THEME"]

    sitemap = SitemapGenerator(context, settings, TEST_DATA, theme, tmp_path)

    default_format = "xml"
    default_priorities = {"articles": 0.5, "indexes": 0.5, "pages": 0.5}

    assert sitemap.format == default_format
    assert sitemap.priorities == default_priorities
