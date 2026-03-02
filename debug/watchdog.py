"""
Watchdog — periodic game-state sampler and integrity checker.

The Watchdog runs on a tick schedule (SAMPLE_INTERVAL ticks, ~5 s at 60 fps).
Each run it:
  1. Samples one category of game state (rotating through all categories so
     every category gets logged every 5 × SAMPLE_INTERVAL ticks).
  2. Runs a fixed set of integrity checks across all entities, logging any
     anomalies it finds.
  3. Calls bug_catcher.flush() so buffered entries reach disk.

Categories (in rotation order):
  entities   — random sample of up to 5 entities (health, state, flags)
  cells      — cell-type histogram for the player's current zone
  zones      — random zone metadata snapshot
  player     — player position, stats, subscreen status, inventory size
  subscreens — random subscreen metadata snapshot

Integrity checks (log-and-detect only — no active healing):
  entity_in_subscreen_but_in_screen_entities
      Entity has in_subscreen=True but its entity_id is still present in
      screen_entities[zone_key].  This causes ghost rendering and frozen
      animation for flying entities (is_flying_idle=False when in_subscreen).

  entity_not_in_subscreen_but_in_subscreen_entities
      Entity has in_subscreen=False but its entity_id is in a subscreen's
      entity list — the inverse mismatch.

Usage
-----
    watchdog = Watchdog(bug_catcher)

    # In main game loop (playing state), once per tick:
    watchdog.update(tick, game)
"""

import random


class Watchdog:
    CATEGORIES = ['entities', 'cells', 'zones', 'player', 'subscreens']
    SAMPLE_INTERVAL = 300   # ticks between sample+check+flush cycles
    ENTITY_SAMPLE_SIZE = 5  # how many entities to snapshot per cycle

    def __init__(self, bug_catcher):
        self.bug_catcher = bug_catcher
        self._category_index = 0
        self._last_run_tick = -99999

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def update(self, tick: int, game) -> None:
        """Call once per game tick during the playing state."""
        if tick - self._last_run_tick < self.SAMPLE_INTERVAL:
            return
        self._last_run_tick = tick

        category = self.CATEGORIES[self._category_index % len(self.CATEGORIES)]
        self._category_index += 1

        _SAMPLERS = {
            'entities':   self._sample_entities,
            'cells':      self._sample_cells,
            'zones':      self._sample_zones,
            'player':     self._sample_player,
            'subscreens': self._sample_subscreens,
        }
        _SAMPLERS[category](tick, game)

        self._check_integrity(tick, game)
        self.bug_catcher.flush()

    # ------------------------------------------------------------------
    # Category samplers
    # ------------------------------------------------------------------

    def _sample_entities(self, tick: int, game) -> None:
        if not game.entities:
            return
        sample = random.sample(list(game.entities.items()),
                               min(self.ENTITY_SAMPLE_SIZE, len(game.entities)))
        for eid, entity in sample:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_entity_sample',
                'id': eid,
                'type': entity.type,
                'zone': f"{entity.screen_x},{entity.screen_y}",
                'grid': [entity.x, entity.y],
                'health': entity.health,
                'ai_state': getattr(entity, 'ai_state', None),
                'in_subscreen': getattr(entity, 'in_subscreen', False),
                'subscreen_key': getattr(entity, 'subscreen_key', None),
                'anim_frame': getattr(entity, 'anim_frame', None),
                'facing': getattr(entity, 'facing', None),
            })

    def _sample_cells(self, tick: int, game) -> None:
        player_zone = f"{game.player['screen_x']},{game.player['screen_y']}"
        if player_zone not in game.screens:
            return
        grid = game.screens[player_zone].get('grid', [])
        cell_counts: dict = {}
        for row in grid:
            for cell in row:
                cell_counts[cell] = cell_counts.get(cell, 0) + 1
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_cells_sample',
            'zone': player_zone,
            'cell_counts': cell_counts,
        })

    def _sample_zones(self, tick: int, game) -> None:
        if not game.screens:
            return
        zone_key = random.choice(list(game.screens.keys()))
        zone_data = game.screens[zone_key]
        entity_count = sum(
            1 for e in game.entities.values()
            if f"{e.screen_x},{e.screen_y}" == zone_key
        )
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_zone_sample',
            'zone': zone_key,
            'has_grid': 'grid' in zone_data,
            'zone_type': zone_data.get('zone_type'),
            'biome': zone_data.get('biome'),
            'entity_count': entity_count,
        })

    def _sample_player(self, tick: int, game) -> None:
        p = game.player
        inv_count = sum(
            v for v in game.inventory.items.values()
            if isinstance(v, int)
        )
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_player_sample',
            'zone': f"{p['screen_x']},{p['screen_y']}",
            'grid': [p['x'], p['y']],
            'health': p.get('health'),
            'max_health': p.get('max_health'),
            'energy': p.get('energy'),
            'max_energy': p.get('max_energy'),
            'in_subscreen': p.get('in_subscreen', False),
            'subscreen_key': p.get('subscreen_key'),
            'facing': p.get('facing'),
            'level': p.get('level'),
            'inventory_item_count': inv_count,
            'follower_count': len(getattr(game, 'followers', [])),
        })

    def _sample_subscreens(self, tick: int, game) -> None:
        if not game.subscreens:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_subscreen_sample',
                'note': 'no subscreens exist',
            })
            return
        sub_key = random.choice(list(game.subscreens.keys()))
        sub_data = game.subscreens[sub_key]
        entities_in_sub = getattr(game, 'subscreen_entities', {}).get(sub_key, [])
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_subscreen_sample',
            'key': sub_key,
            'subscreen_type': sub_data.get('subscreen_type'),
            'entity_count': len(entities_in_sub),
        })

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _check_integrity(self, tick: int, game) -> None:
        screen_entities = getattr(game, 'screen_entities', {})
        subscreen_entities = getattr(game, 'subscreen_entities', {})

        # Build reverse map: entity_id -> [subscreen_keys]
        entity_in_subs: dict = {}
        for sub_key, sub_list in subscreen_entities.items():
            for eid in sub_list:
                entity_in_subs.setdefault(eid, []).append(sub_key)

        for eid, entity in game.entities.items():
            entity_in_sub_flag = getattr(entity, 'in_subscreen', False)
            zone_key = f"{entity.screen_x},{entity.screen_y}"

            # Check 1: in_subscreen=True but still in screen_entities
            if entity_in_sub_flag:
                if zone_key in screen_entities and eid in screen_entities[zone_key]:
                    self.bug_catcher.log({
                        'tick': tick,
                        'category': 'integrity_anomaly',
                        'check': 'entity_in_subscreen_but_in_screen_entities',
                        'entity_id': eid,
                        'entity_type': entity.type,
                        'zone': zone_key,
                        'subscreen_key': getattr(entity, 'subscreen_key', None),
                    })

            # Check 2: in_subscreen=False but in subscreen_entities
            if not entity_in_sub_flag and eid in entity_in_subs:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'integrity_anomaly',
                    'check': 'entity_not_in_subscreen_but_in_subscreen_entities',
                    'entity_id': eid,
                    'entity_type': entity.type,
                    'zone': zone_key,
                    'found_in_subscreens': entity_in_subs[eid],
                })
