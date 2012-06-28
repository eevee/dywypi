from dywypi.plugin_api import Plugin, global_command

class EchoPlugin(Plugin):
    name = 'echo'

    @global_command('echo')
    def do(self, args):
        return u' '.join(args)
