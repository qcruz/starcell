#!/usr/bin/env python3
"""
StarCell v2.0 - Modular Architecture
Run this file to start the game.

Structure:
  constants.py  — Data tables, config, behavior definitions
  entity.py     — Entity, Inventory, Quest classes
  game_core.py  — Rendering, player, world gen, quests, save/load, zone updates
  npc_ai.py     — NPC behavior, AI, movement, combat, action primitives
  autopilot.py  — Player autopilot system
"""

from constants import *
from entity import *
from game_core import GameCoreMixin
from npc_ai import NpcAiMixin
from autopilot import AutopilotMixin


class Game(GameCoreMixin, NpcAiMixin, AutopilotMixin):
    """Main game class combining all systems via mixins."""
    pass


if __name__ == '__main__':
    game = Game()
    game.run()
