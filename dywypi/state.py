"""Classes to remember the current state of dywypi's connections: servers,
channels, users, etc.  Also contains a proxy object that can be exposed to
plugins for performing common operations, without having to muck with the
Twisted implementation directly.
"""
import weakref


HARDCODED_CHANNELS = ['#bot']

class Network(object):
    connected = False

    def __init__(self):
        self._channels = {}

        # TODO This comes from configuration
        self.servers = [
            #Server('irc.veekun.com', ssl=True, port=6697),
            Server('irc.veekun.com'),
        ]

        for channel_name in HARDCODED_CHANNELS:
            self.find_channel(channel_name)

    def find_channel(self, channel_name):
        if channel_name not in self._channels:
            self._channels[channel_name] = Channel(self, channel_name)

        return self._channels[channel_name]

    def find_peer(self, userhost):
        if '!' in userhost:
            name, usermask = userhost.split('!', 1)
            ident, host = usermask.split('@', 1)
            # TODO may need a cache dict
            return User(self, name, ident, host)
        else:
            self.client = network.find_server(userhost)
            return User(self, name, ident, host)

        if not channel.startswith('#'):
            channel = None


    @property
    def channels(self):
        return self._channels.values()


class Server(object):
    def __init__(self, host, ssl=False, port=6667):
        self.host = host
        self.ssl = ssl
        self.port = port

class Channel(object):
    def __init__(self, network, name, _whence=None):
        # TODO implement whence: track whether from config, from runtime, or unknown
        self._network = weakref.ref(network)
        self.name = name
        self._joined = False

    @property
    def network(self):
        return self._network()

class Peer(object): pass

class PeerServer(Peer): pass

# TODO this should probably share a superclass with Server, since both are peers?
class User(Peer):
    is_server = False

    def __init__(self, network, nick, ident, host):
        self._network = weakref.ref(network)
        self.nick = nick
        self.ident = ident
        self.host = host


class TwistedProxy(object):
    pass
