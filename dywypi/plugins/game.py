"""Game helper library."""
# TODO this doesn't seem like it belongs here.  maybe plugin code should live
# in dywypi.plugins and core plugins should populate dywypi_plugins...
import asyncio

#from dywypi.plugin import Load
from dywypi.plugin import Plugin
from dywypi.plugin import PluginCommand


class GamePlugin(Plugin):
    def __init__(self, name, game_factory):
        super().__init__(name)

        self.game_factory = game_factory

        # TODO man i would love for this to work except there's no event loop
        # at initial plugin load time...
        #self.on(Load)(self._onload)

    @asyncio.coroutine
    def _find_game(self, event):
        # TODO how do i let the caller override these?
        if not event.channel:
            yield from event.reply("Sorry, I can only start a game in a channel.")
            return

        games = event.data.setdefault('running_games', {})
        if event.channel not in games:
            games[event.channel] = self.game_factory(event.channel)
        return games[event.channel]


    def game_start(self, command_name):
        def decorator(f):
            def inner_function(event):
                game = yield from self._find_game(event)
                yield from f(event, game)
            coro = asyncio.coroutine(inner_function)
            # TODO collisions etc
            self.commands[command_name] = PluginCommand(
                coro, is_global=False)
            return coro
        return decorator

    def _onload(self, event):
        event.data.setdefault('running_games', {})


class NeedsChannel(Exception):
    """Games can only be played in channels."""
