################################################################################
#                                   sitemap                                    #
#  XML/raw sitemaps with options for compression and including arbitrary URLs  #
#                          (C)2020, 2022 Jeremy Brown                          #
#            Released under Prosperity Public License version 3.0.0            #
################################################################################

from collections import namedtuple
from datetime import datetime
import gzip
from io import StringIO
import logging
from pathlib import Path
import re
from sys import exit
from urllib.parse import quote, urljoin
from xml.etree.ElementTree import (
    Element,
    ElementTree,
    QName,
    SubElement,
    register_namespace,
)

from pytz import timezone

from pelican.contents import Article, Page
from pelican.urlwrappers import URLWrapper
from pelican.utils import get_date

LOG = logging.getLogger(__name__)
MAX_URL_PER_FILE = 50000
QNAME_XSI = QName("http://www.w3.org/2001/XMLSchema-instance", "schemaLocation")
XML_INDEX_ATTRIB = {
    QNAME_XSI: " ".join(
        [
            "http://www.sitemaps.org/schemas/sitemap/0.9",
            "https://www.sitemaps.org/schemas/sitemap/0.9/siteindex.xsd",
        ]
    )
}
XML_INDEX_QNAME = QName("http://www.sitemaps.org/schemas/sitemap/0.9", "sitemapindex")
XML_MAIN_ATTRIB = {
    QNAME_XSI: " ".join(
        [
            "http://www.sitemaps.org/schemas/sitemap/0.9",
            "https://www.sitemaps.org/schemas/sitemap/0.9/sitemap.xsd",
        ]
    )
}
XML_MAIN_QNAME = QName("http://www.sitemaps.org/schemas/sitemap/0.9", "urlset")

register_namespace("", "http://www.sitemaps.org/schemas/sitemap/0.9")
register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")


