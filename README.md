Sitemap
=======

[![Build Status](https://img.shields.io/github/actions/workflow/status/pelican-plugins/sitemap/main.yml?branch=main)](https://github.com/pelican-plugins/sitemap/actions)
[![PyPI Version](https://img.shields.io/pypi/v/pelican-sitemap)](https://pypi.org/project/pelican-sitemap/)
[![Downloads](https://img.shields.io/pypi/dm/pelican-sitemap)](https://pypi.org/project/pelican-sitemap/)
![License](https://img.shields.io/pypi/l/pelican-sitemap?color=blue)

This [Pelican][] plugin generates a site map in plain-text or XML format. You can use the `SITEMAP` variable in your settings file to configure the behavior of the plugin.

Installation
------------

This plugin can be installed via:

    python -m pip install pelican-sitemap

As long as you have not explicitly added a `PLUGINS` setting to your Pelican settings file, then the newly-installed plugin should be automatically detected and enabled. Otherwise, you must add `sitemap` to your existing `PLUGINS` list. For more information, please see the [How to Use Plugins](https://docs.getpelican.com/en/latest/plugins.html#how-to-use-plugins) documentation.

Usage
-----

The `SITEMAP` setting must be a Python dictionary and can contain these keys:

* `format`, which sets the output format of the plugin (`xml` or `txt`)

* `priorities`, which is a dictionary with three keys:

    - `articles`, the priority for the URLs of the articles and their translations

    - `pages`, the priority for the URLs of the static pages

    - `indexes`, the priority for the URLs of the index pages, such as tags, author pages, categories indexes, archives, etc.

    All the values of this dictionary must be decimal numbers between `0` and `1`.

* `changefreqs`, which is a dictionary with three items:

    - `articles`, the update frequency of the articles

    - `pages`, the update frequency of the pages

    - `indexes`, the update frequency of the index pages

    Valid frequency values are `always`, `hourly`, `daily`, `weekly`, `monthly`, `yearly` and `never`.

* `exclude`, which is a list of regular expressions that will be used to exclude matched URLs from the sitemap if *any* of them match. For example:

```python
SITEMAP = {
    "exclude": [
        "^/noindex/",  # starts with "/noindex/"
        "/tag/",       # contains "/tag/"
        "\.json$",     # ends with ".json"
    ]
}
```

If a key is missing or a value is incorrect, it will be replaced with the default value.

You can also exclude an individual URL by adding metadata to it, setting `private` to `True`.

The sitemap is saved in: `<output_path>/sitemap.<format>`

> **Note:** `priorities` and `changefreqs` are information for search engines and are only used in the XML site maps. For more information, see: <https://www.sitemaps.org/protocol.html#xmlTagDefinitions>

**Example**

Here is an example configuration (it is also the default settings):

```python
SITEMAP = {
    "format": "xml",
    "priorities": {
        "articles": 0.5,
        "indexes": 0.5,
        "pages": 0.5
    },
    "changefreqs": {
        "articles": "monthly",
        "indexes": "daily",
        "pages": "monthly"
    }
}
```

Using Metadata
--------------

In addition to applying a configuration to all articles/pages using the `SITEMAP` setting, `ChangeFreq` and `Priority` can also be specified as metadata for individual articles/pages. The same restrictions on the values apply:

* Valid options for `ChangeFreq` are  `always`, `hourly`, `daily`, `weekly`, `monthly`, `yearly` and `never`.
* Valid options for `Priority` must be a decimal number between `0` and `1`.

**Example**

Following is an example of using sitemap-related metadata in a Markdown file:

```
Title: Frequently Changed Article
ChangeFreq: daily
Priority: 0.3

This is the article content.
```

Contributing
------------

Contributions are welcome and much appreciated. Every little bit helps. You can contribute by improving the documentation, adding missing features, and fixing bugs. You can also help out by reviewing and commenting on [existing issues][].

To start contributing to this plugin, review the [Contributing to Pelican][] documentation, beginning with the **Contributing Code** section.

[Pelican]: https://github.com/getpelican/pelican
[existing issues]: https://github.com/pelican-plugins/sitemap/issues
[Contributing to Pelican]: https://docs.getpelican.com/en/latest/contribute.html

License
-------

This project is licensed under the [AGPL-3.0](http://www.gnu.org/licenses/agpl-3.0-standalone.html) license.
