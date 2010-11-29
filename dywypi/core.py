#!/usr/bin/env python

from collections import namedtuple
import sys

from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.words.protocols import irc

nickname = 'dywypi2_0'
connection_specs = [
    ('irc.veekun.com', 6667, ['#bot']),
]


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

        # OK XXX do a bunch of command interpreting here whatever

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event, and to do its own encoding etc.
        response = u"you said `{0}`".format(command)
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


class DywypiConnection(ReconnectingClientFactory):
    protocol = DywypiClient

    def __init__(self, channels):
        self.channels = channels


if __name__ == '__main__':
    connections = []
    for host, port, channels in connection_specs:
        reactor.connectTCP(host, port, DywypiConnection(channels))

    log.startLogging(sys.stdout)
    reactor.run()
