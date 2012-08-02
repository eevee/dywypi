from dywypi.plugin_api import Plugin, global_command

class EchoPlugin(Plugin):
    name = 'echo'

    @global_command('echo')
    def do(self, event):
        event.reply(u' '.join(event.argv))

    @global_command('state')
    def do_state_xxx(self, event):
        print event.argv
        return
