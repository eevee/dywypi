"""Miscellaneous informational commands."""
import re
import unicodedata
import urllib

import aiohttp

from dywypi.plugin import Plugin, PublicMessage


UNICODE_CATEGORIES = dict(
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


plugin = Plugin('info')

@plugin.command('unicode')
def unicode(event):
    try:
        if len(event.argstr) == 1:
            # This is probably a character
            char = event.argstr
        else:
            # This is probably a name
            char = unicodedata.lookup(event.argstr)
    except (KeyError, ValueError):
        yield from event.reply("I don't know what that character is.")
        return

    category = unicodedata.category(char)
    yield from event.reply("{char}  U+{ord:04x} {name}"
        ", in {category} ({category_name})"
        "  http://www.fileformat.info/info/unicode/char/{ord:04x}/index.htm"
    .format(
        char=char,
        ord=ord(char),
        name=unicodedata.name(char),
        category=category,
        category_name=UNICODE_CATEGORIES.get(category, "unknown"),
    ))


@plugin.command('jdic')
def wwwjdic(event):
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

    term = urllib.parse.quote_plus(event.argstr.encode('utf8'))
    response = yield from aiohttp.request(
        'GET',
        "http://www.csse.monash.edu.au/~jwb/cgi-bin/wwwjdic.cgi?1ZUR" + term)

    # TODO logging
    body = yield from response.read()
    m = re.search(b"<pre>(.+)</pre>", body, flags=re.IGNORECASE | re.DOTALL)
    if not m:
        yield from event.reply('Nothing found.')

    # With 'Z' (raw) mode, the output is guaranteed to always be UTF-8
    lines = m.group(1).decode('utf8').strip().splitlines()
    yield from event.reply(lines[0])


@plugin.on(PublicMessage)
def web_youtube(event):
    import re
    import lxml.etree
    for video_id in re.findall(r'https?://www.youtube.com/watch[?]v=(.+?)\b', event.message):
        # TODO this will do them in order instead of in parallel
        response = yield from aiohttp.request(
            'GET',
            "http://gdata.youtube.com/feeds/api/videos/{0}?v=2&fields=title".format(video_id))
        raw_data = yield from response.read()
        # nb: raw_data is a bytearray
        data = lxml.etree.fromstring(bytes(raw_data))
        ns = dict(atom='http://www.w3.org/2005/Atom')
        titles = data.xpath('/atom:entry/atom:title', namespaces=ns)
        if len(titles) == 1:
            yield from event.reply(titles[0].text)
        else:
            # XXX uhh yeah
            raise RuntimeError
