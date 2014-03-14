import asyncio
from io import BytesIO

import pytest

from dywypi.dialect.irc.client import IRCClientProtocol


@pytest.fixture
def loop():
    return asyncio.get_event_loop()


@pytest.fixture
def proto(loop):
    # Transport just needs to be something with a .write() method
    faux_transport = BytesIO()
    proto = IRCClientProtocol(loop, 'dywypi', None)
    proto.connection_made(faux_transport)
    return proto


def test_message_parsing(proto):
    proto.data_received(b":prefix!ident@host COMM")
    proto.data_received(b"AND arg1 arg2 :extra arguments...\r\njunk")
    message = proto.message_queue.get_nowait()
    assert message
    assert message.command == 'COMMAND'
    assert message.prefix == 'prefix!ident@host'
    assert message.args == ('arg1', 'arg2', 'extra arguments...')
