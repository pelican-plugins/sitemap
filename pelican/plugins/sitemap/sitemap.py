# -*- coding: utf-8 -*-
"""
Sitemap
-------

The sitemap plugin generates plain-text or XML sitemaps.
"""
import os.path
import re
from datetime import datetime
from logging import info, warning
from urllib.request import pathname2url

from pelican import contents, signals


XML_FILE_TEMPLATE = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
        xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
        xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{}
</urlset>
"""


XML_URL_TEMPLATE = """
<url>
<loc>{loc}</loc>
<lastmod>{lastmod}</lastmod>
<changefreq>{changefreq}</changefreq>
<priority>{priority}</priority>
</url>
"""


VALID_CHANGEFREQS = (
    "always",
    "hourly",
    "daily",
    "weekly",
    "monthly",
    "yearly",
    "never",
)


CHANGEFREQ_DEFAULTS = dict(
    articles='monthly',
    pages='monthly',
    indexes='daily',
)


PRIORITY_DEFAULTS = dict(
    articles=.5,
    pages=.5,
    indexes=.5,
)


def format_date(date):
    if date.tzinfo:
        tz = date.strftime("%z")
        tz = tz[:-2] + ":" + tz[-2:]
    else:
        tz = "-00:00"
    return date.strftime("%Y-%m-%dT%H:%M:%S") + tz


def _get_format(settings):
    fmt = settings.get("SITEMAP", {}).get('format', 'xml')
    assert fmt in ('txt', 'xml')
    return fmt


def content_written(path, context):
    rel_url = pathname2url(os.path.relpath(path, context['OUTPUT_PATH']))
    obj = context.get('article') or context.get('page')

    def is_excluded(url, obj):
        is_private = getattr(obj, 'private', '') in ('True', 'true', '1')
        is_hidden = not (getattr(obj, 'status', 'published') == 'published')
        excluded = context.get("SITEMAP", {}).get('exclude', ())
        return (is_private or is_hidden or
                any(re.match(pattern, url) for pattern in excluded))

    if is_excluded(rel_url, obj):
        return

    abs_url = context['SITEURL'] + '/' + rel_url
    if abs_url.endswith('/index.html'):
        abs_url = abs_url[:-len('index.html')]

    fmt = _get_format(context)
    filename = os.path.join(context['OUTPUT_PATH'], "sitemap." + fmt)

    with open(filename, 'a') as file:
        if fmt == 'txt':
            file.write(abs_url + '\n')

        elif fmt == 'xml':
            lastmod = (getattr(obj, 'modified', None) or
                       getattr(obj, 'date', None) or
                       datetime.combine(datetime.now(), datetime.min.time()))
            content_type = {contents.Article: 'articles',
                            contents.Page: 'pages'}.get(type(obj), 'indexes')
            print(type(obj), obj)
            changefreq = (context.get('SITEMAP', {})
                          .get('changefreqs', {})
                          .get(content_type,
                               CHANGEFREQ_DEFAULTS[content_type]))
            assert changefreq in VALID_CHANGEFREQS
            priority = float(context.get('SITEMAP', {})
                             .get('priorities', {})
                             .get(content_type,
                                  PRIORITY_DEFAULTS[content_type]))
            file.write(XML_URL_TEMPLATE.format(loc=abs_url,
                                               lastmod=format_date(lastmod),
                                               changefreq=changefreq,
                                               priority=priority))


def _check_config(settings):
    config = settings.get('SITEMAP', {})
    for key in config.keys():
        if key not in ('format', 'exclude', 'priorities', 'changefreqs'):
            warning("sitemap: Invalid 'SITEMAP' key: {!r}".format(key))
    for key in config.get('changefreqs', {}).keys():
        if key not in CHANGEFREQ_DEFAULTS:
            warning("sitemap: Invalid 'changefreqs' key: {!r}".format(key))
    for key in config.get('priorities', {}).keys():
        if key not in PRIORITY_DEFAULTS:
            warning("sitemap: Invalid 'priorities' key: {!r}".format(key))


def initialize(pelican):
    _check_config(pelican.settings)
    fmt = _get_format(pelican.settings)
    filename = os.path.join(pelican.output_path, "sitemap." + fmt)
    with open(filename, 'w') as f:
        f.truncate()


def finalize(pelican):
    fmt = _get_format(pelican.settings)
    filename = os.path.join(pelican.output_path, "sitemap." + fmt)
    if fmt == 'xml':
        with open(filename, 'r+') as f:
            contents = f.read()
            f.seek(0)
            f.truncate()
            f.write(XML_FILE_TEMPLATE.format(contents))
    info("sitemap: written {!r}".format(filename))


def register():
    signals.content_written.connect(content_written)
    signals.initialized.connect(initialize)
    signals.finalized.connect(finalize)
