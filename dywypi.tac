# You can run this .tac file directly with:
#    twistd -ny dywypi.tac

import os
from twisted.application import service, internet
from twisted.web import static, server

from dywypi.core import DywypiFactory, connection_specs

master_service = service.MultiService()

for host, port, channels in connection_specs:
    internet.TCPClient(host, port, DywypiFactory(channels)).setServiceParent(master_service)

application = service.Application("dywypi")
master_service.setServiceParent(application)
