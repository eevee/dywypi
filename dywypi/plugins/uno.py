import asyncio
import contextlib
import random

from dywypi.plugin import Plugin

# TODO: cool features
# - not having to type "dywypi: uno." prefix
# - cheevos?  or should that just be in the form of snarky comments
# - ongoing score tracking

# TODO card objects?
# TODO and better card parsing
# TODO pretty formatting

# TODO uno
# TODO winning...
# TODO wild
# TODO special cards!


plugin = Plugin('uno')


@contextlib.contextmanager
def uno_error_catcher(event):
    # TODO many of these need help strings
    try:
        yield
    except NeedsChannel:
        event.reply("You can only play a game in a channel.")
    except WrongChannel:
        event.reply("There's no game running in this channel.")
    except NotPlaying:
        event.reply("You're not in on this game.")
    except NotYourTurn:
        event.reply("Slow your roll, chief.  Your turn comes later.")
    except NotHoldingThatCard:
        event.reply("You don't have that card.")
    except CardDoesntMatch:
        event.reply("That card doesn't match the top one on the pile.")
    except MustDrawBeforePassing:
        event.reply("Nice try, but you have to draw a card before you can pass.")


# TODO need game to go somewhere.  one per channel...

@asyncio.coroutine
def show_game_state(self, game, event):
    # TODO put more detail here with what just happened
    cur_player = game.current_player()
    next_player = game.current_player(1)
    event.say("Top card is {0!s}.  Next turn is {1}, followed by {2}.".format(
        game.current_card,
        cur_player.peer.name,
        next_player.peer.name))
    yield from event.reply(cur_player.peer, str(cur_player.hand), as_notice=True)


def find_game(self, event):
    if not event.channel:
        raise NeedsChannel

    game = self.game
    if game and game.channel != event.channel:
        raise WrongChannel

    return game


@plugin.command('start', is_global=False)
def setup_game(self, event):
    if not event.channel:
        yield from event.reply("Sorry, I can only start a game in a channel.")
        return

    if self.game:
        # TODO help
        yield from event.reply("There's already a game running.")
        return

    self.game = UnoGame(event.channel)
    self.game.add_player(event.peer)
    # TODO help
    event.say("Starting a game, with {0} as player 1.  Any takers?".format(event.peer.name))


@plugin.command('join', is_global=False)
def join_game(self, event):
    # TODO don't join twice
    # TODO must be in same channel
    # TODO must be a person  :D
    # TODO max players
    if not self.game:
        # TODO help
        event.reply("Join what?  No one's playing.")
        return
    if self.game.started:
        # TODO could still join as long as they wouldn't /have gone/ yet
        event.reply("Sorry, the game's already started.  Maybe next time.")
        return

    self.game.add_player(event.peer)


@plugin.command('deal', is_global=False)
def start_game(self, event):
    with uno_error_catcher(event):
        game = find_game(event)

        if game.started:
            # TODO help
            event.reply("There's already a game in progress.")
            return
        #if len(game.players) < 3:
        #    # TODO help, num players
        #    event.reply("Gotta have at least 3 chumps to play.")
        #    return

        game.deal()
        event.say("Let's get this party started.")
        yield from show_game_state(game, event)


@plugin.command('play', is_global=False)
def play_card(self, event):
    # TODO get/validate player

    card, args = parse_card(event.argv)

    with uno_error_catcher(event):
        game = find_game(event)
        player = game.find_player(event.peer)
        game.play_card(player, card)

        if game.ended:
            event.say("{0} wins!".format(event.peer.name))
            self.game = None
            return

        yield from show_game_state(game, event)


@plugin.command('draw', is_global=False)
def draw_card(self, event):
    with uno_error_catcher(event):
        game = find_game(event)
        player = game.find_player(event.peer)
        card = game.draw_card(player)
        # TODO tell player what card
        yield from show_game_state(game, event)
        # TODO only once


@plugin.command('pass', is_global=False)
def pass_turn(self, event):
    with uno_error_catcher(event):
        game = find_game(event)
        player = game.find_player(event.peer)
        game.pass_turn(player)
        yield from show_game_state(game, event)


