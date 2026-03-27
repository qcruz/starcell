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
  proxy_stagnation — autopilot proxy grid unchanged across consecutive player samples
"""

import random
import traceback
from debug.fixes import fix_entity_subscreen_flag


class Watchdog:
    CATEGORIES = ['entities', 'cells', 'zones', 'player', 'structures', 'followers', 'npc_actions', 'keepers', 'npc_quests', 'inventory_state', 'favor', 'food_behavior', 'ai_state_cycling']
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
        self._last_proxy_grid = None   # for stagnation detection
        self._last_proxy_tick = None

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
            'entities':         self._sample_entities,
            'cells':            self._sample_cells,
            'zones':            self._sample_zones,
            'player':           self._sample_player,
            'structures':       self._sample_structures,
            'followers':        self._sample_followers,
            'npc_actions':      self._sample_npc_actions,
            'keepers':          self._sample_keepers,
            'npc_quests':       self._sample_npc_quests,
            'inventory_state':  self._sample_inventory_state,
            'favor':            self._sample_favor,
            'food_behavior':    self._sample_food_behavior,
            'ai_state_cycling': self._sample_ai_state_cycling,
        }
        _SAMPLERS[category](tick, game)

        self._sample_spiders(tick, game)
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
                'anim_timer': getattr(entity, 'anim_timer', None),
                'facing': getattr(entity, 'facing', None),
                'sprite_base': entity.props.get('sprite_name', entity.type).lower(),
                'faction': getattr(entity, 'faction', None),
                'quest_focus': getattr(entity, 'quest_focus', None),
                'quest_queue': [e.get('type') for e in getattr(entity, 'quest_queue', [])] or None,
                'quest_target': getattr(entity, 'quest_target', None),
                'keeper': getattr(entity, 'keeper', False),
                'keeper_type': getattr(entity, 'keeper_type', None),
                'keeper_target_type': getattr(entity, 'keeper_target', {}).get('type') if getattr(entity, 'keeper_target', None) else None,
                'keeper_target_ref': getattr(entity, 'keeper_target', {}).get('ref') if getattr(entity, 'keeper_target', None) else None,
                'in_subscreen': getattr(entity, 'in_subscreen', False),
                'subscreen_key': getattr(entity, 'subscreen_key', None),
                'ai_state_timer': getattr(entity, 'ai_state_timer', None),
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
            # UI state — critical for diagnosing stuck inventory panels
            'open_menus': list(getattr(game.inventory, 'open_menus', set())),
            'quest_ui_open': getattr(game, 'quest_ui_open', False),
            'trader_display': bool(getattr(game, 'trader_display', None)),
            'inspected_npc': getattr(game, 'inspected_npc', None),
            'ap_input_queue_len': len(getattr(game, '_ap_input_queue', [])),
            'death_counts': dict(getattr(game, 'death_counts', {})),
            'entities_spawned_total': getattr(game, 'entities_spawned_total', 0),
            'entities_alive': len(game.entities),
        })
        # Stagnation check: flag if proxy grid hasn't changed since last player sample
        if proxy_pos and getattr(game, 'autopilot', False):
            current_grid = proxy_pos['grid']
            if self._last_proxy_grid is not None and current_grid == self._last_proxy_grid:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'proxy_stagnation',
                    'grid': current_grid,
                    'ticks_stuck': tick - self._last_proxy_tick,
                    'note': 'proxy grid unchanged since last player sample',
                })
            self._last_proxy_grid = current_grid
            self._last_proxy_tick = tick
        elif not getattr(game, 'autopilot', False):
            self._last_proxy_grid = None
            self._last_proxy_tick = None

    def _sample_structures(self, tick: int, game) -> None:
        """Log full state for ALL structures (type, cells, entities, movement/AI health)."""
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
                    timer = getattr(e, 'ai_state_timer', 0) or 0
                    entity_details.append({
                        'id': eid,
                        'type': e.type,
                        'grid': [e.x, e.y],
                        'world': [round(getattr(e, 'world_x', e.x), 2),
                                  round(getattr(e, 'world_y', e.y), 2)],
                        'health': e.health,
                        'hunger': getattr(e, 'hunger', None),
                        'thirst': getattr(e, 'thirst', None),
                        'ai_state': getattr(e, 'ai_state', None),
                        'ai_state_timer': timer,
                        'frozen_flag': timer > 600,   # stuck in one state >10 s
                        'in_structure': getattr(e, 'in_structure', False),
                        'in_subscreen': getattr(e, 'in_subscreen', False),
                        'current_target': getattr(e, 'current_target', None),
                        'in_combat': getattr(e, 'in_combat', False),
                        'facing': getattr(e, 'facing', None),
                        'anim_frame': getattr(e, 'anim_frame', None),
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
                'frozen_count': sum(1 for e in entity_details if e.get('frozen_flag')),
                'cell_counts': cell_counts,
            })

    def _sample_followers(self, tick: int, game) -> None:
        """Log full state for every active follower."""
        followers = getattr(game, 'followers', [])
        follower_items = getattr(game, 'follower_items', {})
        player_zone = f"{game.player.get('screen_x', 0)},{game.player.get('screen_y', 0)}"
        if not followers:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_follower_sample',
                'note': 'no followers',
            })
            return
        for fid in followers:
            entity = game.entities.get(fid)
            if not entity:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'watchdog_follower_sample',
                    'id': fid,
                    'error': 'missing_from_entities',
                    'item_name': follower_items.get(fid),
                })
                continue
            follower_zone = f"{entity.screen_x},{entity.screen_y}"
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_follower_sample',
                'id': fid,
                'type': entity.type,
                'zone': follower_zone,
                'player_zone': player_zone,
                'zone_match': follower_zone == player_zone,
                'grid': [entity.x, entity.y],
                'health': entity.health,
                'ai_state': getattr(entity, 'ai_state', None),
                'in_combat': getattr(entity, 'in_combat', False),
                'current_target': getattr(entity, 'current_target', None),
                'hostile': entity.props.get('hostile', False),
                'item_name': follower_items.get(fid),
            })

    def _sample_npc_actions(self, tick: int, game) -> None:
        """Log AI state for all entities on the player's current screen."""
        player_zone = f"{game.player.get('screen_x', 0)},{game.player.get('screen_y', 0)}"
        eids = game.screen_entities.get(player_zone, [])
        if not eids:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_npc_actions',
                'note': 'no entities on player screen',
            })
            return
        followers = getattr(game, 'followers', [])
        all_items = [(eid, game.entities[eid]) for eid in eids if eid in game.entities]
        selected = self._trim(tick, 'npc_actions', all_items)
        for eid, entity in selected:
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_npc_actions',
                'id': eid,
                'type': entity.type,
                'grid': [entity.x, entity.y],
                'ai_state': getattr(entity, 'ai_state', None),
                'ai_state_timer': getattr(entity, 'ai_state_timer', None),
                'target_priority': getattr(entity, 'target_priority', None),
                'in_combat': getattr(entity, 'in_combat', False),
                'current_target': getattr(entity, 'current_target', None),
                'hostile': entity.props.get('hostile', False),
                'health': entity.health,
                'is_follower': eid in followers,
                'last_ai_tick': getattr(entity, 'last_ai_tick', None),
                'stuck_counter': getattr(entity, 'stuck_counter', 0),
            })

    def _sample_keepers(self, tick: int, game) -> None:
        """Log all keeper NPCs: target type, target ref, resolved pos, zone, quest queue.

        Captures cross-zone chase state, quest progress, and any keepers that are
        stuck (keeper=True but keeper_target=None for more than one sample cycle).
        """
        keepers = [
            (eid, e) for eid, e in game.entities.items()
            if getattr(e, 'keeper', False)
        ]
        if not keepers:
            self.bug_catcher.log({
                'tick': tick, 'category': 'watchdog_keepers',
                'note': 'no active keepers',
            })
            return
        for eid, entity in keepers:
            kt = getattr(entity, 'keeper_target', None)
            kt_type = kt.get('type') if kt else None
            kt_ref  = kt.get('ref')  if kt else None
            kt_pos  = kt.get('pos')  if kt else None
            kt_screen = kt.get('screen') if kt else None
            my_screen = (entity.screen_x, entity.screen_y)
            cross_zone = kt_screen is not None and kt_screen != my_screen

            # Compute target health % if entity target is alive
            target_hp_pct = None
            if kt_type == 'entity' and kt_ref in game.entities:
                t = game.entities[kt_ref]
                target_hp_pct = round(t.health / max(t.max_health, 1) * 100, 1)

            queue = getattr(entity, 'quest_queue', None)
            queue_snapshot = [
                {'type': e.get('type'), 'base': e.get('base')}
                for e in queue
            ] if queue else None

            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_keepers',
                'id': eid,
                'type': entity.type,
                'zone': f"{my_screen[0]},{my_screen[1]}",
                'grid': [entity.x, entity.y],
                'keeper_type': getattr(entity, 'keeper_type', None),
                'kt_type': kt_type,
                'kt_ref': kt_ref,
                'kt_pos': list(kt_pos) if kt_pos else None,
                'kt_screen': list(kt_screen) if kt_screen else None,
                'cross_zone': cross_zone,
                'target_hp_pct': target_hp_pct,
                'keeper_target_pos': list(entity.keeper_target_pos) if getattr(entity, 'keeper_target_pos', None) else None,
                'quest_focus': getattr(entity, 'quest_focus', None),
                'quest_queue': queue_snapshot,
                'ai_state': getattr(entity, 'ai_state', None),
                'current_target': str(getattr(entity, 'current_target', None)),
            })

            # Integrity: flag keepers with no target reference
            # Type 3 = zone wanderer; naturally has no target — skip false positive
            _ktype = getattr(entity, 'keeper_type', None)
            if not kt and _ktype in (1, 2):
                self.bug_catcher.log({
                    'tick': tick, 'category': 'watchdog_integrity',
                    'check': 'keeper_no_target',
                    'id': eid, 'type': entity.type,
                    'keeper_type': _ktype,
                    'note': 'keeper=True (type 1/2) but keeper_target is None — still searching or bug',
                })

    def _sample_npc_quests(self, tick: int, game) -> None:
        """Log all NPCs that have an active quest queue or quest target.

        Captures lore-assigned and player-assigned quest state: queue contents,
        current target, focus type, progress toward completion, and whether the
        NPC is keeper-anchored to the target.
        """
        from constants import NPC_BASE_QUEST
        active = [
            (eid, e) for eid, e in game.entities.items()
            if e.type in NPC_BASE_QUEST
            and (getattr(e, 'quest_queue', None) or getattr(e, 'quest_target', None))
        ]
        if not active:
            self.bug_catcher.log({
                'tick': tick, 'category': 'watchdog_npc_quests',
                'note': 'no NPCs with active quest queues',
            })
            return
        for eid, entity in active:
            queue = getattr(entity, 'quest_queue', None)
            qt = entity.quest_target
            # Resolve target description
            if isinstance(qt, int) and qt in game.entities:
                t = game.entities[qt]
                target_desc = f"{t.type}(id={qt}) HP:{int(t.health)}/{int(t.max_health)}"
            elif isinstance(qt, tuple):
                target_desc = str(qt)
            else:
                target_desc = str(qt) if qt is not None else None
            self.bug_catcher.log({
                'tick': tick,
                'category': 'watchdog_npc_quests',
                'id': eid,
                'type': entity.type,
                'zone': f"{entity.screen_x},{entity.screen_y}",
                'grid': [entity.x, entity.y],
                'quest_focus': getattr(entity, 'quest_focus', None),
                'quest_queue': [{'type': e.get('type'), 'base': e.get('base')} for e in queue] if queue else None,
                'quest_target': target_desc,
                'ai_state': getattr(entity, 'ai_state', None),
                'keeper': getattr(entity, 'keeper', False),
                'keeper_type': getattr(entity, 'keeper_type', None),
            })

    def _sample_inventory_state(self, tick: int, game) -> None:
        """Log full inventory state: tool_slots, equipment, actions, selection."""
        inv = game.inventory
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_inventory_state',
            'tool_slots': list(inv.tool_slots),
            'tool_slot_filled': sum(1 for s in inv.tool_slots if s is not None),
            'equipment_slots': dict(inv.equipment_slots),
            'any_equipment': any(v is not None for v in inv.equipment_slots.values()),
            'actions': dict(inv.actions),
            'items_count': sum(inv.items.values()) if inv.items else 0,
            'magic_count': sum(inv.magic.values()) if inv.magic else 0,
            'selected_tool_slot_idx': inv.selected_tool_slot_idx,
            'selected_tools': inv.selected.get('tools'),
            'selected_items': inv.selected.get('items'),
            'selected_actions': inv.selected.get('actions'),
            'pending_equip_slot': inv.pending_equip_slot,
            'pending_equip_equipment_slot': inv.pending_equip_equipment_slot,
            'open_menus': sorted(inv.open_menus),
            'items_top5': sorted(inv.items.items(), key=lambda x: -x[1])[:5] if inv.items else [],
        })

    def _sample_favor(self, tick: int, game) -> None:
        """Log favor scores for all NPCs on the player's current screen."""
        player_zone = f"{game.player.get('screen_x', 0)},{game.player.get('screen_y', 0)}"
        eids = game.screen_entities.get(player_zone, [])
        entries = []
        for eid in eids:
            e = game.entities.get(eid)
            if e is None:
                continue
            favor = getattr(e, 'favor', None)
            if favor is not None:
                entries.append({
                    'id': eid,
                    'type': e.type,
                    'name': getattr(e, 'name', None),
                    'favor': favor,
                    'hostile': e.props.get('hostile', False),
                    'grid': [e.x, e.y],
                    'level': e.level,
                })
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_favor',
            'zone': player_zone,
            'npc_count': len(entries),
            'npcs': entries,
            'inspected_npc': getattr(game, 'inspected_npc', None),
        })

    def _sample_food_behavior(self, tick: int, game) -> None:
        """Track hungry NPCs and their food-targeting state across all loaded zones.

        Flags the farmer idle/targeting toggle bug: a FARMER adjacent to a carrot
        cell that keeps flipping between 'targeting' (food) and 'idle' without eating.
        """
        _CARROT_CELLS = {'CARROT1', 'CARROT2', 'CARROT3'}
        entries = []
        for eid, entity in game.entities.items():
            if entity.health <= 0:
                continue
            hunger_pct = entity.hunger / max(1, entity.max_hunger)
            if hunger_pct > 0.6:
                continue  # Only watch hungry entities
            screen_key = f"{entity.screen_x},{entity.screen_y}"
            screen = game.screens.get(screen_key)
            if not screen:
                continue
            grid = screen.get('grid', [])
            # Find nearest carrot and its distance
            nearest_carrot = None
            nearest_dist = float('inf')
            for dy in range(-3, 4):
                for dx in range(-3, 4):
                    nx, ny = entity.x + dx, entity.y + dy
                    if 0 <= nx < 24 and 0 <= ny < 18:
                        try:
                            if grid[ny][nx] in _CARROT_CELLS:
                                d = abs(dx) + abs(dy)
                                if d < nearest_dist:
                                    nearest_dist = d
                                    nearest_carrot = (nx, ny, grid[ny][nx])
                        except IndexError:
                            pass
            entries.append({
                'id': eid,
                'type': entity.type,
                'zone': screen_key,
                'grid': [entity.x, entity.y],
                'hunger': round(entity.hunger, 1),
                'max_hunger': entity.max_hunger,
                'hunger_pct': round(hunger_pct, 2),
                'ai_state': getattr(entity, 'ai_state', None),
                'target_type': getattr(entity, 'target_type', None),
                'current_target': getattr(entity, 'current_target', None),
                'nearest_carrot': nearest_carrot,
                'nearest_carrot_dist': nearest_dist if nearest_carrot else None,
                'adjacent_to_food': nearest_dist <= 1 if nearest_carrot else False,
            })
        self.bug_catcher.log({
            'tick': tick,
            'category': 'watchdog_food_behavior',
            'hungry_npc_count': len(entries),
            'npcs': self._trim(tick, 'food_behavior', entries),
        })

    def _sample_ai_state_cycling(self, tick: int, game) -> None:
        """Snapshot the full AI priority state for every loaded entity.

        Designed to catch target-type cycling bugs: quest → keeper → special →
        role → resource.  Logs each entity's current position in the priority
        stack so bad state (e.g. repeatedly flipping food↔idle, or keeper winning
        when in range, or quest never firing) shows up across consecutive cycles.

        Also tallies a summary histogram of ai_state × target_type combinations
        so the session review can spot population-level imbalances at a glance.
        """
        entries = []
        state_hist = {}   # {(ai_state, target_type): count}
        for eid, entity in game.entities.items():
            if entity.health <= 0:
                continue
            ai_state    = getattr(entity, 'ai_state', None)
            target_type = getattr(entity, 'target_type', None)
            key = (ai_state or 'none', target_type or 'none')
            state_hist[key] = state_hist.get(key, 0) + 1

            h_pct = round(entity.hunger / max(1, entity.max_hunger), 2)
            t_pct = round(entity.thirst / max(1, entity.max_thirst), 2)
            entries.append({
                'id':            eid,
                'type':          entity.type,
                'zone':          f"{entity.screen_x},{entity.screen_y}",
                'level':         round(entity.level, 1),
                'ai_state':      ai_state,
                'target_type':   target_type,
                'current_target':str(getattr(entity, 'current_target', None)),
                'target_priority': getattr(entity, 'target_priority', None),
                'hunger_pct':    h_pct,
                'thirst_pct':    t_pct,
                'in_combat':     getattr(entity, 'in_combat', False),
                'quest_focus':   getattr(entity, 'quest_focus', None),
                'keeper':        getattr(entity, 'keeper', False),
                'keeper_type':   getattr(entity, 'keeper_type', None),
                'keeper_in_range': (
                    getattr(entity, 'keeper', False) and
                    getattr(entity, 'keeper_target_pos', None) is not None and
                    (abs(entity.x - entity.keeper_target_pos[0]) +
                     abs(entity.y - entity.keeper_target_pos[1])) <=
                    (getattr(entity, 'keeper_type', 3) and 4)
                ),
            })

        # Serialise histogram with string keys for JSON
        hist_serialised = {f"{s}|{t}": c for (s, t), c in
                           sorted(state_hist.items(), key=lambda x: -x[1])}

        # Health / resource / level summary stats
        hp_pcts   = [round(e['hunger_pct'], 2) for e in entries]  # reuse entries field names
        alive     = len(entries)
        hp_full   = sum(1 for e in entries
                        if e['hunger_pct'] >= 0.8 and e['thirst_pct'] >= 0.8)
        level_hist = {}
        for e in entries:
            lv = int(e['level'])
            level_hist[lv] = level_hist.get(lv, 0) + 1
        health_80_plus = sum(
            1 for eid, entity in game.entities.items()
            if entity.health > 0 and entity.health / max(1, entity.max_health) >= 0.8
        )

        self.bug_catcher.log({
            'tick':              tick,
            'category':          'watchdog_ai_state_cycling',
            'total_alive':       alive,
            'state_histogram':   hist_serialised,
            'level_histogram':   {str(k): v for k, v in sorted(level_hist.items())},
            'both_bars_80pct':   hp_full,
            'health_80pct_count': health_80_plus,
            'npcs':              self._trim(tick, 'ai_state_cycling', entries),
        })

    def _sample_spiders(self, tick: int, game) -> None:
        """Log full animation + AI state for every BLACK_SPIDER every cycle — no trimming."""
        player_zone = f"{game.player.get('screen_x', 0)},{game.player.get('screen_y', 0)}"
        spider_types = {'BLACK_SPIDER', 'BLACK_SPIDER_double'}
        spiders = [(eid, e) for eid, e in game.entities.items() if e.type in spider_types]
        if not spiders:
            return
        for eid, entity in spiders:
            entity_zone = f"{entity.screen_x},{entity.screen_y}"
            self.bug_catcher.log({
                'tick': tick,
                'category': 'spider_sample',
                'id': eid,
                'type': entity.type,
                'zone': entity_zone,
                'on_player_screen': entity_zone == player_zone,
                'grid': [entity.x, entity.y],
                'world': [round(entity.world_x, 2), round(entity.world_y, 2)],
                'facing': getattr(entity, 'facing', None),
                'anim_frame': getattr(entity, 'anim_frame', None),
                'anim_timer': getattr(entity, 'anim_timer', None),
                'sprite_base': entity.props.get('sprite_name', entity.type).lower(),
                'is_moving': getattr(entity, 'is_moving', None),
                'ai_state': getattr(entity, 'ai_state', None),
                'in_combat': getattr(entity, 'in_combat', False),
                'current_target': getattr(entity, 'current_target', None),
                'health': entity.health,
                'is_alive': entity.is_alive(),
            })

    # ------------------------------------------------------------------
    # Integrity checks
    # ------------------------------------------------------------------

    def _check_integrity(self, tick: int, game) -> None:
        screen_entities = getattr(game, 'screen_entities', {})

        # Build reverse map from STRUCTURE keys only (not overworld zones).
        # screen_entities contains both — filter to keys present in game.structures.
        structure_keys = set(getattr(game, 'structures', {}).keys())
        entity_in_structures: dict = {}
        for sub_key, sub_list in screen_entities.items():
            if sub_key not in structure_keys:
                continue
            for eid in sub_list:
                entity_in_structures.setdefault(eid, []).append(sub_key)

        for eid, entity in game.entities.items():
            entity_in_structure_flag = getattr(entity, 'in_structure', False)
            zone_key = f"{entity.screen_x},{entity.screen_y}"

            # Check 1: in_structure=True but entity is in an OVERWORLD zone's screen_entities.
            # Only fire when zone_key is NOT a structure key — if entity.screen_x/y already
            # points to a structure virtual zone, the entity is properly inside that structure
            # (correct state) and must not be disturbed.
            if entity_in_structure_flag and zone_key not in structure_keys:
                if zone_key in screen_entities and eid in screen_entities[zone_key]:
                    fix_entity_subscreen_flag(
                        eid, entity, game,
                        bug_catcher=self.bug_catcher,
                        tick=tick,
                        apply=True,
                    )

            # Check 2: in_structure=False but found in a true structure zone
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

        # Check 3: frozen entities inside structures (ai_state_timer stuck >600 ticks)
        for sub_key in structure_keys:
            for eid in screen_entities.get(sub_key, []):
                if eid not in game.entities:
                    continue
                e = game.entities[eid]
                timer = getattr(e, 'ai_state_timer', 0) or 0
                if timer > 600:
                    self.bug_catcher.log({
                        'tick': tick,
                        'category': 'integrity_anomaly',
                        'check': 'entity_frozen_in_structure',
                        'entity_id': eid,
                        'entity_type': e.type,
                        'structure_key': sub_key,
                        'interior_type': game.structures.get(sub_key, {}).get('interior_type'),
                        'ai_state': getattr(e, 'ai_state', None),
                        'ai_state_timer': timer,
                        'grid': [e.x, e.y],
                        'health': e.health,
                        'in_structure': getattr(e, 'in_structure', False),
                        'in_subscreen': getattr(e, 'in_subscreen', False),
                    })

        # Check 4: follower integrity
        followers = getattr(game, 'followers', [])
        for fid in followers:
            if fid not in game.entities:
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'integrity_anomaly',
                    'check': 'follower_missing_from_entities',
                    'entity_id': fid,
                })
                continue
            fe = game.entities[fid]
            if fe.props.get('hostile', False):
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'integrity_anomaly',
                    'check': 'follower_is_hostile',
                    'entity_id': fid,
                    'entity_type': fe.type,
                })
            if getattr(fe, 'current_target', None) == 'player':
                self.bug_catcher.log({
                    'tick': tick,
                    'category': 'integrity_anomaly',
                    'check': 'follower_targeting_player',
                    'entity_id': fid,
                    'entity_type': fe.type,
                    'ai_state': getattr(fe, 'ai_state', None),
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
                    'traceback': traceback.format_exc(),
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
                    'traceback': traceback.format_exc(),
                })
