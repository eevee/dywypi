"""Event classes.

As dywypi makes a vain attempt to be protocol-agnostic, these should strive to
be so as well, and anything specific to a particular protocol should indicate
as such in its name.
"""
from dywypi.state import Channel, Peer

class Event:
    """Something happened."""
    def __init__(self, client, raw_message):
        self.client = client
        self.loop = client.loop
        self.raw_message = raw_message

    @classmethod
    def from_event(cls, event, *args, **kwargs):
        return cls(event.client, event.raw_message, *args, **kwargs)


class _MessageMixin:
    """Provides some common accesors used by both the regular `Message` event
    and some special specific plugin events.
    """
    @property
    def target(self):
        """Where the message was directed; either a `Channel` (for a public
        message) or a `Peer` (for a private one).
        """
        target_name = self.raw_message.args[0]
        if target_name[0] in '#&!':
            # TODO this should grab an existing Channel instance from the
            # client
            return Channel(target_name)
        else:
            # TODO this too but less urgent
            # TODO this is actually /us/, so.
            return Peer(target_name, None, None)

    @property
    def channel(self):
        """Channel where the message occurred, or None if this was a private
        message.
        """
        target = self.target
        if isinstance(target, Channel):
            return target
        else:
            return None

    @property
    def source(self):
       return Peer.from_prefix(self.raw_message.prefix)

    @property
    def message(self):
        return self.raw_message.args[1]

class Message(Event, _MessageMixin):
    pass
