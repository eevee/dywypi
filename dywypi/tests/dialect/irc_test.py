import asyncio

@asyncio.coroutine
def test_message_parsing(loop, client, fake_server):
    fake_server.reader.feed_data(b":prefix!ident@host COMM")
    fake_server.reader.feed_data(b"AND arg1 arg2 :extra arguments...\r\njunk")
    message, event = yield from client.read_queue.get()
    assert message
    assert message.command == 'COMMAND'
    assert message.prefix == 'prefix!ident@host'
    assert message.args == ('arg1', 'arg2', 'extra arguments...')


@asyncio.coroutine
def test_gather_messages(loop, client, fake_server):
    # Hypothetical stuff still in the pipe that's not yet a response to us
    fake_server.feed_irc('JUNK', 'nothing')

    fake_server.feed_irc('BEGIN', 'foo')
    fake_server.feed_irc('MIDDLE', 'hello')
    fake_server.feed_irc('END', 'bar')

    messages = yield from client.gather_messages(
        'BEGIN',
        'MIDDLE',
        finish=['END'],
    )

    assert [m.command for m in messages] == ['BEGIN', 'MIDDLE', 'END']


@asyncio.coroutine
def test_whois(loop, client, fake_server):
    # This is the actual response I got from whoising myself on my server
    fake_server.feed_irc('311', 'dywypi', 'eevee', 'eevee', 'b.d.f.l', '*', 'I solve practical problems')
    fake_server.feed_irc('319', 'dywypi', 'eevee', '!#veekun !#flora !#bot ')
    fake_server.feed_irc('312', 'dywypi', 'eevee', 'irc.veekun.com', 'veekun IRC')
    fake_server.feed_irc('313', 'dywypi', 'eevee', 'is an Eevee on veekun')
    fake_server.feed_irc('330', 'dywypi', 'eevee', 'Eevee', 'is logged in as')
    fake_server.feed_irc('317', 'dywypi', 'eevee', '0', '1404550078', 'seconds idle, signon time')
    fake_server.feed_irc('318', 'dywypi', 'eevee', 'End of /WHOIS list.')

    whois = yield from client.whois('eevee')

    # TODO ok well the retval is not yet well-defined
    assert whois


@asyncio.coroutine
def test_names(loop, client, fake_server):
    fake_server.feed_irc('RPL_NAMREPLY', 'dywypi', '=', '#channel', '@fred +wilma barney')
    fake_server.feed_irc('RPL_ENDOFNAMES', 'dywypi', '#channel', 'End of /NAMES list.')

    names = yield from client.names('#channel')

    assert len(names) == 3
    # TODO assert the specific names once the sigil parsing is done
