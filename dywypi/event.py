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


class Message(Event):
    @property
    def channel(self):
        return self.raw_message.args[0]

    @property
    def target(self):
        target_name = self.raw_message.args[0]
        if target_name[0] in '#&!':
            return Channel(target_name)
        else:
            return Peer(target_name)

    @property
    def message(self):
        return self.raw_message.args[1]
