"""Simple (and fast) commands that produce useful information, without
consulting the network.
"""
import re
import unicodedata
import urllib

from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import getPage

from dywypi.event import PublicMessageEvent, listen
from dywypi.plugin_api import Plugin, command, global_command

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
    def unicode(self, event):
        try:
            if len(event.argv) == 1 and len(event.argv[0]) == 1:
                # This is probably a character
                char = event.argv[0]
            else:
                # This is probably a name
                char = unicodedata.lookup(u' '.join(event.argv))
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

    @global_command('jdic')
    @inlineCallbacks
    def wwwjdic(self, event):
        # Brief explanation of this API:
        # Query string is nMtkxxxxxx
        # n, dictionary: 1 for EDICT
        # M, display mode: M for user-facing, Z for raw
        # t, search type: U for dictionary in utf8, M for kanji utf8
        # k, key type: E or J for dictionary, P for common words only, Q for
        #     exact, R for P+Q.  M plus some more options for kanji.
        # xxxxxx is the search term
        # Docs: http://www.csse.monash.edu.au/~jwb/wwwjdicinf.html#backdoor_tag

        # TODO kanji lookup?  ooh.

        term = urllib.quote_plus(event.argv[0].encode('utf8'))
        response = yield getPage(
            b"http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUR" + term)

        # TODO logging
        print response
        m = re.search(b"<pre>(.+)</pre>", response, flags=re.IGNORECASE | re.DOTALL)
        if not m:
            returnValue(u'Nothing found.')

        # With 'Z' (raw) mode, the output is guaranteed to always be UTF-8
        lines = m.group(1).decode('utf8').strip().splitlines()
        event.reply(lines[0])

    @listen(PublicMessageEvent)
    @inlineCallbacks
    def web_youtube(self, event):
        import re
        import lxml.etree
        for video_id in re.findall(r'https?://www.youtube.com/watch[?]v=(.+?)\b', event.message):
            # TODO this will do them in order instead of in parallel
            response = yield getPage(b"http://gdata.youtube.com/feeds/api/videos/{0}?v=2&fields=title".format(video_id))
            data = lxml.etree.fromstring(response)
            ns = dict(atom='http://www.w3.org/2005/Atom')
            titles = data.xpath('/atom:entry/atom:title', namespaces=ns)
            if len(titles) == 1:
                event.reply(titles[0].text)
            else:
                # XXX uhh yeah
                raise RuntimeError
