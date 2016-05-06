"""Shell interface for dywypi.  Allows urwid to take over the terminal and do
interesting things.
"""
# Many thanks to habnabit and aafshar, from whom I stole judiciously.
# Their implementations:
# - https://code.launchpad.net/~habnabit/+junk/urwid-protocol
# - https://bitbucket.org/aafshar/txurwid-main/src

# TODO originally all this code was intended to work with multiple shells (e.g.
# multiple ssh clients).  it still could, but would require a bit of extra work
# to make a fake writer.  also i'm not sure how that interacts with cbreak.

import asyncio
from asyncio.queues import Queue
from io import BytesIO
import logging
import os
import sys

import urwid
from urwid.raw_display import Screen

from dywypi.event import Message
from dywypi.formatting import Bold, Color, Style
from dywypi.state import Peer

log = logging.getLogger(__name__)


class AsyncScreen(Screen):
    """An Urwid screen that speaks to an asyncio stream, rather than mucking
    directly with stdin and stdout.
    """

    def __init__(self, reader, writer, encoding='utf8'):
        self.reader = reader
        self.writer = writer
        self.encoding = encoding

        # Allow using the defaults of stdin and stdout, so the screen size and
        # whatnot are still detected correctly
        Screen.__init__(self)

        self.colors = 256
        self.bright_is_bold = False
        self.register_palette_entry(None, 'default', 'default')

    # Urwid Screen API

    def write(self, data):
        self.writer.write(data.encode(self.encoding))

    def flush(self):
        pass

    _pending_task = None

    def hook_event_loop(self, event_loop, callback):
        # Wait on the reader's read coro, and when there's data to read, call
        # the callback and then wait again
        def pump_reader(fut=None):
            if fut is None:
                # First call, do nothing
                pass
            elif fut.cancelled():
                # This is in response to an earlier .read() call, so don't
                # schedule another one!
                return
            elif fut.exception():
                pass
            else:
                try:
                    self.parse_input(
                        event_loop, callback, bytearray(fut.result()))
                except urwid.ExitMainLoop:
                    # This will immediately close the transport and thus the
                    # connection, which in turn calls connection_lost, which
                    # stops the screen and the loop
                    self.writer.abort()

            # asyncio.async() schedules a coroutine without using `yield from`,
            # which would make this code not work on Python 2
            self._pending_task = asyncio.ensure_future(
                self.reader.read(1024), loop=event_loop._loop)
            self._pending_task.add_done_callback(pump_reader)

        pump_reader()

    def unhook_event_loop(self, event_loop):
        if self._pending_task:
            self._pending_task.cancel()
            del self._pending_task


# TODO: catch ExitMainLoop somewhere
# TODO: when urwid wants to stop, need to close the connection and kill the service AND then the reactor...
# TODO: ctrl-c is apparently caught by twistd, not urwid?
class UrwidProtocol(asyncio.Protocol):
    """A Protocol that passes input along from a transport into urwid's main
    loop.

    There are several methods stubbed out here that you'll need to subclass and
    implement.
    """
    def __init__(self, loop, writer):
        self.loop = loop
        self.writer = writer

    def connection_made(self, transport):
        self.transport = transport

        self.reader = asyncio.StreamReader(loop=self.loop)
        self.screen = AsyncScreen(self.reader, self.writer)

        self.widget = self.build_toplevel_widget()
        self.urwid_loop = urwid.MainLoop(
            self.widget,
            screen=self.screen,
            event_loop=urwid.AsyncioEventLoop(loop=self.loop),
            unhandled_input=self.unhandled_input,
            palette=self.build_palette(),
        )

        self.urwid_loop.start()

        # TODO not sure this belongs here
        self.log_handler = DywypiShellLoggingHandler(self)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)

    def data_received(self, data):
        self.reader.feed_data(data)

    def connection_lost(self, exc):
        self.reader.feed_eof()
        self.urwid_loop.stop()

    # Override these guys:

    def build_toplevel_widget(self):
        """Returns the urwid widget to use as the top-level display."""
        raise NotImplementedError

    def build_palette(self):
        """Returns an Urwid palette to use."""
        raise NotImplementedError

    def unhandled_input(self, input):
        """Do something with unhandled keypresses."""
        pass


