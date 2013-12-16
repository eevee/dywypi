"""Hackery to run an asynchronous Pyramid."""
import asyncio
import types

from aiohttp.wsgi import WSGIServerHttpProtocol
from pyramid.config import Configurator
from pyramid.response import Response


def smuggle_coro_response(fut):
    """Horrendous hack that hides a future inside a Response's iterator
    until it bubbles up to the outer layer.

    This will probably break anything that tries to inspect the response
    body.
    """
    res = Response()
    res.app_iter = fut
    return res


@asyncio.coroutine
def start_web(loop, irc_client):
    config = Configurator(settings=dict(irc_client=irc_client))
    config.add_response_adapter(smuggle_coro_response, types.GeneratorType)
    config.add_response_adapter(smuggle_coro_response, asyncio.Future)

    config.add_route('main', '/')
    config.add_route('slow', '/slow')
    config.add_route('names', '/names/{channel}')

    config.scan('dywypi.web.views')

    app = config.make_wsgi_app()

    def wrapper_app(environ, start_response):
        """Middleware that unpacks a "smuggled" coroutine and finishes building
        the response.
        """
        stealth_response = yield from app(environ, start_response)
        return stealth_response(environ, start_response)

    yield from loop.create_server(
        lambda: WSGIServerHttpProtocol(wrapper_app),
        '0.0.0.0',
        34380)
