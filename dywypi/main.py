import os
from twisted.application import service, internet
from twisted.internet import defer
from twisted.internet.ssl import ClientContextFactory
from twisted.python import log
from twisted.web import static, server

from dywypi.core import DywypiFactory
from dywypi.plugin_api import PluginRegistry

# XXX also need to rig something to make IRC appear more stateful.
# - for commands that require waiting for a response from the server, fire off the initializer and create a deferred that waits on a response matching some simple pattern.  override handleCommand to callback() on these.  if we get disconnected, errback().
# - what to do about disconnections in general?  probably ought to just cancel everything.
def enforce_unicode(res):
    """Deferred callback that rejects plain `str` output."""
    if isinstance(res, str):
        raise ValueError("Return values must be Unicode objects")
    return res


class Dywypi(object):
    """The brains of this operation."""

    def __init__(self):
        self.plugin_registry = PluginRegistry()
        self.plugin_registry.scan()
        self.plugin_registry.load_plugin('echo')
        self.plugin_registry.load_plugin('fyi')
        self.plugin_registry.load_plugin('pagetitles')

    def fire(self, event, *a, **kw):
        for func in self.plugin_registry.get_listeners(event):
            self._make_deferred(func, event, *a, **kw)


    def run_command(self, command, event):
        self._make_deferred(self.plugin_registry.run_command, command, event)

    def _make_deferred(self, func, *args, **kwargs):
        d = defer.maybeDeferred(func, *args, **kwargs)
        d.addErrback(log.err)
        d.addErrback(lambda failure: responder(u"resonance cascade imminent, evacuate immediately"))



class DywypiClient(service.Service):
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


def make_application():
    hub = Dywypi()

    master_service = service.MultiService()

    # TODO load config here  8)
    import dywypi.state
    for network in [dywypi.state.Network()]:
        DywypiClient(hub, network).setServiceParent(master_service)

    application = service.Application("dywypi")
    master_service.setServiceParent(application)

    return application
