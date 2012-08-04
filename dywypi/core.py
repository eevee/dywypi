from twisted.internet import defer
from twisted.python import log

from dywypi.plugin_api import PluginRegistry

nickname = 'dywypi2_0'
encoding = 'utf8'


# XXX also need to rig something to make IRC appear more stateful.
# - for commands that require waiting for a response from the server, fire off the initializer and create a deferred that waits on a response matching some simple pattern.  override handleCommand to callback() on these.  if we get disconnected, errback().
# - what to do about disconnections in general?  probably ought to just cancel everything.
def enforce_unicode(res):
    """Deferred callback that rejects plain `str` output."""
    if isinstance(res, str):
        raise ValueError("Return values must be Unicode objects")
    return res


class Dywypi(object):
    """The brains of this operation."""

    def __init__(self):
        self.plugin_registry = PluginRegistry()
        self.plugin_registry.scan()
        self.plugin_registry.load_plugin('echo')
        self.plugin_registry.load_plugin('fyi')
        self.plugin_registry.load_plugin('pagetitles')

    def fire(self, event, *a, **kw):
        for func in self.plugin_registry.get_listeners(event):
            self._make_deferred(func, event, *a, **kw)


    def run_command(self, command, event):
        self._make_deferred(self.plugin_registry.run_command, command, event)

    def _make_deferred(self, func, *args, **kwargs):
        d = defer.maybeDeferred(func, *args, **kwargs)
        d.addErrback(log.err)
        d.addErrback(lambda failure: responder(u"resonance cascade imminent, evacuate immediately"))
