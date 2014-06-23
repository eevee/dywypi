import asyncio

from dywypi.dialect.irc.message import IRCMessage
from dywypi.event import Message
from dywypi.plugin import PluginManager
from dywypi.state import Peer


class DummyClient:
    def __init__(self, loop):
        self.loop = loop

        self.accumulated_messages = []

    def say(self, target, message):
        self.accumulated_messages.append((target, message))
        yield


def test_echo(loop):
    manager = PluginManager()
    manager.scan_package('dywypi.plugins')
    manager.load('echo')
    assert 'echo' in manager.loaded_plugins

    # TODO this would be much easier if i could just pump messages into
    # somewhere and get them out of somewhere else.  even have an IRC proto on
    # both ends!  wow that sounds like a great idea too.
    client = DummyClient(loop)
    client.nick = 'dywypi'
    ev = Message(
        Peer.from_prefix('nobody!ident@host'),
        Peer('dywypi', None, None),
        'dywypi: echo foo',
        client=client,
    )

    loop.run_until_complete(asyncio.gather(*manager.fire(ev), loop=loop))

    assert client.accumulated_messages == [('nobody', 'foo')]
