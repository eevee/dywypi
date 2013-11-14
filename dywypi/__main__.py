import asyncio
import sys

from dywypi.aioirc import IRCClient


@asyncio.coroutine
def main(loop, host, port, password):
    client = IRCClient(host, port, ssl=True, password=password)
    yield from client.connect(loop)
    while True:
        message = yield from client.read_message()
        print(repr(message))


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # TODO i think this blocks until the connection is made, which seems...
    # not right?  is there a better way to actually get started?
    loop.run_until_complete(main(loop, *sys.argv[1:]))
    loop.run_forever()
