import asyncio

from dywypi.event import Message
from dywypi.plugin import Plugin


import sys
# psycotulip is a bit dated; let's fix it for them
sys.modules['tulip'] = asyncio
import psycotulip

# TODO loop?
pool = psycotulip.PostgresConnectionPool(maxsize=3, dsn='dbname=veekun_pokedex')

plugin = Plugin('pokedex')

@plugin.command('dex')
def dex(event):
    thing = event.args[0]

    conn = yield from pool.get()
    with conn.cursor() as cur:
        yield from cur.begin()
        try:
            yield from cur.execute(
                '''
                select id from pokemon where identifier = %s
                ''', (thing,))
            (id,), = cur.fetchall()
            yield from event.reply(str(id))
        finally:
            yield from cur.rollback()
