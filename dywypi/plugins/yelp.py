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

log = logging.getLogger(__name__)
plugin = Plugin('yelp')


@plugin.command('Yelp')
def where_to_eat(event):
    if event.argstr is None or re.search("@", event.argstr) is None:
        yield from event.reply('Usage: yelp Keyword@Location')
        return
    keyword, location = event.argstr.split("@")

    try:
        yelp = YelpAsyncAPI()
        businesses = yield from yelp.search(location=location, keyword=keyword, sort=2)
        if businesses is None:
            yield from event.reply('Bad Day! Nothing found!')
        else:
            business = random.choice(businesses)
            yield from event.reply("Try this today: {name} {url}".format(
                name=business["name"],
                url=business["url"]
            ))

    except NoKeyError:
        yield from event.reply('You have to setup the following keys: YELP_CONSUMER_(KEY|SECRET), YELP_TOKEN, YELP_TOKEN_SECRET')
    except YelpAPIError as e:
        yield from event.reply('Yelp returns Error: %s'.format(str(e)))


class YelpAsyncAPI:
    def __init__(self):
        # set oauth
        consumer_key = os.environ["YELP_CONSUMER_KEY"]
        consumer_secret = os.environ['YELP_CONSUMER_SECRET']
        token = os.environ['YELP_TOKEN']
        token_secret = os.environ['YELP_TOKEN_SECRET']
        if consumer_key is None or consumer_secret is None or token is None or token_secret is None:
            raise NoKeyError
        self.client = Client( consumer_key,
            client_secret=consumer_secret,
            resource_owner_key=token,
            resource_owner_secret=token_secret)

    @asyncio.coroutine
    def send_query(self, uri, params=None):
        if params:
            params = self.clean_params(params)
        log.debug("yelp send:%s", params)
        uri = uri + "?" + params
        uri, headers, _ = self.client.sign(uri)

        response = yield from aiohttp.request(
            'GET',
            uri,
            headers=headers)

        data = json.loads((yield from response.read()).decode('utf8'))
        if 'error' in data:
            log.debug(data)
            raise YelpError(msg=data['error']['text'])
        return data

    def clean_params(self, params):
        clean_params = {}
        for key in params:
            value = params[key]
            if value:
                clean_params[key] = str(value).replace(' ', '+')
        return urlencode(clean_params)

    @asyncio.coroutine
    def search(self, **kwargs):
        SEARCH_URI = 'http://api.yelp.com/v2/search'
        params=kwargs

        data = yield from self.send_query(SEARCH_URI, params=params)
        return data['businesses']



class NoKeyError(Exception): pass
class YelpAPIError(Exception): pass
