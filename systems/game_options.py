import json
import os

_GAME_OPTIONS_PATH = 'game_options.json'

# Default values for all toggles.  New keys added here are automatically
# forward-compatible: missing keys in a saved file fall back to these defaults.
_DEFAULTS = {
    # Cellular Automata
    'ca_enabled':       True,
    'ca_tree_spread':   True,
    'ca_sand_spread':   True,
    'ca_water_spread':  True,
    'ca_grass_growth':  True,
    'ca_drought':       True,
    # Entity Spawning
    'spawn_goblins':          True,
    'spawn_wolves':           True,
    'spawn_bats':             True,
    'spawn_skeletons_night':  True,
    'spawn_cave_hostiles':    True,
    'spawn_termites':         True,
    # Game Difficulty
    'hunger_decay':              True,
    'thirst_decay':              True,
    'starvation_damage':         True,
    'old_age_damage':            True,
    'skeleton_daylight_damage':  True,
    # World Events
    'raids_enabled':    True,
    'weather_enabled':  True,
    # Factions & Society
    'keeper_assignments': True,
    'npc_aging':          True,
    'npc_promotions':     True,
    'faction_wars':       True,
}


class GameOptions:
    """Runtime-editable boolean toggles for game systems.

    Loaded from game_options.json on startup and auto-saved whenever
    a flag is toggled.  Settings persist across new games.
    """

    def __init__(self):
        for key, val in _DEFAULTS.items():
            setattr(self, key, val)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------

    def save(self, path=_GAME_OPTIONS_PATH):
        data = {k: getattr(self, k) for k in _DEFAULTS}
        try:
            with open(path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    @classmethod
    def load(cls, path=_GAME_OPTIONS_PATH):
        opts = cls()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                for key in _DEFAULTS:
                    if key in data:
                        setattr(opts, key, bool(data[key]))
            except Exception:
                pass
        return opts

    # ------------------------------------------------------------------
    # Toggle
    # ------------------------------------------------------------------

    def toggle(self, flag_name, path=_GAME_OPTIONS_PATH):
        """Flip a boolean flag and immediately save to disk."""
        if flag_name in _DEFAULTS:
            setattr(self, flag_name, not getattr(self, flag_name))
            self.save(path)
            # Sync CA master flag to the module-level constant immediately
            if flag_name == 'ca_enabled':
                try:
                    import world.cells as _wc
                    _wc.CA_RULES_ENABLED = self.ca_enabled
                except Exception:
                    pass
