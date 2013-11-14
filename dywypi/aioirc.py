import asyncio
from asyncio.queues import Queue
import logging
import re

logger = logging.getLogger(__name__)


class IRCClientProtocol(asyncio.Protocol):
    def __init__(self, loop, nick_prefix, password, charset='utf8'):
        self.nick = 'dywypi-' + nick_prefix
        self.password = password
        self.charset = charset

        self.buf = b''
        self.message_queue = Queue(loop=loop)
        self.registered = False

    def connection_made(self, transport):
        self.transport = transport

        # TODO maybe stick this bit in a coroutine?
        self.send_message('PASS', self.password)
        self.send_message('NICK', self.nick)
        self.send_message('USER', 'dywypi', '-', '-', 'dywypi Python IRC bot')

    def data_received(self, data):
        data = self.buf + data
        while True:
            raw_message, delim, data = data.partition(b'\r\n')
            if not delim:
                # Incomplete message; stop here and wait for more
                self.buf = raw_message
                return

            # TODO valerr
            message = Message.parse(raw_message.decode(self.charset))
            logger.debug("recv: %r", message)
            self.handle_message(message)

    def handle_message(self, message):
        if message.command == 'PING':
            self.send_message('PONG', message.args[-1])
            if not self.registered:
                self.registered = True
                self.send_message('JOIN', '#dywypi')

        self.message_queue.put_nowait(message)

    def send_message(self, command, *args):
        message = Message(command, *args)
        logger.debug("sent: %r", message)
        self.transport.write(message.render().encode(self.charset) + b'\r\n')

    @asyncio.coroutine
    def read_message(self):
        return (yield from self.message_queue.get())


class IRCClient:
    def __init__(self, host, port, nick_prefix, *, ssl, password=None):
        self.host = host
        self.port = port
        self.nick_prefix = nick_prefix
        self.ssl = ssl
        self.password = password

        self.pending_joins = {}
        self.pending_channels = {}

    @asyncio.coroutine
    def connect(self, loop):
        self.loop = loop

        _, self.proto = yield from loop.create_connection(
            lambda: IRCClientProtocol(loop, self.nick_prefix, password=self.password),
            self.host, self.port, ssl=self.ssl)

        while True:
            message = yield from self.read_message()
            if self.proto.registered:
                break

        asyncio.async(self.advance(), loop=self.loop)

    @asyncio.coroutine
    def advance(self):
        # TODO this is currently just to keep the message queue going, but
        # eventually it should turn them into events and stuff them in an event
        # queue
        yield from self.read_message()

        asyncio.async(self.advance(), loop=self.loop)

    @asyncio.coroutine
    def read_message(self):
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
            me, equals_sign_for_some_reason, channel, raw_names = message.args
            # TODO modes
            # TODO this doesn't handle the "requesting" part
            # TODO how does this work if it's responding to /names and there'll
            # be multiple lines?
            names = raw_names.strip(' ').split(' ')
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

                #self.channels[channel_name] = channel

                if channel_name in self.pending_joins:
                    self.pending_joins[channel_name].set_result(channel)
                    del self.pending_joins[channel_name]


    # Implementations of particular commands

    def join(self, channel, key=None):
        # TODO multiple?  error on commas?
        if key is None:
            self.proto.send_message('JOIN', channel)
        else:
            self.proto.send_message('JOIN', channel, key)

        # The good stuff is done by read_message, above...

        self.pending_channels[channel] = {}
        fut = asyncio.Future()
        return fut

    @asyncio.coroutine
    def send_message(self, command, *args):
        self.proto.send_message(command, *args)

class Message:
    def __init__(self, command, *args, prefix=None):
        # TODO command can't be a number when coming from a client
        self.command = command
        self.prefix = prefix
        self.args = args

        # TODO stricter validation: all str (?), last arg...

    def __repr__(self):
        prefix = ''
        if self.prefix:
            prefix = " via {}".format(self.prefix)

        return "<{name}: {command} {args}{prefix}>".format(
            name=type(self).__name__,
            command=self.command,
            args=', '.join(repr(arg) for arg in self.args),
            prefix=prefix,
        )

    def render(self):
        parts = [self.command] + list(self.args)
        # TODO assert no spaces
        # TODO assert nothing else begins with colon!
        if self.args and ' ' in parts[-1]:
            parts[-1] = ':' + parts[-1]

        return ' '.join(parts)

    PATTERN = re.compile(
        r'''\A
        (?: : (?P<prefix>[^ ]+) [ ]+ )?
        (?P<command> \d{3} | [a-zA-Z]+ )
        (?P<args>
            (?: [ ]+ [^: \x00\r\n][^ \x00\r\n]* )*
        )
        (?:
            [ ]+ [:] (?P<trailing> [^\x00\r\n]*)
        )?
        [ ]*
        \Z''',
        flags=re.VERBOSE)

    @classmethod
    def parse(cls, string):
        # TODO uhhh what happens with encodings here.  ascii command, arbitrary
        # encoding for everything else?
        m = cls.PATTERN.match(string)
        if not m:
            raise ValueError(repr(string))

        argstr = m.group('args').lstrip(' ')
        if argstr:
            args = re.split(' +', argstr)
        else:
            args = []

        if m.group('trailing'):
            args.append(m.group('trailing'))

        return cls(m.group('command'), *args, prefix=m.group('prefix'))


class Event:
    """Something happened."""
    def __init__(self, message):
        self.message = message
