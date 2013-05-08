"""Provides the base class for plugins and dywypi's access to them."""

import functools
import pkgutil

from twisted.python import log

from dywypi.event import Event


class PluginRegistrationError(Exception): pass


### Decorators for defining commands

# XXX perhaps rename this as register_for(command...) or something.
# I want plugins to be able to listen for other events too, remember.  possibly
# even any arbitrary IRC event.  so going to need a mechanism for that.
# all the things that need triggers:
# - cron (ping at regular intervals)
# - commands (directly addressed by user)
# - IRC events; high-level wrappers, one at a time.
# ALSO:
# - support for long-running tasks
# TODO: things dywypi does now
# - pokedex!  oh no this needs the api
# - calculator kinda
# - nethack death announcement
# - RSS
# - tf2 status checkerino
# - sending messages around
# TODO: other useful stuff
# - regular ol' logger
# - greeter (proof of concept really)
# - url logger (eh)
# - url title getter, for twisted messery
# - git
# - perlbot sort of stuff like leaving messages and factoids?
# TODO not-plugin game plan
# - configuration!
# - write user support
#   - first tracking users
#   - then access via services and STATUS
# - write a core plugin
#   - include documentation  B)
# - add support for redirects: | > < >&??
# - handle errors more nicely
# - I guess make command() work without parens, too, or just require the name

class PluginHook(object):
    def wrap(self, method):
        self.method = method
        return self

    def __get__(self, instance, owner):
        """Replicate the usual method invocation magic."""
        if instance is None:
            return self

        return functools.partial(self, instance)

    def __call__(self, *args, **kwargs):
        return self.method(*args, **kwargs)


class PluginCommand(PluginHook):
    def __init__(self, name, doc, is_global):
        self.name = name
        self.doc = doc
        self.is_global = is_global

    def register(self, plugin, registry):
        if self.is_global:
            fqn = self.name
        else:
            fqn = plugin.name + '.' + self.name

        log.msg(u"...adding command {0!r}".format(fqn))

        # TODO this should probably be a method
        if fqn in registry.commands:
            raise PluginRegistrationError(
                """Can't have two commands named {0}""".format(fqn))

        registry.commands[fqn] = plugin, self


def command(name, doc=None):
    """Decorator that marks a plugin function as a command.  May be stacked to
    give a command several aliases.

    `name` is the name that triggers the command.  `doc` is a help string
    provided to users; it defaults to the function's docstring.
    """
    return PluginCommand(name, doc, is_global=False).wrap

def global_command(name, doc=None):
    """Similar to `command()`, but the function can be called without the
    plugin prefix.  Use with discretion; this is a shared namespace.
    """
    return PluginCommand(name, doc, is_global=True).wrap


class PluginListener(PluginHook):
    def __init__(self, event_cls):
        if not issubclass(event_cls, Event):
            raise TypeError("Can only listen to Event subclasses")

        self.event_cls = event_cls

    def register(self, plugin, registry):
        log.msg(u"...listening for {0!r}".format(self.event_cls))
        registry.listeners.setdefault(self.event_cls, []).append(self)

def listen(event_cls):
    return PluginListener(event_cls).wrap


### Plugin class implementation

class PluginMeta(type):
    """Metaclass for plugins.  Just used as a form of automatic registration of
    plugins, and part of the command registration mechanism.
    """
    def __init__(cls, name, bases, attrs):
        if hasattr(cls, '_plugins'):
            # This must be a subclass.  Register it, using its advertised name
            if cls.name in cls._plugins:
                raise PluginRegistrationError(
                    """Can't have two plugins named {0}""".format(cls.name))
            cls._plugins[cls.name] = cls
        else:
            # If the '_plugins' attribute isn't set yet, then this must be the
            # base class.  Initialize it; it doesn't get registered as a plugin
            # itself
            cls._plugins = {}

        # Amass all the event listeners in this plugin; they've been decorated
        # with an appropriate attribute
        cls._plugin_hooks = []
        for key, attr in attrs.iteritems():
            while isinstance(attr, PluginHook):
                cls._plugin_hooks.append(attr)
                attr = attr.method


class Plugin(object):
    """Base class for plugins.

    Must implement:

    `name`
        Class attribute.  This is the name dywypi uses to refer to your plugin
        everywhere; in configuration, internally, and when users invoke
        commands.  Must be unique across all plugins.
    """
    __metaclass__ = PluginMeta


### Plugin command registry; loading, unloading, dispatching

class PluginRegistry(object):
    """Manages plugins, their states, and finding/executing commands.

    DISREGARD I SUCK COCKS
    """

    def __init__(self):
        # plugin_name => plugin object
        self.plugins = {}
        # command_name => PluginCommand object
        self.commands = {}
        # event class => [callable]
        self.listeners = {}

        self.loaded_module_names = set()

        self.plugin_classes = Plugin._plugins  # instantiated by metaclass

    def scan(self):
        """Imports every module under dywypi.plugins, thus registering the
        plugins they define.
        """
        log.msg('Scanning for plugin modules')
        import dywypi.plugins
        for loader, name, is_pkg in pkgutil.iter_modules(dywypi.plugins.__path__, prefix='dywypi.plugins.'):
            log.msg(u"...found {0!r}".format(name))
            __import__(name)

    def load_plugin(self, plugin_name):
        if plugin_name in self.plugins:
            # Already loaded!  Do nothing.
            # TODO or bomb, or indicate something idk.
            return

        log.msg(u"Loading plugin {0!r}".format(plugin_name))
        plugin_obj = self.plugin_classes[plugin_name]()
        self.plugins[plugin_name] = plugin_obj

        # Collect event listeners
        # TODO 'doc' here doesn't make any sense for general listeners
        for hook in plugin_obj._plugin_hooks:
            hook.register(plugin_obj, self)


    def unload_plugin(self, plugin_name):
        del self.plugins[plugin_name]

    def reload_plugin(self, plugin_name):
        raise NotImplementedError


    def run_command(self, command_name, event):
        """..."""
        # XXX more vague planning ahead: should responses be generators?
        # should we pass a writer object or reply callable?  how does the thing
        # communicate back????
        plugin, plugin_command = self.commands[command_name]
        response = plugin_command(plugin, event)

        # TODO check for unicodes maybe.
        return response

    def get_listeners(self, event):
        for cls in event.__class__.__mro__:
            if cls is Event:
                break

            # TODO don't yield the same guy twice
            for func in self.listeners.get(cls, []):
                yield func

    # TODO make these less of an exception
    #def core_scan()...
