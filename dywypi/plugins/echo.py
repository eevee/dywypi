from dywypi.event import Message
from dywypi.plugin import Plugin


plugin = Plugin('echo')

@plugin.on(Message)
def echo(event):
    if event.channel != '#dywypi':
        return

    if not event.message.startswith("echo: "):
        return

    yield from event.reply(event.message[6:])

@plugin.command('echo')
def echo2(event):
    yield from event.reply(event.argstr)
