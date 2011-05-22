# You can run this .tac file directly with:
#    twistd -ny dywypi.tac

import os
from twisted.application import service, internet
from twisted.internet import defer
from twisted.python import log
from twisted.web import static, server

from dywypi.core import DywypiFactory, connection_specs
from dywypi.plugin_api import PluginRegistry

# XXX also need to rig something to make IRC appear more stateful.
# - for commands that require waiting for a response from the server, fire off the initializer and create a deferred that waits on a response matching some simple pattern.  override handleCommand to callback() on these.  if we get disconnected, errback().
# - what to do about disconnections in general?  probably ought to just cancel everything.
def enforce_unicode(res):
    """Deferred callback that rejects plain `str` output."""
    if isinstance(res, str):
        raise ValueError("Return values must be Unicode objects")
    return res

class DywypiService(service.MultiService):
    def __init__(self):
        service.MultiService.__init__(self)

        self.plugin_registry = PluginRegistry()
        self.plugin_registry.scan()
        self.plugin_registry.load_plugin('echo')
        self.plugin_registry.load_plugin('fyi')

    def dispatch_event(self, responder, command, args):
        d = defer.maybeDeferred(
            self.plugin_registry.run_command, command, args)
        d.addCallback(enforce_unicode)
        d.addCallback(responder)
        d.addErrback(log.err)
        d.addErrback(lambda failure: responder(u"resonance cascade imminent, evacuate immediately"))

master_service = DywypiService()

for host, port, channels in connection_specs:
    factory = DywypiFactory(master_service, channels)
    internet.TCPClient(host, port, factory).setServiceParent(master_service)

application = service.Application("dywypi")
master_service.setServiceParent(application)
