"""Messing around.  Stuff in here is not (yet?) meant to be serious bot
functionality, even more explicitly so than most of what we've got so far.
"""
from dywypi.plugin import Plugin


plugin = Plugin('tmp')


@plugin.command('names')
def names(event):
    if not event.channel:
        yield from event.reply("I can only do this in a channel.")
        return

    yield from event.reply("Got some users: {!r}".format(event.channel.users))


@plugin.command('getnames')
def names(event):
    names = yield from event.client.names(event.args[0])
    yield from event.reply("names returned: {!r}".format(names))
