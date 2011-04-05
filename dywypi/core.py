#!/usr/bin/env python

from collections import namedtuple
import shlex
import sys

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.words.protocols import irc

nickname = 'dywypi2_0'
connection_specs = [
    ('irc.veekun.com', 6667, ['#bot']),
]
encoding = 'utf8'

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

        if context == 'channel':
            def respond(response):
                self.msg(channel, self._encode(u"{0}: {1}".format(user.nickname, response)))
        else:
            def respond(response):
                self.msg(
                    self._encode(user.nickname),
                    self._encode(response),
                )

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event.  right now we have "string of words is directed at bot"
        response = self.factory.service.dispatch_event(
            responder=respond, command=tokens[0], args=tokens[1:])

        return

    ### INTERNAL METHODS

    def _decode(self, s):
        """Returns `s`, cleverly decoded into a unicode object."""
        # TODO  :(  at least implement xchat-style "utf8 or latin1"
        return s.decode('utf8')

    def _encode(self, s):
        """Returns `s`, encoded into what is probably the channel's encoding.
        """
        # TODO encoding per channel?
        return s.encode('utf8')

    user_tuple = namedtuple('user_tuple', ['nickname', 'ident', 'host'])
    def _parse_user(self, raw_user):
        """Parses a user identifier like a!b@c and returns a namedtuple of
        nickname, ident, and host.

        Also takes care of the decoding.
        """
        # XXX is the username actually supposed to be decoded?  does it have to
        # be ascii?
        log.err(raw_user)
        nickname, remainder = self._decode(raw_user).split('!', 2)
        ident, host = remainder.split('@', 2)
        return self.user_tuple(nickname, ident, host)


class DywypiFactory(protocol.ReconnectingClientFactory):
    protocol = DywypiClient

    def __init__(self, service, channels):
        self.service = service
        self.channels = channels
