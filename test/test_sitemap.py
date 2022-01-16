################################################################################
#                                   sitemap                                    #
#  XML/raw sitemaps with options for compression and including arbitrary URLs  #
#                          (C)2020, 2022 Jeremy Brown                          #
#            Released under Prosperity Public License version 3.0.0            #
################################################################################

from copy import deepcopy
from datetime import datetime
from unittest.mock import Mock, patch
from urllib.parse import urljoin
from xml.etree import ElementTree

from hypothesis import HealthCheck, given, settings
from hypothesis.strategies import booleans, composite, floats, just, none, one_of
import pytest
from pytz import timezone

from pelican.contents import Article, Page
from pelican.plugins.sitemap import SitemapGenerator
from pelican.tests.support import get_context, get_settings
from pelican.urlwrappers import Category


@composite
def sitemap_settings(draw):
    result = {
        "compress": draw(one_of(booleans(), none())),
        "format": draw(one_of(just("xml"), just("txt"), just("xyz"))),
        "include": draw(
            one_of(
                none(),
                just(
                    [
                        "http://example.com/bad-entry.html",
                        {"url": "http://example.com/ok-entry.html"},
                    ]
                ),
            )
        ),
        "exclude": draw(one_of(none(), just(["/definitely-excluded"]))),
    }

    art_freq = draw(one_of(none(), just("never"), just("sometimes")))
    ind_freq = draw(one_of(none(), just("never"), just("sometimes")))
    pag_freq = draw(one_of(none(), just("never"), just("sometimes")))

    art_pri = draw(one_of(none(), floats(min_value=-1, max_value=2)))
    ind_pri = draw(one_of(none(), floats(min_value=-1, max_value=2)))
    pag_pri = draw(one_of(none(), floats(min_value=-1, max_value=2)))

    if art_freq is not None or ind_freq is not None or pag_freq is not None:
        result["frequencies"] = {
            "articles": art_freq,
            "indexes": ind_freq,
            "pages": pag_freq,
        }
    else:
        result["frequencies"] = None

    if art_pri is not None or ind_pri is not None or pag_pri is not None:
        result["priorities"] = {
            "articles": art_pri,
            "indexes": ind_pri,
            "pages": pag_pri,
        }
    else:
        result["priorities"] = None

    return result


@pytest.mark.parametrize(
    "has_time, is_modified",
    [[True, True], [True, False], [False, False]],
    ids=["modified-content", "original-content", "no-times"],
)
def test_get_last_modified(has_time, is_modified):
    tz = timezone("UTC")
    mock_content = Mock()
    mock_content.metadata = {}

    if has_time:
        mock_content.metadata["date"] = "2020-04-20"

    if is_modified:
        mock_content.metadata["modified"] = datetime(2020, 6, 9, 10, 17, 0, tzinfo=tz)

    result = SitemapGenerator.get_last_modified(mock_content, tz)

    if is_modified:
        assert result == datetime(2020, 6, 9, 10, 17, 0, tzinfo=tz)
    elif has_time:
        assert result == datetime(2020, 4, 20, tzinfo=tz)
    else:
        assert (datetime.now(tz) - result).seconds == 0


@pytest.mark.parametrize("scenario", ["private", "hidden", "excluded", "public"])
def test_should_exclude(scenario):
    mock_content = Mock()
    mock_content.url = "/maybe-excluded/post.html"
    mock_content.metadata = {
        "private": True if scenario == "private" else False,
        "status": "hidden" if scenario == "hidden" else "published",
    }

    exclusions = [r"/definitely-excluded"]

    if scenario == "excluded":
        exclusions.append(r"/maybe-excluded")

    result = SitemapGenerator.should_exclude(mock_content, exclusions)

    assert result is False if scenario == "public" else True


