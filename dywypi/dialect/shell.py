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


class UrwidDummyInput(object):
    """Fake stdin.

    The only thing we want urwid to know about stdin is that its fd is zero
    (mainly for setting cbreak).
    """
    def fileno(self):
        # TODO this doesn't work over a network.  obviously.  need protocol
        # support for that; telnet can do it.
        return 0


class ProtocolFileAdapter(object):
    """Fake stdout.

    File-like object, at least as much as urwid cares, that redirects
    urwid's stdout through a protocol and ignores flushes.
    """
    def __init__(self, transport):
        self.transport = transport

    def write(self, s):
        if isinstance(s, str):
            s = s.encode('latin1')
        self.transport.write(s)

    def flush(self):
        pass


class AsyncScreen(Screen):
    """An Urwid screen that speaks to an asyncio transport, rather than mucking
    directly with stdin and stdout.
    """

    def __init__(self, transport, protocol):
        self.transport = transport
        self.protocol = protocol

        Screen.__init__(self)
        self.colors = 256
        self.bright_is_bold = True
        self.register_palette_entry(None, 'default', 'default')

        # Don't let urwid mess with stdin/stdout directly; give it these dummy
        # objects instead
        self._term_input_file = UrwidDummyInput()
        self._term_output_file = ProtocolFileAdapter(self.transport)

    # Urwid Screen API

    # XXX untested
    def set_mouse_tracking(self):
        """Enable mouse tracking.

        After calling this function get_input will include mouse
        click events along with keystrokes.
        """
        # XXX FIXME
        return
        self.transport.write(urwid.escape.MOUSE_TRACKING_ON)

        self._start_gpm_tracking()

    def get_input_descriptors(self):
        # We don't really have file descriptors, only transports, so return
        # nothing here and call MainLoop._update manually
        return []

    def get_input(self, raw_keys=False):
        # Do nothing here either.  Only used when MainLoop doesn't have an
        # event loop, which doesn't happen here.
        return

    def get_input_nonblocking(self):
        codes = self.protocol.buf.getvalue()
        self.protocol.buf = BytesIO()

        processed_keys = []
        original_codes = codes
        while codes:
            keys, codes = urwid.escape.process_keyqueue(codes, True)
            processed_keys.extend(keys)

            # TODO catch escape.MoreInputRequired?

        return None, processed_keys, original_codes

    # Private
    def _start_gpm_tracking(self):
        # TODO unclear if any of this is necessary locally
        # also it doesn't work anyway due to missing imports
        if not os.path.isfile("/usr/bin/mev"):
            return
        if not os.environ.get('TERM',"").lower().startswith("linux"):
            return
        if not Popen:
            return
        m = Popen(["/usr/bin/mev","-e","158"], stdin=PIPE, stdout=PIPE,
            close_fds=True)
        fcntl.fcntl(m.stdout.fileno(), fcntl.F_SETFL, os.O_NONBLOCK)
        self.gpm_mev = m

    def _stop_gpm_tracking(self):
        os.kill(self.gpm_mev.pid, signal.SIGINT)
        os.waitpid(self.gpm_mev.pid, 0)
        self.gpm_mev = None


class AsyncioUrwidEventLoop:
    def __init__(self, loop):
        self.loop = loop
        self._started_loop = False
        self._exc_info = None

    def alarm(self, seconds, callback):
        """
        Call callback() given time from from now.  No parameters are
        passed to callback.

        Returns a handle that may be passed to remove_alarm()

        seconds -- floating point time to wait before calling callback
        callback -- function to call from event loop
        """
        handle = self.loop.call_later(seconds, callback)
        return handle

    def remove_alarm(self, handle):
        """
        Remove an alarm.

        Returns True if the alarm exists, False otherwise
        """
        handle.cancel()
        return True

    def watch_file(self, fd, callback):
        """
        Call callback() when fd has some data to read.  No parameters
        are passed to callback.

        Returns a handle that may be passed to remove_watch_file()

        fd -- file descriptor to watch for input
        callback -- function to call when input is available
        """
        self.loop.add_reader(fd, callback)
        return fd

    def remove_watch_file(self, handle):
        """
        Remove an input file.

        Returns True if the input file exists, False otherwise
        """
        fd = handle
        return self.loop.remove_reader(fd)

    def enter_idle(self, callback):
        """
        Add a callback for entering idle.

        Returns a handle that may be passed to remove_enter_idle()
        """
        # There's no such thing as "idle" in asyncio, so use a timer with an
        # arbitrary resolution of, oh I don't know, 10fps.
        return asyncio.async(self._idle_coro(callback), loop=self.loop)

    @asyncio.coroutine
    def _idle_coro(self, callback):
        while True:
            yield from asyncio.sleep(0.1, loop=self.loop)
            callback()

    def remove_enter_idle(self, handle):
        """
        Remove an idle callback.

        Returns True if the handle was removed.
        """
        handle.cancel()
        return True

    def run(self):
        """
        Start the event loop.  Exit the loop when any callback raises
        an exception.  If ExitMainLoop is raised, exit cleanly.
        """
        if self.loop.is_running():
            # Don't try to start it again!
            self._started_loop = False
            # TODO wait i think uh we're supposed to block here or else urwid
            # "cleans up" immediately?
            print('uh wait uhoh')
            return
        else:
            self._started_loop = True
            self.loop.run_forever()

        if self._exc_info:
            # An exception caused us to exit, raise it now
            exc_info = self._exc_info
            self._exc_info = None
            raise exc_info[0](exc_info[1]) from exc_info[2]

    def handle_exit(self, f):
        """
        Decorator that cleanly exits the :class:`TwistedEventLoop` if
        :class:`ExitMainLoop` is thrown inside of the wrapped function. Store the
        exception info if some other exception occurs, it will be reraised after
        the loop quits.

        *f* -- function to be wrapped
        """
        from urwid.main_loop import ExitMainLoop
        def wrapper(*args,**kargs):
            rval = None
            try:
                rval = f(*args,**kargs)
            except ExitMainLoop:
                if self._started_loop:
                    self.loop.stop()
            except Exception:
                self._exc_info = sys.exc_info()
                if self._started_loop:
                    self.loop.stop()
            return rval
        return wrapper


