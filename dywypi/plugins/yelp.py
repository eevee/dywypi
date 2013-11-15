import logging
import json
import os
import re
import random
from urllib.parse import urlencode

import asyncio
import aiohttp
from oauthlib.oauth1 import Client

from dywypi.event import Message
from dywypi.plugin import Plugin

logger = logging.getLogger(__name__)
plugin = Plugin('yelp')

@plugin.command('Yelp')
def where_to_eat(event):
    if event.argstr is None or re.search("@", event.argstr) is None:
        yield from event.reply('Usage: yelp Keyword@Location')
        return

    keyword, location = event.argstr.split("@")
    business = yield from search(location, keyword)

    if business is None:
        yield from event.reply('Bad Day! Nothing found!')
        return
    yield from event.reply("Try this today: {name} {url}".format(
        name=business["name"],
        url=business["url"]
    ))


@asyncio.coroutine
def search(location, keyword=None, category_filter=None):
    SEARCH_URI = 'http://api.yelp.com/v2/search'

    # set oauth
    consumer_key = os.environ["YELP_CONSUMER_KEY"]
    consumer_secret = os.environ['YELP_CONSUMER_SECRET']
    token = os.environ['YELP_TOKEN']
    token_secret = os.environ['YELP_TOKEN_SECRET']
    client = Client(
        consumer_key,
        client_secret=consumer_secret,
        resource_owner_key=token,
        resource_owner_secret=token_secret)

    # start query
    params=clean_params({
        'term': keyword,
        'location': location,
        'category_filter': category_filter,
        'sort': 2})
    logger.debug("yelp send:%s", params)
    uri = SEARCH_URI + "?" + params
    uri, headers, _ = client.sign(uri)
    response = yield from aiohttp.request(
        'GET',
        uri,
        headers=headers)

    data = json.loads((yield from response.read()).decode('utf8'))
    if 'error' in data:
        logger.debug(data)
        return

    business = random.choice(data['businesses'])
    return business


def clean_params(params):
    clean_params = {}
    for key in params:
        value = params[key]
        if value:
            clean_params[key] = str(value).replace(' ', '+')
    return urlencode(clean_params)
