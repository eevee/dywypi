import asyncio
from asyncio.queues import Queue
import re


class IRCClientProtocol(asyncio.Protocol):
    def __init__(self, loop, password, charset='utf8'):
        self.password = password
        self.charset = charset

        self.buf = b''
        self.message_queue = Queue(loop=loop)
        self.registered = False

    def connection_made(self, transport):
        self.transport = transport
        print("connection made!!")

        # TODO maybe stick this bit in a coroutine?
        self.send_message('PASS', self.password)
        self.send_message('NICK', 'dywypi-eevee')
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
            print("recv:", repr(message))
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
        print("sent:", repr(message))
        self.transport.write(message.render().encode(self.charset) + b'\r\n')

    @asyncio.coroutine
    def read_message(self):
        return (yield from self.message_queue.get())


class IRCClient:
    def __init__(self, host, port, *, ssl, password=None):
        self.host = host
        self.port = port
        self.ssl = ssl
        self.password = password

    @asyncio.coroutine
    def connect(self, loop):
        _, self.proto = yield from loop.create_connection(
            lambda: IRCClientProtocol(loop, password=self.password),
            self.host, self.port, ssl=self.ssl)

        return self

    @asyncio.coroutine
    def read_message(self):
        return (yield from self.proto.read_message())


class Message:
    def __init__(self, command, *args, prefix=None):
        # TODO command can't be a number when coming from a client
        self.command = command
        self.prefix = prefix
        self.args = args

        # TODO stricter validation: all str (?), last arg...

    def __repr__(self):
        return "<{name}: {command} {args}>".format(
            name=type(self).__name__,
            command=self.command,
            args=', '.join(repr(arg) for arg in self.args),
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
