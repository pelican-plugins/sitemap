Release type: minor

Re-factor plugin, including the following changes:

* Act on every `content_written` signal to avoid guessing what pages to cover.
* Instead of manually fiddling with timezones, expect `article.date` to be TZ-aware if required.
* Add `xmlns:xhtml` to XML header.
