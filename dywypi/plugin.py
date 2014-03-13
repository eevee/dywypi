import asyncio
from collections import defaultdict
import importlib
import logging
import pkgutil

from dywypi.event import Event, Message

log = logging.getLogger(__name__)


class EventWrapper:
    """Little wrapper around an event object that provides convenient plugin
    methods like `reply`.  All other attributes are delegated to the real
    event.
    """
    def __init__(self, event, plugin_data):
        self.event = event
        self.type = type(event)
        self.plugin_data = plugin_data

    @property
    def data(self):
        return self.plugin_data

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

class PublicMessage(PluginEvent):
    @property
    def message(self):
        return self.raw_message.args[1]

class Command(PluginEvent):
    def __init__(self, client, raw_message, command_name, argstr):
        super().__init__(client, raw_message)
        self.command_name = command_name
        self.argstr = argstr
        self.args = argstr.strip().split()

    @property
    def channel(self):
        return self.raw_message.args[0]

class PluginManager:
    def __init__(self):
        self.loaded_plugins = {}
        self.plugin_data = defaultdict(dict)

    def scan_package(self, package='dywypi.plugins'):
        """Scans a Python package for in-process Python plugins."""
        pkg = importlib.import_module(package)
        for finder, name, is_pkg in pkgutil.iter_modules(pkg.__path__, prefix=package + '.'):
            try:
                finder.find_module(name).load_module(name)
            except ImportError as exc:
                log.error(
                    "Couldn't import plugin module {}: {}"
                    .format(name, exc))

    def loadall(self):
        for name, plugin in BasePlugin._known_plugins.items():
            plugin.start()
            self.loaded_plugins[name] = plugin

    def _wrap_event(self, event, plugin):
        return EventWrapper(event, self.plugin_data[plugin])

    def _fire(self, event):
        for plugin in self.loaded_plugins.values():
            wrapped = self._wrap_event(event, plugin)
            plugin.fire(wrapped)

    def _fire_command(self, original_event):
        message = original_event.message[len(original_event.client.nick) + 1:]
        try:
            command_name, argstr = message.split(None, 1)
        except ValueError:
            command_name, argstr = message.strip(), ''
        event = Command.from_event(original_event, command_name=command_name, argstr=argstr)
        # TODO well this could be slightly more efficient
        # TODO should also mention when no command exists
        for plugin in self.loaded_plugins.values():
            wrapped = self._wrap_event(event, plugin)
            plugin.fire_command(wrapped)

    def fire(self, event):
        self._fire(event)

        # Possibly also fire plugin-specific events.
        if isinstance(event, Message):
            # Messages get broken down a little further.
            is_public = (event.channel[0] in '#&!')
            is_command = (event.message.startswith(event.client.nick) and
                event.message[len(event.client.nick)] in ':, ')

            if is_command or not is_public:
                # Something addressed directly to us; this is a command and
                # needs special handling!
                self._fire_command(event)
            else:
                # Regular public message.
                self._fire(PublicMessage.from_event(event))

            # TODO: what about private messages that don't "look like"
            # commands?  what about "all" public messages?  etc?


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
        self.commands = {}

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

    def command(self, command_name):
        def decorator(f):
            coro = asyncio.coroutine(f)
            # TODO collisions etc
            self.commands[command_name] = coro
            return coro
        return decorator

    def fire(self, event):
        # OK actually fire the event.
        for listener in self.listeners[event.type]:
            # Fire them all off in parallel via async(); `yield from` would run
            # them all in serial and nonblock until they're all done!
            asyncio.async(listener(event), loop=event.loop)

    def fire_command(self, event):
        if event.command_name in self.commands:
            asyncio.async(self.commands[event.command_name](event), loop=event.loop)

    def start(self):
        # TODO need an onload hook or something?
        pass


class PluginError(Exception): pass
