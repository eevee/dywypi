import asyncio
from collections import defaultdict
import importlib
import logging
import pkgutil

from dywypi.event import Event, Message

logger = logging.getLogger(__name__)


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


class PluginEvent(Event):
    """Base class for special plugin-only events that don't make sense for
    generic clients.  Usually more specific versions of main dywypi events, to
    allow for finer-grained listening in plugins.
    """

class PublicMessage(PluginEvent): pass

class PrivateMessage(PluginEvent): pass

class PublicMessage(PluginEvent): pass

class PluginManager:
    def __init__(self):
        self.loaded_plugins = {}

    def scan_package(self, package='dywypi.plugins'):
        """Scans a Python package for in-process Python plugins."""
        pkg = importlib.import_module(package)
        for finder, name, is_pkg in pkgutil.iter_modules(pkg.__path__, prefix=package + '.'):
            finder.find_module(name).load_module(name)

    def loadall(self):
        for name, plugin in BasePlugin._known_plugins.items():
            plugin.start()
            self.loaded_plugins[name] = plugin

    def fire(self, loop, event):
        for plugin in self.loaded_plugins.values():
            plugin.fire(loop, event)


class BasePlugin:
    _known_plugins = {}

    def __init__(self, name):
        if name in self._known_plugins:
            raise NameError("Can't have two plugins named {}!".format(name))

        self.name = name
        self._known_plugins[name] = self


class Plugin(BasePlugin):
    def __init__(self, name):
        self.listeners = defaultdict(list)

        super().__init__(name)

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

        # OK actually fire the event.
        for listener in self.listeners[type(event)]:
            # Fire them all off in parallel via async(); `yield from` would run
            # them all in serial and nonblock until they're all done!
            asyncio.async(listener(wrapped), loop=loop)

    def start(self):
        # TODO need an onload hook or something?
        pass