@pytest.mark.parametrize("gen_index", [True, False], ids=["index", "sitemap"])
def test_generate_xml_sitemap_data(gen_index):
    tz = timezone("UTC")
    now = datetime.now(tz)

    if gen_index:
        entries = [
            SitemapGenerator.SitemapEntry("example.com/map1.xml", now, None, None),
            SitemapGenerator.SitemapEntry("example.com/map2.xml", now, None, None),
            SitemapGenerator.SitemapEntry("example.com/map3.xml", now, None, None),
        ]
    else:
        entries = [
            SitemapGenerator.SitemapEntry("example.com/page1.html", now, "never", 0.5),
            SitemapGenerator.SitemapEntry("example.com/page2.html", now, "never", 0.5),
            SitemapGenerator.SitemapEntry("example.com/page3.html", now, "never", 0.5),
        ]

    result = ElementTree.fromstring(
        SitemapGenerator.generate_xml_sitemap_data(entries, gen_index)
    )

    if gen_index:
        assert result.tag.endswith("sitemapindex")
        maps = result.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}sitemap")
        assert len(maps) == len(entries)
        for (sm, entry) in zip(maps, entries):
            assert (
                sm.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text
                == entry.url
            )
    else:
        assert result.tag.endswith("urlset")
        urls = result.findall("{http://www.sitemaps.org/schemas/sitemap/0.9}url")
        assert len(urls) == len(entries)
        for (url, entry) in zip(urls, entries):
            assert (
                url.find("{http://www.sitemaps.org/schemas/sitemap/0.9}loc").text
                == entry.url
            )


@pytest.mark.parametrize("fmt", ["xml", "txt"])
def test_generate_sitemap_data(fmt):
    entries = [
        SitemapGenerator.SitemapEntry("example.com/page1.html", None, "never", 0.5),
        SitemapGenerator.SitemapEntry("example.com/page2.html", None, "never", 0.5),
        SitemapGenerator.SitemapEntry("example.com/page3.html", None, "never", 0.5),
    ]

    result = SitemapGenerator.generate_sitemap_data(entries, fmt)

    if fmt == "txt":
        assert result == "\n".join(entry.url for entry in entries)
    else:
        result = ElementTree.fromstring(result)
        assert result.tag.endswith("urlset")


@patch("pelican.plugins.sitemap.sitemap.LOG")
def test_make_included_url_entries(mock_logger):
    utc = timezone("UTC")
    est = timezone("EST")
    dt = datetime(2020, 6, 9, 16, 20, 0)

    entries = [
        "www.example.com/raw-url.html",
        {
            "link": "www.example.com/bad-format.html",
            "lm": "2020-04-20T10:17:00",
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/str-priority.html",
            "lm": "2020-04-20T10:17:00",
            "freq": "never",
            "pri": "0.5",
        },
        {
            "url": "www.example.com/neg-priority.html",
            "lm": "2020-04-20T10:17:00",
            "freq": "never",
            "pri": -0.5,
        },
        {
            "url": "www.example.com/bad-frequency.html",
            "lm": "2020-04-20T10:17:00",
            "freq": "sometimes",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/invalid-last-mod.html",
            "lm": (2020, 4, 20, 10, 17, 0),
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/bad-format-last-mod.html",
            "lm": "2020-04-20",
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/dt-last-mod.html",
            "lm": dt,
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/tz-dt-last-mod.html",
            "lm": dt.replace(tzinfo=est),
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/int-last-mod.html",
            "lm": 1591719600,
            "freq": "never",
            "pri": 0.5,
        },
        {
            "url": "www.example.com/str-last-mod.html",
            "lm": "2020-06-09T16:20:00",
            "freq": "never",
            "pri": 0.5,
        },
    ]

    result = SitemapGenerator.make_included_url_entries(entries, utc)

    assert len(result) == 9

    assert result[0].url == "www.example.com/str-priority.html"
    assert result[0].priority is None
    mock_logger.warning.assert_any_call(
        "URL %s priority invalid; skipping", entries[2]["url"]
    )
    mock_logger.debug.assert_any_call("Priority value: %s", entries[2]["pri"])

    assert result[1].url == "www.example.com/neg-priority.html"
    assert result[1].priority is None
    mock_logger.warning.assert_any_call(
        "URL %s priority invalid; skipping", entries[3]["url"]
    )
    mock_logger.debug.assert_any_call("Priority value: %s", entries[3]["pri"])

    assert result[2].url == "www.example.com/bad-frequency.html"
    assert result[2].frequency is None
    mock_logger.warning.assert_any_call(
        "URL %s frequency invalid; skipping", entries[4]["url"]
    )
    mock_logger.debug.assert_any_call("Frequency value: %s", entries[4]["freq"])

    assert result[3].url == "www.example.com/invalid-last-mod.html"
    assert result[3].last_modified is None
    mock_logger.warning.assert_any_call(
        "URL %s modified date invalid; skipping", entries[5]["url"]
    )
    mock_logger.debug.assert_any_call("Last modified value: %s", entries[5]["lm"])

    assert result[4].url == "www.example.com/bad-format-last-mod.html"
    assert result[4].last_modified is None
    mock_logger.warning.assert_any_call(
        "URL %s modified date does not match format; skipping", entries[6]["url"]
    )
    mock_logger.debug.assert_any_call("Last modified value: %s", entries[6]["lm"])

    assert result[5].url == "www.example.com/dt-last-mod.html"
    assert result[5].last_modified == dt.replace(tzinfo=utc)

    assert result[6].url == "www.example.com/tz-dt-last-mod.html"
    assert result[6].last_modified == dt.replace(tzinfo=est)

    assert result[7].url == "www.example.com/int-last-mod.html"
    assert result[7].last_modified == dt.replace(tzinfo=utc)

    assert result[8].url == "www.example.com/str-last-mod.html"
    assert result[8].last_modified == dt.replace(tzinfo=utc)


