import asyncio
import getpass
import logging


log = logging.getLogger(__name__)


class Network:
    """A single place to which you can connect.  Efnet, for example, is a
    single network, even though it has a great many servers.
    """
    def __init__(self, name):
        self.name = name
        self.nicks = []
        self.servers = []
        self.autojoins = []

    def add_preferred_nick(self, nick):
        self.nicks.append(nick)

    @property
    def preferred_nick(self):
        if self.nicks:
            return self.nicks[0]
        else:
            return "dywypi-{0}".format(getpass.getuser())

    def add_server(self, host, port=None, *, tls=False, password=None):
        if not host:
            raise ValueError("No hostname provided")

        # TODO dialect-specific port default
        if port is None:
            if tls:
                port = 6697
            else:
                port = 6667

        self.servers.append(Server(host, port, tls=tls, password=password))

    def add_autojoin(self, channel_name):
        # TODO yet again, irc specific
        # TODO support channel keys
        if not channel_name.startswith('#'):
            channel_name = '#' + channel_name

        self.autojoins.append(channel_name)


class Server:
    # TODO this is TCP only...
    def __init__(self, host, port, tls, password):
        self.host = host
        self.port = port
        self.tls = tls
        # TODO wait is this per-server or per-network
        self.password = password

    def connect(self, loop):
        """Return a coroutine that, when yield from'd, will connect to this
        server and produce a tuple of (reader, writer) streams.
        """
        return asyncio.open_connection(
            host=self.host,
            port=self.port,
            ssl=self.tls,
            loop=loop,
        )

class Peer:
    def __init__(self, name, ident, host, *, is_server=False):
        self.name = name
        self.ident = ident
        self.host = host
        self.is_server = is_server

    @classmethod
    def from_prefix(cls, prefix):
        """Parse a raw IRC prefix (probably from `IRCMessage.prefix`) of the
        form name!ident@host.
        """
        if '!' in prefix:
            # Another user: name!ident@host
            name, identhost = prefix.split('!', 1)
            ident, host = prefix.split('@', 1)
            return cls(name, ident, host)
        else:
            # Must be a server talking to us
            # TODO should this be a different class?  a Server?  have a Server
            # property?  otherwise work differently?
            # TODO this is a bit kludgy.
            return cls(prefix, None, prefix, is_server=True)


class Channel:
    def __init__(self, name, key=None):
        self.name = name
        self.key = key

        self.topic = None
        self.topic_author = None
        self.topic_timestamp = None
        self.users = []
