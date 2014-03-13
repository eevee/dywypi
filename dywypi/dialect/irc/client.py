import asyncio
from asyncio.queues import Queue
import getpass

from dywypi.event import Message
from .protocol import IRCClientProtocol


class IRCClient:
    """Higher-level IRC client.  Takes care of most of the hard parts of IRC:
    incoming server messages are bundled into more intelligible events (see
    ``dywypi.event``), and commands that expect replies are implemented as
    coroutines.
    """

    def __init__(self, loop, network):
        self.loop = loop
        self.network = network

        self.pending_joins = {}
        self.pending_channels = {}
        self.pending_names = {}

        self.event_queue = Queue(loop=loop)

    @asyncio.coroutine
    def connect(self):
        """Coroutine for connecting to a single server.

        Note that this will nonblock until the client is "registered", defined
        as the first PING/PONG exchange.
        """
        # TODO this is a poor excuse for round-robin  :)
        server = self.current_server = self.network.servers[0]

        # TODO i'm pretty sure the server tells us what our nick is, and we
        # should believe that instead
        self.nick = self.network.preferred_nick

        # TODO: handle disconnection, somehow.  probably affects a lot of
        # things.
        _, self.proto = yield from self.loop.create_connection(
            lambda: IRCClientProtocol(
                self.loop, self.network.preferred_nick, password=server.password),
            server.host, server.port, ssl=server.tls)

        while True:
            message = yield from self._read_message()
            if self.proto.registered:
                break

        # Initial joins
        for channel_name in self.network.autojoins:
            # TODO are you telling me there's no .join() yet or
            self.proto.send_message('JOIN', channel_name)

        asyncio.async(self._advance(), loop=self.loop)

    @asyncio.coroutine
    def _advance(self):
        """Internal coroutine that just keeps the protocol message queue going.
        Called once after a connect and should never be called again after
        that.
        """
        # TODO this is currently just to keep the message queue going, but
        # eventually it should turn them into events and stuff them in an event
        # queue
        yield from self._read_message()

        asyncio.async(self._advance(), loop=self.loop)

    @asyncio.coroutine
    def _read_message(self):
        """Internal dispatcher for messages received from the protocol."""
        message = yield from self.proto.read_message()

        if message.command == 'JOIN':
            channel_name, = message.args
            self.pending_channels[channel_name] = {}

        elif message.command == '332':
            # Topic.  Sent when joining or when requesting the topic.
            # TODO this doesn't handle the "requesting" part
            # TODO what if me != me?
            me, channel, topic = message.args
            if channel in self.pending_channels:
                self.pending_channels[channel]['topic'] = topic

        elif message.command == '333':
            # Topic author (NONSTANDARD).  Sent after 332.
            # TODO this doesn't handle the "requesting" part
            # TODO what if me != me?
            me, channel, author, timestamp = message.args
            if channel in self.pending_channels:
                self.pending_channels[channel]['topic_author'] = author
                self.pending_channels[channel]['topic_timestamp'] = int(timestamp)

        elif message.command == '353':
            # Names response.  Sent when joining or when requesting a names
            # list.  Must be ended with a 366.
            me, equals_sign_for_some_reason, channel, *raw_names = message.args
            if raw_names:
                raw_names = raw_names[0]
            else:
                raw_names = ''
            # TODO modes
            # TODO this doesn't handle the "requesting" part
            # TODO how does this work if it's responding to /names and there'll
            # be multiple lines?
            names = raw_names.strip(' ').split(' ')
            # TODO these can't BOTH be true at the same time
            if channel in self.pending_channels:
                self.pending_channels[channel]['names'] = names

        elif message.command == '366':
            # End of names list.  Sent at the very end of a join or the very
            # end of a names request.
            me, channel_name, info = message.args
            if channel_name in self.pending_channels:
                # Join synchronized!
                from dywypi.state import Channel
                channel = Channel(channel_name, None)
                p = self.pending_channels[channel_name]
                channel.topic = p.get('topic')
                channel.topic_author = p.get('topic_author')
                channel.topic_timestamp = p.get('topic_timestamp')
                channel.names = p.get('names')

                # TODO might be from a names, in which case don't do that.
                #self.channels[channel_name] = channel

                if channel_name in self.pending_joins:
                    self.pending_joins[channel_name].set_result(channel)
                    del self.pending_joins[channel_name]

                elif channel_name in self.pending_names:
                    # TODO these should not EVER both be true at once;
                    # rearchitect to enforce that
                    self.pending_names[channel_name].set_result(channel.names)
                    del self.pending_names[channel_name]

        elif message.command == 'PRIVMSG':
            event = Message(self, message)
            self.event_queue.put_nowait(event)

    @asyncio.coroutine
    def read_event(self):
        """Produce a single IRC event.

        This client does not do any kind of multiplexing or event handler
        notification; that's left to a higher level.
        """
        return (yield from self.event_queue.get())


    # Implementations of particular commands

    def join(self, channel, key=None):
        """Coroutine that joins a channel, and nonblocks until the join is
        "synchronized" (defined as receiving the nick list).
        """
        # TODO multiple?  error on commas?
        if key is None:
            self.proto.send_message('JOIN', channel)
        else:
            self.proto.send_message('JOIN', channel, key)

        # The good stuff is done by read_message, above...

        self.pending_channels[channel] = {}
        fut = asyncio.Future()
        self.pending_joins[channel] = fut
        return fut

    def names(self, channel):
        """Coroutine that returns a list of names in a channel."""
        self.proto.send_message('NAMES', channel)

        self.pending_channels[channel] = {}
        fut = asyncio.Future()
        self.pending_names[channel] = fut
        return fut

    def set_topic(self, channel, topic):
        """Sets the channel topic."""
        self.proto.send_message('TOPIC', channel, topic)

    @asyncio.coroutine
    def send_message(self, command, *args):
        self.proto.send_message(command, *args)
