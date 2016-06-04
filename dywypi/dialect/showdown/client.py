import asyncio
from asyncio.queues import Queue
from collections import defaultdict
from collections import deque
from datetime import datetime
import json
import logging

import aiohttp
import websockets

from dywypi.event import Event

log = logging.getLogger(__name__)


# TODO SOME PROBLEMS STILL
# - when you disconnect, you have to rejoin the battle manually..??  i did not get an updatechallenges.  but it still let me continue the battle??
#   possibly listed in updatesearch?  this was localhost though so i can't be sure it's not just...  a list of arbitrary battles, or ones i was watching as well, or...
#   <<< recv: None: updatesearch ['{"searching":[],"games":{"battle-randombattle-2":"Random Battle"}}']
# - how do you tell what's old stuff from joining a channel and what's new?  i guess, uh, maybe the effects of a move can just be the return value from making the move?


# TODO make all this stuff align better with the existing IRC stuff, and come up with some interfaces, and so on

class ShowdownUser:
    def __init__(self, name, mode):
        self.name = name
        self.mode = mode

    @classmethod
    def parse(cls, s):
        return cls(s[1:], s[0])


class ShowdownMessage:
    def __init__(self, room, type, args):
        self.room = room
        # TODO rename to msgtype?
        self.type = type
        self.args = args

    @classmethod
    def parse(cls, room, line):
        if line[0] == '|':
            _, type, *args = line.split('|')
            return cls(room, type, args)
        else:
            return cls(room, None, (line,))


# ------------------------------------------------------------------------------
# Battle stuff

# TODO docs on expanding this:
# https://github.com/Zarel/Pokemon-Showdown/blob/master/PROTOCOL.md#action-requests
# currently not handled:
# - megas (add as a final param to /move)
# - 2v2 or 3v3 (simultaneous choices -- makes `await choose()` more complicated)
# - moves with targets (only 2v2 or 3v3)

class BattleMove:
    def __init__(self, client, room, data):
        self.client = client
        self.room = room

        self.name = data['move']
        self.ident = data['id']
        # These may not exist if we're "trapped"
        self.pp = data['pp']
        self.max_pp = data['maxpp']
        self.target = data['target']
        self.disabled = data['disabled']

    async def choose(self):
        await self.client.send_raw(self.room, '/move ' + self.ident)


class BattlePokemon:
    def __init__(self, client, room, position, data):
        self.client = client
        self.room = room

        self.position = position
        # TODO should parse this; seems to be "playerid: Name"
        self.ident = data['ident']
        # TODO parse me; is "Name, Lnn[, M/F]"
        self.details = data['details']
        self.condition = data['condition']
        self.active = data['active']
        self.stats = data['stats']
        self.moves = data['moves']
        self.base_ability = data['baseAbility']
        self.item = data['item']
        self.pokeball = data['pokeball']

    async def choose(self):
        await self.client.send_raw(self.room, '/switch ' + str(self.position))


class BattleTeam:
    def __init__(self, client, room, data):
        self.client = client
        self.room = room

        self.name = data['name']
        self.id = data['id']
        self.pokemon = [
            BattlePokemon(client, room, n, datum)
            for n, datum in enumerate(data['pokemon'], start=1)
        ]

    def __iter__(self):
        return iter(self.pokemon)


class BattleState:
    def __init__(self, client, room, data):
        # TODO maybe these should be wrapped in a Battle object
        self.client = client
        self.room = room

        # TODO unclear how exactly this works in 2v2 or 3v3
        self.must_switch = any(data.get('forceSwitch', ()))

        if 'active' in data:
            # TODO this sometimes has a key 'trapped', but...  is that useful or interesting?
            # TODO actually i think i'd like to just auto-respond when we're trapped
            self.active_moves = [
                [BattleMove(client, room, movedef)
                    for movedef in activedef['moves']]
                for activedef in data['active']
            ]

        self.team = BattleTeam(client, room, data['side'])
        # TODO use this when choosing
        self.request_id = data.get('rqid')


class ChallengeReceived(Event):
    _invalid = False

    def __init__(self, from_user, to_user, battle_type, **kwargs):
        super().__init__(**kwargs)

        self.issued_at = datetime.now()
        self.from_user = from_user
        self.to_user = to_user
        self.battle_type = battle_type

    async def accept(self):
        if self._invalid:
            raise RuntimeError
        await self.client.send_raw(None, '/accept ' + self.from_user)
        # TODO at this point it really becomes a battle, right?  unless it's expired, or...
        self._invalid = True


class BattleEnded(Event):
    def __init__(self, winner, **kwargs):
        super().__init__(**kwargs)

        self.winner = winner


class ActionRequest(Event):
    """A request from the server for you to make a move or switch out."""
    def __init__(self, raw_data, **kwargs):
        super().__init__(**kwargs)

        self.battle_state = BattleState(self.client, self.raw_message.room, raw_data)


# state
class Channel:
    def __init__(self, name, room_type):
        self.name = name
        self.room_type = room_type