### DYWYPI-SPECIFIC FROM HERE

class UnselectableListBox(urwid.ListBox):
    """A ListBox that cannot receive focus."""
    _selectable = False


class FancyEdit(urwid.Edit):
    """An Edit control with history, that broadcasts its value when Enter is
    pressed.
    """
    def __init__(self, *args, **kwargs):
        self.__super.__init__(*args, **kwargs)
        self._history = []

    def keypress(self, size, key):
        if key == 'enter':
            line = self.edit_text
            urwid.emit_signal(self, 'line_submitted', line)
            self._history.append(line)
            self.edit_text = ''

        else:
            return self.__super.keypress(size, key)


urwid.register_signal(FancyEdit, ['line_submitted'])


class DywypiShell(UrwidProtocol):
    """Creates a Twisted-friendly urwid app that allows interacting with dywypi
    via a shell.
    """

    # TODO i don't think client.nick should really be part of the exposed
    # interface; should be a .me returning a peer probably
    # TODO for some reason this is the client even though the thing below is
    # actually called a Client so we should figure this the fuck out
    nick = 'dywypi'

    def __init__(self, loop, network, *args, **kwargs):
        super().__init__(loop, **kwargs)

        self.event_queue = Queue(loop=self.loop)

        self.network = network

        self.me = Peer('dywypi', 'dywypi', 'localhost')
        self.you = Peer('user', 'user', 'localhost')


    def build_toplevel_widget(self):
        self.pane = UnselectableListBox(urwid.SimpleListWalker([]))
        prompt = FancyEdit('>>> ')
        urwid.connect_signal(prompt, 'line_submitted', self.handle_line)

        return urwid.Pile(
            [
                self.pane,
                ('flow', prompt),
            ],
            focus_item=prompt,
        )

    def build_palette(self):
        return [
            ('default', 'default', 'default'),
            ('logging-debug', 'dark gray', 'default'),
            ('logging-info', 'light gray', 'default'),
            ('logging-warning', 'light red', 'default'),
            ('logging-error', 'dark red', 'default'),
            ('logging-critical', 'light magenta', 'default'),
            ('shell-input', 'light gray', 'default'),
            ('bot-output', 'default', 'default'),
            ('bot-output-label', 'dark cyan', 'default'),
        ]

    def unhandled_input(self, key):
        # Try passing the key along to the listbox, so pgup/pgdn still work.
        # Note that this is a Pile method specifically, and requires an index
        # rather than a widget
        # TODO no indication whether we're currently scrolled up.  scroll back
        # to bottom after x seconds with no input?
        listsize = self.widget.get_item_size(
            self.urwid_loop.screen_size, 0, False)
        key = self.pane.keypress(listsize, key)
        if key:
            # `key` gets returned if it wasn't consumed
            self.add_log_line(key)

    def add_log_line(self, line, color='default'):
        # TODO generalize this color thing in a way compatible with irc, html, ...
        # TODO i super duper want this for logging, showing incoming/outgoing
        # messages in the right colors, etc!!
        self._print_text((color, line.rstrip()))

    def _print_text(self, *encoded_text):
        self.pane.body.append(urwid.Text(list(encoded_text)))
        self.pane.set_focus(len(self.pane.body) - 1)
        # TODO should this just mark dirty??
        self.urwid_loop.draw_screen()

    def handle_line(self, line):
        """Deal with a line of input."""
        try:
            self._handle_line(line)
        except Exception as e:
            log.exception(e)

    def _handle_line(self, line):
        """All the good stuff happens here.

        Various things happen depending on what the line starts with.

        Colon: This is a command; pretend it was sent as a private message.
        """
        # Whatever it was, log it
        self.pane.body.append(urwid.Text(['>>> ', ('shell-input', line)]))

        if line.startswith(':'):
            command_string = line[1:]

            # TODO rather we didn't need raw_message...
            raw_message = ShellMessage(self.me.name, command_string)
            event = Message(self, raw_message)
            self.event_queue.put_nowait(event)

    def _send_message(self, target, message, as_notice=True):
        # TODO cool color
        self.add_log_line(message)

    @asyncio.coroutine
    def say(self, target, message):
        # TODO target should probably be a peer, eh
        if target == self.you.name:
            prefix = "bot to you: "
        else:
            prefix = "bot to {}: ".format(target)
        self._print_text(('bot-output-label', prefix), ('bot-output', message))

    def format_transition(self, current_style, new_style):
        # TODO wait lol shouldn't this be converting to urwid-style tuples
        if new_style == Style.default():
            # Just use the reset sequence
            return '\x1b[0m'

        ansi_codes = []
        if new_style.fg != current_style.fg:
            ansi_codes.append(FOREGROUND_CODES[new_style.fg])

        if new_style.bold != current_style.bold:
            ansi_codes.append(BOLD_CODES[new_style.bold])

        return '\x1b[' + ';'.join(ansi_codes) + 'm'


