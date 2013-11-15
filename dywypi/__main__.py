import asyncio
import logging
import sys
from urllib.parse import urlparse

from dywypi.dialect.irc.client import IRCClient
from dywypi.plugin import echo_plugin

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')


@asyncio.coroutine
def main(loop, uri):
    client = IRCClient(loop, urlparse(uri))
    yield from client.connect()
    echo_plugin.start(client)
    while True:
        event = yield from client.read_event()
        from dywypi.event import Message
        if isinstance(event, Message):
            echo_plugin.fire(loop, event)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.async(main(loop, *sys.argv[1:]), loop=loop)
    loop.run_forever()
