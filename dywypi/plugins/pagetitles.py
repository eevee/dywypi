from dywypi.event import listen
from dywypi.plugin_api import Plugin




from dywypi.core import PublicMessageEvent


class PageTitlesPlugin(Plugin):
    name = 'pagetitles'

    @listen(PublicMessageEvent)
    def scan_for_urls(self, event):
        print event.argv
