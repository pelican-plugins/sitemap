# -*- coding: utf-8 -*-
"""
Sitemap
-------

The sitemap plugin generates plain-text or XML sitemaps.
"""
from datetime import datetime
import logging
import os.path
import re
from urllib.request import pathname2url

from pelican import contents, signals

log = logging.getLogger(__name__)

XML_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
xmlns:xhtml="http://www.w3.org/1999/xhtml"
xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

XML_URL = """
<url>
<loc>{0}/{1}</loc>
<lastmod>{2}</lastmod>
<changefreq>{3}</changefreq>
<priority>{4}</priority>
{translations}</url>
"""

XML_TRANSLATION = """<xhtml:link rel="alternate" hreflang="{}" ref="{}/{}"/>
"""

XML_FOOTER = """
</urlset>
"""


def format_date(date):
    if date.tzinfo:
        tz = date.strftime("%z")
        tz = tz[:-2] + ":" + tz[-2:]
    else:
        tz = "-00:00"
    return date.strftime("%Y-%m-%dT%H:%M:%S") + tz


class SitemapGenerator:
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

    def __init__(self):
        self.now = datetime.now()
        self.page_queue = []
        self._main_pelican = None

    def init(self, pelican):
        log.debug("sitemap: Initialize")
        if self._main_pelican is None:
            self._main_pelican = pelican

    def queue_page(self, path, context):
        obj = context.get("article") or context.get("page")
        self.page_queue.append((path, obj))

    def finalize(self, pelican):
        # Wait for all i18n_subsites to finish
        # https://github.com/pelican-plugins/sitemap/pull/3#discussion_r436390684
        if pelican == self._main_pelican:
            self._write_out(pelican)
            # Reset for autoreload
            self._main_pelican = None
            self.page_queue = []

    def _write_out(self, pelican):
        output_path = pelican.output_path
        log.debug("sitemap: Writing sitemap to %r", output_path)
        context = pelican.settings
        siteurl = context["SITEURL"]
        config = context.get("SITEMAP", {})
        self._check_config(config)
        excluded = config.get("exclude", ())
        changefreqs = dict(self.CHANGEFREQ_DEFAULTS, **config.get("changefreqs", {}))
        priorities = dict(self.PRIORITY_DEFAULTS, **config.get("priorities", {}))
        fmt = config.get("format", "xml")
        is_xml = fmt == "xml"
        filename = os.path.join(output_path, "sitemap." + fmt)

        def to_url(path):
            nonlocal output_path
            return pathname2url(os.path.relpath(path, output_path))

        def clean_url(url):
            # Strip trailing 'index.html'
            return re.sub(r"(?:^|(?<=/))index.html$", "", url)

        def is_excluded(item):
            nonlocal excluded
            url, obj = item
            is_private = getattr(obj, "private", "") == "True"
            is_hidden = not getattr(obj, "status", "published") == "published"
            return (
                is_private
                or is_hidden
                or any(re.match(pattern, url) for pattern in excluded)
            )

        page_queue = [(clean_url(to_url(path)), obj) for path, obj in self.page_queue]
        page_queue = [page for page in page_queue if not is_excluded(page)]
        page_queue.sort(key=lambda i: i[0])

        with open(filename, "w", encoding="utf-8") as fd:
            if is_xml:
                fd.write(XML_HEADER)

            for pageurl, obj in page_queue:
                if not is_xml:
                    fd.write(siteurl + "/" + pageurl + "\n")
                    # That's it for txt. Short circuit the loop, gain an indent level.
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
                changefreq = changefreqs[content_type]
                priority = float(priorities[content_type])
                translations = "".join(
                    XML_TRANSLATION.format(
                        trans.lang,
                        siteurl,
                        # save_as path is already output-relative
                        clean_url(pathname2url(trans.save_as)),
                    )
                    for trans in getattr(obj, "translations", ())
                )

                fd.write(
                    XML_URL.format(
                        siteurl,
                        pageurl,
                        lastmod,
                        changefreq,
                        priority,
                        translations=translations,
                    )
                )

            if is_xml:
                fd.write(XML_FOOTER)

        log.info("sitemap: Written {!r}".format(filename))

    def _check_config(self, config):
        if not isinstance(config, dict):
            log.error("sitemap: The SITEMAP setting must be a dict")
        for key in config.keys():
            if key not in ("format", "exclude", "priorities", "changefreqs"):
                log.error("sitemap: Invalid 'SITEMAP' key: {!r}".format(key))
        changefreqs = config.get("changefreqs", {})
        for key, value in changefreqs.items():
            if key not in self.CHANGEFREQ_DEFAULTS:
                log.error("sitemap: Invalid 'changefreqs' key: {!r}".format(key))
            if value not in self.CHANGEFREQ_VALUES:
                log.error("sitemap: Invalid 'changefreqs' value: {!r}".format(value))
        for key, value in config.get("priorities", {}).items():
            if key not in self.PRIORITY_DEFAULTS:
                log.error("sitemap: Invalid 'priorities' key: {!r}".format(key))
        fmt = config.get("format")
        if fmt not in (None, "txt", "xml"):
            log.error(
                "sitemap: Invalid 'format' value: %r; " "must be 'txt' or 'xml'", fmt,
            )
        exclude = config.get("exclude", ())
        if not all(isinstance(i, str) for i in exclude):
            log.error(
                "sitemap: Invalid 'exclude' value: %r; " "must be a list of str",
                exclude,
            )


generator = SitemapGenerator()


def register():
    # We connect to get_generators (instead of e.g. initialized)
    # because i18n_subsites does, so the whole thing works with
    # pelican --autoreload
    signals.get_generators.connect(generator.init)
    signals.content_written.connect(generator.queue_page)
    signals.finalized.connect(generator.finalize)
