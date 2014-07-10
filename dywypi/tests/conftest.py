"""py.test local plugin, sourced automatically"""
import asyncio
from io import BytesIO

import pytest

from dywypi.dialect.irc.client import IRCClient
from dywypi.state import Network


class DummyTransport(asyncio.WriteTransport):
    def __init__(self):
        self.buf = BytesIO()

    def write(self, data):
        self.buf.write(data)


class FakeServer(object):
    password = None

    @asyncio.coroutine
    def connect(self, loop):
        self.reader = asyncio.StreamReader(loop=loop)
        transport = DummyTransport()
        protocol = asyncio.Protocol()
        writer = asyncio.StreamWriter(transport, protocol, self.reader, loop)

        # Keep with the future-like interface
        fut = asyncio.Future()
        fut.set_result((self.reader, writer))
        return fut

    def feed_irc(self, *args):
        """Used in tests.  Push an entire IRC-style command into the client, as
        though it had come over the network.
        """
        args = list(args)

        # Take care of the trailing argument
        if ' ' in args[-1]:
            args[-1] = ':' + args[-1]

        # Add a (dummy?) prefix
        args = [':prefix!ident@host'] + args

        data = ' '.join(args) + '\r\n'
        self.reader.feed_data(data.encode('utf8'))


@pytest.fixture
def loop():
    loop = asyncio.get_event_loop()
    loop.set_debug(True)
    return loop


@pytest.fixture
def fake_server():
    return FakeServer()


@pytest.fixture
def local_network(loop, fake_server):
    network = Network('dywypi-test')
    # Forcibly add one fake local server
    # TODO this should be possible with slightly less subversion?
    network.servers.append(fake_server)
    return network


@pytest.fixture
def client(loop, local_network):
    # Transport just needs to be something with a .write() method
    client = IRCClient(loop, local_network)
    loop.run_until_complete(client.connect())
    return client


def wrap_coro(corogen):
    """Wrap a coroutine spawner in a regular callable function."""
    # TODO unclear how to get this cleanly from the fixture
    loop = asyncio.get_event_loop()

    def wrapped(**kwargs):
        return loop.run_until_complete(
            asyncio.wait_for(corogen(**kwargs), 100, loop=loop)
        )

    return wrapped


def pytest_pycollect_makeitem(collector, name, obj):
    """py.test hook to convert asyncio coroutines into regular callable tests.
    """
    # The tricky bit is to do this AFTER all the fixtures have been parsed out
    # of the argspec -- which the Function constructor does, inside
    # _genfunctions.  The weird stuff in here was borrowed from various parts
    # of _pytest.python.

    if collector.funcnamefilter(name) and asyncio.iscoroutinefunction(obj):
        items = list(collector._genfunctions(name, obj))
        for item in items:
            item.obj = wrap_coro(item.obj)

        return items
