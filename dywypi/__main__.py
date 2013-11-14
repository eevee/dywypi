import asyncio
import sys

from dywypi.aioirc import IRCClient
from dywypi.plugin import echo_plugin

@asyncio.coroutine
def main(loop, host, port, nick_prefix, password):
    client = IRCClient(host, port, nick_prefix, ssl=True, password=password)
    yield from client.connect(loop)
    echo_plugin.start(client)
    while True:
        message = yield from client.read_message()
        if message.command == 'PRIVMSG':
            asyncio.async(echo_plugin.send_on_message(message))
        print("recv:", repr(message))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # TODO i think this blocks until the connection is made, which seems...
    # not right?  is there a better way to actually get started?
    asyncio.async(main(loop, *sys.argv[1:]), loop=loop)
    loop.run_forever()
