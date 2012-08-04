from twisted.application import service

from dywypi.core import Dywypi

def make_application():
    hub = Dywypi()

    application = service.Application("dywypi")

    import dywypi.dialect.irc
    dywypi.dialect.irc.initialize_service(application, hub)

    import dywypi.dialect.shell
    dywypi.dialect.shell.initialize_service(application)

    return application
