"""Event classes.

As dywypi makes a vain attempt to be protocol-agnostic, these should strive to
be so as well, and anything specific to a particular protocol should indicate
as such in its name.
"""

class Event:
    """Something happened."""
    def __init__(self, client, raw_message):
        self.client = client
        self.raw_message = raw_message


class Message(Event):
    @property
    def channel(self):
        return self.raw_message.args[0]

    @property
    def message(self):
        return self.raw_message.args[1]
