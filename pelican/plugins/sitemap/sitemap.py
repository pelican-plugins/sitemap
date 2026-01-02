"""The Sitemap plugin generates plain-text or XML sitemaps."""

from datetime import datetime
import logging
import os.path
import posixpath
import re
from urllib.parse import urlparse, urlunparse
from urllib.request import pathname2url

from pelican import contents, signals

log = logging.getLogger(__name__)

XML_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
xmlns:xhtml="http://www.w3.org/1999/xhtml"
xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

TXT_URL = "{0}\n"

XML_URL = """<url>
<loc>{0}</loc>
<lastmod>{1}</lastmod>
<changefreq>{2}</changefreq>
<priority>{3}</priority>
{4}</url>
"""

XML_TRANSLATION = """<xhtml:link rel="alternate" hreflang="{0}" href="{1}"/>"""

XML_FOOTER = """
</urlset>
"""


def format_date(date):
    """Format the date in the expected format."""
    if date.tzinfo:
        tz = date.strftime("%z")
        tz = tz[:-2] + ":" + tz[-2:]
    else:
        tz = "-00:00"
    return date.strftime("%Y-%m-%dT%H:%M:%S") + tz


CHANGEFREQ_DEFAULTS = {
    "articles": "monthly",
    "pages": "monthly",
    "indexes": "daily",
}
PRIORITY_DEFAULTS = {
    "articles": 0.5,
    "pages": 0.5,
    "indexes": 0.5,
}
CHANGEFREQ_VALUES = {
    "always",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "yearly",
    "never",
}


