from dywypi.event import Message
from dywypi.plugin import Plugin


plugin = Plugin('core')

@plugin.command('help')
def plugin_help(event):
    manager = event._plugin_manager
    # TODO this reminds me that maybe i want command arg parsing
    if event.args:
        plugin_name, = event.args
        if plugin_name in manager.loaded_plugins:
            plugin = manager.loaded_plugins[plugin_name]
            yield from event.reply(
                "{} commands: {}"
                .format(plugin.name, ', '.join(plugin.commands)))
            # TODO also list other things it listens on?  how?
        else:
            yield from event.reply(
                "I don't seem to have a plugin named {}.".format(plugin_name))

    else:
        yield from event.reply(
            "Loaded plugins: {}".format(
                ', '.join(manager.loaded_plugins.keys())))
