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

    def source_from_message(self, raw_message):
        return Peer.from_prefix(raw_message.prefix)



def test_echo(loop):
    manager = PluginManager()
    manager.scan_package('dywypi.plugins')
    manager.load('echo')
    assert 'echo' in manager.loaded_plugins

    # TODO really this should work with a not-irc-specific raw message.  or
    # maybe it shouldn't take a raw message arg at all.  i'm not sure what i
    # think of the whole raw-message mess.  i suppose with source_from_message
    # i could just make this an arbitrary object?
    # TODO this would be much easier if i could just pump messages into
    # somewhere and get them out of somewhere else.  even have an IRC proto on
    # both ends!  wow that sounds like a great idea too.
    client = DummyClient(loop)
    client.nick = 'dywypi'
    ev = Message(
        client,
        IRCMessage('PRIVMSG', 'dywypi', 'dywypi: echo foo', prefix='nobody!ident@host'),
    )

    loop.run_until_complete(asyncio.gather(*manager.fire(ev), loop=loop))

    assert client.accumulated_messages == [('nobody', 'foo')]
