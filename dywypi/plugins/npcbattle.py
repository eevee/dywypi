"""Accepts all challenges and battles pretty much like a game NPC."""
import logging
import random

from dywypi.plugin import Plugin
from dywypi.dialect.showdown.client import ActionRequest
from dywypi.dialect.showdown.client import BattleEnded
from dywypi.dialect.showdown.client import ChallengeReceived

log = logging.getLogger(__name__)


plugin = Plugin('npcbattle')

@plugin.on(ChallengeReceived)
async def accept_challenge(event):
    # automatically accept
    await event.accept()


@plugin.on(ActionRequest)
async def move_at_random(event):
    log.debug("let's go woo!!")
    state = event.battle_state

    # TODO there's a "noCancel" and i'm not sure what that implies; i got it when forced to switch due to fainting
    switch = False
    if state.must_switch:
        switch = True

    # TODO none of this handles multi-battles, augh
    if switch:
        # switch out
        viable_pokemon = []
        for pokemon in state.team:
            if pokemon.active:
                continue
            if 'fnt' in pokemon.condition:
                continue
            viable_pokemon.append(pokemon)

        # TODO there might be no viable pokemon, especially if i'm on my last and decide to switch at random
        await random.choice(viable_pokemon).choose()
    else:
        # move
        usable_moves = []
        if len(state.active_moves[0]) == 1:
            # Trapped!
            # TODO this seems...  clumsy
            usable_moves = state.active_moves[0]
        else:
            for move in state.active_moves[0]:
                if move.pp <= 0:
                    continue
                if move.disabled:
                    continue
                usable_moves.append(move)
        
        # TODO what happens if you have nothing?  do you auto-struggle?
        log.debug(repr(usable_moves))
        await random.choice(usable_moves).choose()


@plugin.on(BattleEnded)
async def humblebrag(event):
    # TODO how do we know whether we were actually involved in the battle...?
    if event.winner == event.client.username:
        await event.client.say(event.client._current_room, "gg  :)")
    else:
        await event.client.say(event.client._current_room, "gg  :(")
