"""Provides the base class for plugins and dywypi's access to them."""
import exocet


class PluginRegistrationError(Exception): pass


class PluginMeta(type):
    """Metaclass for plugins.  Just used as a form of automatic registration.
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
    """Manages plugins, their states (loading, disabling, reloading), and
    finding commands.

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
            exocet.load(module, self.exocet_mapper)
        # OK, self.plugin_classes now contains every plugin class we've got
