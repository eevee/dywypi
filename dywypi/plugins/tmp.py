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


@plugin.command('whois')
def whois(event):
    messages = yield from event.client.whois(event.args[0])
    for msg in messages:
        yield from event.reply(repr(msg))


@plugin.command('echo-color')
def echo_color(event):
    from dywypi.formatting import FormattedString, Color
    n = len(event.argstr) // 2
    yield from event.reply(FormattedString(Color.green(event.argstr[:n]), Color.purple(event.argstr[n:])))


@plugin.command('rainbow')
def rainbow(event):
    from dywypi.formatting import FormattedString, Color
    colors = [Color.red, Color.yellow, Color.green, Color.cyan, Color.blue, Color.purple]
    chunks = []
    pos0 = 0
    string = event.argstr
    for n, color in enumerate(colors):
        pos = len(string) * (n + 1) // len(colors)
        chunks.append(color(string[pos0:pos]))
        pos0 = pos

    yield from event.reply(FormattedString(*chunks))
