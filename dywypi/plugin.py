import asyncio
from collections import defaultdict

from dywypi.event import Event, Message

class EventWrapper:
    """Little wrapper around an event object that provides convenient plugin
    methods like `reply`.  All other attributes are delegated to the real
    event.
    """
    def __init__(self, event):
        self.event = event

    @asyncio.coroutine
    def reply(self, message):
        # TODO this doesn't work if the event isn't from a channel, if there is
        # no channel, etc.
        yield from self.event.client.send_message('PRIVMSG', self.event.channel, message)

    def __getattr__(self, attr):
        return getattr(self.event, attr)


class Plugin:
    _known_plugins = {}

    def __init__(self, name):
        if name in self._known_plugins:
            raise NameError("Can't have two plugins named {}!".format(name))

        self.name = name
        self.client = None
        self.listeners = defaultdict(list)

        self._known_plugins[name] = self

    def on(self, event_cls):
        if not issubclass(event_cls, Event):
            raise TypeError("Can only listen on an Event subclass, not {}".format(event_cls))

        def decorator(f):
            coro = asyncio.coroutine(f)
            for cls in event_cls.__mro__:
                if cls is Event:
                    # Ignore Event and its superclasses (presumably object)
                    break
                self.listeners[cls].append(coro)
            return coro

        return decorator

    def fire(self, loop, event):
        wrapped = EventWrapper(event)
        for listener in self.listeners[type(event)]:
            # Fire them all off in parallel via async(); `yield from` would run
            # them all in serial and nonblock until they're all done!
            asyncio.async(listener(wrapped), loop=loop)

    def start(self, client):
        self.client = client


echo_plugin = Plugin('echo')

@echo_plugin.on(Message)
def echo_on_message(event):
    if event.channel != '#dywypi':
        return

    if not event.message.startswith("echo: "):
        return

    yield from event.reply(event.message[6:])
