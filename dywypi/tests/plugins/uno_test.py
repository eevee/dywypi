import asyncio
from collections import deque

from dywypi.event import PublicMessage
from dywypi.plugin import PluginManager
from dywypi.state import Channel
from dywypi.state import Peer


class PluginPoker:
    def __init__(self, plugin_name, *, client):
        self.plugin_name = plugin_name
        self.client = client

        self.manager = PluginManager()
        self.manager.scan_package('dywypi.plugins')
        self.manager.load(plugin_name)
        self.plugin = self.manager.loaded_plugins[plugin_name]
        self.data = self.manager.plugin_data[self.plugin]

        self.queued_events = deque()

    def queue(self, event_type, *args):
        self.queued_events.append(event_type(*args, client=self.client))

    @asyncio.coroutine
    def fire_all(self):
        while self.queued_events:
            event = self.queued_events.popleft()
            yield from asyncio.wait(self.manager.fire(event))


@asyncio.coroutine
def test_uno_basic(loop, client, fake_server):
    poker = PluginPoker('uno', client=client)

    # Define the bot, and some players
    bot = Peer(client.nick, None, None)  # TODO should the client have this?
    channel = Channel('#uno')
    alice = Peer('alice', None, None)
    charles = Peer('charles', None, None)
    david = Peer('david', None, None)

    poker.queue(PublicMessage, alice, channel, client.nick + ': uno.start')
    yield from poker.fire_all()
    assert poker.data

    poker.queue(PublicMessage, charles, channel, client.nick + ': uno.join')
    poker.queue(PublicMessage, david, channel, client.nick + ': uno.join')
    yield from poker.fire_all()
    print(poker.data.per_channel)
    assert poker.data
