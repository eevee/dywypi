"""Provides the base class for plugins and dywypi's access to them."""
from collections import namedtuple
import exocet
import functools
import sys

from twisted.python import log


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
# TODO: game plan
# - write a greeter
# - write a url logger
# - write a url title getter
# - write a wwwjdic plugin
# - write a git plugin
# - write a pokedex plugin
# TODO not-plugin game plan
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


# XXX probably oughta use some zope.interface here   >B)
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

    This uses the magic of exocet to load plugin modules, so they can be
    unloaded and reloaded freely without restarting the program.  Additionally,
    you can technically have two plugin registries, and each will have an
    entirely separate set of plugin code.

    Once a registry is created, call `scan()` to import all dywypi.plugins.*
    modules, which registers all the plugins as *known*.  If new modules are
    added at runtime, calling `scan()` again will pick them up.

    All plugins are unloaded at startup.  "Loading" a plugin just means
    instantiating a plugin object; your plugin's `__init__` method should do
    any necessary setup.

    When a plugin is unloaded, its plugin object is deleted.  The module source
    will be reloaded next time the plugin is loaded.
    """

    # TODO how to handle plugin teardown?
    # TODO need to feed plugins a proxy reactor so their connections can be canceled when we're done

    # XXX this needs some better sense of arrangement!
    # MODULES have PLUGINS have COMMANDS.
    # need to get anywhere in this tree given a plugin/module/command name  :(

    def __init__(self):
        # plugin_name => plugin object
        self.plugins = {}
        # command_name => PluginCommand object
        self.commands = {}

        # Small objects representing plugin event listeners
        self.listeners = []

        self.loaded_module_names = set()

        # This is sort of crazy, but: for plugins to register themselves, they
        # need to use a base class with our metaclass, and we want to keep that
        # base class's plugin list local to the registry.  So we create a new
        # base class here, and use exocet to feed it to plugin modules that try
        # to import Plugin.
        class LocalPlugin(object):
            __metaclass__ = PluginMeta

        # TODO make this also localize every module loaded by plugins, but
        # shared within this registry?
        self.exocet_mapper = exocet.pep302Mapper.withOverrides({
            __name__: exocet.proxyModule(
                sys.modules[__name__], Plugin=LocalPlugin),
        })
        self.plugin_classes = LocalPlugin._plugins  # instantiated by metaclass

    def scan(self):
        """Imports every module under dywypi.plugins and finds the plugins they
        define.  Modules that have already been loaded are not loaded again.
        """
        log.msg('Scanning for plugin modules')
        for module in exocet.getModule('dywypi.plugins').iterModules():
            module_name = module.name
            if module.name in self.loaded_module_names:
                log.msg("...already imported: {0}".format(module.name))
                continue

            self.loaded_module_names.add(module.name)
            log.msg("...importing: {0}".format(module.name))

            # No need to do anything with the loaded module; the plugin
            # metaclass kicks in and we don't care about anything else it
            # contains
            exocet.load(module, self.exocet_mapper)

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
                    command=getattr(plugin_obj, listen_spec['func_name']),
                )

            else:
                # TODO generic event support etc
                pass


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

    # TODO make these less of an exception
    #def core_scan()...
