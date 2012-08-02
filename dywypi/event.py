from dywypi.plugin_api import _plugin_hook_decorator

def listen(event_cls):
    """Similar to `command()`, but the function can be called without the
    plugin prefix.  The name is required, in the vain hope that plugin
    developers will think more carefully about cluttering the global namespace.
    """
    return _plugin_hook_decorator(dict(event_type=event_cls))