@pytest.mark.parametrize(
    "siteurl",
    ["http://example.com", "http://example.com/test/path/"],
    ids=["no-trailing-slash", "trailing-slash"],
)
@patch("pelican.plugins.sitemap.sitemap.LOG")
@settings(suppress_health_check=(HealthCheck.function_scoped_fixture,))
@given(settings=sitemap_settings())
def test_parse_settings(mock_logger, settings, siteurl, tmp_path):
    def_freqs = {"articles": "monthly", "indexes": "daily", "pages": "monthly"}

    def_pris = {"articles": 0.5, "indexes": 0.5, "pages": 0.5}

    settings_c = deepcopy(settings)

    if siteurl.endswith("/test/path/"):
        out_path = tmp_path.joinpath("test", "path")
        settings_c["out_path"] = "../../"
    else:
        out_path = tmp_path

    parsed_settings = SitemapGenerator.parse_settings(settings_c, out_path, siteurl)

    assert parsed_settings["siteurl"].endswith("/")
    assert not parsed_settings["siteurl"].endswith("//")

    assert parsed_settings["map_root"] == "http://example.com/"
    assert parsed_settings["out_path"] == tmp_path

    if isinstance(settings["compress"], bool):
        assert parsed_settings["compress"] == settings["compress"]
    else:
        assert parsed_settings["compress"] is True

    if settings["format"] == "xyz":
        assert parsed_settings["format"] == "xml"
    else:
        assert parsed_settings["format"] == settings["format"]

    if settings["frequencies"] is not None:
        for (cat, freq) in settings["frequencies"].items():
            if freq in SitemapGenerator.allowed_frequencies:
                assert parsed_settings["frequencies"][cat] == freq
            else:
                assert parsed_settings["frequencies"][cat] == def_freqs[cat]

    if settings["priorities"] is not None:
        for (cat, pri) in settings["priorities"].items():
            if isinstance(pri, float) and 0.0 <= pri <= 1.0:
                assert parsed_settings["priorities"][cat] == pri
            else:
                assert parsed_settings["priorities"][cat] == def_pris[cat]

    if settings["include"] is None:
        assert parsed_settings["include"] == []
        mock_logger.warning.assert_any_call(
            "URL inclusions not specified as list; defaulting to %s", []
        )
    else:
        assert len(parsed_settings["include"]) == 1
        mock_logger.warning.assert_any_call(
            "Not including URLs specified incorrectly; check settings"
        )

    if settings["exclude"] is None:
        assert parsed_settings["exclude"] == []
        mock_logger.warning.assert_any_call(
            "URL exclusions not specified as list; defaulting to %s", []
        )
    else:
        assert len(parsed_settings["exclude"]) == 1

    if settings.get("frequencies") is None:
        mock_logger.warning.assert_any_call(
            "Frequencies not specified as dict; defaulting to %s", def_freqs
        )
    elif settings["frequencies"].get("articles") is None:
        mock_logger.info.assert_any_call(
            "%s frequency not specified; defaulting to %s", "articles", "monthly"
        )
    elif settings["frequencies"]["articles"] != "never":
        mock_logger.warning.assert_any_call(
            "%s frequency invalid; defaulting to %s", "articles", "monthly"
        )

    if settings.get("priorities") is None:
        mock_logger.warning.assert_any_call(
            "Priorities not specified as dict; defaulting to %s", def_pris
        )
    elif settings["priorities"].get("articles") is None:
        mock_logger.info.assert_any_call(
            "%s priority not specified; defaulting to %s", "articles", 0.5
        )
    elif not 0.0 <= settings["priorities"]["articles"] <= 1.0:
        mock_logger.warning.assert_any_call(
            "%s priority invalid; defaulting to %s", "articles", 0.5
        )


