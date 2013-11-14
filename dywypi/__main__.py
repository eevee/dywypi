import asyncio
import logging
import sys

from dywypi.aioirc import IRCClient
from dywypi.plugin import echo_plugin

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')

@asyncio.coroutine
def main(loop, host, port, nick_prefix, password):
    client = IRCClient(host, port, nick_prefix, ssl=True, password=password)
    yield from client.connect(loop)
    channel = yield from client.join('#dywypi')
    echo_plugin.start(client)
    while True:
        message = yield from client.read_message()
        if message.command == 'PRIVMSG':
            asyncio.async(echo_plugin.send_on_message(message))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    asyncio.async(main(loop, *sys.argv[1:]), loop=loop)
    loop.run_forever()
