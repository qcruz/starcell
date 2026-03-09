#!/usr/bin/env python3
"""
StarCell — Modular Architecture
Run this file to start the game.

Module layout:
  data/            — Game data tables (split from constants.py)
    settings.py    — Screen size, FPS, grid constants
    cells.py       — Cell types, biomes
    items.py       — Item definitions
    entities.py    — Entity type definitions
    factions.py    — Faction data
    quests.py      — Quest type definitions
    spells.py      — Spell definitions

  engine/          — Core engine helpers
    entity.py      — Entity, Inventory, Quest classes
    sprite_manager.py

  systems/         — Game systems
    save_load.py   — SaveLoadMixin
    crafting.py    — CraftingMixin
    combat.py      — CombatMixin
    enchantment.py — EnchantmentMixin
    factions.py    — FactionsMixin
    spawning.py    — SpawningMixin

  world/           — World simulation
    generation.py  — WorldGenerationMixin
    zones.py       — ZonesMixin
    cells.py       — CellsMixin

  ui/              — Rendering
    hud.py         — HudMixin
    inventory.py   — InventoryUIMixin
    menus.py       — MenusMixin

  ai/              — NPC behaviour
    actions.py     — NpcAiActionsMixin
    movement.py    — NpcAiMovementMixin

  lore/            — Quest targeting and world event generation
    engine.py      — LoreEngineMixin

  Legacy monoliths (gradually being emptied as extraction completes):
    game_core.py   — GameCoreMixin
    npc_ai.py      — NpcAiMixin
    autopilot.py   — AutopilotMixin
"""

from constants import *
from entity import *

# ── New modular mixins ────────────────────────────────────────────────────────
from systems import (SaveLoadMixin, CraftingMixin, CombatMixin,
                     EnchantmentMixin, FactionsMixin, SpawningMixin)
from world import WorldGenerationMixin, ZonesMixin, CellsMixin
from ui import HudMixin, InventoryUIMixin, MenusMixin
from ai import NpcAiActionsMixin, NpcAiMovementMixin
from lore import LoreEngineMixin

# ── Legacy monoliths (fallback for methods not yet extracted) ─────────────────
from game_core import GameCoreMixin
from npc_ai import NpcAiMixin
from autopilot import AutopilotMixin


class Game(
    # New modular mixins take precedence over legacy duplicates via MRO
    HudMixin, InventoryUIMixin, MenusMixin,           # ui/
    WorldGenerationMixin, ZonesMixin, CellsMixin,     # world/
    SaveLoadMixin, CraftingMixin, CombatMixin,        # systems/
    EnchantmentMixin, FactionsMixin, SpawningMixin,   # systems/
    NpcAiActionsMixin, NpcAiMovementMixin,            # ai/
    LoreEngineMixin,                                  # lore/
    # Legacy monoliths — cover methods not yet extracted
    GameCoreMixin, NpcAiMixin, AutopilotMixin,
):
    """Main game class combining all systems via multiple inheritance."""
    pass


if __name__ == '__main__':
    import random, time, json, os

    # ── AUTO_DEBUG: set True to run headless autopilot debug sessions ──────────
    AUTO_DEBUG = False
    _STATE_FILE = 'debug/auto_debug_state.json'
    _MIN_SECS   = 60    # floor: 1 min
    _MAX_CAP    = 120   # ceiling: 2 min
    # ──────────────────────────────────────────────────────────────────────────

    game = Game()

    if AUTO_DEBUG:
        # Load run counter
        try:
            with open(_STATE_FILE) as _f:
                _state = json.load(_f)
        except Exception:
            _state = {'run': 0}
        _run = _state.get('run', 0)

        # Session length: random between 2–3 minutes
        _cap = min(_MIN_SECS * (2 ** _run), _MAX_CAP)
        _dur = random.randint(_MIN_SECS, _cap)

        # New game or continue (50/50 if save exists)
        _save_exists = os.path.exists('savegame.json')
        if _save_exists and random.random() < 0.5:
            game.load_game()
            game.toggle_autopilot()
            _mode = 'CONTINUE'
        else:
            game.new_game()
            game.toggle_autopilot()
            _mode = 'NEW GAME'

        game._auto_debug_end_time = time.time() + _dur
        game._auto_debug_run_num  = _run
        game._auto_debug_state_file = _STATE_FILE
        print(f"[AutoDebug] Run {_run + 1} — {_mode} | duration={_dur}s (cap={_cap}s)")

    game.run()
