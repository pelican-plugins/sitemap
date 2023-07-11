"""The Sitemap plugin generates plain-text or XML sitemaps."""


from codecs import open
import collections
from datetime import datetime
from logging import info, warning
import os.path
import re

from pytz import timezone

from pelican import contents, signals
from pelican.utils import get_date

TXT_HEADER = ""

XML_HEADER = """<?xml version="1.0" encoding="utf-8"?>
<urlset xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
xsi:schemaLocation="http://www.sitemaps.org/schemas/sitemap/0.9 http://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd"
xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
"""

TXT_URL = "{0}/{1}\n"

XML_URL = """
<url>
<loc>{0}/{1}</loc>
<lastmod>{2}</lastmod>
<changefreq>{3}</changefreq>
<priority>{4}</priority>
</url>
"""

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


class SitemapGenerator:
    """Sitemap generator class."""

    def __init__(self, context, settings, path, theme, output_path, *null):
        """Initialize the sitemap generator."""
        self.output_path = output_path
        self.context = context
        self.now = datetime.now()
        self.siteurl = settings.get("SITEURL")

        self.default_timezone = settings.get("TIMEZONE", "UTC")
        self.timezone = getattr(self, "timezone", self.default_timezone)
        self.timezone = timezone(self.timezone)

        self.format = "xml"

        self.changefreqs = {
            "articles": "monthly",
            "indexes": "daily",
            "pages": "monthly",
        }

        self.priorities = {"articles": 0.5, "indexes": 0.5, "pages": 0.5}

        self.sitemapExclude = []

        config = settings.get("SITEMAP", {})

        if not isinstance(config, dict):
            warning("sitemap plugin: the SITEMAP setting must be a dict")
        else:
            fmt = config.get("format")
            pris = config.get("priorities")
            chfreqs = config.get("changefreqs")
            self.sitemapExclude = [re.compile(x) for x in config.get("exclude", [])]

            if fmt not in ("xml", "txt"):
                warning("sitemap plugin: SITEMAP['format'] must be 'txt' or 'xml'")
                warning("sitemap plugin: Setting SITEMAP['format'] to 'xml'")
            elif fmt == "txt":
                self.format = fmt
                return

            valid_keys = ("articles", "indexes", "pages")
            valid_chfreqs = (
                "always",
                "hourly",
                "daily",
                "weekly",
                "monthly",
                "yearly",
                "never",
            )

            if isinstance(pris, dict):
                # We use items for Py3k compat. .iteritems() otherwise
                for k, v in pris.items():
                    if k in valid_keys and not isinstance(v, (int, float)):
                        default = self.priorities[k]
                        warning("sitemap plugin: priorities must be numbers")
                        warning(
                            "sitemap plugin: setting SITEMAP['priorities']"
                            "['{}'] on {}".format(k, default)
                        )
                        pris[k] = default
                self.priorities.update(pris)
            elif pris is not None:
                warning("sitemap plugin: SITEMAP['priorities'] must be a dict")
                warning("sitemap plugin: using the default values")

            if isinstance(chfreqs, dict):
                # .items() for py3k compat.
                for k, v in chfreqs.items():
                    if k in valid_keys and v not in valid_chfreqs:
                        default = self.changefreqs[k]
                        warning(f"sitemap plugin: invalid changefreq '{v}'")
                        warning(
                            "sitemap plugin: setting SITEMAP['changefreqs']"
                            "['{}'] on '{}'".format(k, default)
                        )
                        chfreqs[k] = default
                self.changefreqs.update(chfreqs)
            elif chfreqs is not None:
                warning("sitemap plugin: SITEMAP['changefreqs'] must be a dict")
                warning("sitemap plugin: using the default values")

    def write_url(self, page, fd):
        """Write the URL."""
        if getattr(page, "status", "published") != "published":
            return

        if getattr(page, "private", "False") == "True":
            return

        # We can disable categories/authors/etc by using False instead of ''
        if not page.save_as:
            return

        page_path = os.path.join(self.output_path, page.save_as)
        if not os.path.exists(page_path):
            return

        lastdate = getattr(page, "date", self.now)
        try:
            lastdate = self.get_date_modified(page, lastdate)
        except ValueError:
            warning(
                "sitemap plugin: " + page.save_as + " has invalid modification date,"
            )
            warning("sitemap plugin: using date value as lastmod.")
        lastmod = format_date(lastdate)

        if isinstance(page, contents.Article):
            pri = self.priorities["articles"]
            chfreq = self.changefreqs["articles"]
        elif isinstance(page, contents.Page):
            pri = self.priorities["pages"]
            chfreq = self.changefreqs["pages"]
        else:
            pri = self.priorities["indexes"]
            chfreq = self.changefreqs["indexes"]

        pageurl = "" if page.url == "index.html" else page.url

        # Exclude URLs from the sitemap:
        if any(x.search(pageurl) for x in self.sitemapExclude):
            return

        if self.format == "xml":
            fd.write(XML_URL.format(self.siteurl, pageurl, lastmod, chfreq, pri))
        else:
            fd.write(TXT_URL.format(self.siteurl, pageurl))

    def get_date_modified(self, page, default):
        """Return the page's modified date."""
        if hasattr(page, "modified"):
            if isinstance(page.modified, datetime):
                return page.modified
            return get_date(page.modified)
        else:
            return default

    def set_url_wrappers_modification_date(self, wrappers):
        """Set the URL wrapper's modification date."""
        for wrapper, articles in wrappers:
            lastmod = datetime.min.replace(tzinfo=self.timezone)
            for article in articles:
                lastmod = max(lastmod, article.date.replace(tzinfo=self.timezone))
                try:
                    modified = self.get_date_modified(article, datetime.min).replace(
                        tzinfo=self.timezone
                    )
                    lastmod = max(lastmod, modified)
                except ValueError:
                    # Supressed: user will be notified.
                    pass
            setattr(wrapper, "modified", str(lastmod))

    def generate_output(self, writer):
        """Generate and write the output to disk."""
        path = os.path.join(self.output_path, f"sitemap.{self.format}")

        pages = (
            self.context["pages"]
            + self.context["articles"]
            + [c for (c, a) in self.context["categories"]]
            + [t for (t, a) in self.context["tags"]]
            + [a for (a, b) in self.context["authors"]]
        )

        self.set_url_wrappers_modification_date(self.context["categories"])
        self.set_url_wrappers_modification_date(self.context["tags"])
        self.set_url_wrappers_modification_date(self.context["authors"])

        for article in self.context["articles"]:
            pages += article.translations

        info(f"writing {path}")

        with open(path, "w", encoding="utf-8") as fd:
            if self.format == "xml":
                fd.write(XML_HEADER)
            else:
                fd.write(TXT_HEADER.format(self.siteurl))

            FakePage = collections.namedtuple(
                "FakePage", ["status", "date", "url", "save_as"]
            )

            for standard_page in self.context["DIRECT_TEMPLATES"]:
                standard_page_url = self.context.get(f"{standard_page.upper()}_URL")
                standard_page_save_as = self.context.get(
                    f"{standard_page.upper()}_SAVE_AS"
                )

                # No save _SAVE_AS field means no output file. Skip.
                if not standard_page_save_as:
                    continue

                fake = FakePage(
                    status="published",
                    date=self.now,
                    url=standard_page_url or f"{standard_page}.html",
                    save_as=standard_page_save_as,
                )
                self.write_url(fake, fd)

            # add template pages
            # We use items for Py3k compat. .iteritems() otherwise
            for template_page_url in self.context["TEMPLATE_PAGES"].items():
                # don't add duplicate entry for index page
                if template_page_url == "index.html":
                    continue

                fake = FakePage(
                    status="published",
                    date=self.now,
                    url=template_page_url,
                    save_as=template_page_url,
                )
                self.write_url(fake, fd)

            for page in pages:
                self.write_url(page, fd)

            if self.format == "xml":
                fd.write(XML_FOOTER)


def get_generators(generators):
    """Return the Sitemap generator."""
    return SitemapGenerator


def register():
    """Register the plugin with Pelican."""
    signals.get_generators.connect(get_generators)
