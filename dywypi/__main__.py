import asyncio
import logging

from dywypi.brain import Brain

logging.basicConfig()
logging.getLogger('dywypi').setLevel('DEBUG')


if __name__ == '__main__':
    brain = Brain()
    brain.configure_from_argv()
    loop = asyncio.get_event_loop()
    try:
        brain.run(loop)
    finally:
        loop.close()
