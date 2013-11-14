import asyncio
import logging
import sys

from dywypi.dialect.irc.client import IRCClient
from dywypi.plugin import echo_plugin

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')


@asyncio.coroutine
def main(loop, host, port, nick_prefix, password):
    client = IRCClient(loop, host, port, nick_prefix, ssl=True, password=password)
    yield from client.connect()
    channel = yield from client.join('#dywypi')
    echo_plugin.start(client)
    while True:
        event = yield from client.read_event()
        from dywypi.event import Message
        if isinstance(event, Message):
            asyncio.async(echo_plugin.send_on_message(event.message))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.async(main(loop, *sys.argv[1:]), loop=loop)
    loop.run_forever()
