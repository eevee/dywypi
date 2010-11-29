#!/usr/bin/env python

import sys

from twisted.internet import reactor
from twisted.internet.protocol import ReconnectingClientFactory
from twisted.python import log
from twisted.words.protocols import irc

nickname = 'dywypi2_0'
connection_specs = [
    ('irc.veekun.com', 6667, ['#bot']),
]

class DywypiClient(irc.IRCClient):
    nickname = nickname

    def signedOn(self):
        for channel in self.factory.channels:
            self.join(channel)


class DywypiConnection(ReconnectingClientFactory):
    protocol = DywypiClient

    def __init__(self, channels):
        self.channels = channels


if __name__ == '__main__':
    connections = []
    for host, port, channels in connection_specs:
        reactor.connectTCP(host, port, DywypiConnection(channels))

    log.startLogging(sys.stdout)
    reactor.run()
