import asyncio
from asyncio.queues import Queue
from datetime import datetime
import getpass

from dywypi.event import Message
from dywypi.formatting import Bold, Color, Style
from dywypi.state import Peer
from .protocol import IRCClientProtocol
from .state import IRCChannel
from .state import IRCMode
from .state import IRCTopic


FOREGROUND_CODES = {
    Color.white: '\x0300',
    Color.black: '\x0301',
    Color.navy: '\x0302',
    Color.green: '\x0303',
    Color.red: '\x0304',
    Color.darkred: '\x0305',
    Color.purple: '\x0306',
    Color.brown: '\x0307',  # actually orange, close enough
    Color.yellow: '\x0308',
    Color.lime: '\x0309',
    Color.teal: '\x0310',
    Color.cyan: '\x0311',
    Color.blue: '\x0312',
    Color.magenta: '\x0313',
    Color.darkgray: '\x0314',
    Color.gray: '\x0315',
}


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

        # IRC server features, as reported by ISUPPORT, with defaults taken
        # from the RFC.
        self.len_nick = 9
        self.len_channel = 200
        self.len_message = 510
        # These lengths don't have limits mentioned in the RFC, so going with
        # the smallest known values in the wild
        self.len_kick = 80
        self.len_topic = 80
        self.len_away = 160
        self.max_watches = 0
        self.max_targets = 1
        self.channel_types = set('#&')
        self.channel_modes = {}  # TODO, haha.
        self.channel_prefixes = {}  # TODO here too.  IRCMode is awkward.
        self.network_title = self.network.name
        self.features = {}

        # Various intermediate state used for waiting for replies and
        # aggregating multi-part replies
        # TODO hmmm so what happens if state just gets left here forever?  do
        # we care?
        self._pending_names = {}
        self._names_futures = {}
        self._pending_topics = {}
        self._join_futures = {}

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
        # TODO kind of wish this weren't here, since the creation of the
        # connection isn't inherently part of a client.  really it should be on
        # the...  network, perhaps?  and there's no reason i shouldn't be able
        # to "connect" to a unix socket or pipe or anywhere else that has data.
        self.proto = yield from IRCClientProtocol.connect_tcp(
            self.loop, self.network.preferred_nick, server)

        while True:
            yield from self._read_message()
            # TODO this is dumb garbage; more likely this client itself should
            # just wait for 001/RPL_WELCOME.
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
    def disconnect(self):
        self.proto.send_message('QUIT', 'Seeya!')
        yield from self.proto.writer.drain()
        self.proto.writer.close()
        # TODO wait until reader gets eof?

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

        # TODO there is a general ongoing problem here with matching up
        # responses.  ESPECIALLY when error codes are possible.  something here
        # is gonna have to get a bit fancier.  maybe it should live at the
        # protocol level, actually...?

        # Boy do I ever hate this pattern but it's slightly more maintainable
        # than a 500-line if tree.
        handler = getattr(self, '_handle_' + message.command, None)
        if handler:
            handler(message)

    def _handle_RPL_ISUPPORT(self, message):
        me, *features, human_text = message.args
        for feature_string in features:
            feature, _, value = feature_string.partition('=')
            if value is None:
                value = True

            self.features[feature] = value

            if feature == 'NICKLEN':
                self.len_nick = int(value)
            elif feature == 'CHANNELLEN':
                self.len_channel = int(value)
            elif feature == 'KICKLEN':
                self.len_kick = int(value)
            elif feature == 'TOPICLEN':
                self.len_topic = int(value)
            elif feature == 'AWAYLEN':
                self.len_away = int(value)
            elif feature == 'WATCH':
                self.max_watches = int(value)
            elif feature == 'CHANTYPES':
                self.channel_types = set(value)
            elif feature == 'PREFIX':
                # List of channel user modes, in relative priority order, in
                # the format (ov)@+
                assert value[0] == '('
                letters, symbols = value[1:].split(')')
                assert len(letters) == len(symbols)
                self.channel_prefixes.clear()
                for letter, symbol in zip(letters, symbols):
                    mode = IRCMode(letter, prefix=symbol)
                    self.channel_modes[letter] = mode
                    self.channel_prefixes[symbol] = mode
            elif feature == 'MAXTARGETS':
                self.max_targets = int(value)
            elif feature == 'CHANMODES':
                # Four groups delimited by lists: list-style (+b), arg required
                # (+k), arg required only to set (+l), argless
                lists, args, argsets, argless = value.split(',')
                for letter in lists:
                    self.channel_modes[letter] = IRCMode(
                        letter, multi=True)
                for letter in args:
                    self.channel_modes[letter] = IRCMode(
                        letter, arg_on_set=True, arg_on_remove=True)
                for letter in argsets:
                    self.channel_modes[letter] = IRCMode(
                        letter, arg_on_set=True)
                for letter in argless:
                    self.channel_modes[letter] = IRCMode(letter)
            elif feature == 'NETWORK':
                self.network_title = value

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

    def _handle_RPL_TOPIC(self, message):
        # Topic.  Sent when joining or when requesting the topic.
        # TODO this doesn't handle the "requesting" part
        # TODO what if me != me?
        me, channel_name, topic_text = message.args
        self._pending_topics[channel_name] = IRCTopic(topic_text)

    def _handle_RPL_TOPICWHOTIME(self, message):
        # Topic author (NONSTANDARD).  Sent after RPL_TOPIC.
        # Unfortunately, there's no way to know whether to expect this.
        # TODO this doesn't handle the "requesting" part
        # TODO what if me != me?
        me, channel_name, author, timestamp = message.args
        topic = self._pending_topics.setdefault(channel_name, IRCTopic(''))
        topic.author = Peer.from_prefix(author)
        topic.timestamp = datetime.utcfromtimestamp(int(timestamp))

    def _handle_RPL_NAMREPLY(self, message):
        # Names response.  Sent when joining or when requesting a names
        # list.  Must be ended with a RPL_ENDOFNAMES.
        me, useless_equals_sign, channel_name, *raw_names = message.args
        # List of names is actually optional (?!)
        if raw_names:
            raw_names = raw_names[0]
        else:
            raw_names = ''

        names = raw_names.strip(' ').split(' ')
        namelist = self._pending_names.setdefault(channel_name, [])
        # TODO modes?  should those be stripped off here?
        # TODO for that matter should these become peers here?
        namelist.extend(names)

    def _handle_RPL_ENDOFNAMES(self, message):
        # End of names list.  Sent at the very end of a join or the very
        # end of a NAMES request.
        me, channel_name, info = message.args
        namelist = self._pending_names.pop(channel_name, [])

        if channel_name in self._names_futures:
            # TODO we should probably not ever have a names future AND a
            # pending join at the same time.  or, does it matter?
            self._names_futures[channel_name].set_result(namelist)
            del self._names_futures[channel_name]

        if channel_name in self.joined_channels:
            # Join synchronized!
            channel = self.joined_channels[channel_name]
            channel.sync = True

            channel.topic = self._pending_topics.pop(channel_name, None)

            for name in namelist:
                modes = set()
                # TODO use features!
                while name and name[0] in '+%@&~':
                    modes.add(name[0])
                    name = name[1:]

                # TODO haha no this is so bad.
                # TODO the bot should, obviously, keep a record of all
                # known users as well.  alas, mutable everything.
                peer = Peer(name, None, None)

                channel.add_user(peer, modes)

            if channel_name in self._join_futures:
                # Update the Future
                self._join_futures[channel_name].set_result(channel)
                del self._join_futures[channel_name]

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

    # TODO should this be part of the general client interface, or should there
    # be a separate thing that smooths out the details?
    @asyncio.coroutine
    def say(self, target, message):
        """Coroutine that sends a message to a target, which may be either a
        `Channel` or a `Peer`.
        """
        yield from self.send_message('PRIVMSG', target, message)

    def join(self, channel_name, key=None):
        """Coroutine that joins a channel, and nonblocks until the join is
        "synchronized" (defined as receiving the nick list).
        """
        if channel_name in self._join_futures:
            return self._join_futures[channel_name]

        # TODO multiple?  error on commas?
        if key is None:
            self.proto.send_message('JOIN', channel_name)
        else:
            self.proto.send_message('JOIN', channel_name, key)

        # Clear out any lingering names list
        self._pending_names[channel_name] = []

        # Return a Future, to be populated by the message loop
        fut = self._join_futures[channel_name] = asyncio.Future()
        return fut

    def names(self, channel_name):
        """Coroutine that returns a list of names in a channel."""
        self.proto.send_message('NAMES', channel_name)

        # No need to do the same thing twice
        if channel_name in self._names_futures:
            return self._names_futures[channel_name]

        # Clear out any lingering names list
        self._pending_names[channel_name] = []

        # Return a Future, to be populated by the message loop
        fut = self._names_futures[channel_name] = asyncio.Future()
        return fut

    def set_topic(self, channel, topic):
        """Sets the channel topic."""
        self.proto.send_message('TOPIC', channel, topic)

    @asyncio.coroutine
    def send_message(self, command, *args):
        self.proto.send_message(command, *args)

    def format_transition(self, current_style, new_style):
        if new_style == Style.default():
            # Reset code, ^O
            return '\x0f'

        if new_style.fg != current_style.fg and new_style.fg is Color.default:
            # IRC has no "reset to default" code.  mIRC claims color 99 is for
            # this, but it lies, at least in irssi.  So we must reset and
            # reapply everything.
            ret = '\x0f'
            if new_style.bold is Bold.on:
                ret += '\x02'
            return ret

        ret = ''
        if new_style.fg != current_style.fg:
            ret += FOREGROUND_CODES[new_style.fg]

        if new_style.bold != current_style.bold:
            # There's no on/off for bold, just a toggle
            ret += '\x02'

        return ret