class ShowdownClient:
    def __init__(self, loop, network):
        self.loop = loop
        self.network = network

        # TODO the whole "network" system is designed for irc and makes no
        # sense for showdown; this is the primary server, hardcoded for now
        #self.url = 'ws://sim.smogon.com/showdown/websocket'
        # or, for local development:
        self.url = 'ws://localhost:8000/showdown/websocket'

        self.websocket = None
        self.username = None
        self.is_guest = None
        self.avatar = None

        # TODO private until i can figure out how this should look
        self._challenges_from = {}

        self._read_loop_task = None
        self._current_room = None
        self._event_queue = Queue(loop=self.loop)
        self._awaiting_messages = defaultdict(deque)
        self._challenge = None

    async def connect(self):
        self.websocket = await websockets.connect(self.url, loop=self.loop)
        self._read_loop_task = asyncio.ensure_future(self._read_loop(), loop=self.loop)

        # TODO this is the worst
        await self.set_name('eevee-sandbox')

    async def disconnect(self):
        self._read_loop_task.cancel()
        await self.websocket.close()
        self.websocket = None

    async def __aenter__(self):
        self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()

    async def _read_loop(self):
        pending = deque()

        while True:
            while not pending:
                text = await self.websocket.recv()
                pending.extend(msg for msg in text.split('\n') if msg)
                while pending and pending[0].startswith('>'):
                    self._current_room = pending.popleft()[1:]

            event = ShowdownMessage.parse(self._current_room, pending.popleft())
            if not (event.type and event.type.isupper()):
                log.debug("<<< recv: {}: {} {!r}".format(event.room, event.type, event.args))

            method = "_handle__{}".format(event.type)
            if hasattr(self, method):
                await getattr(self, method)(event)

            awaiting = self._awaiting_messages[event.type]
            while awaiting:
                awaiting.popleft().set_result(None)

            await self._event_queue.put(event)

    async def read_event(self):
        return await self._event_queue.get()

    async def _handle__challstr(self, event):
        self._challenge = '|'.join(event.args)

    def _wait_message(self, message_type):
        fut = asyncio.Future()
        self._awaiting_messages[message_type].append(fut)
        return fut

    async def get_challenge(self):
        if not self._challenge:
            await self._wait_message('challstr')
        return self._challenge

    async def send_raw(self, room, text):
        log.debug('>>> send: {} {}'.format(repr(room), repr(text)))
        # TODO do commands have more structured arguments?
        if room is None:
            room = ''
        await self.websocket.send("{}|{}".format(room, text))

    async def say(self, room, text):
        # TODO should reject commands here eventually
        await self.send_raw(room, text)

    async def set_name(self, username):
        # NOTE: this is the same as login but it uses "getassertion" and no password.  also i dunno 
        # TODO this should wait on the challstr
        # TODO but then this can't be called from the same stack that's reading events.  unless there's an independent big ol' buffer
        challenge = await self.get_challenge()
        # TODO in my browser this has a /~~localhost/ bit
        async with aiohttp.get('https://play.pokemonshowdown.com/action.php', params={'act': 'getassertion', 'userid': username, 'challstr': challenge}, loop=self.loop) as resp:
            # seems to give back either the assertion, or a single semicolon on failure (i.e. the nick is taken)???
            assertion = await resp.text()
            if assertion == ";":
                # TODO yadda yadda
                raise RuntimeError
            await self.websocket.send('|' + '/trn {},0,{}'.format(username, assertion))

    async def login(self, username, password):
        # TODO this should wait on the challstr
        # TODO but then this can't be called from the same stack that's reading events.  unless there's an independent big ol' buffer
        challenge = await self.get_challenge()
        # TODO in my browser this has a /~~localhost/ bit
        async with aiohttp.post('https://play.pokemonshowdown.com/action.php', data={'act': 'login', 'name': username, 'pass': password, 'challstr': challenge}, loop=self.loop) as resp:
            text = await resp.text()
            login_payload = json.loads(text[1:])
            await self.websocket.send('|' + '/trn {},0,{}'.format(username, login_payload['assertion']))

    async def _handle__updateuser(self, event):
        new_name, new_logged_in, new_avatar = event.args
        self.username = new_name
        if new_logged_in == '1':
            self.is_guest = False
        elif new_logged_in == '0':
            self.is_guest = True
        else:
            self.is_guest = None
        self.avatar = new_avatar

    # --------------------------------------------------------------------------
    # CHAT STUFF

    async def _handle__init(self, event):
        # Joined a channel
        # TODO surprise, this doesn't actually do anything
        Channel(event.room, event.args[0])

    # --------------------------------------------------------------------------
    # BATTLE STUFF

    async def _handle__updatechallenges(self, event):
        try:
            new_challenges = json.loads(event.args[0])
        except json.decoder.JSONDecodeError:
            # TODO what do i do here, i wonder.
            return

        for from_user, battle_type in new_challenges.get('challengesFrom', {}).items():
            if from_user not in self._challenges_from:
                # TODO i guess this should use more objects or whatever; do i have user objects from irc land?
                await self._event_queue.put(
                    ChallengeReceived(from_user, self.username, battle_type, client=self, raw=event))

        # TODO should update this more, ah, carefully, and put the challenges in it, etc...
        self._challenges_from = new_challenges.get('challengesFrom', {})

        # TODO handle challenging other users too...!

    async def _handle__request(self, message):
        # TODO megas are a thing!  but i have no idea how you do them
        # TODO errors here are being silently lost
        # Sim is requesting that you choose what to do
        data = json.loads(message.args[0])
        log.debug(repr(data))
        if not data:
            # For some reason I just get 'null' sometimes?
            return
        if data.get('wait'):
            # Nothing to do; don't bother firing an event
            return
        log.debug("ALRIGHT, let's go, adding to the queue")
        await self._event_queue.put(
            ActionRequest(data, client=self, raw=message))

    async def _handle__win(self, message):
        # Sim is announcing the end of a battle
        await self._event_queue.put(BattleEnded(message.args[0], client=self, raw=message))
