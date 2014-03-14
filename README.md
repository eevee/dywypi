# dywypi

**dywypi** is an IRC bot you can extend with plugins.

It also contains a simple IRC protocol implementation for `asyncio`, which can be used independently of the bot.

## Setup

dywypi requires at least Python 3.3 — it's based on the `asyncio` library, which uses the `yield from` syntax.

dywypi has not yet had a stable release, so you must install it from git.  (You may wish to do this from a virtualenv.)

```
pip install [--user] 'git+https://github.com/eevee/dywypi.git#egg=dywypi'
```

## Starting the bot

To start the bot run `python -m dywypi ircs://<nick>:<password>@<host>/<channel>`, for example: `python -m dywypi ircs://atlas:hunter2@irc.example.com/example`.

Note that depending on your system, your Python 3 binary may be called `python3`.

By default, the bot doesn't load any plugins.  Pass one or more `-p <name>` to load plugins by name, or use `-p ALL` to load all detected plugins.

## Creating a plugin

You _do not_ need to edit dywypi's codebase to create new plugins.  Instead, put your plugin modules in a `dywypi_plugins` directory.  Any module in the `dywypi_plugins.` namespace will be automatically discovered and scanned.  (Of course, you must still load your plugin with `-p <name>` or `-p ALL`.)

**Don't** create a `dywypi_plugins/__init__.py`.  `dywypi_plugins` is a _namespace package_ (see [PEP 420](http://legacy.python.org/dev/peps/pep-0420/)) and should never contain an `__init__.py`.

### Example Plugin: Reverse

```python
from dywypi.plugin import Plugin

plugin = Plugin('reverse')

@plugin.command('reverse')
def reverse(event):
    yield from event.reply(event.message[::-1])
```

A conversation with a bot running the reverse plugin would look something like this:

```
<campaul> atlas: reverse foobar
<atlas> campaul: raboof
```

## Development

You can install in "editable" mode by passing `-e` to `pip install`.

The (currently rather small) test suite uses [pytest](http://pytest.org/latest/).  Run it with `py.test dywypi`.  Tox is also supported; you should be able to run `tox` to run the test suite with coverage support and also do a flake8 pass.

Tickets and pull requests are welcome!