class SitemapGenerator:
    """Sitemap generator class."""

    def __init__(self):
        """Initialize the sitemap generator."""
        self.now = datetime.now()
        self.page_queue = []
        self._main_pelican = None
        self._main_siteurl = None
        self._main_lang = None

    def init(self, pelican):
        """Initialize the plugin."""
        log.debug("sitemap: Initialize")
        if self._main_pelican is None:
            self._main_pelican = pelican
            self._main_siteurl = pelican.settings.get("SITEURL", "")
            self._main_lang = pelican.settings.get("DEFAULT_LANG", "en")

    def queue_page(self, path, context):
        """Queue one site page for later generation."""
        obj = context.get("article") or context.get("page")
        # Store the current language context along with the page
        current_lang = context.get("DEFAULT_LANG", self._main_lang)
        current_siteurl = context.get("SITEURL", self._main_siteurl)
        self.page_queue.append((path, obj, current_lang, current_siteurl))

    def finalize(self, pelican):
        """Write the sitemap of queued pages."""
        # Wait for all i18n_subsites to finish
        # https://github.com/pelican-plugins/sitemap/pull/3#discussion_r436390684
        if pelican == self._main_pelican:
            self._write_out(pelican)
            # Reset for autoreload
            self._main_pelican = None
            self._main_siteurl = None
            self._main_lang = None
            self.page_queue = []

    def _write_out(self, pelican):
        output_path = pelican.output_path
        log.debug("sitemap: Writing sitemap to %r", output_path)
        context = pelican.settings
        siteurl = context["SITEURL"]
        config = context.get("SITEMAP", {})
        self._check_config(config)
        excluded = config.get("exclude", ())
        changefreqs = dict(CHANGEFREQ_DEFAULTS, **config.get("changefreqs", {}))
        priorities = dict(PRIORITY_DEFAULTS, **config.get("priorities", {}))
        fmt = config.get("format", "xml")
        is_xml = fmt == "xml"
        filename = os.path.join(output_path, "sitemap." + fmt)

        def to_url(path):
            nonlocal output_path
            return pathname2url(os.path.relpath(path, output_path))

        def clean_url(url):
            # Strip trailing 'index.html'
            return re.sub(r"(?:^|(?<=/))index.html$", "", url)

        def is_excluded(url, obj):
            nonlocal excluded
            is_private = getattr(obj, "private", "") == "True"
            is_hidden = getattr(obj, "status", "published") != "published"
            return (
                is_private
                or is_hidden
                or any(re.search(pattern, url) for pattern in excluded)
            )

        def get_full_url(page_siteurl, page_url, is_index=False):
            """Build full URL and normalize any ../ segments."""
            if page_url.startswith("http"):
                return page_url
            base = siteurl if is_index else page_siteurl
            full = "{0}/{1}".format(base.rstrip("/"), page_url.lstrip("/"))
            # Normalize path using posixpath (handles ../ segments)
            parsed = urlparse(full)
            normalized = posixpath.normpath(parsed.path)
            # Restore trailing slash if original had one
            if parsed.path.endswith("/") and not normalized.endswith("/"):
                normalized += "/"
            return urlunparse(parsed._replace(path=normalized))

        def add_to_url_map(url_map, slug_translations, path, obj, lang, page_siteurl):
            """Add a page to the URL map and track slug translations."""
            if obj is None:
                # Index pages - no translations
                page_url = clean_url(to_url(path))
                if any(re.search(pattern, page_url) for pattern in excluded):
                    return
                full_url = get_full_url(page_siteurl, page_url, is_index=True)
                if full_url not in url_map:
                    url_map[full_url] = {"obj": None, "slug": None, "translations": {}}
                return

            # Articles and pages
            page_url = clean_url(obj.url)
            if is_excluded(page_url, obj):
                return
            full_url = get_full_url(page_siteurl, page_url)
            slug = getattr(obj, "slug", None)
            obj_lang = getattr(obj, "lang", lang)
            if full_url not in url_map:
                url_map[full_url] = {"obj": obj, "slug": slug, "translations": {}}
            # Group by slug for i18n_subsites
            if slug:
                slug_translations.setdefault(slug, {})[obj_lang] = full_url

        def link_translations(url_map, slug_translations):
            """Link translations to each URL entry."""
            for full_url, data in url_map.items():
                obj = data["obj"]
                slug = data["slug"]
                translations = {}
                # Add translations from slug grouping (i18n_subsites)
                if slug in slug_translations:
                    translations.update(slug_translations[slug])
                # Add translations from Pelican's native translation mechanism
                if obj is not None:
                    obj_lang = getattr(obj, "lang", None)
                    if obj_lang:
                        translations[obj_lang] = full_url
                    for trans in getattr(obj, "translations", []):
                        trans_lang = getattr(trans, "lang", None)
                        trans_url = clean_url(trans.url)
                        if trans_lang and trans_url:
                            translations[trans_lang] = get_full_url(siteurl, trans_url)
                data["translations"] = translations

        # Build URL map and group translations by slug
        url_map = {}  # full_url -> {obj, slug, translations}
        slug_translations = {}  # slug -> {lang: full_url}

        for path, obj, lang, page_siteurl in self.page_queue:
            add_to_url_map(url_map, slug_translations, path, obj, lang, page_siteurl)

        link_translations(url_map, slug_translations)

        def format_hreflang(translations):
            if len(translations) <= 1:
                return ""
            lines = []
            for lang, url in sorted(translations.items()):
                lines.append(XML_TRANSLATION.format(lang, url))
            return "\n".join(lines)

        with open(filename, "w", encoding="utf-8") as fd:
            if is_xml:
                fd.write(XML_HEADER)

            for full_url in sorted(url_map.keys()):
                data = url_map[full_url]
                obj = data["obj"]

                if not is_xml:
                    fd.write(full_url + "\n")
                    continue

                lastmod = format_date(
                    getattr(obj, "modified", None)
                    or getattr(obj, "date", None)
                    or self.now
                )
                content_type = (
                    "articles"
                    if isinstance(obj, contents.Article)
                    else "pages"
                    if isinstance(obj, contents.Page)
                    else "indexes"
                )

                # see if changefreq specified in metadata headers; fall back to config
                changefreq = getattr(obj, "changefreq", changefreqs[content_type]) if obj else changefreqs[content_type]
                if changefreq not in CHANGEFREQ_VALUES:
                    log.error(f"sitemap: Invalid 'changefreqs' value: {changefreq!r}")
                    changefreq = changefreqs[content_type]

                # see if priority specified in metadata headers; fall back to config
                priority_raw = getattr(obj, "priority", priorities[content_type]) if obj else priorities[content_type]
                try:
                    priority = float(priority_raw)
                except ValueError:
                    log.exception(
                        f"sitemap: Specify priority as a floating-point number, "
                        f"not the current value: {priority_raw!r}"
                    )
                    priority = priorities[content_type]

                hreflang = format_hreflang(data["translations"])

                fd.write(XML_URL.format(
                    full_url, lastmod, changefreq, priority, hreflang
                ))

            if is_xml:
                fd.write(XML_FOOTER)

        log.info(f"sitemap: Written {filename!r}")

    def _check_config(self, config):
        if not isinstance(config, dict):
            log.error("sitemap: The SITEMAP setting must be a dict")
        for key in config:
            if key not in ("format", "exclude", "priorities", "changefreqs"):
                log.error(f"sitemap: Invalid 'SITEMAP' key: {key!r}")
        changefreqs = config.get("changefreqs", {})
        for key, value in changefreqs.items():
            if key not in CHANGEFREQ_DEFAULTS:
                log.error(f"sitemap: Invalid 'changefreqs' key: {key!r}")
            if value not in CHANGEFREQ_VALUES:
                log.error(f"sitemap: Invalid 'changefreqs' value: {value!r}")
        for key, value in config.get("priorities", {}).items():
            if key not in PRIORITY_DEFAULTS:
                log.error(f"sitemap: Invalid 'priorities' key: {key!r}")
            if not isinstance(value, float):
                log.error(f"sitemap: Require numeric priority. Got: {value!r}")
        fmt = config.get("format")
        if fmt not in (None, "txt", "xml"):
            log.error(
                "sitemap: Invalid 'format' value: %r; should be 'txt' or 'xml'",
                fmt,
            )
        exclude = config.get("exclude", ())
        if not all(isinstance(i, str) for i in exclude):
            log.error(
                "sitemap: Invalid 'exclude' value: %r; must be a list of str",
                exclude,
            )


generator = SitemapGenerator()


def register():
    """Register the plugin callbacks."""
    # We connect to get_generators (instead of e.g. initialized)
    # because i18n_subsites does, so the whole thing works with
    # pelican --autoreload
    signals.get_generators.connect(generator.init)
    signals.content_written.connect(generator.queue_page)
    signals.finalized.connect(generator.finalize)
