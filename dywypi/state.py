
class Peer:
    def __init__(self, name, ident, host):
        self.name = name
        self.ident = ident
        self.host = host


class Channel:
    def __init__(self, name, key):
        self.topic = None
        self.topic_author = None
        self.topic_timestamp = None
        self.users = []