# TODO: catch ExitMainLoop somewhere
# TODO: when urwid wants to stop, need to close the connection and kill the service AND then the reactor...
# TODO: ctrl-c is apparently caught by twistd, not urwid?
class UrwidProtocol(asyncio.Protocol):
    """A Protocol that passes input along from a transport into urwid's main
    loop.

    There are several methods stubbed out here that you'll need to subclass and
    implement.
    """

    def __init__(self, loop, *, writer=None):
        self.buf = BytesIO()

        self.loop = loop
        # TODO this is a dumb hack because it's needlessly painful to get a
        # bidirectional transport from a pair of existing pipes
        self.writer = writer

    ### Protocol interface
    def connection_made(self, transport):
        # TODO more dumb hack
        if not self.writer:
            self.writer = transport

        self.widget = self.build_toplevel_widget()
        self.screen = AsyncScreen(self.writer, self)
        self.urwid_loop = urwid.MainLoop(
            self.widget,
            screen=self.screen,
            event_loop=AsyncioUrwidEventLoop(self.loop),
            unhandled_input=self.unhandled_input,
            palette=self.build_palette(),
        )

        self.start()

        self.log_handler = DywypiShellLoggingHandler(self)
        root_logger = logging.getLogger()
        root_logger.addHandler(self.log_handler)
        # TODO remove handler shenanigans on connection lost

    def _loop_exception_handler(self, loop, context):
        if context.get('exception'):
            try:
                log.exception(context['exception'])
            except Exception as e:
                import sys
                sys.stderr.write(repr(context))
                sys.stderr.write(repr(e))

    def data_received(self, data):
        """Pass keypresses to urwid's main loop, which knows how to handle
        them.
        """
        self.buf.write(data)
        # This is what Urwid usually schedules with watch_file, but we don't
        # HAVE files, so call it manually
        self.urwid_loop._update()
        self.urwid_loop.draw_screen()

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

    # Starting and stopping urwid

    def start(self):
        self.screen.start()
        # TODO it would be nice for this to work, but it expects to block on
        # running the event loop, which obviously is a no go
        #self.urwid_loop.run()

        # Instead, we have to schedule this ourselves...
        # TODO rather not use this hacky method in the first place
        self.urwid_loop.event_loop.enter_idle(self.urwid_loop.entering_idle)

    def stop(self):
        # TODO this probably needs slightly more effort
        self.screen.stop()


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
            ('logging-debug', 'dark green', 'default'),
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

    def start(self):
        super(DywypiShell, self).start()

        #self.hub.network_connected(self.network, self)

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

    # TODO split the client interface out from the protocol?
    def source_from_message(self, raw_message):
        """Produce a peer of some sort from a raw message."""
        # TODO maybe a less dumb thing
        return self.you

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

        # TODO why do i not need this???
        #from asyncio.unix_events import _set_nonblocking
        #_set_nonblocking(self.stdin.fileno())

        proto = DywypiShell(self.loop, self.network, writer=self.stdout)
        _, self.protocol = yield from self.loop.connect_read_pipe(
            lambda: proto, self.stdin)

    @asyncio.coroutine
    def disconnect(self):
        self.protocol.stop()
        # TODO close reader?  or is that the protocol's problem?

    @asyncio.coroutine
    def read_event(self):
        # For now, this will never ever do anything.
        # TODO this sure looks a lot like IRCClient
        return (yield from self.protocol.event_queue.get())
