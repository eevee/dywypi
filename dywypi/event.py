from collections import namedtuple

"""Covenience container for the 'source' of an event -- who fired it and
where."""
EventSource = namedtuple('EventSource', ['network', 'peer', 'channel'])

class Event(object):
    """Base class for a fired event.  Event objects act as a conduit between
    plugin code and dywypi core: they contain interesting state of the event
    and expose methods for communicating with the network.
    """
    def __init__(self, hub, source):
        self.hub = hub
        self.network = source.network
        self.peer = source.peer
        self.channel = source.channel

        # ok so an event OR command may be fired:
        # - on a network
        # - [optionally] in a channel
        # - by a peer
        # OR...
        # - from the shell.
        # OR...
        # - from the web interface.
        # OR...
        # - via jabber or something.
        # TODO need to look up protocol in case there's a reconnect

    def find_protocol(self):
        # TODO make me a deferred so i work even when disconnected
        return self.hub.protocol_for_network(self.network)

    # TODO these need to operate on a dialect-specific thing.  can i get from a
    # network/protocol to such an implementation?

    def reply(self, *messages):
        """Reply to the source of the event."""
        protocol = self.find_protocol()
        # XXX not every event may have a source i think
        # XXX e.g., what does replying to a system message like PING mean?

        if self.channel:
            prefix = self.peer.name + ': '
            target = self.channel
        else:
            prefix = ''
            target = self.peer

        for message in messages:
            # XXX
            message = message.encode('utf8')
            protocol._send_message(target, prefix + message, as_notice=False)

    def say(self, *messages):
        """Say something wherever the event occurred."""
        protocol = self.find_protocol()

        if self.channel:
            target = self.channel
        else:
            target = self.peer

        for message in messages:
            # XXX belongs to the protocol imo
            message = message.encode('utf8')
            protocol._send_message(target, message, as_notice=False)

    def send_message(self, target, message, as_notice=True):
        protocol = self.find_protocol()
        protocol._send_message(target, message, as_notice=as_notice)

    # TODO there also need to be dialect-specific IRC-like operations attached
    # here!


class CommandEvent(Event):
    def __init__(self, hub, source, command, argv):
        super(CommandEvent, self).__init__(hub, source)
        self.command = command
        self.argv = argv

class MessageEvent(Event):
    def __init__(self, *args, **kwargs):
        self.message = kwargs.pop('message')

        super(MessageEvent, self).__init__(*args, **kwargs)

class PublicMessageEvent(MessageEvent): pass
