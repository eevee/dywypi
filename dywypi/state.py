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
        self._peers = {}

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

    def __init__(self, network, name, ident, host):
        self._network = weakref.ref(network)
        self.name = name
        self.ident = ident
        self.host = host


class TwistedProxy(object):
    pass

