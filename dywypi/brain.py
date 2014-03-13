import argparse
import asyncio
from concurrent.futures import FIRST_COMPLETED
from functools import partial
import logging
from urllib.parse import urlparse

from dywypi.dialect.irc.client import IRCClient
from dywypi.plugin import PluginManager
from dywypi.state import Network
from dywypi.state import Server
# TODO making this work would be lovely, but i'm not quite sure how it applies
# as a "client"
#from dywypi.web import start_web

log = logging.getLogger(__name__)



class parser_action:
    """Decorator that turns a method into a callable argparse `Action`.

    argparse assumes whatever you give it as an action is an `Action` subclass,
    which it then instantiates, and then calls some number of times.

    The goal here is to transparently create that subclass so you can write an
    action handler like so:

        @parser_action
        def handle_some_argument(self, action, parser, ns, vals, option=None):
            self.do_a_thing(vals)

    Note that the action object has been jammed in as the second argument.
    """
    def __init__(self, method):
        self.method = method

    def __get__(self, instance, owner):
        if instance is None:
            return self

        # This is where the `self` passed to the original function comes from
        return partial(self, instance)

    def __call__(self, instance, *args, **kwargs):
        # Note that we get called once by argparse to "instantiate" the Action,
        # and the resulting object is called to actually do the work.
        # So this function should only return the instance.
        class InnerAction(argparse.Action):
            def __call__(action, *args, **kwargs):
                self.method(instance, action, *args, **kwargs)

        return InnerAction(*args, **kwargs)


class Brain:
    """Central nervous system of the bot.  Handles initial configuration,
    plugin discovery, initial connections, and all that fun stuff.
    """

    def __init__(self):
        self.networks = {}
        self.plugin_manager = PluginManager()

    def configure_from_argv(self, argv=None):
        # Scan for known plugins first
        self.plugin_manager.scan_package()

        parser = self.build_parser()
        # The returned namespace should be junk, since arguments all have
        # actions that configure the brain immediately
        parser.parse_args(argv)

        # Load everything
        self.plugin_manager.loadall()

    def run(self, loop):
        asyncio.async(self._run(loop), loop=loop)
        loop.run_forever()

    @asyncio.coroutine
    def _run(self, loop):
        # TODO less hard-coded here would be nice
        clients = []
        for network in self.networks.values():
            clients.append(IRCClient(loop, network))

        # TODO gracefully handle failed connections, and only bail entirely if
        # they all fail?
        yield from asyncio.gather(*[client.connect() for client in clients])

        # This is it, this is the event loop right here.
        # It's basically a select() loop across all our clients, except there's
        # nothing quite like select() at the moment, so we have to fake it by
        # keeping a fresh list of read_event calls per client.
        coros = {client: asyncio.Task(client.read_event()) for client in clients}
        while True:
            done, pending = yield from asyncio.wait(
                coros.values(),
                return_when=FIRST_COMPLETED)

            # Replace any coros that finished with fresh ones for the next run
            # of the loop
            for client, coro in coros.items():
                if coro in done:
                    coros[client] = asyncio.Task(client.read_event())

            # Evaluate all the tasks that completed (probably just one)
            for d in done:
                event = yield from d
                self.plugin_manager.fire(event)

    def add_network(self, network):
        # TODO check for dupes!
        self.networks[network.name] = network

    def build_parser(self):
        p = argparse.ArgumentParser()
        p.add_argument('adhoc_connections', nargs='*', action=self.add_adhoc_connections)

        return p

    @parser_action
    def add_adhoc_connections(self, action, parser, ns, vals, option=None):
        for uri in vals:
            uriobj = urlparse(uri)

            if uriobj.scheme not in ('irc', 'ircs'):
                raise ValueError(
                    "Don't know how to handle protocol {}: {}"
                    .format(uriobj.scheme, uri)
                )

            # Try to guess a network name based on the host
            host = uriobj.hostname
            # TODO handle IPs?  and have some other kind of ultimate fallback?
            parts = host.split('.')
            # TODO this doesn't work for second-level like .co.jp
            if len(parts) > 1:
                name = parts[-2]
            else:
                name = parts[0]

            # TODO hmm should this stuff be delegated to a dialect?  some of it may
            # not make sense for some dialects
            network = Network(name)
            if uriobj.username:
                network.add_preferred_nick(uriobj.username)

            # TODO lol this tls hack is so bad.
            network.add_server(
                uriobj.hostname,
                uriobj.port,
                tls=uriobj.scheme.endswith('s'),
                password=uriobj.password,
            )

            if uriobj.path:
                channel_name = uriobj.path.lstrip('/')
                network.add_autojoin(channel_name)

            self.add_network(network)
