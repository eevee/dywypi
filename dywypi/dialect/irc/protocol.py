import asyncio
from asyncio.queues import Queue
import logging
import re

logger = logging.getLogger(__name__)


class IRCClientProtocol(asyncio.Protocol):
    """Low-level protocol that speaks the client end of IRC.

    This isn't responsible for very much besides the barest minimum definition
    of an IRC client: connecting and responding to PING.

    You probably want `read_message`, or the higher-level client class.
    """
    def __init__(self, loop, nick_prefix, password, charset='utf8'):
        self.nick = 'dywypi-' + nick_prefix
        self.password = password
        self.charset = charset

        self.buf = b''
        self.message_queue = Queue(loop=loop)
        self.registered = False

    def connection_made(self, transport):
        self.transport = transport

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
            message = IRCMessage.parse(raw_message.decode(self.charset))
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
        message = IRCMessage(command, *args)
        logger.debug("sent: %r", message)
        self.transport.write(message.render().encode(self.charset) + b'\r\n')

    @asyncio.coroutine
    def read_message(self):
        return (yield from self.message_queue.get())


class IRCMessage:
    """A single IRC message, either sent or received.

    Despite how clueless the IRC protocol is about character encodings, this
    class deals only with strings, not bytes.  Decode elsewhere, thanks.
    """
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
        """String representation of an IRC message.  DOES NOT include the
        trailing newlines.
        """
        parts = [self.command] + list(self.args)
        # TODO assert no spaces
        # TODO assert nothing else begins with colon!
        if self.args and ' ' in parts[-1]:
            parts[-1] = ':' + parts[-1]

        return ' '.join(parts)

    # Oh boy this is ugly!
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
        """Parse an IRC message.  DOES NOT expect to receive the trailing
        newlines.
        """
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
