import asyncio.tasks

from pyramid.renderers import render_to_response
from pyramid.response import Response
from pyramid.view import view_config


@view_config(route_name='main')
@asyncio.coroutine
def main(context, request):
    return render_to_response(
        'dywypi.web:templates/main.mako',
        dict(
            foo='foo',
        ),
        request=request)


@view_config(route_name='slow')
@asyncio.coroutine
def slow(context, request):
    yield from asyncio.tasks.sleep(5)
    return Response('Phew!  That took a while.')


@view_config(route_name='names')
@asyncio.coroutine
def names(context, request):
    channel = '#' + request.matchdict['channel']
    names = yield from request.registry.settings['irc_client'].names(channel)
    return Response('<br>'.join(names))
    return render_to_response(
        'dywypi.web:templates/main.mako',
        dict(
            foo='foo',
        ),
        request=request)
