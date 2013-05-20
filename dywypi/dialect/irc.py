import shlex

from twisted.application import service
from twisted.internet import protocol
from twisted.internet.ssl import ClientContextFactory
from twisted.words.protocols import irc

from dywypi.event import Source
from dywypi.event import CommandEvent, PublicMessageEvent

nickname = 'dywypi2_0'
encoding = 'utf8'


# XXX REALLY REALLY NEED FIRST-CLASS VERSIONS OF SERVERS, CHANNELS, AND CONTEXT
class DywypiProtocol(irc.IRCClient):
    nickname = nickname

    ### Bookkeeping

    def connectionMade(self):
        irc.IRCClient.connectionMade(self)

        self.hub.network_connected(self.irc_network, self)

    def connectionLost(self, *args, **kwargs):
        self.hub.network_disconnected(self.irc_network)

        irc.IRCClient.connectionLost(*args, **kwargs)

    ### Properties

    @property
    def irc_network(self):
        return self.factory.irc_network

    @property
    def hub(self):
        return self.factory.hub


    def parse_source(self, userhost, channel_name):
        from dywypi.state import User

        # TODO this should live on the Network, really, but the parsing is
        # IRC-specific.  maybe break it into pieces and pass the pieces as the
        # key?  (whoops lol the User contains the protocol rather than the
        # network anyway so it's not like this stuff is very agnostic)
        # TODO what about:
        # - nickname changes
        # - disconnects (and parts, if from the last channel i know about)
        # - when *i* disconnect
        # (how about for now we assume none of these will happen, BUT plz fix
        # soon omg)
        if userhost not in self.irc_network._peers:
            if '!' in userhost:
                name, usermask = userhost.split('!', 1)
                ident, host = usermask.split('@', 1)
                user = User(self, name, ident, host)
            else:
                self.client = network.find_server(userhost)
                user = User(self, name, ident, host)

            self.irc_network._peers[userhost] = user

        user = self.irc_network._peers[userhost]

        if channel_name and channel_name[0] in '#&+':
            channel = self.irc_network.find_channel(channel_name)
        else:
            channel = None

        return Source(
            hub=self.hub,
            network=self.irc_network,
            channel=channel,
            peer=user,
        )



    ### EVENT HANDLERS

    def signedOn(self):
        for channel in self.irc_network.channels:
            self.join(channel.name)

    def joined(self, channel_name):
        self.irc_network.find_channel(channel_name).joined = True

    def privmsg(self, raw_user, channel_name, msg):
        source = self.parse_source(raw_user, channel_name)

        #if peer.is_server:
        #    return

        # TODO we need pub/priv message events both that do and do NOT fire
        # when the message is also a command
        if source.channel:
            # In a channel, only direct addressing is a command
            if not msg.startswith(self.nickname + ': '):
                self.hub.fire(PublicMessageEvent(
                    source, message=msg))
                return

            command_string = msg[len(self.nickname) + 2:]
        else:
            # In a private message, everything is aimed at us
            # TODO private message event
            channel = None
            command_string = msg

        # Split the command into words, using shell-ish syntax
        tokens = [token.decode(encoding) for token in shlex.split(command_string)]
        command = tokens.pop(0)

        # XXX this will become 'respond to an event' I guess.  needs a concept
        # of an event.  right now we have "string of words is directed at bot"
        self.hub.run_command_string(source, command_string.decode(encoding))

    ### INTERNAL METHODS

    def _send_public_message(self, target, message):
        self.msg(target, message)

    def _decode(self, s):
        """Returns `s`, cleverly decoded into a unicode object."""
        # TODO  :(  at least implement xchat-style "utf8 or latin1"
        return s.decode('utf8')

    def _encode(self, s):
        """Returns `s`, encoded into what is probably the channel's encoding.
        """
        # TODO encoding per channel?
        return s.encode('utf8')


class DywypiFactory(protocol.ReconnectingClientFactory):
    protocol = DywypiProtocol

    def __init__(self, hub, irc_network):
        self.hub = hub
        self.irc_network = irc_network


class DywypiIRCService(service.Service):
    """IRC client -- the part that makes connections, not the part that speaks
    the protocol.

    I know how to round-robin to a cluster of servers.  Or, I will, someday.

    I'm based on the `twisted.application.internet.TCPClient` service.
    """

    _connection = None

    def __init__(self, hub, irc_network, reactor=None, *args, **kwargs):
        self.hub = hub
        self.irc_network = irc_network
        self.reactor = reactor

        # Other args go to the reactor later
        self.args = args
        self.kwargs = kwargs

    def startService(self):
        service.Service.startService(self)
        self._connection = self._make_connection()

    def stopService(self):
        service.Service.stopService(self)
        if self._connection is not None:
            self._connection.disconnect()
            del self._connection

    def _make_connection(self):
        """Pick the next server for this network, and try connecting to it.

        Returns the `Connector` object.
        """
        reactor = self.reactor
        if reactor is None:
            from twisted.internet import reactor

        # TODO actually do that round-robin thing
        irc_server = self.irc_network.servers[0]
        factory = DywypiFactory(self.hub, self.irc_network)

        # TODO timeout, bind address?
        if irc_server.ssl:
            return reactor.connectSSL(
                irc_server.host, irc_server.port, factory, ClientContextFactory())
        else:
            return reactor.connectTCP(
                irc_server.host, irc_server.port, factory)


def initialize_service(application, hub):
    master_service = service.MultiService()

    # TODO load config here  8)
    import dywypi.state
    for network in [dywypi.state.Network()]:
        DywypiIRCService(hub, network).setServiceParent(master_service)

    master_service.setServiceParent(application)