@pytest.mark.parametrize(
    "siteurl", ["http://example.com/test/", ""], ids=["siteurl", "no-siteurl"]
)
@pytest.mark.parametrize(
    "tz", ["America/New_York", ""], ids=["timezone", "no-timezone"]
)
@patch("pelican.plugins.sitemap.sitemap.exit")
@patch("pelican.plugins.sitemap.sitemap.LOG")
def test_pelican_init(mock_logger, mock_exit, tz, siteurl, tmp_path):
    mock_pelican = Mock()
    mock_pelican.output_path = str(tmp_path)

    settings = {}

    mock_pelican.settings = get_settings(
        SITEURL=siteurl,
        TIMEZONE=tz,
        SITEMAP=settings,
    )

    gen = SitemapGenerator()
    gen.pelican_init(mock_pelican)

    assert gen._timezone == timezone(tz) if tz else timezone("UTC")

    if siteurl:
        assert gen._settings["siteurl"] == siteurl
    else:
        mock_logger.critical.assert_called_once_with(
            "SITEURL not defined; cannot create sitemap"
        )
        mock_exit.assert_called_once_with(1)


@pytest.mark.parametrize("fmt", ["xml", "txt"])
@pytest.mark.parametrize(
    "has_entries, multimap",
    [[True, True], [True, False], [False, False]],
    ids=["multi-map", "single-map", "no-map"],
)
@patch("pelican.plugins.sitemap.sitemap.MAX_URL_PER_FILE", 2)
@patch("pelican.plugins.sitemap.sitemap.LOG")
def test_write_output(mock_logger, has_entries, multimap, fmt, tmp_path):
    sm_settings = {
        "compress": True if fmt == "xml" else False,
        "format": fmt,
    }

    if has_entries:
        sm_settings["include"] = [
            {
                "url": "http://example.com/page1.html",
                "lm": "2020-04-20T06:09:00",
                "freq": "never",
                "pri": 0.5,
            },
            {
                "url": "http://example.com/page2.html",
                "lm": "2020-06-09T10:17:00",
                "freq": "never",
                "pri": 0.5,
            },
        ]

    if multimap:
        sm_settings["include"].append(
            {
                "url": "http://example.com/page3.html",
                "lm": "2020-10-17T16:20:00",
                "freq": "never",
                "pri": 0.5,
            }
        )

    mock_pelican = Mock()
    mock_pelican.output_path = str(tmp_path)
    mock_pelican.settings = get_settings(
        SITEURL="http://example.com/test/",
        SITEMAP=sm_settings,
    )

    gen = SitemapGenerator()
    gen.pelican_init(mock_pelican)
    gen.write_output(mock_pelican)

    if multimap:
        assert len(list(tmp_path.iterdir())) == (3 if fmt == "xml" else 2)
    elif has_entries:
        assert len(list(tmp_path.iterdir())) == 1
    else:
        assert len(list(tmp_path.iterdir())) == 0