# TODO this shouldn't need to exist i think
class ShellMessage:
    def __init__(self, *args):
        self.args = args

LOG_LEVEL_COLORS = {
    logging.DEBUG: 'logging-debug',
    logging.INFO: 'logging-info',
    logging.WARNING: 'logging-warning',
    logging.ERROR: 'logging-error',
    logging.CRITICAL: 'logging-critical',
}
class DywypiShellLoggingHandler(logging.Handler):
    def __init__(self, shell_service):
        self.shell_service = shell_service
        super().__init__()

    def emit(self, record):
        try:
            msg = self.format(record)
            try:
                color = LOG_LEVEL_COLORS[record.levelno]
            except KeyError:
                color = LOG_LEVEL_COLORS[logging.INFO]
            self.shell_service.add_log_line(msg, color=color)
        except Exception:
            self.handleError(record)


        '''
        # Format
        line = "{time} [{system}] {text}\n".format(
            time=self.formatTime(event['time']),
            system=event['system'],
            text=text.replace('\n', '\n\t'),
        )
        '''


FOREGROUND_CODES = {
    Color.default: '39',

    Color.black: '30',
    Color.red: '31',
    Color.green: '32',
    Color.brown: '33',
    Color.blue: '34',
    Color.purple: '35',
    Color.teal: '36',
    Color.gray: '37',

    # Bright colors use aixterm sequences, which are nonstandard, but work
    # virtually everywhere in practice
    Color.darkgray: '90',
    Color.red: '91',
    Color.lime: '92',
    Color.yellow: '93',
    Color.blue: '94',
    Color.magenta: '95',
    Color.cyan: '96',
    Color.white: '97',
}
BOLD_CODES = {
    Bold.on: '1',
    Bold.off: '22',
}


# TODO standardize what these look like
class ShellClient:
    def __init__(self, loop, network):
        self.loop = loop
        self.network = network

        # TODO it would be nice to parametrize these (or even accept arbitrary
        # transports), but the event loop doesn't support async reading from
        # ttys for some reason...
        # Note that we're using .buffer here so the underlying handles all work
        # in bytes, just like any other socket normally would.
        self.stdin = sys.stdin.buffer
        self.stdout = sys.stdout.buffer.raw

    @asyncio.coroutine
    def connect(self):
        # TODO would be nice to intercept stdout and turn it into logging?

        # I need fdopen() here for some complicated reasons relating to how
        # stdin/stdout work; they're references to the same bidirectional pty,
        # which something something a miracle occurs, causes asyncio to get
        # confused about when they're readable or writable, which in turn
        # causes os.write() to fail eventually.
        writer, _ = yield from self.loop.connect_write_pipe(
            asyncio.Protocol, os.fdopen(0, 'wb'))
        proto = DywypiShell(self.loop, self.network, writer=writer)
        _, self.protocol = yield from self.loop.connect_read_pipe(
            lambda: proto, self.stdin)

    @asyncio.coroutine
    def disconnect(self):
        self.protocol.connection_lost(None)
        # TODO close reader?  or is that the protocol's problem?

    @asyncio.coroutine
    def read_event(self):
        # For now, this will never ever do anything.
        # TODO this sure looks a lot like IRCClient
        return (yield from self.protocol.event_queue.get())
