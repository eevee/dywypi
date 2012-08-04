"""Provides the base class for plugins and dywypi's access to them."""
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

def _plugin_hook_decorator(listen_spec):
    # All this really does is stash the arguments away until PluginMeta, below,
    # catches them and moves them to a class in the list.
    def decorator(func):
        if not hasattr(func, '_plugin_listeners'):
            func._plugin_listeners = []

        listen_spec['func_name'] = func.__name__
        func._plugin_listeners.append(listen_spec)

        return func

    return decorator

def command(name=None, doc=None):
    """Decorator that marks a plugin function as a command.  May be stacked to
    give a command several aliases.

    `name` is the name that triggers the command, defaulting to the name of the
    function.  `doc` is a help string provided to users; it defaults to the
    function's docstring.
    """
    return _plugin_hook_decorator(dict(
        event_type='local_command', name=name, doc=doc, is_global=False))

def global_command(name, doc=None):
    """Similar to `command()`, but the function can be called without the
    plugin prefix.  The name is required, in the vain hope that plugin
    developers will think more carefully about cluttering the global namespace.
    """
    return _plugin_hook_decorator(dict(
        event_type='global_command', name=name, doc=doc, is_global=True))

def handler(event_type):
    pass

# TODO: make a @listen thing.  commands can't be general events though because we need to know that exactly one thing corresponds to a command OR we throw an error at eithe rload or runtime


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
        cls._plugin_listeners = []
        for attr_name, attr in attrs.iteritems():
            try:
                cls._plugin_listeners.extend(attr._plugin_listeners)
                del attr._plugin_listeners
            except AttributeError:
                pass


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

class PluginCommand(object):
    def __init__(self, name, doc, command):
        self.name = name
        self.doc = doc
        self.command = command

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
            log.msg('...found ' + name)
            __import__(name)

    def load_plugin(self, plugin_name):
        if plugin_name in self.plugins:
            # Already loaded!  Do nothing.
            # TODO or bomb, or indicate something idk.
            return

        plugin_obj = self.plugin_classes[plugin_name]()
        self.plugins[plugin_name] = plugin_obj

        # Collect event listeners
        # TODO 'doc' here doesn't make any sense for general listeners
        for listen_spec in plugin_obj._plugin_listeners:
            method = getattr(plugin_obj, listen_spec['func_name'])

            # Commands are a little different, as they're aimed directly at a
            # particular plugin
            if listen_spec['event_type'] in ('local_command', 'global_command'):
                if listen_spec['event_type'] == 'global_command':
                    fqn = listen_spec['name']
                else:
                    fqn = '.'.join((plugin_name, listen_spec['name']))

                if fqn in self.commands:
                    raise PluginRegistrationError(
                        """Can't have two commands named {0}""".format(fqn))

                # XXX what should this init look like?  what does a command
                # need to know?  docs, usage...?
                # TODO plugin_command should probably just be callable
                self.commands[fqn] = PluginCommand(
                    name=fqn,
                    doc=listen_spec['doc'],
                    command=method,
                )

            else:
                if not issubclass(listen_spec['event_type'], Event):
                    raise TypeError("Can only listen to Event subclasses")

                # TODO generic event support etc
                self.listeners.setdefault(listen_spec['event_type'], []).append(method)



    def unload_plugin(self, plugin_name):
        del self.plugins[plugin_name]

    def reload_plugin(self, plugin_name):
        raise NotImplementedError


    def run_command(self, command_name, args):
        """..."""
        # XXX more vague planning ahead: should responses be generators?
        # should we pass a writer object or reply callable?  how does the thing
        # communicate back????
        plugin_command = self.commands[command_name]
        response = plugin_command.command(args)

        # TODO check for unicodes maybe.
        return response

    def get_listeners(self, event):
        for cls in event.__class__.__mro__:
            if cls is Event:
                break

            for func in self.listeners.get(cls, []):
                yield func

    # TODO make these less of an exception
    #def core_scan()...
