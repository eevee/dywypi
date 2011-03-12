"""Simple (and fast) commands that produce useful information, without
consulting the network.
"""
from dywypi.plugin_api import Plugin, command, global_command

import unicodedata

unicode_categories = dict(
    Cc='Other, Control',
    Cf='Other, Format',
    Cn='Other, Not Assigned',
    Co='Other, Private Use',
    Cs='Other, Surrogate',
    LC='Letter, Cased',
    Ll='Letter, Lowercase',
    Lm='Letter, Modifier',
    Lo='Letter, Other',
    Lt='Letter, Titlecase',
    Lu='Letter, Uppercase',
    Mc='Mark, Spacing Combining',
    Me='Mark, Enclosing',
    Mn='Mark, Nonspacing',
    Nd='Number, Decimal Digit',
    Nl='Number, Letter',
    No='Number, Other',
    Pc='Punctuation, Connector',
    Pd='Punctuation, Dash',
    Pe='Punctuation, Close',
    Pf='Punctuation, Final quote',
    Pi='Punctuation, Initial quote',
    Po='Punctuation, Other',
    Ps='Punctuation, Open',
    Sc='Symbol, Currency',
    Sk='Symbol, Modifier',
    Sm='Symbol, Math',
    So='Symbol, Other',
    Zl='Separator, Line',
    Zp='Separator, Paragraph',
    Zs='Separator, Space',
)

class FYIPlugin(Plugin):
    name = 'fyi'

    @global_command('unicode')
    @command('unicode')
    @command('hurrdurr')
    def unicode(self, args):
        try:
            if len(args) == 1 and len(args[0]) == 1:
                # This is probably a character
                char = args[0]
            else:
                # This is probably a name
                char = unicodedata.lookup(u' '.join(args))
        except (KeyError, ValueError):
            return u"I don't know what that character is."

        category = unicodedata.category(char)
        return u"{char}  U+{ord:04x} {name}" \
            u", in {category} ({category_name})" \
            u"  http://www.fileformat.info/info/unicode/char/{ord:04x}/index.htm" \
        .format(
            char=char,
            ord=ord(char),
            name=unicodedata.name(char),
            category=category,
            category_name=unicode_categories.get(category, "unknown"),
        )
