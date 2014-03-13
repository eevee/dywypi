# dywypi

**dywypi** is an IRC bot you can extend with plugins.

## Setup

To run dywypi you will need at least Python 3.3 and the asyncio package. Once those are setup, you can install dywypi from the git repo. It is recommended to do this inside a virtualenv.

```
git clone https://github.com/eevee/dywypi.git
cd dywypi
python setup.py develop
```

## Starting the Server

To start the server run `python -m dywypi ircs://<nick>:<password>@<site> <room>`, for example: `python -m dywpi ircs://atlas:hunter2@irc.example.com #example`.

## Creating a Plugin

Once dywypi is installed, you can create plugins in your own project. To do this, simply create a dywypi_plugins directory in the root of your project. Any plugin in that directory will be automatically loaded when you start dywypi.

### Example Plugin: Reverse

```
from dywypi.plugin import Plugin

plugin = Plugin('reverse')

@plugin.command('reverse')
def reverse(event):
    yield from event.reply(event.message[::-1])
```

A conversation with a bot running the reverse plugin would look something like this:

<campaul> atlas: reverse foobar
<atlas> raboof
