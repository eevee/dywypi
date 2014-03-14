UNKNOWN = object()


class IRCMode:
    def __init__(self, letter, *,
            prefix=None, arg_on_set=False, arg_on_remove=False, multi=False):
        self.letter = letter
        self.prefix = prefix
        self.arg_on_set = multi or arg_on_set
        self.arg_on_remove = multi or arg_on_remove
        self.multi = multi


class IRCTopic:
    def __init__(self, text, author=None, timestamp=None):
        self.text = text
        self.author = author
        self.timestamp = timestamp


# TODO in general, parts of this object may or may not exist at any given time.
# how do i handle this.  just make coroutine @propertys?  dear lord
class IRCChannel:
    def __init__(self, client, name, *, key=UNKNOWN):
        self.client = client
        self.name = name
        self.key = key
        self.users = {}
        self.topic = None
        self.sync = False

    def add_user(self, user, modes=()):
        self.users[user.name] = user, set(modes)
