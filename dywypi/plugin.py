import asyncio
class MessageEvent:
    def __init__(self, client, message):
        self.client = client
        self.channel = message.args[0]
        self.message = message.args[1]

    def reply(self, message):
        asyncio.async(self.client.send_message('PRIVMSG', self.channel, message))

class Plugin:
    def __init__(self, name):
        self.name = name
        self.client = None
        self.message_listeners = []

    def on_message(self, func):
        self.message_listeners.append(asyncio.coroutine(func))

    @asyncio.coroutine
    def send_on_message(self, message):
        event = MessageEvent(self.client, message)
        for listener in self.message_listeners:
            asyncio.async(listener(event))

    def start(self, client):
        self.client = client

echo_plugin = Plugin('echo')

@echo_plugin.on_message
def echo_on_message(event):
    if event.channel != '#dywypi':
        return

    if not event.message.startswith("echo: "):
        return

    event.reply(event.message[6:])
