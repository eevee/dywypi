"""Provides the base class for plugins and dywypi's access to them."""
import exocet
import functools


class PluginRegistrationError(Exception): pass


### Decorators for defining commands

class PluginCommand(object):
    def __init__(self, name, doc):
        self.name = name
        self.doc = doc

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
def command(name=None, doc=None):
    """Decorator that marks a plugin function as a command.  May be stacked to
    give a command several aliases.

    `name` and `doc` default to the name and docstring of the function.
    """
    def decorator(func):
        try:
            command_specs = func._command_specs
        except AttributeError:
            command_specs = []
            func._command_specs = command_specs

        inner_name = name
        if inner_name is None:
            # TODO better checking of name here I guess
            inner_name = func.__name__
        inner_doc = doc
        if inner_doc is None:
            inner_doc = func.__doc__

        spec = PluginCommand(name=inner_name, doc=inner_doc)
        command_specs.append(spec)

        return func

    return decorator


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

        cls._plugin_commands = {}
        # Hunt for commands in this plugin, indicated by being decorated
        for attr_name, attr in attrs.iteritems():
            command_specs = getattr(attr, '_command_specs', [])

            # Associate the command names with method names, not methods
            # themselves, so they can still be called normally -- just in
            # case there are more decorators or other shenanigans
            for spec in command_specs:
                # TODO check for collisions, perhaps.
                spec.func_name = attr_name
                cls._plugin_commands[spec.name] = spec

        # XXX globals only here
        # Use the same trick as below to keep this attribute only on the
        # super-est class
        if hasattr(cls, '_plugin_commands'):
            pass
        else:
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





class _PluginModuleProxy(object):
    def __init__(self, proxy_class):
        self.proxy_class = proxy_class

    def __getattribute__(self, name):
        if name == 'Plugin':
            return object.__getattribute__(self, 'proxy_class')
        else:
            return globals()[name]

class PluginRegistry(object):
    """Manages plugins, their states, and finding/executing commands.

    Plugins are always registered if they're known at all, but they may or may
    not be enabled.  All plugins are disabled initially.  There are three
    primary operations on plugins: `enable_plugin()`, `disable_plugin()`, and
    `reload_plugin()`.

    This uses the magic of exocet to load plugin modules, so they can be
    unloaded and reloaded freely without restarting the program.  Additionally,
    you can technically have two plugin registries, and each will have an
    entirely separate set of plugin code.
    """

    def __init__(self):
        self.plugins = {}

        # This is sort of crazy, but: for plugins to register themselves, they
        # need to use a base class with our metaclass, and we want to keep that
        # base class's plugin list local to the registry.  So we create a new
        # base class here, and use exocet to feed it to plugin modules that try
        # to import Plugin.
        class LocalPlugin(object):
            __metaclass__ = PluginMeta

        # TODO make this also localize every module loaded by plugins, but
        # shared within this registry
        self.exocet_mapper = exocet.pep302Mapper.withOverrides({
            __name__: _PluginModuleProxy(LocalPlugin),
        })
        self.plugin_classes = LocalPlugin._plugins  # instantiated by metaclass

    def discover_plugins(self):
        """Loads every package under dywypi.plugins and finds plugins they
        define.  You probably want to call this early on.
        """
        for module in exocet.getModule('dywypi.plugins').iterModules():
            # No need to do anything with the loaded module; the plugin
            # metaclass kicks in and we don't care about anything else it
            # contains
            print module
            exocet.load(module, self.exocet_mapper)
        print self.plugin_classes
        # OK, self.plugin_classes now contains every plugin class we've got


    def enable_plugin(self, plugin_name):
        if plugin_name in self.plugins:
            # Already enabled!  Do nothing.
            return

        self.plugins[plugin_name] = self.plugin_classes[plugin_name]()
        # TODO register commands, or whatever.

    def disable_plugin(self, plugin_name):
        del self.plugins[plugin_name]
        # TODO unregister commands!

    def reload_plugin(self, plugin_name):
        raise NotImplementedError


    def run_command(self, command, args):
        """..."""
        # PART 1: Find the command
        # XXX commands in general will be "plugin.command", with commands able
        # to be explicitly marked as global and then they can just be
        # "command".  eventually.  for now, commands are just plugin names.
        # XXX also, default commands.
        plugin_name, command_name = command.split('.', 1)

        # PART 2: Do it faggot
        # XXX more vague planning ahead: should responses be generators?
        # should we pass a writer object or reply callable?  how does the thing
        # communicate back????
        plugin = self.plugins[plugin_name]
        spec = plugin._plugin_commands[command_name]
        method = getattr(plugin, spec.func_name)
        response = method(args)

        # TODO check for unicodes maybe.
        return response
