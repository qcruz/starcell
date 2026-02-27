import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, ENTITY_TYPES,
    MAX_CATCHUP_PER_FRAME, MAX_CYCLES_TO_SIMULATE,
    UPDATE_FREQUENCY, MAX_ZONES_PER_UPDATE,
    NEW_ZONE_INSTANTIATE_CHANCE,
    SKELETON_DAYLIGHT_DAMAGE,
    CAMP_HEALING_MULTIPLIER, HOUSE_HEALING_MULTIPLIER,
    NPC_CAMP_PLACE_RATE, ENHANCED_SETTLEMENT_RATE,
)
from entity import Entity


class ZonesMixin:
    """Handles zone update loop, priority queue, catch-up simulation,
    biome shifts, and entity lifecycle across zones."""

    # -------------------------------------------------------------------------
    # Main update loop
    # -------------------------------------------------------------------------

    def probabilistic_zone_updates(self):
        """Priority queue based zone updates. Zones scored by distance, staleness,
        connections, quests, and structures. Higher priority = updated first."""
        if self.tick % UPDATE_FREQUENCY != 0:
            return

        self.update_weather()
        self.update_day_night_cycle()
        self.move_items_to_nearest_chest()

        # Small chance to instantiate a new random zone
        if random.random() < NEW_ZONE_INSTANTIATE_CHANCE:
            range_x = random.randint(-20, 20)
            range_y = random.randint(-20, 20)
            new_zone_key = f"{range_x},{range_y}"
            if new_zone_key not in self.screens:
                self.generate_screen(range_x, range_y)
                self.instantiated_zones.add(new_zone_key)

        if self.tick % 600 == 0:
            self.cleanup_screen_entities()

        self.ensure_nearby_zones_exist()

        priority_queue = self.get_priority_sorted_zones()

        zones_updated = 0
        total_entities_updated = 0
        total_cells_updated = 0

        # Always update the player's zone first at full coverage
        player_zone_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            player_zone_key = self.player['subscreen_key']

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

        # Update all mandatory zones at 100% coverage
        for mz_key in mandatory_zones:
            if mz_key in self.structure_zones:
                self.update_structure_zone(mz_key, 1.0, 1.0)
            elif self.is_overworld_zone(mz_key):
                parts = mz_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), 1.0, 1.0)
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

            coverage = update_chance

            if zone_key in self.structure_zones:
                self.update_structure_zone(zone_key, coverage, coverage)
            elif self.is_overworld_zone(zone_key):
                parts = zone_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), coverage, coverage)
            else:
                continue

            zones_updated += 1
            ent_count = len(self.screen_entities.get(zone_key, []))
            total_entities_updated += int(ent_count * coverage)
            total_cells_updated += int(GRID_WIDTH * GRID_HEIGHT * coverage)

        if self.tick % 1800 == 0:
            total_entities = len(self.entities)
            total_zones = len(self.screens)
            print(f"[UpdateCycle] tick={self.tick} "
                  f"zones={zones_updated}/{total_zones} "
                  f"entities={total_entities_updated}/{total_entities} "
                  f"cells={total_cells_updated} "
                  f"mandatory={len(mandatory_zones)} "
                  f"player_zone={player_zone_key}"
                  f"({len(self.screen_entities.get(player_zone_key, []))}ent) "
                  f"queue={len(priority_queue)}")

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

        # === ZONE-LEVEL UPDATES ===
        self.check_zone_threats(zone_key)
        self.check_raid_event(zone_key)
        self.check_cave_spawn_hostile(zone_key)
        self.check_night_skeleton_spawn(zone_key)
        self.check_termite_spawn(zone_key)
        self.decay_dropped_items(zone_x, zone_y)
        self.consolidate_dropped_items(zone_key)

        # === CELL UPDATES ===
        if self.is_raining:
            distance = abs(zone_x - self.player['screen_x']) + abs(zone_y - self.player['screen_y'])
            if distance <= 2:
                self.apply_rain(zone_x, zone_y)

        self.apply_cellular_automata(zone_x, zone_y)

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                if self.is_cell_enchanted(x, y, zone_key):
                    continue

                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]

                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        screen['grid'][y][x] = cell_info['grows_to']
                    elif 'degrades_to' in cell_info and random.random() < cell_info.get('degrade_rate', 0):
                        if cell == 'COBBLESTONE':
                            center_x = GRID_WIDTH // 2
                            center_y = GRID_HEIGHT // 2
                            on_horizontal_center = abs(y - center_y) <= 2
                            on_vertical_center = abs(x - center_x) <= 2
                            if on_horizontal_center or on_vertical_center:
                                continue
                            has_structure_neighbor = False
                            for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                                    neighbor_cell = screen['grid'][ny][nx]
                                    if neighbor_cell in ['HOUSE', 'CAMP', 'CAVE', 'MINESHAFT']:
                                        has_structure_neighbor = True
                                        break
                            if has_structure_neighbor:
                                continue

                        old_cell = cell
                        screen['grid'][y][x] = cell_info['degrades_to']

                        if old_cell == 'HOUSE':
                            self.process_house_destruction(x, y, zone_key)

        # === BIOME REVERSION & SPREADING ===
        biome = screen.get('biome', 'FOREST')
        biome_base_map = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
        }
        base_cell = biome_base_map.get(biome, 'GRASS')

        biome_native = {
            'FOREST': {'GRASS', 'DIRT', 'TREE1', 'TREE2', 'FLOWER'},
            'PLAINS': {'GRASS', 'DIRT', 'FLOWER'},
            'DESERT': {'SAND', 'DIRT'},
            'MOUNTAINS': {'DIRT', 'STONE', 'GRASS'},
            'TUNDRA': {'DIRT', 'STONE'},
            'SWAMP': {'DIRT', 'WATER', 'GRASS'},
        }
        native_cells = biome_native.get(biome, {'GRASS', 'DIRT'})

        protected_cells = {'HOUSE', 'CAVE', 'MINESHAFT', 'CAMP', 'CHEST', 'WALL',
                           'COBBLESTONE', 'WATER', 'DEEP_WATER', 'WOOD', 'PLANKS',
                           'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'STAIRS_UP',
                           'STAIRS_DOWN', 'HIDDEN_CAVE', 'SOIL', 'CARROT1', 'CARROT2', 'CARROT3'}

        foreign_revert = {
            'DESERT': {'GRASS', 'TREE1', 'TREE2', 'FLOWER', 'DIRT'},
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

                if cell in revert_targets and random.random() < 0.003:
                    screen['grid'][y][x] = base_cell
                    continue

                if cell in native_cells and random.random() < 0.005:
                    dx, dy = random.choice([(1, 0), (-1, 0), (0, 1), (0, -1)])
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                        neighbor = screen['grid'][ny][nx]
                        if neighbor not in protected_cells and neighbor not in native_cells:
                            screen['grid'][ny][nx] = cell

        # === ENTITY UPDATES ===
        if getattr(self, 'autopilot', False) and zone_key in self.screen_entities:
            for eid in self.screen_entities[zone_key]:
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False
            self.inspected_npc = None

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

                            print(f"{entity.name} defected from {old_faction} to {new_faction}!")

                # Age entities every 600 ticks
                if self.tick % 600 == 0 and entity.type != 'SKELETON':
                    entity.age += 1

                entity.decay_stats()

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

                entity.regenerate_health(heal_boost)

                if not entity.is_alive():
                    entities_to_remove.append(entity_id)
                    continue

                self.update_entity_ai(entity_id, entity)

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

                    # Pick up from adjacent chest
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
                                    grid[cy][cx] = 'WOOD'
                                break

                    # Inventory overflow: place chest if >10 unique item types
                    if len(entity.inventory) > 10:
                        ground_cells = {'GRASS', 'DIRT', 'SAND', 'FLOOR_WOOD', 'CAVE_FLOOR', 'COBBLESTONE'}
                        for dx, dy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                            cx, cy = ex + dx, ey + dy
                            if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                                cell = grid[cy][cx]
                                if cell in ground_cells:
                                    grid[cy][cx] = 'CHEST'
                                    chest_key = f"{zone_key}:{cx},{cy}"
                                    items_list = list(entity.inventory.items())
                                    half = len(items_list) // 2
                                    chest_items = {n: c for n, c in items_list[:half]}
                                    self.chest_contents[chest_key] = chest_items
                                    for item_name in chest_items:
                                        del entity.inventory[item_name]
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
                print(f"ZONE REVOLUTION in [{zone_key}]! {len(warriors_in_zone)} warriors formed {new_faction} faction!")

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
                        print(f"FACTION RAID in [{zone_key}]! {raiders_spawned} {raiding_faction} warriors invade!")

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

            if random.random() < spawn_chance:
                biome = screen.get('biome', 'FOREST')
                spawned = False
                if 'TRADER' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='TRADER')
                    if spawned:
                        print(f"[SPAWN] TRADER spawned in [{zone_key}] (pop: {npc_count})")
                elif 'GUARD' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='GUARD')
                    if spawned:
                        print(f"[SPAWN] GUARD spawned in [{zone_key}] (pop: {npc_count})")

                if not spawned:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome)
                    if spawned:
                        print(f"[SPAWN] Entity spawned in [{zone_key}] (pop: {npc_count})")

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
                            print(f"Two traders merged into {t1.type} at [{zone_key}]")

                    if len(guards) > 2:
                        g1_id, g1 = guards[0]
                        g2_id, g2 = guards[1]
                        if g1.can_merge_with(g2):
                            g1.merge_with(g2)
                            del self.entities[g2_id]
                            print(f"Two guards merged into {g1.type} at [{zone_key}]")

                    if traders:
                        trader_id, trader = random.choice(traders)
                        if not has_farmer and random.random() < 0.5:
                            old_name = trader.name
                            trader.type = 'FARMER'
                            trader.props = ENTITY_TYPES['FARMER']
                            print(f"{old_name} (Trader) settled as a farmer at [{zone_key}]")
                        elif not has_lumberjack and random.random() < 0.5:
                            old_name = trader.name
                            trader.type = 'LUMBERJACK'
                            trader.props = ENTITY_TYPES['LUMBERJACK']
                            print(f"{old_name} (Trader) settled as a lumberjack at [{zone_key}]")
                        elif not has_miner:
                            old_name = trader.name
                            trader.type = 'MINER'
                            trader.props = ENTITY_TYPES['MINER']
                            print(f"{old_name} (Trader) settled as a miner at [{zone_key}]")

                    if guards:
                        guard_id, guard = random.choice(guards)
                        if not has_farmer and random.random() < 0.5:
                            old_name = guard.name
                            guard.type = 'FARMER'
                            guard.props = ENTITY_TYPES['FARMER']
                            print(f"{old_name} (Guard) settled as a farmer at [{zone_key}]")
                        elif not has_miner and random.random() < 0.5:
                            old_name = guard.name
                            guard.type = 'MINER'
                            guard.props = ENTITY_TYPES['MINER']
                            print(f"{old_name} (Guard) settled as a miner at [{zone_key}]")

            if self.tick % 600 == 0:
                self.promote_to_commander(zone_key)
                self.promote_to_king()
                self.recruit_to_hostile_faction(zone_key)

    def update_structure_zone(self, struct_zone_key, cell_coverage, entity_coverage):
        """Update a structure zone (cave/house interior) like a regular zone."""
        if struct_zone_key not in self.screens:
            return

        screen = self.screens[struct_zone_key]
        self.screen_last_update[struct_zone_key] = self.tick

        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]
                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['grows_to'])
                    elif 'degrades_to' in cell_info and random.random() < cell_info.get('degrade_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['degrades_to'])

        entity_list = self.screen_entities.get(struct_zone_key, [])
        if not entity_list:
            entity_list = self.subscreen_entities.get(struct_zone_key, [])

        if getattr(self, 'autopilot', False):
            for eid in list(entity_list):
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False

        entities_to_remove = []
        for entity_id in list(entity_list):
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]
            entity.decay_stats()
            entity.regenerate_health(1.0)

            if not entity.is_alive():
                entities_to_remove.append(entity_id)
                continue

            self.update_entity_ai(entity_id, entity)

        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)

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
                    hostile_count = random.randint(1, 2)
                    hostile_type = random.choice(['GOBLIN', 'BANDIT', 'WOLF'])

                    for _ in range(hostile_count):
                        spawn_x = random.randint(3, GRID_WIDTH - 4)
                        spawn_y = random.randint(3, GRID_HEIGHT - 4)
                        if not CELL_TYPES[screen['grid'][spawn_y][spawn_x]].get('solid', False):
                            entity = Entity(hostile_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
                            entity_id = self.next_entity_id
                            self.next_entity_id += 1
                            self.entities[entity_id] = entity
                            self.screen_entities[screen_key].append(entity_id)

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
                        cave_x = random.randint(2, GRID_WIDTH - 3)
                        cave_y = random.randint(2, GRID_HEIGHT - 3)
                        screen['grid'][cave_y][cave_x] = 'CAVE'

                    print(f"Catch-up: Raid event simulated in [{screen_key}] - {hostile_count} {hostile_type}(s) spawned")

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
                    print(f"Catch-up: Faction war in [{screen_key}] - {casualty.name} ({casualty.faction}) killed")

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
                        if random.random() < NPC_CAMP_PLACE_RATE:
                            self.miner_place_cave(entity)

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

                if cell in ['WALL', 'HOUSE', 'CAVE']:
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
                elif cell == 'DIRT' and total_water == 0 and counts.get('sand', 0) >= 2:
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
        """Calculate priority score for a zone. Higher = update sooner."""
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']
        player_zone = f"{player_x},{player_y}"

        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            player_zone = self.player['subscreen_key']

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

        if zone_key == player_zone:
            distance_score = 100.0
        elif distance == 0:
            distance_score = 90.0
        elif distance <= 1:
            distance_score = 50.0
        elif distance <= 2:
            distance_score = 25.0
        elif distance <= 3:
            distance_score = 10.0
        else:
            distance_score = max(1.0, 5.0 / distance)

        last_update = self.screen_last_update.get(zone_key, 0)
        staleness_ticks = self.tick - last_update
        staleness_score = min(30.0, staleness_ticks / 60.0)

        connection_score = 0.0
        if zone_key in self.zone_connections:
            for connected_key, conn_type, *_ in self.zone_connections[zone_key]:
                if connected_key == player_zone:
                    connection_score = 40.0
                    break
                if self.is_overworld_zone(connected_key):
                    cp = connected_key.split(',')
                    cd = abs(int(cp[0]) - player_x) + abs(int(cp[1]) - player_y)
                    if cd <= 1:
                        connection_score = max(connection_score, 20.0)

        structure_score = 0.0
        if zone_key in self.structure_zones:
            structure_score = 15.0
        elif zone_key in self.zone_structures:
            structure_score = 5.0

        quest_score = 0.0
        for quest_type, quest in self.quests.items():
            if hasattr(quest, 'target_zone') and quest.target_zone == zone_key:
                quest_score = 20.0
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
            int(parts[0])
            int(parts[1])
            return True
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

        new_biome = current_biome
        if sand_pct > 0.4:
            new_biome = 'DESERT'
        elif stone_pct > 0.3:
            new_biome = 'MOUNTAINS'
        elif grass_pct > 0.5 and tree_pct < 0.1:
            new_biome = 'PLAINS'
        elif grass_pct > 0.3 and tree_pct > 0.15:
            new_biome = 'FOREST'

        if new_biome != current_biome:
            screen['biome'] = new_biome
            print(f"Zone [{screen_x},{screen_y}] biome shifted: {current_biome} → {new_biome}")

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
            DIRT_TO_GRASS_RATE, GRASS_TO_DIRT_RATE, DIRT_TO_SAND_RATE,
            TREE_GROWTH_RATE, SAND_RECLAIM_RATE, DEEP_WATER_FORM_RATE,
            DEEP_WATER_EVAPORATE_RATE, WATER_TO_DIRT_RATE, FLOODING_RATE,
            FLOWER_SPREAD_RATE, FLOWER_DECAY_RATE, TREE_DECAY_RATE,
        )

        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        cell = screen['grid'][y][x]

        if cell in ['WALL', 'HOUSE', 'CAVE']:
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
        elif cell == 'DIRT' and total_water == 0 and (sand_count >= 2 or grass_count == 0):
            if random.random() < DIRT_TO_SAND_RATE:
                new_cell = 'SAND'
        elif cell == 'GRASS' and 1 <= tree_count <= 2 and total_water >= 1:
            if random.random() < TREE_GROWTH_RATE:
                new_cell = 'TREE1'
        elif cell == 'SAND' and total_water >= 2:
            if random.random() < SAND_RECLAIM_RATE:
                new_cell = 'DIRT'
        elif cell == 'WATER' and water_count >= 4:
            if random.random() < DEEP_WATER_FORM_RATE:
                new_cell = 'DEEP_WATER'
        elif cell == 'DEEP_WATER' and (water_count + deep_water_count) < 2:
            if random.random() < DEEP_WATER_EVAPORATE_RATE:
                new_cell = 'WATER'
        elif cell == 'WATER' and total_water <= 1:
            if random.random() < WATER_TO_DIRT_RATE:
                new_cell = 'DIRT'
        elif cell == 'DIRT' and total_water >= 3:
            if random.random() < FLOODING_RATE:
                new_cell = 'WATER'
        elif cell == 'GRASS' and flower_count >= 1 and flower_count <= 2 and total_water >= 1:
            if random.random() < FLOWER_SPREAD_RATE:
                new_cell = 'FLOWER'
        elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
            if random.random() < FLOWER_DECAY_RATE:
                new_cell = 'GRASS'
        elif cell.startswith('TREE') and tree_count >= 4:
            if random.random() < TREE_DECAY_RATE:
                new_cell = 'GRASS'

        # Biome spreading: base terrain has small chance to spread
        if new_cell == cell:
            base_terrain_cells = ['GRASS', 'SAND', 'SNOW', 'DIRT']
            if cell in base_terrain_cells and random.random() < 0.001:
                adjacent_coords = [
                    (x + dx, y + dy)
                    for dy in range(-1, 2) for dx in range(-1, 2)
                    if not (dx == 0 and dy == 0)
                    and 0 <= x + dx < GRID_WIDTH and 0 <= y + dy < GRID_HEIGHT
                ]
                if adjacent_coords:
                    target_x, target_y = random.choice(adjacent_coords)
                    target_cell = screen['grid'][target_y][target_x]
                    if target_cell in base_terrain_cells and target_cell != cell:
                        screen['grid'][target_y][target_x] = cell

        if new_cell != cell:
            screen['grid'][y][x] = new_cell
