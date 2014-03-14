from dywypi.plugin import PluginManager


def test_scan_package():
    manager = PluginManager()
    #assert not manager.known_plugins
    manager.scan_package('dywypi.plugins')
    assert 'echo' in manager.known_plugins
    manager.scan_package('dywypi.plugins')
