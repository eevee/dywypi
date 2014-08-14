import asyncio

from dywypi.event import PublicMessage
from dywypi.plugin import PluginManager
from dywypi.state import Channel
from dywypi.state import Peer


@asyncio.coroutine
def test_uno_basic(loop, client, fake_server):
    manager = PluginManager()
    manager.scan_package('dywypi.plugins')
    manager.load('uno')
    assert 'uno' in manager.loaded_plugins
    plugin = manager.loaded_plugins['uno']
    data = manager.plugin_data[plugin]

    # Define the bot, and some players
    bot = Peer(client.nick, None, None)  # TODO should the client have this?
    channel = Channel('#uno')
    alice = Peer('alice', None, None)
    charles = Peer('charles', None, None)
    david = Peer('david', None, None)

    yield from asyncio.wait(manager.fire(
        PublicMessage(alice, channel, client.nick + ': uno.start', client=client)
    ))

    assert data