@plugin.command('status', is_global=False)
def show_status(self, event):
    game = find_game(event)

    # TODO help
    if not game:
        event.say("Not currently running a game.")
    elif not game.started:
        event.say("A game is starting soon; still waiting for players.")
    else:
        # TODO
        event.say("TODO")



class UnoGame(object):
    started = False
    ended = False
    turn_player_idx = None
    direction = 1
    drawn_this_turn = 0

    ### Setup

    def __init__(self, channel):
        self.channel = channel

        self.players = []
        self.player_map = {}

        self.discard = []
        self.deck = []

        for color in ('red', 'yellow', 'blue', 'green'):
            for number in range(10):
                self.deck.append((color, number))
                if number != 0:
                    self.deck.append((color, number))

        random.shuffle(self.deck)

    def add_player(self, peer):
        player = UnoPlayer(peer, self)
        self.players.append(player)
        self.player_map[peer] = player

    def deal(self):
        for _ in range(7):
            # TODO supposed to start at dealer's left, right?  should this skip
            # the first player, then?  :)
            for player in self.players:
                # TODO what if the deck runs out of cards here
                player.hand.append(self.deck.pop(0))

        # TODO deck runs out here
        self.discard.append(self.deck.pop(0))

        self.started = True
        # TODO assert more than 1 player.  also, should this class do simple
        # error checking or leave it to the plugin...?
        self.turn_player_idx = 0

        print([_.hand for _ in self.players])


    ### Utils

    def find_player(self, peer):
        try:
            return self.player_map[peer]
        except KeyError:
            raise NotPlaying

    def check_player(self, player):
        if not self.started:
            raise NotStarted

        if self.ended:
            raise GameOver

        if player.game is not self:
            raise NotPlaying

        if self.players[self.turn_player_idx] is not player:
            raise NotYourTurn

    def reverse_direction(self):
        self.direction *= -1

    def advance_turn(self):
        self.turn_player_idx += self.direction
        self.turn_player_idx %= len(self.players)

        # Clear out some state
        self.drawn_this_turn = 0

    @property
    def current_card(self):
        return self.discard[-1]

    def current_player(self, delta=0):
        """Returns the current player.  Pass an integer to find a player that
        number of turns away -- e.g., pass 1 to retrieve the next player.
        """
        idx = self.turn_player_idx + delta * self.direction
        idx %= len(self.players)

        return self.players[idx]


    ### Player API

    def play_card(self, player, card):
        self.check_player(player)

        if card not in player.hand:
            raise NotHoldingThatCard

        # TODO need to change this for wild, clear
        current = self.current_card
        if not (current[0] == card[0] or current[1] == card[1]):
            raise CardDoesntMatch

        player.hand.remove(card)
        self.discard.append(card)

        # Check for game end
        # TODO this does not seem like the cleanest way to communicate this
        # information to the caller
        if any(not player.hand for player in self.players):
            self.ended = True
            return

        print([_.hand for _ in self.players])

        self.advance_turn()

    def draw_card(self, player):
        self.check_player(player)
        # TODO what if run out of cards, yadda
        player.hand.append(self.deck.pop(0))
        self.drawn_this_turn += 1

        # TODO according to The Rules: once you draw a card you MUST play THAT
        # CARD, or pass

    def pass_turn(self, player):
        self.check_player(player)

        if not self.drawn_this_turn:
            raise MustDrawBeforePassing

        # TODO: must draw at least one card first

        self.advance_turn()


class UnoPlayer(object):
    def __init__(self, peer, game):
        self.peer = peer
        self.game = game
        self.hand = []

    # TODO avoid direct access to self.hand?
    def add_card(self, card):
        pass


def parse_card(card_parts):
    # TODO...
    # TODO raise exception on invalid card type
    return (card_parts[0], int(card_parts[1])), card_parts[2:]


### Exception classes

class NotStarted(Exception): pass

class GameOver(Exception): pass

class NeedsChannel(Exception): pass

class WrongChannel(Exception): pass

class NotPlaying(Exception): pass

class NotYourTurn(Exception): pass

class NotHoldingThatCard(Exception): pass

class CardDoesntMatch(Exception): pass

class MustDrawBeforePassing(Exception): pass
