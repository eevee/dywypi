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


class Event(object):
    def __init__(self, peer, channel, _protocol, command, argv):
        # TODO need to look up protocol in case there's a reconnect
        self.peer = peer
        self.channel = channel
        self._protocol = _protocol

        self.command = command
        self.argv = argv

    def reply(self, *messages):
        """Reply to the source of the event."""
        # XXX not every event has a source
        # XXX oughta require unicode, or cast, or somethin

        if self.channel:
            prefix = self.peer.nick + ': '
            target = self.channel.name
        else:
            prefix = ''
            target = self.peer.nick

        for message in messages:
            # XXX
            message = message.encode('utf8')
            self._protocol.msg(target, prefix + message)

class CommandEvent(Event): pass

class MessageEvent(Event):
    def __init__(self, *args, **kwargs):
        self.message = kwargs.pop('message')

        super(MessageEvent, self).__init__(*args, **kwargs)

class PublicMessageEvent(MessageEvent): pass



