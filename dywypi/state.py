"""Classes to remember the current state of dywypi's connections: servers,
channels, users, etc.  Also contains a proxy object that can be exposed to
plugins for performing common operations, without having to muck with the
Twisted implementation directly.
"""

class Network(object):
    connected = False

    def __init__(self):
        # This comes from configuration
        self.servers = [
            #Server('irc.veekun.com', ssl=True, port=6697),
            Server('irc.veekun.com'),
        ]
        self.channels = ['#bot']

class Server(object):
    def __init__(self, host, ssl=False, port=6667):
        self.host = host
        self.ssl = ssl
        self.port = port

class Channel(object):
    pass

class TwistedProxy(object):
    pass
