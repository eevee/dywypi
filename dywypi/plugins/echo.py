from dywypi.plugin_api import Plugin, command

class EchoPlugin(Plugin):
    name = 'echo'

    @command()
    def do(self, args):
        return u' '.join(args)
