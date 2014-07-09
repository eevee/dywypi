import asyncio

@asyncio.coroutine
def test_message_parsing(loop, client, fake_server):
    fake_server.feed(b":prefix!ident@host COMM")
    fake_server.feed(b"AND arg1 arg2 :extra arguments...\r\njunk")
    message, event = yield from client.read_queue.get()
    assert message
    assert message.command == 'COMMAND'
    assert message.prefix == 'prefix!ident@host'
    assert message.args == ('arg1', 'arg2', 'extra arguments...')
