CHANGELOG
=========

1.2.0 - 2024-11-05
------------------

- Allow changefreq and priority to be set by page/article metadata ([#30](https://github.com/pelican-plugins/sitemap/pull/30) by [dgaylo](https://github.com/dgaylo))
- Fix error message for invalid changefreq value ([#31](https://github.com/pelican-plugins/sitemap/pull/31) by [dgaylo](https://github.com/dgaylo))
- Fix error in tests ([#37](https://github.com/pelican-plugins/sitemap/pull/37) by [projectgus](https://github.com/projectgus))
- Support Python 3.9 – 3.13 ([#38](https://github.com/pelican-plugins/sitemap/pull/38) by [justinmayer](https://github.com/justinmayer))
- Pin Blinker temporarily to 1.7 until upstream fix is released ([#35](https://github.com/pelican-plugins/sitemap/issues/35) by [justinmayer](https://github.com/justinmayer))

1.1.0 - 2023-07-24
------------------

Re-factor plugin, including the following changes:

* Act on every `content_written` signal to avoid guessing what pages to cover.
* Instead of manually fiddling with timezones, expect `article.date` to be TZ-aware if required.
* Add `xmlns:xhtml` to XML header.

Contributed by [kernc](https://github.com/kernc) via [PR #3](https://github.com/pelican-plugins/sitemap/pull/3/)


1.0.3 - 2023-07-12
------------------

- Enable URL exclusion when using `txt` format
- Improve performance by compiling "exclude" regexes
- Look for the "exclude" regexes anywhere in the URL instead of just at the start

Contributed by [Carey Metcalfe](https://github.com/pR0Ps) via [PR #16](https://github.com/pelican-plugins/sitemap/pull/16/)


1.0.2 - 2020-08-22
------------------

Specify Pelican 4.5 as minimum required version

1.0.1 - 2020-05-03
------------------

* Remove duplicate entries from TXT file header
* Avoid listing `DIRECT_TEMPLATES` for which `*_SAVE_AS` is empty string

1.0.0 - 2020-04-20
------------------

First release in new namespace plugin format
