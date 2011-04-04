#!/usr/bin/env python

from collections import namedtuple
import shlex
import sys

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.words.protocols import irc

from dywypi.plugin_api import PluginRegistry

nickname = 'dywypi2_0'
connection_specs = [
    ('irc.veekun.com', 6667, ['#bot']),
]
encoding = 'utf8'
plugin_registry = None


class DywypiClient(irc.IRCClient):
    nickname = nickname

    ### EVENT HANDLERS

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)

    def privmsg(self, raw_user, channel, msg):
        # XXX gross
        if '!' not in raw_user:
            return

        user = self._parse_user(raw_user)
        # First see if this is actually aimed at us
        command = None

        if channel.startswith('#'):
            context = 'channel'
            # In a channel, only accept direct addressing
            if msg.startswith(self.nickname + ': '):
                command = msg[len(self.nickname) + 2:]
        else:
            context = 'privmsg'
            # In a private message, everything is aimed at us
            command = msg

        if not command:
            # Nothing to do here
            return

        # Split the command into words, using shell-ish syntax
        tokens = [token.decode(encoding) for token in shlex.split(command)]

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event.  right now we have "string of words is directed at bot"
        response = plugin_registry.run_command(tokens[0], tokens[1:])
        if context == 'channel':
            self.msg(channel, u"{0}: {1}".format(user.nickname, response).encode('utf8'))
        else:
            self.msg(user.nickname.encode('utf8'), response.encode('utf8'))

        # Done
        return

    ### INTERNAL METHODS

    def _decode(self, s):
        """Returns `s`, cleverly decoded into a unicode object."""
        # TODO  :(  at least implement xchat-style "utf8 or latin1"
        return s.decode('utf8')

    user_tuple = namedtuple('user_tuple', ['nickname', 'ident', 'host'])
    def _parse_user(self, raw_user):
        """Parses a user identifier like a!b@c and returns a namedtuple of
        nickname, ident, and host.

        Also takes care of the decoding.
        """
        log.err(raw_user)
        nickname, remainder = self._decode(raw_user).split('!', 2)
        ident, host = remainder.split('@', 2)
        return self.user_tuple(nickname, ident, host)


class DywypiFactory(protocol.ReconnectingClientFactory):
    protocol = DywypiClient

    def __init__(self, channels):
        self.channels = channels


if __name__ == '__main__':
    # XXX uhh should probably make this an Application and run under twistd,
    # then add the registry to that
    plugin_registry = PluginRegistry()
    plugin_registry.discover_plugins()
    plugin_registry.load_plugin('echo')
    plugin_registry.load_plugin('fyi')

    connections = []
    for host, port, channels in connection_specs:
        reactor.connectTCP(host, port, DywypiFactory(channels))

    log.startLogging(sys.stdout)
    reactor.run()
