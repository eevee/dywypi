from dywypi.event import listen
from dywypi.event import PublicMessageEvent
from dywypi.plugin_api import Plugin

class PageTitlesPlugin(Plugin):
    name = 'pagetitles'

    @listen(PublicMessageEvent)
    def scan_for_urls(self, event):
        print event.argv
