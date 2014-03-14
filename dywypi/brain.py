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


class Brain:
    """Central nervous system of the bot.  Handles initial configuration,
    plugin discovery, initial connections, and all that fun stuff.
    """

    def __init__(self):
        self.networks = {}
        self.plugin_manager = PluginManager()

    def configure_from_argv(self, argv=None):
        # Scan for known plugins first
        self.plugin_manager.scan_package('dywypi.plugins')
        self.plugin_manager.scan_package('dywypi_plugins')

        parser = self.build_parser()
        ns = parser.parse_args(argv)

        for uristr in ns.adhoc_connections:
            self.add_adhoc_connection(uristr)

        if not ns.plugin:
            pass
        elif 'ALL' in ns.plugin:
            self.plugin_manager.loadall()
        else:
            for plugin_name in ns.plugin:
                if '.' in plugin_name:
                    self.plugin_manager.loadmodule(plugin_name)
                else:
                    self.plugin_manager.load(plugin_name)

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
        p.add_argument('adhoc_connections', nargs='+', action='store',
            help='URIs defining where to connect initially.')
        p.add_argument('-p', '--plugin', action='append',
            help='Load a plugin by name or module.  '
                'Specify ALL to auto-load all detected plugins.')

        return p

    def add_adhoc_connection(self, uristr):
        uri = urlparse(uristr)

        if uri.scheme not in ('irc', 'ircs'):
            raise ValueError(
                "Don't know how to handle protocol {}: {}"
                .format(uri.scheme, uri)
            )

        # Try to guess a network name based on the host
        host = uri.hostname
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
        if uri.username:
            network.add_preferred_nick(uri.username)

        # TODO lol this tls hack is so bad.
        network.add_server(
            uri.hostname,
            uri.port,
            tls=uri.scheme.endswith('s'),
            password=uri.password,
        )

        if uri.path:
            channel_name = uri.path.lstrip('/')
            network.add_autojoin(channel_name)

        self.add_network(network)
