import shlex

from twisted.internet import defer
from twisted.python import log

from dywypi.plugin_api import PluginRegistry
from dywypi.state import CommandEvent

nickname = 'dywypi2_0'
encoding = 'utf8'


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

        self.network_protocols = {}
        self.network_deferreds = {}

    def network_connected(self, network, protocol):
        if network in self.network_protocols:
            raise KeyError("already connected")

        self.network_protocols[network] = protocol

    def network_disconnected(self, network):
        del self.network_protocols[network]

    def protocol_for_network(self, network):
        return self.network_protocols[network]


    ### Event stuff

    def fire(self, event, *a, **kw):
        for func in self.plugin_registry.get_listeners(event):
            self._make_deferred(func, event, *a, **kw)


    def run_command_string(self, source, command_string):
        # shlex doesn't support unicode before 2.7.3, so do the bytes dance
        command_string = command_string.encode('utf8')
        tokens = [token.decode('utf8') for token in shlex.split(command_string)]
        command = tokens.pop(0)

        event = CommandEvent(source, command=command, argv=tokens)

        self._make_deferred(self.plugin_registry.run_command, command, event)

    def _make_deferred(self, func, *args, **kwargs):
        d = defer.maybeDeferred(func, *args, **kwargs)
        d.addErrback(log.err)
        d.addErrback(lambda failure: responder(u"resonance cascade imminent, evacuate immediately"))
