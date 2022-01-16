################################################################################
#                                   sitemap                                    #
#  XML/raw sitemaps with options for compression and including arbitrary URLs  #
#                          (C)2020, 2022 Jeremy Brown                          #
#       Released under version 3.0 of the Non-Profit Open Source License       #
################################################################################

from pelican import signals

from .sitemap import SitemapGenerator

gen = SitemapGenerator()


def register():
    signals.get_generators.connect(gen.pelican_init)
    signals.content_written.connect(gen.add_entry)
    signals.finalized.connect(gen.write_output)
