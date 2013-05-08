from twisted.application import service
from twisted.internet import reactor

from dywypi.core import Dywypi

def make_application():
    hub = Dywypi()
    reactor.callWhenRunning(hub.scan_for_plugins)

    application = service.Application("dywypi")

    import dywypi.dialect.irc
    dywypi.dialect.irc.initialize_service(application, hub)

    import dywypi.dialect.shell
    dywypi.dialect.shell.initialize_service(application, hub)

    return application
