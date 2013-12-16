class FormattedString:
    def __init__(self, string):
        self.string = string

    def render_irc(self):
        return self.string.format(**{
            'white': '\x0300',
            'blue': '\x0302',
            'bold': '\x02',
            '/bold': '\x02',
        })
