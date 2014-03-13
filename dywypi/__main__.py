import asyncio
import logging

from dywypi.brain import Brain

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')


if __name__ == '__main__':
    brain = Brain()
    brain.configure_from_argv()
    loop = asyncio.get_event_loop()
    brain.run(loop)
    #from dywypi.dialect.shell import initialize
    #asyncio.async(initialize(loop), loop=loop)
