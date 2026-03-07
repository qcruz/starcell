"""
Watchdog — periodic full-coverage game-state sampler and integrity checker.

The Watchdog runs every SAMPLE_INTERVAL ticks (~5 s at 60 fps).  Each cycle it:
  1. Samples ONE category comprehensively — logging ALL available items in that
     category (all entities, all zones, all structures, etc.).
  2. If the full dataset exceeds MAX_ENTRIES_PER_SAMPLE, a RANDOM subset is
     chosen so different cycles cover different slices.  Over time the full
     space is sampled uniformly without any single cycle blowing the log budget.
  3. Runs integrity checks across all entities and logs any anomalies.
  4. Calls bug_catcher.flush() so buffered entries reach disk.

Categories (rotating):
  entities   — ALL entities: full health/position/AI/structure/combat state
  cells      — ALL instantiated zones: cell-type histogram + notable cell positions
  zones      — ALL zones: metadata, entity lists, exits, chest presence
  player     — Complete player state including autopilot fields and full inventory
  structures — ALL structures: type, depth, entity list, cell histogram

Random trim: when an item list exceeds MAX_ENTRIES_PER_SAMPLE, random.sample()
selects the subset.  A watchdog_sample_meta entry records total vs sampled count
so log readers can see what fraction was captured each cycle.

Integrity checks (log-and-detect, no active healing):
  entity_in_subscreen_but_in_screen_entities
  entity_not_in_subscreen_but_in_subscreen_entities
"""

import random
from debug.fixes import fix_entity_subscreen_flag


