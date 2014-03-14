# dywypi

**dywypi** is an IRC bot you can extend with plugins.

## Setup

To run dywypi you will need at least Python 3.3 and the asyncio package. Once those are setup, you can install dywypi from the git repo. It is recommended to do this inside a virtualenv.

```
git clone https://github.com/eevee/dywypi.git
cd dywypi
python setup.py develop
```

## Starting the bot

To start the bot run `python -m dywypi ircs://<nick>:<password>@<host>/<channel>`, for example: `python -m dywypi ircs://atlas:hunter2@irc.example.com/example`.

By default, the bot doesn't load any plugins.  Pass one or more `-p <name>` to load plugins by name (or fully-qualified module name), or use `-p ALL` to load all detected plugins.

## Creating a Plugin

Once dywypi is installed, you can create plugins in your own project. To do this, simply create a dywypi_plugins directory in the root of your project. Any plugin in that directory will be automatically loaded when you start dywypi.

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
<atlas> raboof
```
