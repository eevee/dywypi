# You can run this .tac file directly with:
#    twistd -ny dywypi.tac

import os
from twisted.application import service, internet
from twisted.internet import defer
from twisted.web import static, server

from dywypi.core import DywypiFactory, connection_specs
from dywypi.plugin_api import PluginRegistry

class DywypiService(service.MultiService):
    def __init__(self):
        service.MultiService.__init__(self)

        self.plugin_registry = PluginRegistry()
        self.plugin_registry.discover_plugins()
        self.plugin_registry.load_plugin('echo')
        self.plugin_registry.load_plugin('fyi')

    def dispatch_event(self, responder, command, args):
        d = defer.maybeDeferred(
            self.plugin_registry.run_command, command, args)
        d.addCallback(responder)
        d.addErrback(lambda failure: responder(u"resonance cascade imminent, evacuate immediately"))

master_service = DywypiService()

for host, port, channels in connection_specs:
    factory = DywypiFactory(master_service, channels)
    internet.TCPClient(host, port, factory).setServiceParent(master_service)

application = service.Application("dywypi")
master_service.setServiceParent(application)
