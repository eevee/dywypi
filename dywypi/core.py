from collections import namedtuple
import shlex
import sys

from twisted.internet import reactor, protocol
from twisted.python import log
from twisted.words.protocols import irc

nickname = 'dywypi2_0'
encoding = 'utf8'


class Event(object):
    def __init__(self, peer, channel, _protocol, command, argv):
        # TODO need to look up protocol in case there's a reconnect
        self.peer = peer
        self.channel = channel
        self._protocol = _protocol

        self.command = command
        self.argv = argv

    def reply(self, *messages):
        """Reply to the source of the event."""
        # XXX not every event has a source
        # XXX oughta require unicode, or cast, or somethin

        if self.channel:
            prefix = self.peer.nick + ': '
            target = self.channel.name
        else:
            prefix = ''
            target = self.peer.nick

        for message in messages:
            # XXX
            message = message.encode('utf8')
            self._protocol.msg(target, prefix + message)

class CommandEvent(Event): pass

class MessageEvent(Event):
    def __init__(self, *args, **kwargs):
        self.message = kwargs.pop('message')

        super(MessageEvent, self).__init__(*args, **kwargs)

class PublicMessageEvent(MessageEvent): pass



# XXX REALLY REALLY NEED FIRST-CLASS VERSIONS OF SERVERS, CHANNELS, AND CONTEXT
class DywypiProtocol(irc.IRCClient):
    nickname = nickname

    @property
    def irc_network(self):
        return self.factory.irc_network

    @property
    def hub(self):
        return self.factory.hub


    ### EVENT HANDLERS

    def signedOn(self):
        for channel in self.irc_network.channels:
            self.join(channel.name)

    def joined(self, channel_name):
        self.irc_network.find_channel(channel_name).joined = True

    def privmsg(self, raw_user, channel_name, msg):
        peer = self.irc_network.find_peer(raw_user)

        if peer.is_server:
            return

        if channel_name[0] in '#&+':
            channel = self.irc_network.find_channel(channel_name)

            # In a channel, only direct addressing is a command
            if not msg.startswith(self.nickname + ': '):
                self.hub.fire(PublicMessageEvent(
                    peer, channel, self,
                    command=None, argv=None,
                    message=msg))
                return

            command_string = msg[len(self.nickname) + 2:]
        else:
            # In a private message, everything is aimed at us
            channel = None
            command_string = msg

        # Split the command into words, using shell-ish syntax
        tokens = [token.decode(encoding) for token in shlex.split(command_string)]
        command = tokens.pop(0)

        event = CommandEvent(
            peer, channel, self,
            command=command, argv=tokens)

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event.  right now we have "string of words is directed at bot"
        self.hub.run_command(command, event)

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
    protocol = DywypiProtocol

    def __init__(self, hub, irc_network):
        self.hub = hub
        self.irc_network = irc_network
