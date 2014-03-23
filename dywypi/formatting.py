from enum import Enum


class Style:
    __slots__ = ('fg', 'bg', 'bold', 'inverse')

    def __init__(self, *, fg=None, bg=None, bold=None, inverse=None):
        # XXX clarify that `None` means "inherit", versus meaning the default
        self.fg = fg
        self.bg = bg
        self.bold = bold
        self.inverse = inverse

    @classmethod
    def default(cls):
        return cls(
            fg=Color.default,
            bold=Bold.off,
        )

    def __repr__(self):
        return "<{}{}>".format(
            type(self).__qualname__,
            repr(self.to_kwargs()),
        )

    def __eq__(self, other):
        if not isinstance(other, Style):
            return NotImplemented

        return self.to_kwargs() == other.to_kwargs()

    def __ne__(self, other):
        return not (self == other)

    def with_(self, *other_styles, **override_kwargs):
        kwargs = self.to_kwargs()

        # TODO i don't like having to skip Nones here...
        for style in other_styles:
            for k, v in style.to_kwargs().items():
                if v is not None:
                    kwargs[k] = v

        for k, v in override_kwargs.items():
            if v is not None:
                kwargs[k] = v

        return type(self)(**kwargs)

    def to_kwargs(self):
        return {
            key: getattr(self, key)
            for key in self.__slots__
        }


# TODO no idea how background works here haha.
class Color(Enum):
    """The sixteen basic terminal/IRC/etc. colors, plus "default" to mean the
    recipient's default colors.
    """
    default = 'default'

    black = 'black'
    blue = 'blue'
    brown = 'brown'
    cyan = 'cyan'
    darkgray = 'darkgray'
    darkred = 'darkred'
    gray = 'gray'
    green = 'green'
    lime = 'lime'
    magenta = 'magenta'
    navy = 'navy'
    purple = 'purple'
    red = 'red'
    teal = 'teal'
    white = 'white'
    yellow = 'yellow'

    def to_style(self):
        return Style(fg=self)

    def __call__(self, *chunks):
        return FormattedString(*chunks, fg=self)


class Bold(Enum):
    off = False
    on = True

    def to_style(self):
        return Style(bold=self)

    def __call__(self, *chunks):
        return FormattedString(*chunks, bold=self)


class FormattedString:
    def __init__(self, *chunks, **styles):
        self.chunks = []
        current_style = Style(**styles)
        for chunk in chunks:
            if isinstance(chunk, FormattedString):
                for subchunk, style in chunk.chunks:
                    self.chunks.append((subchunk, current_style.with_(style)))
            elif isinstance(chunk, Color):
                current_style = current_style.with_(chunk.to_style())
            elif isinstance(chunk, Style):
                current_style = current_style.with_(chunk)
            else:
                self.chunks.append((chunk, current_style))

    @classmethod
    def parse(cls, string, formats):
        raise NotImplementedError

    def __add__(self, other):
        return type(self)(self, other)

    def render(self, format_transition):
        buf = []
        current_style = Style.default()
        for chunk, style in self.chunks + [('', Style.default())]:
            style = Style.default().with_(style)
            if current_style != style:
                buf.append(format_transition(current_style, style))
            buf.append(chunk)
            current_style = style

        buf.append(format_transition(current_style, Style.default()))

        return ''.join(buf)