class Watchdog:
    CATEGORIES = ['entities', 'cells', 'zones', 'player', 'structures']
    SAMPLE_INTERVAL   = 300    # ticks between cycles (~5 s at 60 fps)
    MAX_ENTRIES_PER_SAMPLE = 200  # max JSON entries per category per cycle
    BACKUP1_INTERVAL  = 3600   # ~60 s at 60 fps
    BACKUP2_INTERVAL  = 7200   # ~120 s at 60 fps

    def __init__(self, bug_catcher):
        self.bug_catcher = bug_catcher
        self._category_index = 0
        self._last_run_tick = -99999
        self._last_backup1_tick = -99999
        self._last_backup2_tick = -99999

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def update(self, tick: int, game) -> None:
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
            'structures': self._sample_structures,
        }
        _SAMPLERS[category](tick, game)

        self._check_integrity(tick, game)
        self._maybe_backup(tick, game)
        self.bug_catcher.flush()

    # ------------------------------------------------------------------
    # Random trim helper
    # ------------------------------------------------------------------

    def _trim(self, tick: int, category_name: str, items: list) -> list:
        """Return up to MAX_ENTRIES_PER_SAMPLE items, chosen randomly.
        Logs a meta entry when trimming occurs so reviewers see coverage ratio.
        """
        total = len(items)
        if total <= self.MAX_ENTRIES_PER_SAMPLE:
            return items
        selected = random.sample(items, self.MAX_ENTRIES_PER_SAMPLE)
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_sample_meta',
            'sampler': category_name,
            'total': total,
            'sampled': self.MAX_ENTRIES_PER_SAMPLE,
            'note': 'randomly trimmed — different items sampled each cycle',
        })
        return selected

    # ------------------------------------------------------------------
    # Category samplers — each captures ALL available data for its domain
    # ------------------------------------------------------------------

    def _sample_entities(self, tick: int, game) -> None:
        if not game.entities:
            return
        all_items = list(game.entities.items())
        selected = self._trim(tick, 'entities', all_items)
        for eid, entity in selected:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_entity_sample',
                'id': eid,
                'type': entity.type,
                'zone': f"{entity.screen_x},{entity.screen_y}",
                'grid': [entity.x, entity.y],
                'world': [round(entity.world_x, 2), round(entity.world_y, 2)],
                'health': entity.health,
                'max_health': entity.max_health,
                'hunger': entity.hunger,
                'thirst': entity.thirst,
                'level': entity.level,
                'is_alive': entity.is_alive(),
                'ai_state': getattr(entity, 'ai_state', None),
                'ai_state_timer': getattr(entity, 'ai_state_timer', None),
                'in_combat': getattr(entity, 'in_combat', False),
                'current_target': getattr(entity, 'current_target', None),
                'flee_target': getattr(entity, 'flee_target', None),
                'in_structure': getattr(entity, 'in_structure', False),
                'structure_key': getattr(entity, 'structure_key', None),
                'anim_frame': getattr(entity, 'anim_frame', None),
                'facing': getattr(entity, 'facing', None),
                'faction': getattr(entity, 'faction', None),
                'quest_focus': getattr(entity, 'quest_focus', None),
            })

    def _sample_cells(self, tick: int, game) -> None:
        """Log cell-type histogram and notable cell positions for ALL zones."""
        if not game.screens:
            return
        all_zones = list(game.screens.keys())
        selected_zones = self._trim(tick, 'cells', all_zones)
        notable_types = {'HOUSE', 'STONE_HOUSE', 'CAMP', 'WELL', 'IRON_ORE',
                         'CAVE', 'MINESHAFT', 'FORGE', 'BARREL'}
        for zone_key in selected_zones:
            zone_data = game.screens[zone_key]
            grid = zone_data.get('grid', [])
            cell_counts: dict = {}
            notable: dict = {}
            for y, row in enumerate(grid):
                for x, cell in enumerate(row):
                    cell_counts[cell] = cell_counts.get(cell, 0) + 1
                    if cell in notable_types:
                        notable[f"{x},{y}"] = cell
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_cells_sample',
                'zone': zone_key,
                'cell_counts': cell_counts,
                'notable_cells': notable,
            })

    def _sample_zones(self, tick: int, game) -> None:
        """Log metadata for ALL instantiated zones."""
        if not game.screens:
            return
        all_items = list(game.screens.items())
        selected = self._trim(tick, 'zones', all_items)
        screen_entities = getattr(game, 'screen_entities', {})
        for zone_key, zone_data in selected:
            entity_ids = screen_entities.get(zone_key, [])
            entity_types = [
                game.entities[eid].type
                for eid in entity_ids
                if eid in game.entities
            ]
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_zone_sample',
                'zone': zone_key,
                'has_grid': 'grid' in zone_data,
                'zone_type': zone_data.get('zone_type'),
                'biome': zone_data.get('biome'),
                'exits': zone_data.get('exits'),
                'has_chests': bool(zone_data.get('chests')),
                'chest_count': len(zone_data.get('chests', {})),
                'entity_ids': entity_ids,
                'entity_types': entity_types,
            })

    def _sample_player(self, tick: int, game) -> None:
        """Log complete player state including autopilot and full inventory."""
        p = game.player
        inv = {
            cat: dict(getattr(game.inventory, cat, {}))
            for cat in ('items', 'tools', 'magic', 'followers')
        }
        # Autopilot proxy position (if active) for correlating teleport events
        proxy_pos = None
        proxy_id = getattr(game, 'autopilot_proxy_id', None)
        if proxy_id and proxy_id in game.entities:
            px = game.entities[proxy_id]
            proxy_pos = {
                'zone': f"{px.screen_x},{px.screen_y}",
                'grid': [px.x, px.y],
                'world': [round(px.world_x, 2), round(px.world_y, 2)],
                'ai_state': getattr(px, 'ai_state', None),
                'facing': getattr(px, 'facing', None),
                'in_structure': getattr(px, 'in_structure', False),
            }
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_player_sample',
            'zone': f"{p['screen_x']},{p['screen_y']}",
            'grid': [p['x'], p['y']],
            'world': [
                round(p.get('world_x', float(p['x'])), 2),
                round(p.get('world_y', float(p['y'])), 2),
            ],
            'facing': p.get('facing'),
            'is_moving': p.get('is_moving', False),
            'health': p.get('health'),
            'max_health': p.get('max_health'),
            'energy': p.get('energy'),
            'max_energy': p.get('max_energy'),
            'hunger': p.get('hunger', 0),
            'thirst': p.get('thirst', 0),
            'level': p.get('level'),
            'xp': p.get('xp', 0),
            'blocking': p.get('blocking', False),
            'in_structure': p.get('in_structure', False),
            'structure_key': p.get('structure_key'),
            'active_quest': getattr(game, 'active_quest', None),
            'followers': list(getattr(game, 'followers', [])),
            'inventory': inv,
            # Autopilot state — critical for diagnosing teleport glitches
            'autopilot': getattr(game, 'autopilot', False),
            'autopilot_locked': getattr(game, 'autopilot_locked', False),
            'autopilot_proxy_id': proxy_id,
            'last_input_tick': getattr(game, 'last_input_tick', None),
            'proxy': proxy_pos,
        })

    def _sample_structures(self, tick: int, game) -> None:
        """Log full state for ALL structures (type, cells, entities)."""
        if not game.structures:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_structure_sample',
                'note': 'no structures exist',
            })
            return
        all_items = list(game.structures.items())
        selected = self._trim(tick, 'structures', all_items)
        structure_entities = getattr(game, 'screen_entities', {})
        for sub_key, sub_data in selected:
            entity_ids = structure_entities.get(sub_key, [])
            entity_details = []
            for eid in entity_ids:
                if eid in game.entities:
                    e = game.entities[eid]
                    entity_details.append({
                        'id': eid,
                        'type': e.type,
                        'grid': [e.x, e.y],
                        'health': e.health,
                        'ai_state': getattr(e, 'ai_state', None),
                        'in_structure': getattr(e, 'in_structure', False),
                    })
            grid = sub_data.get('grid', [])
            cell_counts: dict = {}
            for row in grid:
                for cell in row:
                    cell_counts[cell] = cell_counts.get(cell, 0) + 1
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_structure_sample',
                'key': sub_key,
                'interior_type': sub_data.get('interior_type'),
                'depth': sub_data.get('depth'),
                'parent_screen': str(sub_data.get('parent_screen')),
                'parent_cell': str(sub_data.get('parent_cell')),
                'entity_count': len(entity_ids),
                'entities': entity_details,
                'cell_counts': cell_counts,
            })

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _check_integrity(self, tick: int, game) -> None:
        screen_entities = getattr(game, 'screen_entities', {})
        structure_entities = getattr(game, 'screen_entities', {})

        # Build reverse map: entity_id -> [structure_keys it appears in]
        entity_in_structures: dict = {}
        for sub_key, sub_list in structure_entities.items():
            for eid in sub_list:
                entity_in_subs.setdefault(eid, []).append(sub_key)

        for eid, entity in game.entities.items():
            entity_in_structure_flag = getattr(entity, 'in_structure', False)
            zone_key = f"{entity.screen_x},{entity.screen_y}"

            # Check 1: in_structure=True but still in screen_entities
            # apply=True: root cause is patched (try_entity_screen_crossing guard);
            # the safety net clears the flag for any entities already in bad state.
            if entity_in_structure_flag:
                if zone_key in screen_entities and eid in screen_entities[zone_key]:
                    fix_entity_subscreen_flag(
                        eid, entity, game,
                        bug_catcher=self.bug_catcher,
                        tick=tick,
                        apply=True,
                    )

            # Check 2: in_structure=False but present in screen_entities
            if not entity_in_structure_flag and eid in entity_in_structures:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'integrity_anomaly',
                    'check': 'entity_not_in_subscreen_but_in_subscreen_entities',
                    'entity_id': eid,
                    'entity_type': entity.type,
                    'zone': zone_key,
                    'found_in_structures': entity_in_structures[eid],
                })

    # ------------------------------------------------------------------
    # Rolling backup saves
    # ------------------------------------------------------------------

    def _maybe_backup(self, tick: int, game) -> None:
        """Write rolling backup saves every ~60 s and ~120 s."""
        import datetime
        if not hasattr(game, 'save_game'):
            return

        if tick - self._last_backup1_tick >= self.BACKUP1_INTERVAL:
            self._last_backup1_tick = tick
            try:
                game.save_game(path='savegame_backup1.json')
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'backup_save',
                    'file': 'savegame_backup1.json',
                    'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'note': 'rolling 60-s backup',
                })
            except Exception as exc:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'backup_save_error',
                    'file': 'savegame_backup1.json',
                    'error': str(exc),
                })

        if tick - self._last_backup2_tick >= self.BACKUP2_INTERVAL:
            self._last_backup2_tick = tick
            try:
                game.save_game(path='savegame_backup2.json')
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'backup_save',
                    'file': 'savegame_backup2.json',
                    'ts': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'note': 'rolling 120-s backup',
                })
            except Exception as exc:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'backup_save_error',
                    'file': 'savegame_backup2.json',
                    'error': str(exc),
                })