class SitemapGenerator:

    SitemapEntry = namedtuple(
        "_sitemap_entry", ["url", "last_modified", "frequency", "priority"]
    )

    allowed_frequencies = (
        "always",
        "hourly",
        "daily",
        "weekly",
        "monthly",
        "yearly",
        "never",
    )

    @staticmethod
    def generate_sitemap_data(entries, fmt):
        """
        Helper function to generate either an XML document or txt file
        for a sitemap as necessary

        :param entries: (list) SitemapEntry objects to be included
                                                   in the sitemap
        :param fmt: (str) Sitemap format
        :returns: (str) Sitemap data
        """
        if fmt == "txt":
            result = "\n".join(entry.url for entry in entries)
        elif fmt == "xml":
            result = SitemapGenerator.generate_xml_sitemap_data(entries)

        return result

    @staticmethod
    def generate_xml_sitemap_data(entries, index=False):
        """
        Create a conformant XML document containing the data of the
        given sitemap entries

        :param entries: (list) SitemapEntry objects to be included
                                                   in the sitemap
        :param index: (bool) Whether the XML document should be a
                                                sitemap or a sitemap index
        :returns: (str) An XML document containing the data of the
                                        provided entries
        """
        result = StringIO()

        if index:
            root = Element(XML_INDEX_QNAME, XML_INDEX_ATTRIB)
            entry_type = "sitemap"
        else:
            root = Element(XML_MAIN_QNAME, XML_MAIN_ATTRIB)
            entry_type = "url"

        for entry in entries:
            elem = SubElement(root, entry_type)
            SubElement(elem, "loc").text = entry.url

            if entry.last_modified is not None:
                SubElement(elem, "lastmod").text = entry.last_modified.isoformat()

            if entry.frequency is not None:
                SubElement(elem, "changefreq").text = entry.frequency

            if entry.priority is not None:
                SubElement(elem, "priority").text = str(entry.priority)

        tree = ElementTree(element=root)
        tree.write(result, encoding="unicode", xml_declaration=True)
        return result.getvalue()

    @staticmethod
    def get_last_modified(content, default_tz):
        """
        Find the most recent instant in which the given content was
        modified

        :param content: (Content) The content to find the mtime for
        :param default_tz: (pytz.timezone) Default timezone of the site
        :returns: (datetime) The most recent instance the given content
                                                 was modified, timezone-aware
        """
        result = datetime.now(default_tz)

        last_mod = content.metadata.get(
            "modified", content.metadata.get("date", result)
        )

        if not isinstance(last_mod, datetime):
            result = get_date(last_mod).replace(tzinfo=default_tz)
        else:
            result = last_mod

        return result

    @staticmethod
    def make_included_url_entries(included_list, default_tz):
        """
        Parse entries in the config file for URLs slated
        to be included in the sitemap

        :param included_list: (list) Raw entries from the config file
        :param default_tz: (pytz.timezone) Default timezone of the site
        :returns: (list) SitemapEntry objects corresponding to
                                         valid config file entries
        """
        result = []

        for raw_entry in included_list:
            if not isinstance(raw_entry, dict):
                LOG.warning("Sitemap entry object is invalid; skipping")
                LOG.debug("Invalid object: %s", raw_entry)
            elif "url" not in raw_entry:
                LOG.warning("Sitemap entry object missing URL; skipping")
            else:
                url = raw_entry.get("url")
                last_mod = raw_entry.get("lm")
                freq = raw_entry.get("freq")
                pri = raw_entry.get("pri")

                if pri is not None:
                    if not isinstance(pri, float) or not 0.0 <= pri <= 1.0:
                        LOG.warning("URL %s priority invalid; skipping", url)
                        LOG.debug("Priority value: %s", pri)
                        pri = None

                if freq is not None:
                    if freq not in SitemapGenerator.allowed_frequencies:
                        LOG.warning("URL %s frequency invalid; skipping", url)
                        LOG.debug("Frequency value: %s", freq)
                        freq = None

                if last_mod is not None:
                    if isinstance(last_mod, datetime):
                        # Update naive datetimes with default timezone
                        if (
                            last_mod.tzinfo is None
                            or last_mod.tzinfo.utcoffset(last_mod) is None
                        ):
                            last_mod = last_mod.replace(tzinfo=default_tz)

                    # Assume all numerical timestamps are naive
                    # and use default timezone
                    elif isinstance(last_mod, (int, float)):
                        last_mod = datetime.fromtimestamp(last_mod, default_tz)

                    # String timestamps must be naive, use default timezone
                    elif isinstance(last_mod, str):
                        ts_string = "%Y-%m-%dT%H:%M:%S"
                        try:
                            last_mod = datetime.strptime(last_mod, ts_string).replace(
                                tzinfo=default_tz
                            )
                        except ValueError:
                            LOG.warning(
                                "URL %s modified date does not match format; skipping",
                                url,
                            )
                            LOG.debug("Last modified value: %s", last_mod)
                            last_mod = None
                    else:
                        LOG.warning("URL %s modified date invalid; skipping", url)
                        LOG.debug("Last modified value: %s", last_mod)
                        last_mod = None

                LOG.debug("Adding URL %s to sitemap", url)
                url = quote(url, safe="/:")
                result.append(SitemapGenerator.SitemapEntry(url, last_mod, freq, pri))

        return result

    @staticmethod
    def parse_settings(raw_settings, orig_path, siteurl):
        """
        Parse the settings specified in the config file,
        reverting to defaults when user-specified settings are invalid
        or missing

        :param raw_settings: (dict) Settings from the config file
        :param orig_path: (str) Output path from the config file
        :param siteurl: (str) Root URL from the config file
        :returns: (dict) Parsed settings from the config file,
                                          using defaults where necessary
        """
        allowed_formats = ("txt", "xml")
        result = {
            "siteurl": siteurl if siteurl.endswith("/") else f"{siteurl}/",
            "compress": True,
            "format": "xml",
            "out_path": ".",
            "frequencies": {
                "articles": "monthly",
                "indexes": "daily",
                "pages": "monthly",
            },
            "priorities": {"articles": 0.5, "indexes": 0.5, "pages": 0.5},
            "include": [],
            "exclude": [],
        }

        raw_path = raw_settings.get("out_path", result["out_path"])

        # Set output path for sitemap file(s)
        path = orig_path.joinpath(raw_path).resolve()

        # Set root path for sitemap URL(s)
        root = urljoin(result["siteurl"], raw_path)

        # Set compression flag
        comp = raw_settings.get("compress", result["compress"])
        if not isinstance(comp, bool):
            LOG.warning(
                "Compression not specified as bool; defaulting to %s",
                result["compress"],
            )
            comp = result["compress"]

        # Set output format
        fmt = raw_settings.get("format", result["format"])
        if fmt not in allowed_formats:
            LOG.warning(
                "Given output format not allowed; defaulting to %s", result["format"]
            )
            fmt = result["format"]

        # Set change frequencies
        freqs = raw_settings.get("frequencies", result["frequencies"])
        if not isinstance(freqs, dict):
            LOG.warning(
                "Frequencies not specified as dict; defaulting to %s",
                result["frequencies"],
            )
            freqs = result["frequencies"]
        else:
            for category in result["frequencies"]:
                val = freqs.get(category)
                if val is None:
                    LOG.info(
                        "%s frequency not specified; defaulting to %s",
                        category,
                        result["frequencies"][category],
                    )

                    freqs[category] = result["frequencies"][category]

                elif val not in SitemapGenerator.allowed_frequencies:
                    LOG.warning(
                        "%s frequency invalid; defaulting to %s",
                        category,
                        result["frequencies"][category],
                    )

                    freqs[category] = result["frequencies"][category]

        # Set URL priorities
        priorities = raw_settings.get("priorities", result["priorities"])
        if not isinstance(priorities, dict):
            LOG.warning(
                "Priorities not specified as dict; defaulting to %s",
                result["priorities"],
            )
        else:
            for category in result["priorities"]:
                val = priorities.get(category)
                if val is None:
                    LOG.info(
                        "%s priority not specified; defaulting to %s",
                        category,
                        result["priorities"][category],
                    )

                    priorities[category] = result["priorities"][category]

                elif not isinstance(val, float) or not 0.0 <= val <= 1.0:
                    LOG.warning(
                        "%s priority invalid; defaulting to %s",
                        category,
                        result["priorities"][category],
                    )

                    priorities[category] = result["priorities"][category]

        # Lightly validate URLs outside generated site to be included in sitemap
        inclusions = raw_settings.get("include", result["include"])
        if not isinstance(inclusions, list):
            LOG.warning(
                "URL inclusions not specified as list; defaulting to %s",
                result["include"],
            )
            inclusions = result["include"]
        else:
            filtered_inclusions = [
                entry for entry in inclusions if isinstance(entry, dict)
            ]

            if len(filtered_inclusions) != len(inclusions):
                LOG.warning("Not including URLs specified incorrectly; check settings")

            inclusions = filtered_inclusions

        # Lightly validate URLs to be excluded from sitemap
        exclusions = raw_settings.get("exclude", result["exclude"])
        if not isinstance(exclusions, list):
            LOG.warning(
                "URL exclusions not specified as list; defaulting to %s",
                result["exclude"],
            )
            exclusions = result["exclude"]
        else:
            exclusions = [re.compile(x) for x in exclusions]

        result["compress"] = comp
        result["out_path"] = path
        result["format"] = fmt
        result["frequencies"] = freqs
        result["priorities"] = priorities
        result["map_root"] = root
        result["include"] = inclusions
        result["exclude"] = exclusions

        return result

    @staticmethod
    def should_exclude(content, exclusions):
        """
        Determine if a given location should be excluded from the
        sitemap due to explicit exclusion in the settings or assorted
        metadata

        :param content: (Content) Object relating to the URL to check
                                                          for exclusion
        :param exclusions: (list) Entries from the settings relating to
                                                          URL fragments to exclude
        :returns: (bool) Whether or not to exclude the location
        """
        result = True

        if (
            content.metadata.get("private", False) is False
            and content.metadata.get("status", "published") != "hidden"
        ):
            if not any([re.match(x, content.url) for x in exclusions]):
                result = False

        return result

    def __init__(self):
        self._entries = []
        self._seen_categories = set()

    def pelican_init(self, pelican):
        """
        Plugin initialization function

        :param pelican: (Pelican) Pelican object
        """
        out_root = Path(pelican.output_path)
        siteurl = pelican.settings.get("SITEURL", "")
        sitemap_settings = pelican.settings.get("SITEMAP", {})

        LOG.debug("Initializing sitemap plugin")
        if not siteurl:
            LOG.critical("SITEURL not defined; cannot create sitemap")
            exit(1)

        self._timezone = timezone(pelican.settings.get("TIMEZONE") or "UTC")
        self._start_time = datetime.now(self._timezone)
        self._settings = self.parse_settings(sitemap_settings, out_root, siteurl)

        # Handle URLs outside generated site to be included in sitemap
        self._entries = self.make_included_url_entries(
            self._settings["include"], self._timezone
        )

    def add_entry(self, path, context):
        """
        Add generated content to sitemap,
        so long as it should be included

        :param path: (str) Path content will be written to
        :param context: (dict) Pelican context for content
        """
        entry = None
        content = (
            context.get("article") or context.get("page") or context.get("category")
        )

        if isinstance(content, Article):
            default_freq = self._settings["frequencies"]["articles"]
            default_pri = self._settings["priorities"]["articles"]

        elif isinstance(content, Page):
            default_freq = self._settings["frequencies"]["pages"]
            default_pri = self._settings["priorities"]["pages"]

        elif isinstance(content, URLWrapper):
            default_freq = self._settings["frequencies"]["indexes"]
            default_pri = self._settings["priorities"]["indexes"]

        else:
            LOG.debug("Could not determine what type of output %s belonged to", path)

        if isinstance(content, (Article, Page)):
            if self.should_exclude(content, self._settings["exclude"]):
                return

            last_mod = self.get_last_modified(content, self._timezone)
            url = urljoin(self._settings["siteurl"], quote(content.url))
            freq = content.metadata.get("sitemap_freq", default_freq)
            raw_pri = content.metadata.get("sitemap_pri", default_pri)

            if freq not in self.allowed_frequencies:
                LOG.warning(
                    "Content at %s has invalid %s value %s; using default value",
                    "frequency",
                    path,
                    freq,
                )
                freq = default_freq

            try:
                pri = float(raw_pri)
            except ValueError:
                LOG.warning(
                    "Content at %s has invalid %s value %s; using default value",
                    "priority",
                    path,
                    raw_pri,
                )
                pri = default_pri
            else:
                if not 0.0 <= pri <= 1.0:
                    LOG.warning(
                        "Content at %s has invalid %s value %s; using default value",
                        "priority",
                        path,
                        raw_pri,
                    )
                    pri = default_pri

            entry = self.SitemapEntry(url, last_mod, freq, pri)

        elif isinstance(content, URLWrapper):
            last_mod = self._start_time
            url = urljoin(self._settings["siteurl"], quote(content.url))

            if content.name not in self._seen_categories:
                self._seen_categories.add(content.name)
                entry = self.SitemapEntry(url, last_mod, default_freq, default_pri)

        if entry:
            LOG.debug("Adding URL %s to sitemap", entry.url)
            self._entries.append(entry)

    def write_output(self, pelican):
        """
        Create the sitemap(s) and write them to disk

        :param pelican: (Pelican) Pelican object
        """
        ext = self._settings["format"]
        if self._settings["compress"]:
            ext = f"{ext}.gz"

        if not self._entries:
            LOG.info("No paths for sitemap; skipping creation")
            return

        split_entries = [
            self._entries[i * MAX_URL_PER_FILE : (i + 1) * MAX_URL_PER_FILE]
            for i in range((len(self._entries) // MAX_URL_PER_FILE) + 1)
        ]

        split_entries = list(filter(None, split_entries))
        out_root = self._settings["out_path"]
        index_path = None

        if len(split_entries) == 1:
            paths = [out_root.joinpath(f"sitemap.{ext}")]
        else:
            paths = [
                out_root.joinpath(f"sitemap{i}.{ext}")
                for i in range(1, len(split_entries) + 1)
            ]

            if self._settings["format"] == "xml":
                index_path = out_root.joinpath(f"sitemap.{ext}")

        prepped_maps = {
            path: self.generate_sitemap_data(entries, self._settings["format"])
            for (path, entries) in zip(paths, split_entries)
        }

        if index_path:
            sm_entries = [
                self.SitemapEntry(
                    urljoin(self._settings["map_root"], path.name),
                    self._start_time,
                    None,
                    None,
                )
                for path in paths
            ]
            prepped_maps[index_path] = self.generate_xml_sitemap_data(
                sm_entries, index=True
            )

        for (map_path, map_data) in prepped_maps.items():
            if self._settings["compress"]:
                with gzip.open(map_path, "wb") as f:
                    f.write(map_data.encode(encoding="UTF-8"))
            else:
                map_path.write_bytes(map_data.encode(encoding="UTF-8"))

            LOG.debug("Wrote sitemap to %s", str(map_path))
