"""Shell interface for dywypi.  Allows urwid to take over the terminal and do
interesting things.
"""
# Many thanks to habnabit and aafshar, from whom I stole judiciously.
# Their implementations:
# - https://code.launchpad.net/~habnabit/+junk/urwid-protocol
# - https://bitbucket.org/aafshar/txurwid-main/src

import asyncio
from asyncio.queues import Queue
import logging
import os
import sys

import urwid
from urwid.raw_display import Screen

logger = logging.getLogger(__name__)


class UrwidDummyInput(object):
    """Fake stdin.

    The only thing we want urwid to know about stdin is that its fd is zero
    (mainly for setting cbreak).
    """
    def fileno(self):
        return 0

# TODO was adapter
class ProtocolFileAdapter(object):
    """Fake stdout.

    File-like object, at least as much as urwid cares, that redirects
    urwid's stdout through a protocol and ignores flushes.
    """
    def __init__(self, transport):
        self.transport = transport

    def write(self, s):
        self.transport.write(s)

    def flush(self):
        pass


class AsyncScreen(Screen):
    """An Urwid screen that speaks to an asyncio transport, rather than mucking
    directly with stdin and stdout.
    """

    def __init__(self, transport):
        self.transport = transport

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
        self.transport.write(urwid.escape.MOUSE_TRACKING_ON)

        self._start_gpm_tracking()

    # asyncio handles polling, so we don't need the loop to do it, we just push
    # what we get to the loop from dataReceived.
    def get_input_descriptors(self):
        return []

    # Do nothing here either. Not entirely sure when it gets called.
    def get_input(self, raw_keys=False):
        return

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


class UrwidTerminalProtocol(asyncio.Protocol):
    """A Protocol that passes input along from a transport into urwid's main
    loop.
    """

    def __init__(self, bridge_factory, loop):
        self.bridge_factory = bridge_factory
        self.loop = loop

    def connection_made(self, transport):
        self.bridge = self.bridge_factory(self.loop, self, transport)
        self.bridge.start()
        self.log_handler = DywypiShellLoggingHandler(self.bridge)
        dywypi_logger = logging.getLogger('dywypi')
        dywypi_logger.addHandler(self.log_handler)
        dywypi_logger.propagate = False
        # TODO remove handler shenanigans on connection lost
        logger.info('connection made')

    def data_received(self, data):
        """Pass keypresses along the bridge to urwid's main loop, which knows
        how to handle them.
        """
        self.bridge.push_input(data)


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
        return self.loop.call_soon(callback)

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
class AsyncUrwidBridge(object):
    """Core of a simple bridge between asyncio and Urwid running on a local
    terminal.  Subclass this guy.
    """

    loop = None

    def __init__(self, loop, terminal_protocol, write_transport):
        self.terminal_protocol = terminal_protocol

        self.widget = self.build_toplevel_widget()

        self.screen = AsyncScreen(write_transport)
        self.loop = urwid.MainLoop(
            self.widget,
            screen=self.screen,
            event_loop=AsyncioUrwidEventLoop(loop),
            unhandled_input=self.unhandled_input,
            palette=self.build_palette(),
        )

    def redraw(self):
        self.loop.draw_screen()

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
        self.loop.run()

    def stop(self):
        # TODO this probably needs slightly more effort
        self.screen.stop()

    # UrwidTerminalProtocol interface

    def push_input(self, data):
        """Receive data from Twisted and push it into urwid's main loop.
        """
        # Emulate urwid's input handling.
        # Filter the input...
        filtered_data = self.loop.input_filter(data, [])
        # Let urwid do some crunching to figure out escape sequences...
        codes = list(map(ord, filtered_data))
        processed_keys = []
        while codes:
            keys, codes = urwid.escape.process_keyqueue(codes, True)
            processed_keys.extend(keys)
        # Send it along to the main loop...
        self.loop.process_input(processed_keys)
        # And redraw.
        self.redraw()


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


