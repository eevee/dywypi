from dywypi.event import PublicMessageEvent
from dywypi.plugin_api import Plugin, listen

class PageTitlesPlugin(Plugin):
    name = 'pagetitles'

    @listen(PublicMessageEvent)
    def scan_for_urls(self, event):
        print event.message
