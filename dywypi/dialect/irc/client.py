import asyncio
from asyncio.queues import Queue
from datetime import datetime
import getpass

from dywypi.event import Message
from dywypi.state import Peer
from .protocol import IRCClientProtocol
from .state import IRCChannel
from .state import IRCTopic


class IRCClient:
    """Higher-level IRC client.  Takes care of most of the hard parts of IRC:
    incoming server messages are bundled into more intelligible events (see
    ``dywypi.event``), and commands that expect replies are implemented as
    coroutines.
    """

    def __init__(self, loop, network):
        self.loop = loop
        self.network = network

        self.joined_channels = {}  # name => Channel
        self.pending_joins = {}
        self.pending_channels = {}
        self.pending_names = {}

        self.event_queue = Queue(loop=loop)

    def get_channel(self, channel_name):
        """Returns a `Channel` object containing everything the client
        definitively knows about the given channel.

        Note that if you, say, ask for the topic of a channel you aren't in and
        then immediately call `get_channel`, the returned object won't have its
        topic populated.  State is only tracked persistently for channels the
        bot is in; otherwise there's no way to know whether or not it's stale.
        """
        if channel_name in self.joined_channels:
            return self.joined_channels[channel_name]
        else:
            return IRCChannel(self, channel_name)

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
            yield from self._read_message()
            if self.proto.registered:
                break

        # Start the event loop as soon as we've synched, or we can't respond to
        # anything
        asyncio.async(self._advance(), loop=self.loop)

        # Initial joins
        yield from asyncio.gather(*[
            self.join(channel_name)
            for channel_name in self.network.autojoins
        ], loop=self.loop)

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

        # Boy do I ever hate this pattern but it's slightly more maintainable
        # than a 500-line if tree.
        handler = getattr(self, '_handle_' + message.command, None)
        if handler:
            handler(message)

    def _handle_JOIN(self, message):
        channel_name, = message.args
        joiner = Peer.from_prefix(message.prefix)
        # TODO should there be a self.me?  how...
        if joiner.name == self.nick:
            # We just joined a channel
            #assert channel_name not in self.joined_channels
            # TODO key?  do we care?
            # TODO what about channel configuration and anon non-joined
            # channels?  how do these all relate...
            channel = IRCChannel(self, channel_name)
            self.joined_channels[channel.name] = channel
        else:
            # Someone else just joined the channel
            self.joined_channels[channel_name].add_user(joiner)

    def _handle_332(self, message):
        # Topic.  Sent when joining or when requesting the topic.
        # TODO this doesn't handle the "requesting" part
        # TODO what if me != me?
        me, channel, topic = message.args
        if channel in self.pending_channels:
            self.pending_channels[channel]['topic'] = topic

    def _handle_333(self, message):
        # Topic author (NONSTANDARD).  Sent after 332.
        # TODO this doesn't handle the "requesting" part
        # TODO what if me != me?
        me, channel, author, timestamp = message.args
        if channel in self.pending_channels:
            self.pending_channels[channel]['topic_author'] = Peer.from_prefix(author)
            self.pending_channels[channel]['topic_timestamp'] = datetime.utcfromtimestamp(int(timestamp))

    def _handle_353(self, message):
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

    def _handle_366(self, message):
        # End of names list.  Sent at the very end of a join or the very
        # end of a NAMES request.
        me, channel_name, info = message.args
        if channel_name in self.pending_channels:
            # Join synchronized!
            if channel_name in self.joined_channels:
                channel = self.joined_channels[channel_name]
            else:
                channel = IRCChannel(channel_name, None)
            p = self.pending_channels.pop(channel_name, {})
            # We don't receive a RPL_TOPIC if the topic has never been set
            if 'topic' in p:
                channel.topic = IRCTopic(
                    p['topic'],
                    # These are nonstandard and thus optional
                    p.get('topic_author'),
                    p.get('topic_timestamp'),
                )

            for name in p.get('names', ()):
                modes = set()
                # TODO use features!
                while name and name[0] in '+%@&~':
                    modes.append(name[0])
                    name = name[1:]

                # TODO haha no this is so bad.
                # TODO the bot should, obviously, keep a record of all
                # known users as well.  alas, mutable everything.
                peer = Peer(name, None, None)

                channel.add_user(peer, modes)

            if channel_name in self.pending_joins:
                # Record the join
                self.joined_channels[channel_name] = channel

                # Update the Future
                self.pending_joins[channel_name].set_result(channel)
                del self.pending_joins[channel_name]

            elif channel_name in self.pending_names:
                # TODO these should not EVER both be true at once;
                # rearchitect to enforce that
                self.pending_names[channel_name].set_result(channel.names)
                del self.pending_names[channel_name]

    def _handle_PRIVMSG(self, message):
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
