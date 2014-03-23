import asyncio
from io import BytesIO

import pytest

from dywypi.dialect.irc.client import IRCClient
from dywypi.state import Server, Network


class DummyTransport(asyncio.WriteTransport):
    def __init__(self):
        self.buf = BytesIO()

    def write(self, data):
        self.buf.write(data)


class FakeServer(object):
    password = None

    @asyncio.coroutine
    def connect(self, loop):
        reader = asyncio.StreamReader(loop=loop)
        transport = DummyTransport()
        protocol = asyncio.Protocol()
        writer = asyncio.StreamWriter(transport, protocol, reader, loop)

        # Keep with the future-like interface
        fut = asyncio.Future()
        fut.set_result((reader, writer))
        return fut


@pytest.fixture
def loop():
    return asyncio.get_event_loop()


@pytest.fixture
def local_network(loop):
    network = Network('dywypi-test')
    # Forcibly add one fake local server
    # TODO this should be possible with slightly less subversion?
    network.servers.append(FakeServer())
    return network


@pytest.fixture
def client(loop, local_network):
    # Transport just needs to be something with a .write() method
    return IRCClient(loop, local_network)


def test_message_parsing(client):
    client.loop.run_until_complete(client.connect())
    client._reader.feed_data(b":prefix!ident@host COMM")
    client._reader.feed_data(b"AND arg1 arg2 :extra arguments...\r\njunk")
    # TODO maaybe put timeouts on these run-until-completes
    message, event = client.loop.run_until_complete(client.read_queue.get())
    assert message
    assert message.command == 'COMMAND'
    assert message.prefix == 'prefix!ident@host'
    assert message.args == ('arg1', 'arg2', 'extra arguments...')
