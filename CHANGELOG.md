CHANGELOG
=========

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
