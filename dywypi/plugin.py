import asyncio
from collections import defaultdict
import importlib
import logging
import pkgutil

from dywypi.event import Event, Message, _MessageMixin

log = logging.getLogger(__name__)


class EventWrapper:
    """Little wrapper around an event object that provides convenient plugin
    methods like `reply`.  All other attributes are delegated to the real
    event.
    """
    def __init__(self, event, plugin_data, plugin_manager):
        self.event = event
        self.type = type(event)
        self.plugin_data = plugin_data
        self._plugin_manager = plugin_manager

    @property
    def data(self):
        return self.plugin_data

    @asyncio.coroutine
    def reply(self, message):
        if self.event.channel:
            reply_to = self.event.channel.name
        else:
            reply_to = self.event.source.name
        yield from self.event.client.send_message('PRIVMSG', reply_to, message)

    def __getattr__(self, attr):
        return getattr(self.event, attr)


class PluginEvent(Event):
    """Base class for special plugin-only events that don't make sense for
    generic clients.  Usually more specific versions of main dywypi events, to
    allow for finer-grained listening in plugins.
    """


class PublicMessage(PluginEvent, _MessageMixin):
    pass


class Command(PluginEvent, _MessageMixin):
    def __init__(self, client, raw_message, command_name, argstr):
        super().__init__(client, raw_message)
        self.command_name = command_name
        self.argstr = argstr
        self.args = argstr.strip().split()

    def __repr__(self):
        return "<{}: {} {!r}>".format(
            type(self).__qualname__, self.command_name, self.args)


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
            self.load(name)

    def load(self, plugin_name):
        if plugin_name in self.loaded_plugins:
            return
        # TODO keyerror
        plugin = BasePlugin._known_plugins[plugin_name]
        plugin.start()
        log.info("Loaded plugin {}".format(plugin.name))
        self.loaded_plugins[plugin.name] = plugin

    def loadmodule(self, modname):
        # This is a little chumptastic, but: figure out which plugins a module
        # adds by comparing the list of known plugins before and after.
        before_plugins = set(BasePlugins._known_plugins)
        importlib.import_module(modname)
        after_plugins = set(BasePlugins._known_plugins)

        for plugin_name in after_plugins - before_plugins:
            self.load(plugin_name)

    def _wrap_event(self, event, plugin):
        return EventWrapper(event, self.plugin_data[plugin], self)

    def _fire(self, event):
        for plugin in self.loaded_plugins.values():
            wrapped = self._wrap_event(event, plugin)
            plugin.fire(wrapped)

    def _fire_global_command(self, command_event):
        # TODO well this could be slightly more efficient
        # TODO should also mention when no command exists
        for plugin in self.loaded_plugins.values():
            wrapped = self._wrap_event(command_event, plugin)
            plugin.fire_command(wrapped, is_global=True)

    def _fire_plugin_command(self, plugin_name, command_event):
        # TODO should DEFINITELY complain when plugin OR command doesn't exist
        try:
            plugin = self.loaded_plugins[plugin_name]
        except KeyError:
            raise
            # TODO
            #raise SomeExceptionThatGetsSentAsAReply(...)

        wrapped = self._wrap_event(command_event, plugin)
        plugin.fire_command(wrapped, is_global=False)

    def fire(self, event):
        self._fire(event)

        # Possibly also fire plugin-specific events.
        if isinstance(event, Message):
            # Messages get broken down a little further.
            is_public = (event.channel)
            is_command = (event.message.startswith(event.client.nick) and
                event.message[len(event.client.nick)] in ':, ')

            if is_command or not is_public:
                # Something addressed directly to us; this is a command and
                # needs special handling!
                if is_command:
                    message = event.message[len(event.client.nick) + 1:]
                else:
                    message = event.message
                try:
                    command_name, argstr = message.split(None, 1)
                except ValueError:
                    command_name, argstr = message.strip(), ''

                plugin_name, _, command_name = command_name.rpartition('.')
                command_event = Command.from_event(
                    event,
                    command_name=command_name,
                    argstr=argstr,
                )
                if plugin_name:
                    self._fire_plugin_command(plugin_name, command_event)
                else:
                    self._fire_global_command(command_event)
            else:
                # Regular public message.
                self._fire(PublicMessage.from_event(event))

            # TODO: what about private messages that don't "look like"
            # commands?  what about "all" public messages?  etc?


class PluginCommand:
    def __init__(self, coro, *, is_global):
        self.coro = coro
        self.is_global = is_global


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

    def command(self, command_name, *, is_global=True):
        def decorator(f):
            coro = asyncio.coroutine(f)
            # TODO collisions etc
            self.commands[command_name] = PluginCommand(
                coro, is_global=is_global)
            return coro
        return decorator

    def fire(self, event):
        # OK actually fire the event.
        for listener in self.listeners[event.type]:
            # Fire them all off in parallel via async(); `yield from` would run
            # them all in serial and nonblock until they're all done!
            asyncio.async(listener(event), loop=event.loop)

    def fire_command(self, event, *, is_global):
        if event.command_name in self.commands:
            command = self.commands[event.command_name]
            # Don't execute if the command is local-only and this wasn't
            # invoked with a prefix
            if command.is_global or not is_global:
                asyncio.async(command.coro(event), loop=event.loop)

    def start(self):
        # TODO need an onload hook or something?
        pass


class PluginError(Exception): pass
