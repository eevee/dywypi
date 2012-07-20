from collections import namedtuple
import shlex
import sys

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.words.protocols import irc

nickname = 'dywypi2_0'
encoding = 'utf8'

# TODO make Event and CommandEvent and dispatch that
# TODO this context thinger should probably be part of the dywypi service; nothing should stick to the client/factory
class IRCContext(object):
    def __init__(self, name, ident, host, channel):
        self.name = name
        self.ident = ident
        self.host = host
        self.channel = channel

    @classmethod
    def parse(cls, raw_user, channel):
        # XXX is the username actually supposed to be decoded?  does it have to
        # be ascii?
        # Three possible contexts: server message, user message in channel,
        # direct private message.
        if '!' in raw_user:
            name, usermask = raw_user.split('!', 1)
            ident, host = usermask.split('@', 1)
        else:
            name = raw_user
            ident = host = None

        if not channel.startswith('#'):
            channel = None

        return cls(name, ident, host, channel)

    @property
    def is_server(self):
        return self.host is None


# XXX REALLY REALLY NEED FIRST-CLASS VERSIONS OF SERVERS, CHANNELS, AND CONTEXT
class DywypiClient(irc.IRCClient):
    nickname = nickname

    ### EVENT HANDLERS

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)

    def privmsg(self, raw_user, channel, msg):
        ctx = IRCContext.parse(raw_user, channel)
        if ctx.is_server:
            return

        if ctx.channel:
            # In a channel, only accept direct addressing
            if not msg.startswith(self.nickname + ': '):
                return

            command_string = msg[len(self.nickname) + 2:]
            def respond(response):
                self.msg(channel, self._encode(u"{0}: {1}".format(ctx.name, response)))
        else:
            # In a private message, everything is aimed at us
            command_string = msg
            def respond(response):
                self.msg(
                    self._encode(ctx.name),
                    self._encode(response),
                )

        # Split the command into words, using shell-ish syntax
        tokens = [token.decode(encoding) for token in shlex.split(command_string)]
        command = tokens.pop(0)

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event.  right now we have "string of words is directed at bot"
        response = self.factory.service.dispatch_event(
            responder=respond, command=command, args=tokens)

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


class DywypiFactory(protocol.ReconnectingClientFactory):
    protocol = DywypiClient

    def __init__(self, service, channels):
        self.service = service
        self.channels = channels
