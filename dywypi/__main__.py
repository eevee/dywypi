import asyncio
import logging
import sys
from urllib.parse import urlparse

from dywypi.dialect.irc.client import IRCClient
from dywypi.plugin import PluginManager

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')


@asyncio.coroutine
def main(loop, uri):
    client = IRCClient(loop, urlparse(uri))
    yield from client.connect()
    manager = PluginManager()
    manager.scan_package()
    manager.loadall()

    while True:
        event = yield from client.read_event()
        manager.fire(loop, event)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.async(main(loop, *sys.argv[1:]), loop=loop)
    loop.run_forever()
