"""Event classes.

As dywypi makes a vain attempt to be protocol-agnostic, these should strive to
be so as well, and anything specific to a particular protocol should indicate
as such in its name.
"""

class Event:
    """Something happened."""
    def __init__(self, client, message):
        self.client = client
        self.message = message

class Message(Event):
    pass
