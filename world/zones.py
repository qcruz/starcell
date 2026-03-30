import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, ENTITY_TYPES,
    MAX_CATCHUP_PER_FRAME, MAX_CYCLES_TO_SIMULATE,
    UPDATE_FREQUENCY, MAX_ZONES_PER_UPDATE,
    NEW_ZONE_INSTANTIATE_CHANCE, ZONE_SOFT_CAP,
    SKELETON_DAYLIGHT_DAMAGE,
    CAMP_HEALING_MULTIPLIER, HOUSE_HEALING_MULTIPLIER,
    NPC_CAMP_PLACE_RATE, ENHANCED_SETTLEMENT_RATE,
    KEEPER_ENTITY_TYPE, KEEPER_ASSIGNMENT_RATE,
    KEEPER_TYPE_BY_ENTITY, KEEPER_RANGE,
    DESERT_ROCK_FORMATION_RATE, DESERT_ORE_FORMATION_RATE,
    RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX,
    RAIN_DURATION_MIN, RAIN_DURATION_MAX,
)
from entity import Entity


class ZonesMixin:
    """Handles zone update loop, priority queue, catch-up simulation,
    biome shifts, and entity lifecycle across zones."""

    # -------------------------------------------------------------------------
    # Zone purge helper
    # -------------------------------------------------------------------------

    def _purge_zone(self, zone_key):
        """Thoroughly remove a zone and all associated data from every game structure.

        Covers: screens, instantiated_zones, screen_last_update, zone_rain,
        screen_entities (+ entity deletion), dropped_items, buried_items,
        chest_contents, opened_chests, door_map, enchanted_cells, zone_keepers,
        enchanted_entities (entity-keyed, so checked by zone membership).
        """
        zone_prefix = zone_key + ':'

        # --- Entities in this zone ---
        for eid in list(self.screen_entities.get(zone_key, [])):
            self.followers = [f for f in self.followers if f != eid]
            if hasattr(self, 'follower_items'):
                self.follower_items.pop(eid, None)
            self.entities.pop(eid, None)
        self.screen_entities.pop(zone_key, None)

        # --- Keeper slots ---
        self.zone_keepers.pop(zone_key, None)

        # --- Items ---
        self.dropped_items.pop(zone_key, None)
        if hasattr(self, 'buried_items'):
            self.buried_items.pop(zone_key, None)

        # --- Chest contents (keyed "zone_key:x,y") ---
        for ck in [k for k in self.chest_contents if k.startswith(zone_prefix)]:
            del self.chest_contents[ck]
        for ok in [k for k in self.opened_chests if k.startswith(zone_prefix)]:
            self.opened_chests.discard(ok)

        # --- Door map (tuple keys: (zone_key, x, y) → (dest_zone, dx, dy)) ---
        for dk in [k for k in self.door_map
                   if k[0] == zone_key or self.door_map[k][0] == zone_key]:
            self.door_map.pop(dk, None)

        # --- Enchanted cells (keyed {zone_key: {(x,y): level}}) ---
        if hasattr(self, 'enchanted_cells'):
            self.enchanted_cells.pop(zone_key, None)

        # --- Zone world data ---
        self.screens.pop(zone_key, None)
        self.instantiated_zones.discard(zone_key)
        self.screen_last_update.pop(zone_key, None)
        if hasattr(self, 'zone_rain'):
            self.zone_rain.pop(zone_key, None)

        self.zones_deleted = getattr(self, 'zones_deleted', 0) + 1

    # -------------------------------------------------------------------------
    # Main update loop
    # -------------------------------------------------------------------------

    def probabilistic_zone_updates(self):
        """Priority queue based zone updates. Zones scored by distance, staleness,
        connections, quests, and structures. Higher priority = updated first."""
        if not getattr(self, 'time_pass_active', False) and self.tick % UPDATE_FREQUENCY != 0:
            return

        self.update_day_night_cycle()
        self.move_items_to_nearest_chest()

        # Chance to instantiate a new random overworld zone, scaled down with distance from player.
        # Soft cap: above ZONE_SOFT_CAP overworld zones the chance drops sharply.
        _overworld_count = sum(1 for zk in self.screens if self.is_overworld_zone(zk))
        _inst_chance = NEW_ZONE_INSTANTIATE_CHANCE
        if _overworld_count >= ZONE_SOFT_CAP:
            _excess = _overworld_count - ZONE_SOFT_CAP
            _inst_chance *= max(0.02, 1.0 / (1.0 + _excess * 0.15))
        if random.random() < _inst_chance:
            _pox = self.player['screen_x'] if self.is_overworld_zone(f"{self.player['screen_x']},{self.player['screen_y']}") else 0
            _poy = self.player['screen_y'] if self.is_overworld_zone(f"{self.player['screen_x']},{self.player['screen_y']}") else 0
            range_x = random.randint(-20, 20)
            range_y = random.randint(-20, 20)
            new_zone_key = f"{range_x},{range_y}"
            if new_zone_key not in self.screens:
                dist = abs(range_x - _pox) + abs(range_y - _poy)
                if random.random() < 1.0 / (1.0 + dist * 0.25):
                    self.generate_screen(range_x, range_y)
                    self.instantiated_zones.add(new_zone_key)

        if self.tick % 600 == 0:
            self.cleanup_screen_entities()
            # Recompute faction control for all overworld zones and update domains
            for zk in list(self.screens.keys()):
                if self.is_overworld_zone(zk):
                    self.update_zone_faction_control(zk)
            # Sync instantiated_zones exactly with self.screens (bidirectional)
            self.instantiated_zones = set(self.screens.keys())
            # Validate door_map: remove entries where either zone is missing
            for door_key in list(getattr(self, 'door_map', {}).keys()):
                src_zone = door_key[0]
                dest = self.door_map[door_key]
                dest_zone = dest[0]
                if src_zone not in self.screens or dest_zone not in self.screens:
                    del self.door_map[door_key]
            # Clean up structure zones whose parent entrance cell has been destroyed
            for struct_key in list(self.structure_zones.keys()):
                sz = self.structure_zones[struct_key]
                parent = sz.get('parent_zone')
                cell_pos = sz.get('cell')
                if not parent or not cell_pos:
                    continue
                if parent not in self.screens:
                    self.deinstantiate_structure_zone(struct_key)
                    continue
                cx, cy = cell_pos
                if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                    continue
                parent_screen = self.screens[parent]
                parent_cell = parent_screen['grid'][cy][cx]
                if parent_cell not in ('HOUSE', 'STONE_HOUSE', 'CAVE', 'MINESHAFT'):
                    self.deinstantiate_structure_zone(struct_key)

            # De-instantiate distant overworld zones that have been idle and empty
            # Probability of removal increases with distance; nearby zones are protected
            _px = self.player['screen_x']
            _py = self.player['screen_y']
            _idle_threshold = 3600  # ~1 min at 60fps
            for _zk in list(self.instantiated_zones):
                if not self.is_overworld_zone(_zk):
                    continue
                _zx, _zy = int(_zk.split(',')[0]), int(_zk.split(',')[1])
                _dist = abs(_zx - _px) + abs(_zy - _py)
                if _dist <= 4:
                    continue  # always keep player-adjacent zones
                if self.tick - self.screen_last_update.get(_zk, 0) < _idle_threshold:
                    continue  # not idle long enough
                # Keep zone only if it has ALIVE entities (dead IDs in screen_entities don't count)
                _has_alive = any(
                    eid in self.entities and self.entities[eid].health > 0
                    for eid in self.screen_entities.get(_zk, [])
                )
                if _has_alive:
                    continue
                # Remove with probability proportional to distance
                if random.random() < min(0.9, _dist * 0.04):
                    self._purge_zone(_zk)

        # --- Staleness hard trim: zones not updated in >20k ticks get deleted
        # regardless of content. Chance = ticks_since_update / 100_000 per cycle. ---
        _px = self.player['screen_x']
        _py = self.player['screen_y']
        for _zk in list(self.instantiated_zones):
            if not self.is_overworld_zone(_zk):
                continue
            _zx, _zy = int(_zk.split(',')[0]), int(_zk.split(',')[1])
            if abs(_zx - _px) + abs(_zy - _py) <= 4:
                continue  # always protect player-adjacent zones
            _stale = self.tick - self.screen_last_update.get(_zk, 0)
            if _stale < 20000:
                continue
            _delete_chance = min(1.0, _stale / 100000)
            if random.random() < _delete_chance:
                self._purge_zone(_zk)

        self.ensure_nearby_zones_exist()

        priority_queue = self.get_priority_sorted_zones()

        zones_updated = 0
        total_entities_updated = 0
        total_cells_updated = 0

        # Always update the player's zone first at full coverage
        # player screen_x/y reflects virtual coords when in structure zone — no special case needed
        player_zone_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Build set of mandatory zones: player + 4 cardinal neighbors
        psx, psy = self.player['screen_x'], self.player['screen_y']
        mandatory_zones = {player_zone_key}
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nk = f"{psx + dx},{psy + dy}"
            if nk in self.screens:
                mandatory_zones.add(nk)
        # Include structure zones connected to player zone
        if player_zone_key in self.zone_connections:
            for connected_key, *_ in self.zone_connections[player_zone_key]:
                if connected_key in self.screens:
                    mandatory_zones.add(connected_key)

        # Update all mandatory zones: entities 100%, cells 50%
        for mz_key in mandatory_zones:
            if mz_key in self.structure_zones:
                self.update_structure_zone(mz_key, 0.5, 1.0)
            elif self.is_overworld_zone(mz_key):
                parts = mz_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), 0.5, 1.0)
            else:
                continue
            zones_updated += 1
            ent_count = len(self.screen_entities.get(mz_key, []))
            total_entities_updated += ent_count
            total_cells_updated += GRID_WIDTH * GRID_HEIGHT

        # Process remaining zones from priority queue with position-based falloff
        queue_position = 0
        for priority, zone_key in priority_queue:
            if zones_updated >= MAX_ZONES_PER_UPDATE:
                break

            if zone_key in mandatory_zones:
                continue

            queue_position += 1

            update_chance = max(0.05, (100 - queue_position) / 100.0)
            if random.random() > update_chance:
                continue

            entity_coverage = update_chance
            cell_coverage = update_chance * 0.5   # cells always get half entity rate

            if zone_key in self.structure_zones:
                self.update_structure_zone(zone_key, cell_coverage, entity_coverage)
            elif self.is_overworld_zone(zone_key):
                parts = zone_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), cell_coverage, entity_coverage)
            else:
                continue

            zones_updated += 1
            ent_count = len(self.screen_entities.get(zone_key, []))
            total_entities_updated += int(ent_count * entity_coverage)
            total_cells_updated += int(GRID_WIDTH * GRID_HEIGHT * cell_coverage)

        # Sync global is_raining to the player zone's per-zone rain state (for UI/sounds)
        _pzk = f"{self.player['screen_x']},{self.player['screen_y']}"
        if hasattr(self, 'zone_rain') and _pzk in self.zone_rain:
            self.is_raining = self.zone_rain[_pzk]['is_raining']


    # -------------------------------------------------------------------------
    # Per-zone update methods
    # -------------------------------------------------------------------------

    def update_zone_with_coverage(self, zone_x, zone_y, cell_coverage, entity_coverage):
        """Update a zone — when selected, update ALL its features."""
        zone_key = f"{zone_x},{zone_y}"

        if zone_key not in self.screens:
            return

        screen = self.screens[zone_key]
        self.screen_last_update[zone_key] = self.tick

        # Distance-based decay multiplier: structures and items decay faster in distant zones
        _dist_from_player = abs(zone_x - self.player['screen_x']) + abs(zone_y - self.player['screen_y'])
        _decay_factor = 1.0 + _dist_from_player * 0.02  # +2% per zone, no cap

        # === ZONE-LEVEL UPDATES ===
        self.check_zone_threats(zone_key)
        self.check_raid_event(zone_key)
        self.check_cave_spawn_hostile(zone_key)
        self.check_night_skeleton_spawn(zone_key)
        self.check_termite_spawn(zone_key)
        self.decay_dropped_items(zone_x, zone_y, _decay_factor)
        self.decay_items_to_buried(zone_key, _decay_factor)
        self.decay_buried_items(zone_key, _decay_factor)
        self.consolidate_dropped_items(zone_key)
        self.consolidate_chests(zone_key)
        self.assign_zone_keepers(zone_key)
        # Wolf pack check: ~0.5% per update or on the 600-tick sweep
        if self.tick % 600 == 0 or random.random() < 0.005:
            self.assign_wolf_pack_keepers(zone_key)

        # === PER-ZONE RAIN ===
        if not hasattr(self, 'zone_rain'):
            self.zone_rain = {}
        if zone_key not in self.zone_rain:
            self.zone_rain[zone_key] = {
                'is_raining': False,
                'weather_timer': random.randint(0, RAIN_FREQUENCY_MAX),
                'weather_cycle': random.randint(RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX),
                'rain_timer': 0,
                'rain_duration': 0,
            }
        _zr = self.zone_rain[zone_key]
        _zr['weather_timer'] += 1
        if _zr['weather_timer'] >= _zr['weather_cycle']:
            _zr['weather_timer'] = 0
            _zr['weather_cycle'] = random.randint(RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX)
            _zr['is_raining'] = True
            _zr['rain_duration'] = random.randint(RAIN_DURATION_MIN, RAIN_DURATION_MAX)
            _zr['rain_timer'] = 0
        if _zr['is_raining']:
            _zr['rain_timer'] += 1
            if _zr['rain_timer'] >= _zr['rain_duration']:
                _zr['is_raining'] = False
                _zr['rain_timer'] = 0
        _zone_is_raining = _zr['is_raining']

        # === CELL UPDATES ===
        if _zone_is_raining:
            time_passing = getattr(self, 'time_pass_active', False)
            if time_passing or _dist_from_player <= 2:
                self.apply_rain(zone_x, zone_y)

        # apply_cellular_automata reads self.is_raining; use this zone's rain state
        _saved_is_raining = self.is_raining
        self.is_raining = _zone_is_raining
        self.apply_cellular_automata(zone_x, zone_y, cell_coverage)
        self.is_raining = _saved_is_raining

        _tp = getattr(self, 'time_pass_speed', 1.0)
        _biome = screen.get('biome', 'FOREST')
        _biome_base_map = {'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
                           'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT'}
        base_cell = _biome_base_map.get(_biome, 'GRASS')

        # Count caves for elevated decay when zone is over-caved
        cave_count = sum(1 for row in screen['grid'] for c in row if c == 'CAVE')
        cave_decay_rate = 0.01 if cave_count > 2 else 0.0

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                if self.is_cell_enchanted(x, y, zone_key):
                    continue

                cell = screen['grid'][y][x]

                # Decay excess caves back to base cell
                if cell == 'CAVE' and cave_decay_rate > 0 and random.random() < cave_decay_rate:
                    screen['grid'][y][x] = base_cell
                    continue

                # Chest lifecycle: decay with contents, restore background when empty
                if cell == 'CHEST':
                    chest_key = f"{zone_key}:{x},{y}"
                    contents = self.chest_contents.get(chest_key, {})
                    if any(v > 0 for v in contents.values()):
                        if random.random() < 0.005 * _tp:
                            # Dump all contents as dropped items at this position
                            if zone_key not in self.dropped_items:
                                self.dropped_items[zone_key] = {}
                            pos = (x, y)
                            if pos not in self.dropped_items[zone_key]:
                                self.dropped_items[zone_key][pos] = {}
                            for item_name, count in contents.items():
                                if count > 0:
                                    self.dropped_items[zone_key][pos][item_name] = (
                                        self.dropped_items[zone_key][pos].get(item_name, 0) + count
                                    )
                            self.chest_contents.pop(chest_key, None)
                            bg = getattr(self, 'chest_backgrounds', {}).pop(chest_key, None)
                            screen['grid'][y][x] = bg if bg else base_cell
                    else:
                        bg = getattr(self, 'chest_backgrounds', {}).pop(chest_key, None)
                        screen['grid'][y][x] = bg if bg else base_cell
                        self.chest_contents.pop(chest_key, None)
                    continue
                if cell == 'EMPTY_CRATE':
                    chest_key = f"{zone_key}:{x},{y}"
                    contents = self.chest_contents.get(chest_key, {})
                    if any(v > 0 for v in contents.values()):
                        screen['grid'][y][x] = 'CHEST'
                    continue

                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]

                    if 'grows_to' in cell_info and random.random() < min(1.0, cell_info.get('growth_rate', 0) * _tp):
                        self.set_grid_cell(screen, x, y, cell_info['grows_to'])
                    elif cell == 'WELL' and _biome == 'DESERT' and random.random() < min(1.0, 0.00002 * _tp):
                        self.set_grid_cell(screen, x, y, 'DESERT_WELL')
                    elif 'degrades_to' in cell_info:
                        _base_rate = cell_info.get('degrade_rate', 0)
                        _decay_target = cell_info['degrades_to']

                        # Carrots decay faster on hostile terrain (cobblestone/sand)
                        if cell in ('CARROT1', 'CARROT2', 'CARROT3'):
                            _has_cob = _has_sand = False
                            for _nx, _ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                                if 0 <= _nx < GRID_WIDTH and 0 <= _ny < GRID_HEIGHT:
                                    _nc = screen['grid'][_ny][_nx]
                                    if _nc == 'COBBLESTONE':
                                        _has_cob = True
                                    elif _nc == 'SAND':
                                        _has_sand = True
                            if _has_cob:
                                _base_rate *= 50.0
                            elif _has_sand:
                                _base_rate *= 10.0
                                if cell == 'CARROT1':
                                    _decay_target = 'DIRT'

                        if random.random() < min(1.0, _base_rate * _tp * _decay_factor):
                            if cell == 'COBBLESTONE':
                                center_x = GRID_WIDTH // 2
                                center_y = GRID_HEIGHT // 2
                                if abs(y - center_y) <= 2 or abs(x - center_x) <= 2:
                                    continue
                                skip = False
                                for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                                        if screen['grid'][ny][nx] in ('HOUSE', 'CAMP', 'CAVE', 'MINESHAFT'):
                                            skip = True
                                            break
                                if skip:
                                    continue

                            old_cell = cell
                            self.set_grid_cell(screen, x, y, _decay_target)

                            if old_cell == 'HOUSE':
                                self.process_house_destruction(x, y, zone_key)

        # Desert rock/ore formation — SAND slowly solidifies into STONE;
        # existing STONE rarely yields IRON_ORE
        if screen.get('biome') == 'DESERT':
            for y in range(1, GRID_HEIGHT - 1):
                for x in range(1, GRID_WIDTH - 1):
                    cell = screen['grid'][y][x]
                    if cell == 'SAND' and random.random() < min(1.0, DESERT_ROCK_FORMATION_RATE * _tp):
                        self.set_grid_cell(screen, x, y, 'STONE')
                    elif cell == 'STONE' and random.random() < min(1.0, DESERT_ORE_FORMATION_RATE * _tp):
                        self.set_grid_cell(screen, x, y, 'IRON_ORE')

        # === BIOME REVERSION & SPREADING ===
        biome = screen.get('biome', 'FOREST')
        biome_base_map = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
        }
        base_cell = biome_base_map.get(biome, 'GRASS')

        _flower_patterns = {'FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3'}
        biome_native = {
            'FOREST': {'GRASS', 'DIRT', 'TREE1', 'TREE2', 'FLOWER', 'BUSH'} | _flower_patterns,
            'PLAINS': {'GRASS', 'DIRT', 'FLOWER', 'BUSH'} | _flower_patterns,
            'DESERT': {'SAND', 'DIRT', 'BUSH'},
            'MOUNTAINS': {'DIRT', 'STONE', 'GRASS'},
            'TUNDRA': {'DIRT', 'STONE'},
            'SWAMP': {'DIRT', 'WATER', 'GRASS', 'BUSH'},
        }
        native_cells = biome_native.get(biome, {'GRASS', 'DIRT'})

        protected_cells = {'HOUSE', 'CAVE', 'MINESHAFT', 'CAMP', 'CHEST', 'EMPTY_CRATE', 'WALL',
                           'COBBLESTONE', 'WATER', 'DEEP_WATER',
                           'CAVE_FLOOR', 'CAVE_WALL', 'STAIRS_UP',
                           'STAIRS_DOWN', 'HIDDEN_CAVE', 'SOIL', 'CARROT1', 'CARROT2', 'CARROT3',
                           'CLIFF', 'STONE_HOUSE', 'BUSH', 'GRAVESTONE',
                           # New permanent cells
                           'BROKEN_GRAVESTONE', 'LOCKED_CHEST', 'OPEN_CHEST',
                           'BOOKSHELF', 'WOOD_CHAIR', 'WOOD_TABLE', 'BED_WHITE',
                           'WATER_TROUGH', 'SMALL_POTTED_PLANT', 'BLUE_MUSHROOM',
                           'APPLE_CRATE'}

        foreign_revert = {
            'DESERT': {'GRASS', 'TREE1', 'TREE2', 'FLOWER'},
            'FOREST': {'SAND'},
            'PLAINS': {'SAND'},
            'MOUNTAINS': {'SAND'},
            'TUNDRA': {'SAND', 'GRASS'},
            'SWAMP': {'SAND'},
        }
        revert_targets = foreign_revert.get(biome, set())

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]

                # Trees decay especially fast in desert
                if biome == 'DESERT' and cell in ('TREE1', 'TREE2'):
                    if random.random() < 0.08:
                        screen['grid'][y][x] = base_cell
                    continue

                if cell in revert_targets:
                    # Count how many cardinal neighbours are native to this biome.
                    # More native neighbours → faster revert (cell is stranded/surrounded).
                    _native_adj = sum(
                        1 for ddx, ddy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + ddx < GRID_WIDTH and 0 <= y + ddy < GRID_HEIGHT
                        and screen['grid'][y + ddy][x + ddx] in native_cells
                    )
                    if _native_adj >= 3:
                        _revert_r = 0.12   # Deep in foreign territory — revert quickly
                    elif _native_adj == 2:
                        _revert_r = 0.035
                    else:
                        _revert_r = 0.003  # Edge cell — slow revert (biome boundary)
                    # Rain washes sand away quickly in non-desert biomes
                    if cell == 'SAND' and biome != 'DESERT' and _zone_is_raining:
                        _revert_r = max(_revert_r, 0.08)
                    if random.random() < _revert_r:
                        screen['grid'][y][x] = base_cell
                    continue

                # Revert stray interior/placeable cells that shouldn't appear in overworld
                if cell in ('WOOD', 'PLANKS', 'FLOOR_WOOD') and random.random() < 0.1:
                    screen['grid'][y][x] = base_cell
                    continue

                if cell in native_cells and random.random() < 0.005:
                    dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                        neighbor = screen['grid'][ny][nx]
                        if neighbor not in protected_cells and neighbor not in native_cells:
                            screen['grid'][ny][nx] = cell

        # Very sparse bush growth; rarer than trees, rarest in desert scrub
        if biome in ('FOREST', 'PLAINS', 'SWAMP'):
            for y in range(1, GRID_HEIGHT - 1):
                for x in range(1, GRID_WIDTH - 1):
                    if screen['grid'][y][x] == 'GRASS' and random.random() < min(1.0, 0.000005 * _tp):
                        self.set_grid_cell(screen, x, y, 'BUSH')
        elif biome == 'DESERT':
            for y in range(1, GRID_HEIGHT - 1):
                for x in range(1, GRID_WIDTH - 1):
                    if screen['grid'][y][x] == 'SAND' and random.random() < min(1.0, 0.0000008 * _tp):
                        self.set_grid_cell(screen, x, y, 'BUSH')

        # Rare flower pattern growth from grass (forest/plains only)
        if biome in ('FOREST', 'PLAINS'):
            _fp_variants = ('FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3')
            for y in range(1, GRID_HEIGHT - 1):
                for x in range(1, GRID_WIDTH - 1):
                    if screen['grid'][y][x] == 'GRASS' and random.random() < min(1.0, 0.000008 * _tp):
                        self.set_grid_cell(screen, x, y, random.choice(_fp_variants))

        # === ENTITY UPDATES ===
        if getattr(self, 'autopilot', False) and zone_key in self.screen_entities:
            for eid in self.screen_entities[zone_key]:
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False
            self.inspected_npc = None

        # Extra decay passes for distant zones: 1 extra per 4 zones beyond dist 8, cap 4
        _extra_decay = max(0, min(4, (_dist_from_player - 8) // 4)) if _dist_from_player > 8 else 0

        # Extra decay from zone overcrowding: 1 extra per 4 entities above 8, cap 3
        _zone_pop = sum(
            1 for eid in self.screen_entities.get(zone_key, [])
            if eid in self.entities and self.entities[eid].is_alive()
        )
        _pop_extra = max(0, min(3, (_zone_pop - 8) // 4)) if _zone_pop > 8 else 0

        if zone_key in self.screen_entities:
            entities_to_remove = []

            for entity_id in list(self.screen_entities[zone_key]):
                if entity_id not in self.entities:
                    continue

                entity = self.entities[entity_id]

                # Faction assignment for warriors
                if self.tick % 300 == 0 and entity.type == 'WARRIOR' and not entity.faction:
                    self.assign_warrior_faction(entity, zone_key)

                # Chance for warrior/commander to defect (0.1% per update, requires 3+ warriors)
                if entity.type in ['WARRIOR', 'COMMANDER'] and entity.faction:
                    warrior_count = sum(1 for eid in self.screen_entities.get(zone_key, [])
                                        if eid in self.entities and self.entities[eid].type in ['WARRIOR', 'COMMANDER', 'KING'])

                    if warrior_count >= 3 and random.random() < 0.001:
                        available_factions = [f for f in self.factions.keys() if f != entity.faction]
                        if available_factions:
                            old_faction = entity.faction
                            new_faction = random.choice(available_factions)

                            if old_faction in self.factions and entity_id in self.factions[old_faction]['warriors']:
                                self.factions[old_faction]['warriors'].remove(entity_id)

                            entity.faction = new_faction
                            if new_faction not in self.factions:
                                self.factions[new_faction] = {'warriors': [], 'zones': set()}
                            if entity_id not in self.factions[new_faction]['warriors']:
                                self.factions[new_faction]['warriors'].append(entity_id)


                # Age entities every 600 ticks (accelerated during time pass)
                age_interval = max(1, int(600 / _tp))
                if self.tick % age_interval == 0 and entity.type != 'SKELETON':
                    entity.age += 1

                entity.decay_stats()
                for _ in range(_extra_decay + _pop_extra):
                    entity.decay_stats()

                # NPC item consumption: remove full stack of a random item
                if random.random() < 0.25 and entity.inventory:
                    item = random.choice(list(entity.inventory.keys()))
                    count = entity.inventory.pop(item)
                    if item in ('meat', 'carrot', 'cooked_meat', 'stew', 'bones'):
                        if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 60:
                            entity.health = min(entity.max_health, entity.health + 5 * min(count, 10))

                # Skeletons burn in daylight
                if entity.type == 'SKELETON' and not self.is_night:
                    entity.health -= SKELETON_DAYLIGHT_DAMAGE
                    if entity.health <= 0:
                        entity.health = 0
                        entity.killed_by = 'sunlight'

                # Healing boost near camp/house
                heal_boost = 1.0
                if not entity.props.get('hostile', False):
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            check_x = entity.x + dx
                            check_y = entity.y + dy
                            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                cell = screen['grid'][check_y][check_x]
                                if cell == 'CAMP':
                                    heal_boost = CAMP_HEALING_MULTIPLIER
                                    break
                                elif cell == 'HOUSE':
                                    heal_boost = HOUSE_HEALING_MULTIPLIER
                                    break
                        if heal_boost > 1.0:
                            break

                # Regen health only if not recently attacked (120 ticks = ~2s)
                if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 60:
                    entity.regenerate_health(heal_boost)

                # Energy regen: idle = +2/tick, stationary = +1/tick, moving = no regen
                if hasattr(entity, 'energy') and entity.energy < entity.max_energy:
                    if entity.ai_state == 'idle':
                        entity.energy = min(entity.max_energy, entity.energy + 2)
                    elif not entity.is_moving:
                        entity.energy = min(entity.max_energy, entity.energy + 1)

                if not entity.is_alive():
                    entities_to_remove.append(entity_id)
                    continue

                self.update_entity_ai(entity_id, entity)

                # Butterfly grows flowers as it passes over grass/dirt
                if entity.type == 'BUTTERFLY' and random.random() < 0.04:
                    bx, by = entity.x, entity.y
                    if 0 <= bx < GRID_WIDTH and 0 <= by < GRID_HEIGHT:
                        _btfly_cell = screen['grid'][by][bx]
                        if _btfly_cell == 'GRASS':
                            screen['grid'][by][bx] = random.choice(
                                ('FLOWER', 'FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3'))
                        elif _btfly_cell == 'DIRT':
                            screen['grid'][by][bx] = random.choice(
                                ('GRASS', 'FLOWER', 'FLOWER_PATTERN1'))

            for entity_id in entities_to_remove:
                self.remove_entity(entity_id)

            # Entity-item interactions (every second)
            if zone_key in self.screens and self.tick % 60 == 0:
                grid = self.screens[zone_key]['grid']
                for entity_id in list(self.screen_entities.get(zone_key, [])):
                    if entity_id not in self.entities:
                        continue
                    entity = self.entities[entity_id]
                    if not entity.is_alive():
                        continue

                    ex, ey = entity.x, entity.y

                    # Pick up dropped items at entity position and adjacent cells
                    if zone_key in self.dropped_items:
                        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                            px, py = ex + dx, ey + dy
                            cell_key = (px, py)
                            if cell_key in self.dropped_items[zone_key]:
                                for item_name, count in self.dropped_items[zone_key][cell_key].items():
                                    entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                                del self.dropped_items[zone_key][cell_key]

                    # Pick up from adjacent chest — hostile entities only
                    if entity.props.get('hostile', False):
                        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                            cx, cy = ex + dx, ey + dy
                            if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                                if grid[cy][cx] == 'CHEST':
                                    chest_key = f"{zone_key}:{cx},{cy}"
                                    if chest_key in self.chest_contents:
                                        contents = self.chest_contents[chest_key]
                                        for item_name, count in contents.items():
                                            entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                                        self.chest_contents[chest_key] = {}
                                    break

                    # Fill a nearby existing chest when any item stack exceeds 100
                    _inv_overflow = any(c > 20 for c in entity.inventory.values())
                    if _inv_overflow and random.random() < 0.70:
                        for dx, dy in [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]:
                            cx, cy = ex + dx, ey + dy
                            if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                                if grid[cy][cx] == 'CHEST':
                                    chest_key = f"{zone_key}:{cx},{cy}"
                                    if chest_key not in self.chest_contents:
                                        self.chest_contents[chest_key] = {}
                                    for item_name, count in list(entity.inventory.items()):
                                        self.chest_contents[chest_key][item_name] = (
                                            self.chest_contents[chest_key].get(item_name, 0) + count
                                        )
                                    entity.inventory.clear()
                                    break

                    # Place a new chest only if no chest within 5 cells
                    _inv_overflow = any(c > 20 for c in entity.inventory.values())
                    if _inv_overflow and random.random() < 0.60:
                        _chest_nearby = any(
                            grid[ny][nx] == 'CHEST'
                            for nx in range(max(0, ex - 5), min(GRID_WIDTH, ex + 6))
                            for ny in range(max(0, ey - 5), min(GRID_HEIGHT, ey + 6))
                        )
                        if not _chest_nearby:
                            ground_cells = {'GRASS', 'DIRT', 'SAND', 'FLOOR_WOOD', 'CAVE_FLOOR', 'COBBLESTONE'}
                            for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                                cx, cy = ex + dx, ey + dy
                                if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                                    cell = grid[cy][cx]
                                    if cell in ground_cells:
                                        grid[cy][cx] = 'CHEST'
                                        chest_key = f"{zone_key}:{cx},{cy}"
                                        self.chest_contents[chest_key] = dict(entity.inventory)
                                        entity.inventory.clear()
                                        break

        # Entity consolidation: when >2 of same base type, merge pairs into _double
        if zone_key in self.screen_entities and self.tick % 300 == 0:
            type_counts = {}
            for eid in list(self.screen_entities.get(zone_key, [])):
                if eid not in self.entities:
                    continue
                e = self.entities[eid]
                if not e.is_alive() or e.props.get('is_autopilot_proxy'):
                    continue
                base = e.type.replace('_double', '')
                if base not in type_counts:
                    type_counts[base] = []
                type_counts[base].append(eid)

            for base_type, eids in type_counts.items():
                singles = [eid for eid in eids if self.entities[eid].type == base_type]
                if len(singles) > 2:
                    singles.sort(key=lambda eid: self.entities[eid].level, reverse=True)
                    while len(singles) > 2:
                        if len(singles) < 2:
                            break
                        keep_id = singles.pop(0)
                        remove_id = singles.pop(0)
                        keeper = self.entities[keep_id]
                        removed = self.entities[remove_id]
                        keeper.type = f"{base_type}_double"
                        keeper.max_health = int(keeper.max_health * 1.5)
                        keeper.health = min(keeper.health + removed.health, keeper.max_health)
                        keeper.strength = int(keeper.strength * 1.3)
                        for item, count in removed.inventory.items():
                            keeper.inventory[item] = keeper.inventory.get(item, 0) + count
                        self.remove_entity(remove_id)

        # Zone-wide faction revolution (0.05% chance, requires 3+ warriors)
        if zone_key in self.screen_entities and random.random() < 0.0005:
            warriors_in_zone = [
                (eid, self.entities[eid]) for eid in self.screen_entities[zone_key]
                if eid in self.entities and self.entities[eid].type == 'WARRIOR'
                and self.entities[eid].faction
            ]

            if len(warriors_in_zone) >= 3:
                new_faction = self.generate_faction_name()
                for warrior_id, warrior in warriors_in_zone:
                    old_faction = warrior.faction
                    if old_faction in self.factions and warrior_id in self.factions[old_faction]['warriors']:
                        self.factions[old_faction]['warriors'].remove(warrior_id)
                    warrior.faction = new_faction
                    if new_faction not in self.factions:
                        self.factions[new_faction] = {'warriors': [], 'zones': set()}
                    if warrior_id not in self.factions[new_faction]['warriors']:
                        self.factions[new_faction]['warriors'].append(warrior_id)

        # Faction raid: 0.1% chance for raid on high-population zones
        if zone_key in self.screen_entities and random.random() < 0.001:
            total_warriors = sum(len(f.get('warriors', [])) for f in self.factions.values())

            if total_warriors >= 3:
                human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR']
                human_count = sum(
                    1 for eid in self.screen_entities[zone_key]
                    if eid in self.entities
                    and self.entities[eid].type.replace('_double', '') in human_npc_types
                )

                if human_count >= 8 and self.factions:
                    raiding_faction = random.choice(list(self.factions.keys()))
                    raiders_spawned = 0

                    for _ in range(3):
                        spawn_x = random.randint(3, GRID_WIDTH - 4)
                        spawn_y = random.randint(3, GRID_HEIGHT - 4)

                        if zone_key in self.screens:
                            if not CELL_TYPES[screen['grid'][spawn_y][spawn_x]].get('solid', False):
                                warrior = Entity('WARRIOR', spawn_x, spawn_y, zone_x, zone_y,
                                                 level=random.randint(2, 4))
                                warrior.faction = raiding_faction
                                warrior.home_zone = None

                                warrior_id = self.next_entity_id
                                self.next_entity_id += 1
                                self.entities[warrior_id] = warrior
                                self.screen_entities[zone_key].append(warrior_id)

                                if raiding_faction not in self.factions:
                                    self.factions[raiding_faction] = {'warriors': [], 'zones': set()}
                                if warrior_id not in self.factions[raiding_faction]['warriors']:
                                    self.factions[raiding_faction]['warriors'].append(warrior_id)

                                raiders_spawned += 1

                    if raiders_spawned > 0:
                        pass  # raid initiated

        # Population maintenance (every 5 seconds)
        if not hasattr(self, 'zone_last_spawn_check'):
            self.zone_last_spawn_check = {}

        npc_count = 0
        types_in_zone = set()
        if zone_key in self.screen_entities:
            for entity_id in self.screen_entities[zone_key]:
                if entity_id in self.entities:
                    npc_count += 1
                    types_in_zone.add(self.entities[entity_id].type)

        if zone_key not in self.zone_last_spawn_check:
            self.zone_last_spawn_check[zone_key] = 0

        if self.tick - self.zone_last_spawn_check[zone_key] >= 300:
            self.zone_last_spawn_check[zone_key] = self.tick

            if npc_count == 0:
                spawn_chance = 0.8
            elif npc_count < 3:
                spawn_chance = 0.4
            elif npc_count < 5:
                spawn_chance = 0.2
            else:
                spawn_chance = 0.05

            # Reduce spawn rate for distant zones: -3% per zone of distance, floor 0
            _spawn_dist = abs(zone_x - self.player['screen_x']) + abs(zone_y - self.player['screen_y'])
            spawn_chance *= max(0.0, 1.0 - _spawn_dist * 0.03)

            if random.random() < spawn_chance:
                biome = screen.get('biome', 'FOREST')
                spawned = False
                if 'TRADER' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='TRADER')
                elif 'GUARD' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='GUARD')
                elif 'WARRIOR' not in types_in_zone and random.random() < 0.5:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='WARRIOR')

                if not spawned:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome)

            # NPC role conversion / settlement
            if zone_key in self.screen_entities:
                has_farmer = has_lumberjack = has_miner = False
                traders = []
                guards = []

                for entity_id in self.screen_entities[zone_key]:
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        if entity.type == 'FARMER':
                            has_farmer = True
                        elif entity.type == 'LUMBERJACK':
                            has_lumberjack = True
                        elif entity.type == 'MINER':
                            has_miner = True
                        elif entity.type in ('TRADER', 'TRADER_double'):
                            traders.append((entity_id, entity))
                        elif entity.type in ('GUARD', 'GUARD_double'):
                            guards.append((entity_id, entity))

                missing_roles = not has_farmer or not has_lumberjack or not has_miner
                settlement_rate = ENHANCED_SETTLEMENT_RATE if missing_roles else 0.05

                if random.random() < settlement_rate:
                    if len(traders) > 2:
                        t1_id, t1 = traders[0]
                        t2_id, t2 = traders[1]
                        if t1.can_merge_with(t2):
                            t1.merge_with(t2)
                            del self.entities[t2_id]

                    if len(guards) > 2:
                        g1_id, g1 = guards[0]
                        g2_id, g2 = guards[1]
                        if g1.can_merge_with(g2):
                            g1.merge_with(g2)
                            del self.entities[g2_id]

                    if traders:
                        trader_id, trader = random.choice(traders)
                        new_trader_type = None
                        if not has_farmer and random.random() < 0.5:
                            new_trader_type = 'FARMER'
                        elif not has_lumberjack and random.random() < 0.5:
                            new_trader_type = 'LUMBERJACK'
                        elif not has_miner:
                            new_trader_type = 'MINER'
                        if new_trader_type:
                            trader.type = new_trader_type
                            trader.props = ENTITY_TYPES[new_trader_type]
                            if hasattr(trader, 'quest_queue'):
                                del trader.quest_queue
                            trader.quest_focus = None
                            trader.quest_target = None

                    if guards:
                        guard_id, guard = random.choice(guards)
                        new_guard_type = None
                        if not has_farmer and random.random() < 0.5:
                            new_guard_type = 'FARMER'
                        elif not has_miner and random.random() < 0.5:
                            new_guard_type = 'MINER'
                        if new_guard_type:
                            guard.type = new_guard_type
                            guard.props = ENTITY_TYPES[new_guard_type]
                            if hasattr(guard, 'quest_queue'):
                                del guard.quest_queue
                            guard.quest_focus = None
                            guard.quest_target = None

            if self.tick % 600 == 0:
                self.promote_to_commander(zone_key)
                self.promote_to_king()
                self.recruit_to_hostile_faction(zone_key)

        # Prune empty distant zones: no alive entities, no structures, no items → delete.
        if _dist_from_player > 4:
            _has_alive = any(
                eid in self.entities and self.entities[eid].health > 0
                for eid in self.screen_entities.get(zone_key, [])
            )
            if not _has_alive:
                _struct_cells = {'HOUSE', 'STONE_HOUSE', 'CAVE', 'MINESHAFT',
                                 'CHEST', 'BARREL', 'CAMP', 'WELL', 'FORGE'}
                _has_structures = any(
                    cell in _struct_cells
                    for row in screen['grid']
                    for cell in row
                )
                if not _has_structures:
                    _has_drops = any(self.dropped_items.get(zone_key, {}).values())
                    _has_buried = any(getattr(self, 'buried_items', {}).get(zone_key, {}).values())
                    if not _has_drops and not _has_buried:
                        self._purge_zone(zone_key)

    def update_structure_zone(self, struct_zone_key, cell_coverage, entity_coverage):
        """Update a structure zone (cave/house interior) like a regular zone."""
        if struct_zone_key not in self.screens:
            return

        screen = self.screens[struct_zone_key]
        self.screen_last_update[struct_zone_key] = self.tick

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                if self.is_cell_enchanted(x, y, struct_zone_key):
                    continue
                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]
                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['grows_to'])
                    elif 'degrades_to' in cell_info and random.random() < cell_info.get('degrade_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['degrades_to'])
        self.check_raid_event(struct_zone_key)

        entity_list = self.screen_entities.get(struct_zone_key, [])

        if getattr(self, 'autopilot', False):
            for eid in list(entity_list):
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False

        _tp = getattr(self, 'time_pass_speed', 1.0)
        _age_interval = max(1, int(600 / _tp))

        # Overcrowding: compute once per cycle — extra decay passes if structure is packed
        _live_pop = sum(
            1 for eid in entity_list
            if eid in self.entities and self.entities[eid].is_alive()
        )
        _overcrowd_extra = max(0, min(4, (_live_pop - 3) // 2)) if _live_pop > 3 else 0

        # Healing multiplier depends on structure type
        _structure_type = screen.get('type', '')
        _heal_boost = HOUSE_HEALING_MULTIPLIER if _structure_type == 'HOUSE_INTERIOR' else 1.0

        entities_to_remove = []
        for entity_id in list(entity_list):
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]

            # Age increment (mirrors overworld logic)
            if self.tick % _age_interval == 0 and entity.type != 'SKELETON':
                entity.age += 1

            # Hunger/thirst decay — plus extra passes when structure is overcrowded
            entity.decay_stats()
            for _ in range(_overcrowd_extra):
                entity.decay_stats()

            # Item consumption — same rate as overworld
            if random.random() < 0.25 and entity.inventory:
                _item = random.choice(list(entity.inventory.keys()))
                _count = entity.inventory.pop(_item)
                if _item in ('meat', 'carrot', 'cooked_meat', 'stew', 'bones'):
                    if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 60:
                        entity.health = min(entity.max_health, entity.health + 5 * min(_count, 10))

            # Health regen — only when not recently attacked; house boost for peaceful NPCs
            if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 60:
                _boost = _heal_boost if not entity.props.get('hostile', False) else 1.0
                entity.regenerate_health(_boost)

            # Energy regen — mirrors overworld
            if hasattr(entity, 'energy') and entity.energy < entity.max_energy:
                if entity.ai_state == 'idle':
                    entity.energy = min(entity.max_energy, entity.energy + 2)
                elif not entity.is_moving:
                    entity.energy = min(entity.max_energy, entity.energy + 1)

            if not entity.is_alive():
                entities_to_remove.append(entity_id)
                continue

            self.update_entity_ai(entity_id, entity)

        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)

        self.assign_zone_keepers(struct_zone_key)

    # -------------------------------------------------------------------------
    # Catch-up system
    # -------------------------------------------------------------------------

    def catch_up_entities(self, screen_x, screen_y, cycles):
        """Simplified entity simulation for catch-up with eating, drinking, and healing"""
        screen_key = f"{screen_x},{screen_y}"
        if screen_key not in self.screen_entities or screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Simplified raid simulation for high-population zones
        if cycles > 20:
            human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR', 'WIZARD']
            human_count = sum(
                1 for eid in self.screen_entities[screen_key]
                if eid in self.entities
                and self.entities[eid].type.replace('_double', '') in human_npc_types
            )

            if human_count >= 7:
                has_cave = any(
                    screen['grid'][y][x] in ['CAVE', 'HIDDEN_CAVE', 'MINESHAFT']
                    for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
                )

                if random.random() < 0.20:
                    hostile_count = random.randint(2, max(2, human_count))
                    hostile_type = random.choice(['GOBLIN', 'BANDIT', 'WOLF', 'BLACK_SPIDER', 'SKELETON', 'TERMITE'])

                    # Build entrance positions: zone edges + adjacent to cave/mineshaft cells
                    _cx = GRID_WIDTH // 2
                    _cy = GRID_HEIGHT // 2
                    _raid_positions = []
                    if screen['exits'].get('top'):
                        _raid_positions += [(x, 1) for x in range(_cx - 1, _cx + 2)]
                    if screen['exits'].get('bottom'):
                        _raid_positions += [(x, GRID_HEIGHT - 2) for x in range(_cx - 1, _cx + 2)]
                    if screen['exits'].get('left'):
                        _raid_positions += [(1, y) for y in range(_cy - 1, _cy + 2)]
                    if screen['exits'].get('right'):
                        _raid_positions += [(GRID_WIDTH - 2, y) for y in range(_cy - 1, _cy + 2)]
                    # Also allow spawning adjacent to cave/mineshaft entrances
                    for _gy in range(GRID_HEIGHT):
                        for _gx in range(GRID_WIDTH):
                            if screen['grid'][_gy][_gx] in ('CAVE', 'HIDDEN_CAVE'):
                                for _dx, _dy in ((-1,0),(1,0),(0,-1),(0,1)):
                                    _nx, _ny = _gx + _dx, _gy + _dy
                                    if 0 < _nx < GRID_WIDTH - 1 and 0 < _ny < GRID_HEIGHT - 1:
                                        _raid_positions.append((_nx, _ny))
                    if not _raid_positions:
                        _raid_positions = [(_cx, _cy)]

                    for _ in range(hostile_count):
                        for _attempt in range(15):
                            spawn_x, spawn_y = random.choice(_raid_positions)
                            if not CELL_TYPES[screen['grid'][spawn_y][spawn_x]].get('solid', False):
                                entity = Entity(hostile_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
                                entity_id = self.next_entity_id
                                self.next_entity_id += 1
                                self.entities[entity_id] = entity
                                self.screen_entities[screen_key].append(entity_id)
                                break

                    # Kill a low-level NPC (simulate raid casualty)
                    lowest_entity = None
                    lowest_level = 999
                    for entity_id in self.screen_entities[screen_key]:
                        if entity_id in self.entities:
                            entity = self.entities[entity_id]
                            if entity.type in human_npc_types and entity.level < lowest_level:
                                lowest_entity = entity_id
                                lowest_level = entity.level
                    if lowest_entity:
                        self.remove_entity(lowest_entity)

                    if not has_cave:
                        self.spawn_hidden_cave(screen_key)


        # Faction simulation for warriors during catch-up
        if cycles > 10:
            warriors_in_zone = [
                (eid, self.entities[eid]) for eid in self.screen_entities[screen_key]
                if eid in self.entities and self.entities[eid].type == 'WARRIOR'
            ]

            for warrior_id, warrior in warriors_in_zone:
                if not warrior.faction:
                    self.assign_warrior_faction(warrior, screen_key)

            if len(warriors_in_zone) >= 2:
                faction_groups = {}
                for warrior_id, warrior in warriors_in_zone:
                    if warrior.faction:
                        if warrior.faction not in faction_groups:
                            faction_groups[warrior.faction] = []
                        faction_groups[warrior.faction].append((warrior_id, warrior))

                if len(faction_groups) >= 2 and random.random() < 0.1:
                    factions = list(faction_groups.keys())
                    faction1, faction2 = factions[0], factions[1]
                    if len(faction_groups[faction1]) < len(faction_groups[faction2]):
                        casualty_id, casualty = random.choice(faction_groups[faction1])
                    else:
                        casualty_id, casualty = random.choice(faction_groups[faction2])
                    self.remove_entity(casualty_id)

        entities_to_remove = []
        entities_to_transition = []

        for entity_id in self.screen_entities[screen_key][:]:
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]

            peaceful_humans = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'WIZARD']
            can_travel = entity.type not in peaceful_humans

            if can_travel and cycles > 10:
                transition_chance = min(cycles * 0.005, 0.3)
                if random.random() < transition_chance:
                    entities_to_transition.append(entity_id)
                    continue

            food_sources = entity.props.get('food_sources', [])
            water_sources = entity.props.get('water_sources', [])

            has_food = False
            has_water = False

            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    cell = screen['grid'][y][x]
                    if cell in food_sources:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist <= 5:
                            has_food = True
                    if cell in water_sources:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist <= 5:
                            has_water = True

            for cycle_num in range(cycles):
                if not getattr(entity, 'keeper', False):
                    entity.hunger = max(0, entity.hunger - 0.5)
                    entity.thirst = max(0, entity.thirst - 0.3)

                if cycle_num % 2 == 0:
                    behavior_config = entity.props.get('behavior_config')
                    if behavior_config:
                        self.execute_entity_behavior(entity, behavior_config)
                    elif entity.type in ['GOBLIN', 'BANDIT', 'TERMITE']:
                        self.hostile_structure_behavior(entity)

                    if behavior_config and behavior_config.get('can_place_camp'):
                        if random.random() < NPC_CAMP_PLACE_RATE:
                            self.npc_place_camp(entity)
                    if entity.type in ['FARMER', 'TRADER', 'BANDIT', 'GUARD', 'LUMBERJACK', 'WIZARD']:
                        if random.random() < 0.01:
                            self.npc_place_camp(entity)

                    if entity.type == 'MINER':
                        # Higher priority: mine existing caves into mineshafts
                        if not self.miner_mine_cave(entity):
                            # No cave to mine — excavate a new mineshaft
                            if random.random() < NPC_CAMP_PLACE_RATE:
                                self.miner_place_mineshaft(entity)

                if entity.hunger < 80 and has_food:
                    if random.random() < 0.6:
                        food_value = 30
                        for food in food_sources:
                            if food.startswith('CARROT'):
                                food_value = 40
                                break
                            elif food == 'GRASS':
                                food_value = 20
                        entity.eat(food_value)

                if entity.thirst < 80 and has_water:
                    if random.random() < 0.6:
                        entity.drink(40)

                heal_boost = 1.0
                if not entity.props.get('hostile', False):
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            check_x = entity.x + dx
                            check_y = entity.y + dy
                            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                cell = screen['grid'][check_y][check_x]
                                if cell == 'CAMP':
                                    heal_boost = 2.0
                                    break
                                elif cell == 'HOUSE':
                                    heal_boost = 3.0
                                    break
                        if heal_boost > 1.0:
                            break

                if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 60:
                    entity.regenerate_health(heal_boost)

                if entity.hunger <= 0:
                    entity.health -= 1
                if entity.thirst <= 0:
                    entity.health -= 2

            if entity.health <= 0:
                entities_to_remove.append(entity_id)
                continue

        for entity_id in entities_to_transition:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                dx, dy = random.choice(directions)

                new_screen_x = screen_x + dx
                new_screen_y = screen_y + dy
                new_screen_key = f"{new_screen_x},{new_screen_y}"

                if new_screen_key not in self.screens:
                    self.generate_screen(new_screen_x, new_screen_y)

                if dx == -1:
                    new_x = GRID_WIDTH - 4
                    new_y = random.randint(2, GRID_HEIGHT - 3)
                elif dx == 1:
                    new_x = 3
                    new_y = random.randint(2, GRID_HEIGHT - 3)
                elif dy == -1:
                    new_x = random.randint(2, GRID_WIDTH - 3)
                    new_y = GRID_HEIGHT - 4
                else:
                    new_x = random.randint(2, GRID_WIDTH - 3)
                    new_y = 3

                if new_screen_key in self.screens:
                    target_screen = self.screens[new_screen_key]
                    if not CELL_TYPES[target_screen['grid'][new_y][new_x]].get('solid', False):
                        if screen_key in self.screen_entities and entity_id in self.screen_entities[screen_key]:
                            self.screen_entities[screen_key].remove(entity_id)

                        entity.screen_x = new_screen_x
                        entity.screen_y = new_screen_y
                        entity.x = new_x
                        entity.y = new_y

                        if new_screen_key not in self.screen_entities:
                            self.screen_entities[new_screen_key] = []
                        self.screen_entities[new_screen_key].append(entity_id)

        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)

    def catch_up_screen(self, screen_x, screen_y, cycles_missed):
        """Apply catch-up updates efficiently"""
        from world.cells import CA_RULES_ENABLED
        if not CA_RULES_ENABLED:
            return
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        cycles_missed = min(cycles_missed, MAX_CYCLES_TO_SIMULATE)

        # Tier 1: Recent — run normally
        if cycles_missed < 5:
            for _ in range(cycles_missed):
                self.apply_cellular_automata(screen_x, screen_y)
            self.screen_last_update[key] = self.tick
            return

        # Tier 2 & 3: Use bulk updates
        screen = self.screens[key]
        biome = screen.get('biome', 'FOREST')

        neighbor_cache = {}
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                neighbors = self.get_neighbors(x, y, key)
                neighbor_cache[(x, y)] = {
                    'water': self.count_cell_type(neighbors, 'WATER'),
                    'deep_water': self.count_cell_type(neighbors, 'DEEP_WATER'),
                    'dirt': self.count_cell_type(neighbors, 'DIRT'),
                    'grass': self.count_cell_type(neighbors, 'GRASS'),
                    'tree': self.count_cell_type(neighbors, 'TREE'),
                    'sand': self.count_cell_type(neighbors, 'SAND'),
                    'flower': self.count_cell_type(neighbors, 'FLOWER')
                }

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]

                if cell in ['WALL', 'HOUSE', 'CAVE', 'CLIFF']:
                    continue

                counts = neighbor_cache.get((x, y), {})
                total_water = counts.get('water', 0) + counts.get('deep_water', 0)

                change_prob = 0
                new_cell = cell

                if cell == 'DIRT' and total_water >= 2:
                    change_prob = min(cycles_missed * 0.03, 0.8)
                    new_cell = 'GRASS'
                elif cell == 'GRASS' and total_water == 0 and counts.get('dirt', 0) >= 2:
                    change_prob = min(cycles_missed * 0.02, 0.7)
                    new_cell = 'DIRT'
                elif cell == 'GRASS' and 1 <= counts.get('tree', 0) <= 2 and total_water >= 1:
                    change_prob = min(cycles_missed * 0.01, 0.5)
                    new_cell = 'TREE1'
                elif cell == 'DIRT' and total_water == 0 and counts.get('sand', 0) >= 2 and biome != 'DESERT':
                    change_prob = min(cycles_missed * 0.02, 0.7)
                    new_cell = 'SAND'
                elif cell == 'WATER' and counts.get('water', 0) >= 4:
                    change_prob = min(cycles_missed * 0.05, 0.8)
                    new_cell = 'DEEP_WATER'
                elif cell == 'GRASS' and 1 <= counts.get('flower', 0) <= 2:
                    change_prob = min(cycles_missed * 0.01, 0.3)
                    new_cell = 'FLOWER'

                if random.random() < change_prob:
                    self.set_grid_cell(screen, x, y, new_cell)

        self.consolidate_dropped_items(key)
        self.catch_up_entities(screen_x, screen_y, cycles_missed)
        self.screen_last_update[key] = self.tick

    def on_zone_transition(self, new_screen_x, new_screen_y):
        """When player enters new zone, catch up nearby zones"""
        self.gain_xp(1)
        new_key = f"{new_screen_x},{new_screen_y}"
        if new_key in self.screen_last_update:
            cycles = (self.tick - self.screen_last_update[new_key]) // 60
            if cycles > 0:
                self.catch_up_screen(new_screen_x, new_screen_y, cycles)

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            adj_x, adj_y = new_screen_x + dx, new_screen_y + dy
            adj_key = f"{adj_x},{adj_y}"
            if adj_key in self.screens and adj_key in self.screen_last_update:
                cycles = (self.tick - self.screen_last_update[adj_key]) // 60
                if cycles >= 5:
                    distance = abs(dx) + abs(dy)
                    self.catchup_queue.append((distance, adj_x, adj_y, cycles))

    def process_catchup_queue(self):
        """Process catch-up queue during idle or safe moments"""
        if not self.catchup_queue:
            return

        self.catchup_queue.sort()

        processed = 0
        while self.catchup_queue and processed < MAX_CATCHUP_PER_FRAME:
            priority, sx, sy, cycles = self.catchup_queue.pop(0)
            self.catch_up_screen(sx, sy, min(cycles, MAX_CYCLES_TO_SIMULATE))
            processed += 1

    # -------------------------------------------------------------------------
    # Priority queue system
    # -------------------------------------------------------------------------

    def calculate_zone_priority(self, zone_key):
        """Calculate priority score for a zone. Higher = update sooner.

        All positional scores are expressed as fractions of total_zones so
        the current zone always tops the queue regardless of world size.
        Staleness is uncapped so every zone eventually gets updated.
        """
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']
        player_zone = f"{player_x},{player_y}"
        total_zones = max(1, len(self.screens))

        if self.is_overworld_zone(zone_key):
            parts = zone_key.split(',')
            zone_x, zone_y = int(parts[0]), int(parts[1])
            distance = abs(zone_x - player_x) + abs(zone_y - player_y)
        else:
            if zone_key in self.structure_zones:
                parent = self.structure_zones[zone_key]['parent_zone']
                parts = parent.split(',')
                zone_x, zone_y = int(parts[0]), int(parts[1])
                distance = abs(zone_x - player_x) + abs(zone_y - player_y)
            else:
                distance = 50

        # Distance score as % of total_zones: current zone = 100%, falls off with distance
        if zone_key == player_zone:
            distance_score = total_zones * 1.0
        elif distance == 0:
            distance_score = total_zones * 0.9   # same-coord structure zone
        else:
            distance_score = total_zones * (0.5 / distance)

        # Uncapped staleness — zones that haven't been updated keep climbing
        # until they get processed, guaranteeing rotation across all zones
        last_update = self.screen_last_update.get(zone_key, 0)
        staleness_score = (self.tick - last_update) / 30.0

        # Connection score as % of total_zones
        connection_score = 0.0
        if zone_key in self.zone_connections:
            for connected_key, conn_type, *_ in self.zone_connections[zone_key]:
                if connected_key == player_zone:
                    connection_score = total_zones * 0.4
                    break
                if self.is_overworld_zone(connected_key):
                    cp = connected_key.split(',')
                    cd = abs(int(cp[0]) - player_x) + abs(int(cp[1]) - player_y)
                    if cd <= 1:
                        connection_score = max(connection_score, total_zones * 0.2)

        # Structure and quest scores as % of total_zones
        structure_score = 0.0
        if zone_key in self.structure_zones:
            structure_score = total_zones * 0.15
        elif zone_key in self.zone_structures:
            structure_score = total_zones * 0.05

        quest_score = 0.0
        for quest_type, quest in self.quests.items():
            if hasattr(quest, 'target_zone') and quest.target_zone == zone_key:
                quest_score = total_zones * 0.2
                break

        return distance_score + staleness_score + connection_score + structure_score + quest_score

    def get_priority_sorted_zones(self):
        """Get all zones sorted by priority (highest first).
        Returns list of (priority, zone_key) tuples."""
        zone_priorities = []

        for zone_key in self.instantiated_zones:
            if zone_key in self.screens:
                priority = self.calculate_zone_priority(zone_key)
                zone_priorities.append((priority, zone_key))

        for struct_key in self.structure_zones:
            if struct_key in self.screens:
                priority = self.calculate_zone_priority(struct_key)
                zone_priorities.append((priority, struct_key))

        zone_priorities.sort(reverse=True)
        return zone_priorities

    @staticmethod
    def is_overworld_zone(zone_key):
        """Check if zone key is an overworld zone (format 'x,y') vs structure zone."""
        if ':' in zone_key or zone_key.startswith('struct_'):
            return False
        parts = zone_key.split(',')
        if len(parts) != 2:
            return False
        try:
            x = int(parts[0])
            int(parts[1])
            # Structure zones use virtual coords with x <= -1000
            return x > -500
        except ValueError:
            return False

    # -------------------------------------------------------------------------
    # Zone maintenance helpers
    # -------------------------------------------------------------------------

    def cleanup_screen_entities(self):
        """Remove None and invalid entity_ids from screen_entities"""
        for screen_key in list(self.screen_entities.keys()):
            if screen_key in self.screen_entities:
                self.screen_entities[screen_key] = [
                    eid for eid in self.screen_entities[screen_key]
                    if eid is not None and eid in self.entities
                ]
                if not self.screen_entities[screen_key]:
                    del self.screen_entities[screen_key]

    def ensure_nearby_zones_exist(self):
        """Ensure zones around player are generated"""
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']

        # Structure zones use virtual coords (x <= -1000) — don't generate nearby overworld zones
        if player_x < -500:
            return

        for dx in range(-4, 4):
            for dy in range(-4, 4):
                zone_x = player_x + dx
                zone_y = player_y + dy
                zone_key = f"{zone_x},{zone_y}"

                if zone_key not in self.screens:
                    self.generate_screen(zone_x, zone_y)

                self.instantiated_zones.add(zone_key)

    def check_zone_biome_shift(self, screen_x, screen_y):
        """Check if zone biome should change based on dominant cell types"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        grid = screen['grid']
        current_biome = screen.get('biome', 'FOREST')

        cell_counts = {'GRASS': 0, 'SAND': 0, 'STONE': 0, 'DIRT': 0, 'WATER': 0, 'TREE': 0}
        total_cells = 0

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = grid[y][x]
                total_cells += 1
                if cell == 'GRASS':
                    cell_counts['GRASS'] += 1
                elif cell == 'SAND':
                    cell_counts['SAND'] += 1
                elif cell == 'STONE':
                    cell_counts['STONE'] += 1
                elif cell == 'DIRT':
                    cell_counts['DIRT'] += 1
                elif cell in ['WATER', 'DEEP_WATER']:
                    cell_counts['WATER'] += 1
                elif cell.startswith('TREE'):
                    cell_counts['TREE'] += 1

        grass_pct = cell_counts['GRASS'] / total_cells
        sand_pct = cell_counts['SAND'] / total_cells
        stone_pct = cell_counts['STONE'] / total_cells
        tree_pct = cell_counts['TREE'] / total_cells
        water_pct = cell_counts['WATER'] / total_cells

        new_biome = current_biome
        if water_pct > 0.5:
            new_biome = 'LAKE'
        elif sand_pct > 0.4:
            new_biome = 'DESERT'
        elif stone_pct > 0.3:
            new_biome = 'MOUNTAINS'
        elif grass_pct > 0.5 and tree_pct < 0.05:
            new_biome = 'PLAINS'
        elif grass_pct > 0.3 and tree_pct > 0.1:
            new_biome = 'FOREST'

        if new_biome != current_biome:
            screen['biome'] = new_biome
            screen['biome_domain_id'] = None  # Removed from old domain; will be reassigned
            self.update_biome_domain(key)

    # -------------------------------------------------------------------------
    # Domain management
    # -------------------------------------------------------------------------

    def _new_domain_id(self):
        self._domain_counter += 1
        return self._domain_counter

    def update_biome_domain(self, zone_key):
        """Assign or merge biome domain for zone_key after a biome change.

        Called when a zone's biome shifts. Removes the zone from any prior biome
        domain, checks cardinal neighbors for same-biome zones, and merges or
        creates domains accordingly. Triggers contiguity split check on any domain
        the zone just left.
        """
        if zone_key not in self.screens:
            return

        screen = self.screens[zone_key]
        biome = screen.get('biome')

        # --- Leave old domain ---
        old_domain_id = screen.get('biome_domain_id')
        if old_domain_id and old_domain_id in self.domains:
            old_domain = self.domains[old_domain_id]
            old_domain['zones'].discard(zone_key)
            if len(old_domain['zones']) == 0:
                del self.domains[old_domain_id]
            elif len(old_domain['zones']) == 1:
                # Shrank to one zone — re-roll its name
                remaining_key = next(iter(old_domain['zones']))
                if remaining_key in self.screens:
                    new_name = self.generate_zone_name(self.screens[remaining_key].get('biome', 'FOREST'))
                    old_domain['name'] = new_name
                    self.screens[remaining_key]['name'] = new_name
            else:
                self._check_biome_domain_contiguity(old_domain_id)
        screen['biome_domain_id'] = None

        # --- Find adjacent same-biome zones connected by a shared exit ---
        # exit_pairs: (dx, dy, my_exit_key, their_exit_key)
        exit_pairs = [
            (-1,  0, 'left',   'right'),
            ( 1,  0, 'right',  'left'),
            ( 0, -1, 'top',    'bottom'),
            ( 0,  1, 'bottom', 'top'),
        ]
        sx, sy = map(int, zone_key.split(','))
        my_exits = screen.get('exits', {})
        neighbor_domain_ids = set()
        domainless_neighbors = []  # same-biome neighbors not yet in any domain
        for dx, dy, my_exit, their_exit in exit_pairs:
            nkey = f"{sx+dx},{sy+dy}"
            if nkey not in self.screens:
                continue
            # Only merge zones connected by an actual open exit in both directions
            if not my_exits.get(my_exit):
                continue
            nbr = self.screens[nkey]
            if not nbr.get('exits', {}).get(their_exit):
                continue
            if nbr.get('biome') == biome:
                did = nbr.get('biome_domain_id')
                if did:
                    neighbor_domain_ids.add(did)
                else:
                    domainless_neighbors.append(nkey)

        if not neighbor_domain_ids and not domainless_neighbors:
            # Truly isolated — create a single-zone domain so future neighbors can find it
            new_id = self._new_domain_id()
            self.domains[new_id] = {
                'name': screen.get('name', self.generate_zone_name(biome)),
                'type': 'biome',
                'biome': biome,
                'faction': None,
                'zones': {zone_key},
            }
            screen['biome_domain_id'] = new_id
            return

        # --- Pick or create the surviving domain ---
        surviving_id = None
        if neighbor_domain_ids:
            candidate = max(
                neighbor_domain_ids,
                key=lambda d: (len(self.domains[d]['zones']), random.random()) if d in self.domains else (0, 0)
            )
            if candidate in self.domains:
                surviving_id = candidate

        if surviving_id is None:
            # No valid existing domain — create one named after this zone
            surviving_id = self._new_domain_id()
            self.domains[surviving_id] = {
                'name': screen.get('name', self.generate_zone_name(biome)),
                'type': 'biome',
                'biome': biome,
                'faction': None,
                'zones': set(),
            }

        surviving_domain = self.domains[surviving_id]

        # Absorb all other touching domains
        for other_id in neighbor_domain_ids:
            if other_id == surviving_id or other_id not in self.domains:
                continue
            other_domain = self.domains[other_id]
            for zk in list(other_domain['zones']):
                surviving_domain['zones'].add(zk)
                if zk in self.screens:
                    self.screens[zk]['biome_domain_id'] = surviving_id
                    self.screens[zk]['name'] = surviving_domain['name']
            del self.domains[other_id]

        # Pull in domainless same-biome neighbors
        for nkey in domainless_neighbors:
            surviving_domain['zones'].add(nkey)
            if nkey in self.screens:
                self.screens[nkey]['biome_domain_id'] = surviving_id
                self.screens[nkey]['name'] = surviving_domain['name']

        # Add this zone to the surviving domain
        surviving_domain['zones'].add(zone_key)
        screen['biome_domain_id'] = surviving_id
        screen['name'] = surviving_domain['name']

    def _check_biome_domain_contiguity(self, domain_id):
        """BFS check: if a domain has split into disconnected fragments, split it.

        Assigns directional modifiers (North/South/East/West) to fragments based
        on their centroid position relative to each other.
        """
        if domain_id not in self.domains:
            return
        domain = self.domains[domain_id]
        all_zones = set(domain['zones'])
        if len(all_zones) <= 1:
            return

        # BFS to find connected fragments
        visited = set()
        fragments = []
        for start in list(all_zones):
            if start in visited:
                continue
            fragment = set()
            queue = [start]
            while queue:
                zk = queue.pop()
                if zk in visited:
                    continue
                visited.add(zk)
                if zk not in all_zones:
                    continue
                fragment.add(zk)
                sx, sy = map(int, zk.split(','))
                zdata = self.screens.get(zk, {})
                z_exits = zdata.get('exits', {})
                exit_pairs = [
                    (-1,  0, 'left',   'right'),
                    ( 1,  0, 'right',  'left'),
                    ( 0, -1, 'top',    'bottom'),
                    ( 0,  1, 'bottom', 'top'),
                ]
                for dx, dy, my_exit, their_exit in exit_pairs:
                    nk = f"{sx+dx},{sy+dy}"
                    if nk not in all_zones or nk in visited:
                        continue
                    if not z_exits.get(my_exit):
                        continue
                    nbr_exits = self.screens.get(nk, {}).get('exits', {})
                    if not nbr_exits.get(their_exit):
                        continue
                    queue.append(nk)
            fragments.append(fragment)

        if len(fragments) <= 1:
            return  # Still contiguous

        base_name = domain['name']
        DIRECTION_MODIFIERS = ['North', 'South', 'East', 'West', 'Old', 'New', 'Inner', 'Outer']

        # Sort fragments by centroid (north-to-south then west-to-east)
        def centroid(frag):
            coords = [list(map(int, k.split(','))) for k in frag]
            return (sum(c[1] for c in coords) / len(coords), sum(c[0] for c in coords) / len(coords))

        fragments.sort(key=centroid)

        for i, fragment in enumerate(fragments):
            if i == 0:
                # Largest/primary fragment keeps the domain id
                domain['zones'] = fragment
                for zk in fragment:
                    if zk in self.screens:
                        self.screens[zk]['biome_domain_id'] = domain_id
            else:
                # New domain for each additional fragment
                modifier = DIRECTION_MODIFIERS[i] if i < len(DIRECTION_MODIFIERS) else str(i)
                new_id = self._new_domain_id()
                new_name = f"{modifier} {base_name}"
                self.domains[new_id] = {
                    'name': new_name,
                    'type': 'biome',
                    'biome': domain['biome'],
                    'faction': None,
                    'zones': fragment,
                }
                for zk in fragment:
                    if zk in self.screens:
                        self.screens[zk]['biome_domain_id'] = new_id
                        self.screens[zk]['name'] = new_name

    def update_faction_domain(self, faction_name):
        """Rebuild the faction domain for faction_name from scratch.

        Called when a zone changes faction control. Finds all zones controlled
        by this faction, groups them into contiguous sets, and creates/updates
        faction domains accordingly. Faction domain name = faction_name + first zone name.
        """
        # Collect all zones controlled by this faction
        controlled = set()
        for zk, screen in self.screens.items():
            if screen.get('controlling_faction') == faction_name:
                controlled.add(zk)

        # Remove old faction domain entries for this faction
        old_ids = [did for did, d in self.domains.items()
                   if d['type'] == 'faction' and d['faction'] == faction_name]
        for old_id in old_ids:
            for zk in self.domains[old_id]['zones']:
                if zk in self.screens:
                    self.screens[zk]['faction_domain_id'] = None
            del self.domains[old_id]

        if not controlled:
            return

        # BFS to find contiguous groups
        visited = set()
        fragments = []
        for start in list(controlled):
            if start in visited:
                continue
            fragment = set()
            queue = [start]
            while queue:
                zk = queue.pop()
                if zk in visited:
                    continue
                visited.add(zk)
                if zk not in controlled:
                    continue
                fragment.add(zk)
                sx, sy = map(int, zk.split(','))
                for nx, ny in [(sx, sy-1), (sx, sy+1), (sx-1, sy), (sx+1, sy)]:
                    nk = f"{nx},{ny}"
                    if nk in controlled and nk not in visited:
                        queue.append(nk)
            fragments.append(fragment)

        for fragment in fragments:
            new_id = self._new_domain_id()
            # Use the name of the first zone in the fragment as the domain root name
            sample_key = next(iter(fragment))
            zone_name = self.screens[sample_key].get('name', sample_key) if sample_key in self.screens else sample_key
            domain_name = f"{faction_name} {zone_name}"
            self.domains[new_id] = {
                'name': domain_name,
                'type': 'faction',
                'biome': None,
                'faction': faction_name,
                'zones': fragment,
            }
            for zk in fragment:
                if zk in self.screens:
                    self.screens[zk]['faction_domain_id'] = new_id

    def get_zone_domain_id(self, zone_key, domain_type='biome'):
        """Return the domain ID for a zone. domain_type: 'biome' or 'faction'."""
        if zone_key not in self.screens:
            return None
        field = 'biome_domain_id' if domain_type == 'biome' else 'faction_domain_id'
        return self.screens[zone_key].get(field)

    def is_same_domain(self, zone_key_a, zone_key_b):
        """True if both zones share any domain (biome or faction)."""
        if zone_key_a == zone_key_b:
            return True
        for field in ('biome_domain_id', 'faction_domain_id'):
            da = self.screens.get(zone_key_a, {}).get(field)
            db = self.screens.get(zone_key_b, {}).get(field)
            if da and da == db:
                return True
        return False

    def is_near_structure(self, x, y, screen_key):
        """Check if cell is near HOUSE/CAMP (within 2 cells)"""
        if screen_key not in self.screens:
            return False

        grid = self.screens[screen_key]['grid']
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                check_x = x + dx
                check_y = y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if grid[check_y][check_x] in ['HOUSE', 'CAMP']:
                        return True
        return False

    def update_single_cell(self, screen_x, screen_y, x, y):
        """Apply cellular automata rules to a single cell"""
        from constants import (
            DIRT_TO_GRASS_RATE, GRASS_TO_DIRT_RATE, DIRT_TO_SAND_DROUGHT_RATE,
            GRASS_TO_TREE_RATE, SAND_TO_DIRT_WATER_RATE, WATER_TO_DEEP_WATER_RATE,
            DEEP_WATER_TO_WATER_RATE, WATER_TO_BASE_ISOLATED_RATE, DIRT_TO_WATER_RAIN_RATE,
            GRASS_TO_FLOWER_RATE, FLOWER_TO_GRASS_RATE, TREE_TO_GRASS_RATE,
            BIOME_BORDER_SPREAD_RATE,
        )

        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        biome = screen.get('biome', 'FOREST')
        cell = screen['grid'][y][x]

        if cell in ['WALL', 'HOUSE', 'CAVE', 'CLIFF']:
            return

        if self.is_cell_enchanted(x, y, key):
            return

        neighbors = self.get_neighbors(x, y, key)
        if not neighbors:
            return

        water_count = self.count_cell_type(neighbors, 'WATER')
        deep_water_count = self.count_cell_type(neighbors, 'DEEP_WATER')
        dirt_count = self.count_cell_type(neighbors, 'DIRT')
        grass_count = self.count_cell_type(neighbors, 'GRASS')
        tree_count = self.count_cell_type(neighbors, 'TREE')
        sand_count = self.count_cell_type(neighbors, 'SAND')
        flower_count = self.count_cell_type(neighbors, 'FLOWER')

        total_water = water_count + deep_water_count
        new_cell = cell

        if cell == 'DIRT' and total_water >= 2:
            if random.random() < DIRT_TO_GRASS_RATE:
                new_cell = 'GRASS'
        elif cell == 'GRASS' and total_water == 0:
            if random.random() < GRASS_TO_DIRT_RATE:
                new_cell = 'DIRT'
        elif cell == 'DIRT' and total_water == 0 and (sand_count >= 2 or grass_count == 0) and biome != 'DESERT':
            if random.random() < DIRT_TO_SAND_DROUGHT_RATE:
                new_cell = 'SAND'
        elif cell == 'GRASS' and 1 <= tree_count <= 2 and total_water >= 1:
            if random.random() < GRASS_TO_TREE_RATE:
                new_cell = 'TREE1'
        elif cell == 'SAND' and total_water >= 2:
            if random.random() < SAND_TO_DIRT_WATER_RATE:
                new_cell = 'DIRT'
        elif cell == 'WATER':
            cardinal_water = sum(
                1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                and screen['grid'][y + cdy][x + cdx] in ('WATER', 'DEEP_WATER')
            )
            if cardinal_water == 4 and random.random() < WATER_TO_DEEP_WATER_RATE:
                new_cell = 'DEEP_WATER'
            elif total_water <= 1 and random.random() < WATER_TO_BASE_ISOLATED_RATE:
                new_cell = 'DIRT'
        elif cell == 'DEEP_WATER' and (water_count + deep_water_count) < 2:
            if random.random() < DEEP_WATER_TO_WATER_RATE:
                new_cell = 'WATER'
        elif cell == 'DIRT' and total_water >= 3:
            if random.random() < DIRT_TO_WATER_RAIN_RATE:
                new_cell = 'WATER'
        elif cell == 'GRASS' and flower_count >= 1 and flower_count <= 2 and total_water >= 1:
            if random.random() < GRASS_TO_FLOWER_RATE:
                new_cell = 'FLOWER'
        elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
            if random.random() < FLOWER_TO_GRASS_RATE:
                new_cell = 'GRASS'
        elif cell.startswith('TREE') and tree_count >= 4:
            if random.random() < TREE_TO_GRASS_RATE:
                new_cell = 'GRASS'

        # General neighbor-copy: base terrain may adopt a random NSEW neighbor's type
        if new_cell == cell and cell in ('GRASS', 'DIRT', 'SAND', 'WATER'):
            nx, ny = random.choice(((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)))
            if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                neighbor = screen['grid'][ny][nx]
                if neighbor in ('GRASS', 'DIRT', 'SAND', 'WATER') and neighbor != cell:
                    if random.random() < BIOME_BORDER_SPREAD_RATE:
                        new_cell = neighbor

        if new_cell != cell:
            screen['grid'][y][x] = new_cell

    # -------------------------------------------------------------------------
    # Keeper assignment
    # -------------------------------------------------------------------------

    def assign_zone_keepers(self, zone_key):
        """Check entities in zone_key and assign keeper status to fill vacant slots.

        Called once per zone update cycle.  Each zone/structure maintains a dict
        of keeper slots keyed by keeper_type.  If a slot is vacant and an eligible
        entity is present, there is a KEEPER_ASSIGNMENT_RATE chance per call to
        assign one as keeper.  Keepers are permanent anchors — they cannot exit
        the zone or structure they were assigned in.
        """
        if zone_key not in self.zone_keepers:
            self.zone_keepers[zone_key] = {}

        keepers = self.zone_keepers[zone_key]

        # --- Prune dead or missing keepers ---
        for ktype, eid in list(keepers.items()):
            if eid not in self.entities:
                del keepers[ktype]
            # If somehow the entity lost its keeper flag, clear the slot too
            elif not getattr(self.entities[eid], 'keeper', False):
                del keepers[ktype]

        # --- Collect candidates from this zone ---
        entity_ids = list(self.screen_entities.get(zone_key, []))

        for eid in entity_ids:
            if eid not in self.entities:
                continue
            entity = self.entities[eid]

            # Skip followers — they travel with the player
            if eid in self.followers:
                continue

            # Skip autopilot proxies — their keeper state is managed by the autopilot
            if entity.props.get('is_autopilot_proxy', False):
                continue

            ktype = KEEPER_ENTITY_TYPE.get(entity.type)
            if not ktype:
                continue  # TRADER, KING, etc. — never become keepers

            if getattr(entity, 'keeper', False):
                continue  # Already a keeper somewhere

            if ktype in keepers:
                continue  # Slot already occupied

            # In non-structure zones the first entity of each type is immediately
            # assigned keeper — no probability roll needed.
            # Structure zones use the slower probabilistic rate.
            is_structure_zone = zone_key in self.structure_zones
            if is_structure_zone:
                if random.random() >= KEEPER_ASSIGNMENT_RATE:
                    continue
            entity.keeper = True
            keepers[ktype] = eid
            # Assign patrol type and target position
            entity.keeper_type = KEEPER_TYPE_BY_ENTITY.get(entity.type, 3)
            if entity.keeper_type < 3:
                entity.keeper_target_pos = self._find_keeper_target(zone_key)

    def _find_keeper_target(self, zone_key):
        """Return (grid_x, grid_y) for a keeper's anchor point in zone_key.

        Priority:
        1. First WELL cell found in the zone grid
        2. First structure entrance cell (DOOR, STAIRS_DOWN) found
        3. Zone center as fallback
        """
        screen = self.screens.get(zone_key)
        if screen:
            grid = screen.get('grid', [])
            target_cells = {'WELL', 'DOOR', 'STAIRS_DOWN'}
            for y, row in enumerate(grid):
                for x, cell in enumerate(row):
                    if cell in target_cells:
                        return (x, y)
        # Fallback: zone center
        return (GRID_WIDTH // 2, GRID_HEIGHT // 2)

    _WOLF_TYPES = frozenset(('WOLF', 'WOLF_double'))

    def assign_wolf_pack_keepers(self, zone_key):
        """Form or refresh wolf pack hierarchy in zone_key.

        The strongest wolf (highest level, oldest as tiebreak) becomes the pack
        leader and roams freely.  All other wolves become keepers tracking the
        leader so they follow it when it crosses zones.  Called occasionally
        from the zone update loop (~0.5% per update or every 600 ticks).
        """
        wolf_ids = [
            eid for eid in self.screen_entities.get(zone_key, [])
            if eid in self.entities
            and self.entities[eid].health > 0
            and self.entities[eid].type in self._WOLF_TYPES
            and eid not in self.followers
        ]

        if len(wolf_ids) < 2:
            # Single wolf or empty — clear any stale follower flags
            for eid in wolf_ids:
                e = self.entities[eid]
                if getattr(e, '_wolf_follower', False):
                    e.keeper = False
                    e.keeper_type = None
                    e.keeper_target = None
                    e.keeper_target_pos = None
                    e._wolf_follower = False
            return

        # Pick leader: highest level, then oldest (highest age) as tiebreak
        def _leader_key(eid):
            e = self.entities[eid]
            return (getattr(e, 'level', 1), getattr(e, 'age', 0))

        leader_id = max(wolf_ids, key=_leader_key)
        leader = self.entities[leader_id]

        # Leader roams freely — not a keeper, can cross zones at high travel rate
        leader.keeper = False
        leader.keeper_type = None
        leader.keeper_target = None
        leader.keeper_target_pos = None
        leader._wolf_leader = True
        leader._wolf_follower = False

        # Followers: keepers that track the leader across zones
        for eid in wolf_ids:
            if eid == leader_id:
                continue
            follower = self.entities[eid]
            follower.keeper = True
            follower._wolf_follower = True
            follower._wolf_leader = False
            follower.keeper_target = {
                'type': 'entity',
                'ref': leader_id,
                'pos': (leader.x, leader.y),
                'screen': (leader.screen_x, leader.screen_y),
            }
            follower.keeper_target_pos = (leader.x, leader.y)
            follower.keeper_type = 2  # Within 5 cells of leader
