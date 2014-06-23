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
