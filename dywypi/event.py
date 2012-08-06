#from dywypi.plugin_api import _plugin_hook_decorator

nickname = 'dywypi2_0'
encoding = 'utf8'

def listen(event_cls):
    """Similar to `command()`, but the function can be called without the
    plugin prefix.  The name is required, in the vain hope that plugin
    developers will think more carefully about cluttering the global namespace.
    """
    from dywypi.plugin_api import _plugin_hook_decorator
    return _plugin_hook_decorator(dict(event_type=event_cls))



# XXX move me to state?  unclear
class Source(object):
    """Source of an event..."""

    def __init__(self, hub, network, channel, peer):
        self.hub = hub
        self.network = network
        self.channel = channel
        self.peer = peer

    def find_protocol(self):
        # TODO make me a deferred so i work even when disconnected
        return self.hub.protocol_for_network(self.network)

    def reply(self, *messages):
        protocol = self.find_protocol()
        # XXX not even event may have a source i think
        # XXX e.g., what does replying to a system message like PING mean?

        if self.channel:
            prefix = self.peer.name + ': '
            target = self.channel.name
        else:
            prefix = ''
            target = self.peer.name

        for message in messages:
            # XXX
            message = message.encode('utf8')

            protocol._send_public_message(target, prefix + message)






class Event(object):
    def __init__(self, source):
        self.source = source
        # ok so an event OR command may be fired:
        # - on a network
        # - [optionally] in a channel
        # - by a peer
        # OR...
        # - from the shell.
        # OR...
        # - from the web interface.
        # OR...
        # - via jabber or something.
        # TODO need to look up protocol in case there's a reconnect

    def reply(self, *messages):
        """Reply to the source of the event."""
        self.source.reply(*messages)

class CommandEvent(Event):
    def __init__(self, source, command, argv):
        super(CommandEvent, self).__init__(source)
        self.command = command
        self.argv = argv

class MessageEvent(Event):
    def __init__(self, *args, **kwargs):
        self.message = kwargs.pop('message')

        super(MessageEvent, self).__init__(*args, **kwargs)

class PublicMessageEvent(MessageEvent): pass



