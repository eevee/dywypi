from dywypi.plugin_api import Plugin

class EchoPlugin(Plugin):
    name = 'echo'

    def do(self, args):
        return u' '.join(args)