class DywypiShell(AsyncUrwidBridge):
    """Creates a Twisted-friendly urwid app that allows interacting with dywypi
    via a shell.
    """
    def __init__(self, *args, **kwargs):
        #self.hub = kwargs.pop('hub')
        super(DywypiShell, self).__init__(*args, **kwargs)

        # TODO does this need to be a real object?  a real Network instance?
        self.network = object()

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
        ]

    def unhandled_input(self, key):
        # Try passing the key along to the listbox, so pgup/pgdn still work.
        # Note that this is a Pile method specifically, and requires an index
        # rather than a widget
        # TODO no indication whether we're currently scrolled up.  scroll back
        # to bottom after x seconds with no input?
        listsize = self.widget.get_item_size(
            self.loop.screen_size, 0, False)
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
        self.pane.body.append(urwid.Text((color, line.rstrip())))
        self.pane.set_focus(len(self.pane.body) - 1)
        self.redraw()

    def handle_line(self, line):
        """Deal with a line of input."""
        logger.info(line)

        #from twisted.internet import defer
        # XXX this is here cause it allows exceptions to actually be caught; be more careful with that in general
        #defer.execute(self._handle_line, line)

    def _handle_line(self, line):
        if line.startswith(':'):
            command_string = line[1:]

            encoding = 'utf8'

            from dywypi.event import EventSource
            class wat(object): pass
            peer = wat()
            peer.name = None
            source = EventSource(self.network, peer, None)

            #self.hub.run_command_string(source, command_string.decode(encoding))

    def _send_message(self, target, message, as_notice=True):
        # TODO cool color
        self.add_log_line(message)


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


# TODO i want to write some nice wrappers for this i think...
class TrivialFileTransport(asyncio.Transport):
    """Transport that wraps two arbitrary file-likes -- which should probably
    be normal local files, or you'd be better off using a different transport.
    """

    def __init__(self, loop, infile, outfile, protocol):
        super().__init__()
        self._loop = loop
        self._infile = infile
        self._outfile = outfile
        self._protocol = protocol

        # TODO maybe i belong elsewhere
        from asyncio.unix_events import _set_nonblocking
        _set_nonblocking(self._infile.fileno())

        # TODO it would perhaps be possible for this to work with arbitrary
        # file-likes, too.
        loop.add_reader(infile, self._do_read)
        loop.call_soon(protocol.connection_made, self)

    def _do_read(self):
        self._protocol.data_received(self._infile.read())

    # ReadTransport interface

    def pause_reading(self):
        pass

    def resume_reading(self):
        pass

    # WriteTransport interface

    def set_write_buffer_limits(self, high=None, low=None):
        """Set the high- and low-water limits for write flow control.

        These two values control when to call the protocol's
        pause_writing() and resume_writing() methods.  If specified,
        the low-water limit must be less than or equal to the
        high-water limit.  Neither value can be negative.

        The defaults are implementation-specific.  If only the
        high-water limit is given, the low-water limit defaults to a
        implementation-specific value less than or equal to the
        high-water limit.  Setting high to zero forces low to zero as
        well, and causes pause_writing() to be called whenever the
        buffer becomes non-empty.  Setting low to zero causes
        resume_writing() to be called only once the buffer is empty.
        Use of zero for either limit is generally sub-optimal as it
        reduces opportunities for doing I/O and computation
        concurrently.
        """
        pass

    def get_write_buffer_size(self):
        """Return the current size of the write buffer."""
        return 0

    def write(self, data):
        """Write some data bytes to the transport.

        This does not block; it buffers the data and arranges for it
        to be sent out asynchronously.
        """
        # TODO this totally blocks.  but should be instant.  right?
        self._outfile.write(data)
        self._outfile.flush()

    def write_eof(self):
        """Closes the write end after flushing buffered data.

        (This is like typing ^D into a UNIX program reading from stdin.)

        Data may still be received.
        """
        self._outfile.close()

    def can_write_eof(self):
        """Return True if this protocol supports write_eof(), False if not."""
        return True

    def abort(self):
        """Closes the transport immediately.

        Buffered data will be lost.  No more data will be received.
        The protocol's connection_lost() method will (eventually) be
        called with None as its argument.
        """
        self._outfile.close()


# TODO standardize what these look like
class ShellClient:
    def __init__(self, loop, network):
        self.loop = loop

        # TODO it would be nice to parametrize these (or even accept arbitrary
        # transports), but the event loop doesn't support async reading from
        # ttys for some reason...
        self.stdin = sys.stdin
        self.stdout = sys.stdout

        self.event_queue = Queue(loop=loop)

    @asyncio.coroutine
    def connect(self):
        protocol = UrwidTerminalProtocol(DywypiShell, self.loop)
        self.transport = TrivialFileTransport(self.loop, self.stdin, self.stdout, protocol)

    @asyncio.coroutine
    def read_event(self):
        # For now, this will never ever do anything.
        # TODO this sure looks a lot like IRCClient
        return (yield from self.event_queue.get())
