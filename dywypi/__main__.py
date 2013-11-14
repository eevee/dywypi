import asyncio
import sys

from dywypi.aioirc import IRCClient


@asyncio.coroutine
def main(loop, host, port, password):
    tr, pr = yield from loop.create_connection(
        lambda: IRCClient(password), host, port, ssl=True)


if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # TODO i think this blocks until the connection is made, which seems...
    # not right?  is there a better way to actually get started?
    loop.run_until_complete(main(loop, *sys.argv[1:]))
    loop.run_forever()