@pytest.mark.parametrize(
    "content_type", [None, "article", "page", "category", "excluded"]
)
@patch("pelican.plugins.sitemap.sitemap.LOG")
def test_add_entry(mock_logger, content_type, tmp_path):
    mock_pelican = Mock()
    mock_pelican.output_path = str(tmp_path)
    now = datetime.now(timezone("UTC"))
    sm_settings = {
        "exclude": ["/exclude"],
    }
    mock_pelican.settings = get_settings(
        SITEURL="http://example.com/test/",
        SITEMAP=sm_settings,
    )
    context = get_context(mock_pelican.settings)

    if content_type in ("article", "excluded"):
        content_path = tmp_path.joinpath("test-article.html")
        md = {
            "title": "Test Article",
            "date": datetime(2020, 6, 9, 16, 20, 0, tzinfo=timezone("UTC")),
            "modified": now,
            "status": "published",
            "sitemap_freq": "sometimes",
            "sitemap_pri": "-0.42",
        }

        if content_type == "excluded":
            md["url"] = "/excluded/test-article.html"

        context["article"] = Article(
            content=None,
            context=context,
            settings=mock_pelican.settings,
            metadata=md,
        )

    elif content_type == "page":
        split_path = ["pages", "test-page.html"]
        content_path = tmp_path.joinpath(*split_path)
        md = {
            "title": "Test Page",
            "date": datetime(2020, 4, 20, 6, 9, 0, tzinfo=timezone("UTC")),
            "status": "published",
            "sitemap_freq": "yearly",
            "sitemap_pri": "x",
        }

        context["page"] = Page(
            content=None,
            context=context,
            settings=mock_pelican.settings,
            metadata=md,
        )

    elif content_type == "category":
        split_path = ["category", "test-category.html"]
        content_path = str(tmp_path.joinpath(*split_path))
        context["category"] = Category(
            name="Test Category",
            settings=mock_pelican.settings,
        )
    else:
        content_path = tmp_path.joinpath("test-random-content.html")

    gen = SitemapGenerator()
    gen.pelican_init(mock_pelican)
    gen.add_entry(str(content_path), context)

    if content_type == "article":
        assert len(gen._entries) == 1
        mock_logger.warning.assert_any_call(
            "Content at %s has invalid %s value %s; using default value",
            "frequency",
            str(content_path),
            md["sitemap_freq"],
        )
        mock_logger.warning.assert_any_call(
            "Content at %s has invalid %s value %s; using default value",
            "priority",
            str(content_path),
            md["sitemap_pri"],
        )
        assert gen._entries[0].url == urljoin(
            "http://example.com/test/", content_path.name
        )
        assert gen._entries[0].last_modified == now
        assert gen._entries[0].frequency == "monthly"
        assert gen._entries[0].priority == 0.5
    elif content_type == "page":
        assert len(gen._entries) == 1
        mock_logger.warning.assert_any_call(
            "Content at %s has invalid %s value %s; using default value",
            "priority",
            str(content_path),
            md["sitemap_pri"],
        )
        assert gen._entries[0].url == urljoin(
            "http://example.com/test/", "/".join(split_path)
        )
        assert gen._entries[0].last_modified == md["date"]
        assert gen._entries[0].frequency == "yearly"
        assert gen._entries[0].priority == 0.5
    elif content_type == "category":
        assert len(gen._entries) == 1
        assert gen._entries[0].url == urljoin(
            "http://example.com/test/", "/".join(split_path)
        )
        assert gen._entries[0].last_modified == gen._start_time
        assert gen._entries[0].frequency == "daily"
        assert gen._entries[0].priority == 0.5
    elif content_type == "excluded":
        assert len(gen._entries) == 0
    else:
        assert len(gen._entries) == 0
        mock_logger.debug.assert_any_call(
            "Could not determine what type of output %s belonged to", str(content_path)
        )
