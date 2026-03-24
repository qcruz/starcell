import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, ENTITY_TYPES,
    RAID_CHANCE_BASE, RAID_POPULATION_THRESHOLD,
    HIDDEN_CAVE_SPAWN_CHANCE,
    CAVE_HOSTILE_SPAWN_CHANCE,
    NIGHT_SKELETON_SPAWN_CHANCE,
    TERMITE_SPAWN_CHANCE,
)
from entity import Entity

# NPC types that get random starting resources on spawn
_HUMANOID_NPC_TYPES = frozenset([
    'FARMER', 'GUARD', 'WARRIOR', 'COMMANDER', 'KING',
    'TRADER', 'BLACKSMITH', 'WIZARD', 'LUMBERJACK', 'MINER', 'BANDIT',
])

# Combined item pool drawn from ITEMS + CELL_PICKUP (structural/meta entries excluded)
_SPAWN_ITEM_POOL = [
    'wood', 'planks', 'stone', 'carrot', 'seeds', 'gold', 'bones',
    'fur', 'meat', 'cooked_meat', 'stew', 'rope', 'leather',
    'axe', 'hoe', 'shovel', 'pickaxe', 'bucket',
    'stone_pickaxe', 'stone_axe', 'watering_can',
    'hilt', 'bone_sword', 'club', 'leather_armor',
    'iron_ore', 'iron_ingot', 'sandstone',
    'grass', 'dirt', 'soil', 'sand', 'tree_sapling', 'flower',
]


class SpawningMixin:
    """Handles all entity spawning: initial zone population, raids, cave hostiles,
    night skeletons, termites, runestones, and quest entities."""

    # -------------------------------------------------------------------------
    # Spawn inventory helpers
    # -------------------------------------------------------------------------

    def _give_random_starting_inventory(self, entity):
        """Give a humanoid NPC random starting resources.

        Always rolls 0-30 for wood, stone, and meat independently.
        Also gives 0-2 random items drawn from the shared item pool.
        """
        for resource in ('wood', 'stone', 'meat'):
            amount = random.randint(0, 30)
            if amount > 0:
                entity.inventory[resource] = entity.inventory.get(resource, 0) + amount

        extra_count = random.randint(0, 2)
        for _ in range(extra_count):
            item = random.choice(_SPAWN_ITEM_POOL)
            entity.inventory[item] = entity.inventory.get(item, 0) + random.randint(1, 5)

    # -------------------------------------------------------------------------
    # Initial zone population
    # -------------------------------------------------------------------------

    def spawn_entities_for_screen(self, screen_x, screen_y, biome_name):
        """Spawn initial entities for a newly generated screen - only at zone edges.
        WARNING: This clears existing entities - use spawn_single_entity_at_entrance for runtime spawning"""
        screen_key = f"{screen_x},{screen_y}"
        self.screen_entities[screen_key] = []  # Clear for initial generation

        # Biome-based spawning probabilities
        spawn_tables = {
            'FOREST': [
                ('DEER', 0.90, 1, 3),
                ('WOLF', 0.45, 0, 3),
                ('SHEEP', 0.55, 0, 2),
                ('CHICKEN', 0.45, 0, 2),
                ('BUTTERFLY', 0.90, 1, 4),
                ('BAT', 0.60, 1, 3),
                ('FARMER', 0.5, 0, 2),
                ('LUMBERJACK', 0.6, 1, 2),
                ('WIZARD', 0.25, 1, 2),
                ('TRADER', 0.5, 1, 2),
                ('BLACKSMITH', 0.5, 0, 1),
                ('GUARD', 0.7, 1, 2),
                ('WARRIOR', 0.35, 0, 1),
                ('BANDIT', 0.03, 0, 1),
                ('GOBLIN', 0.07, 0, 1),
                ('TERMITE', 0.3, 0, 2),
                ('RED_BIRD', 0.75, 1, 3),
                ('BLACK_SPIDER', 0.15, 0, 1),
            ],
            'PLAINS': [
                ('SHEEP', 0.90, 1, 4),
                ('DEER', 0.75, 0, 3),
                ('WOLF', 0.3, 0, 2),
                ('CHICKEN', 0.85, 1, 3),
                ('BUTTERFLY', 0.90, 1, 4),
                ('BAT', 0.50, 1, 2),
                ('FARMER', 0.7, 1, 3),
                ('LUMBERJACK', 0.3, 0, 1),
                ('WIZARD', 0.25, 1, 2),
                ('TRADER', 0.5, 1, 2),
                ('BLACKSMITH', 0.5, 0, 1),
                ('GUARD', 0.7, 1, 2),
                ('WARRIOR', 0.35, 0, 1),
                ('BANDIT', 0.03, 0, 1),
                ('GOBLIN', 0.05, 0, 1),
                ('TERMITE', 0.15, 0, 1),
                ('RED_BIRD', 0.65, 0, 2),
            ],
            'DESERT': [
                ('SHEEP', 0.65, 0, 2),
                ('DEER', 0.65, 0, 2),
                ('WOLF', 0.40, 0, 2),
                ('CHICKEN', 0.45, 0, 1),
                ('BUTTERFLY', 0.70, 1, 3),
                ('BAT', 0.60, 1, 3),
                ('GOBLIN', 0.18, 0, 2),
                ('BANDIT', 0.07, 0, 1),
                ('WIZARD', 0.25, 1, 2),
                ('FARMER', 0.3, 0, 1),
                ('LUMBERJACK', 0.2, 0, 1),
                ('MINER', 0.5, 0, 2),
                ('TRADER', 0.5, 1, 2),
                ('BLACKSMITH', 0.4, 0, 1),
                ('GUARD', 0.7, 1, 2),
                ('WARRIOR', 0.35, 0, 1),
                ('BLACK_SPIDER', 0.18, 0, 1),
            ],
            'MOUNTAINS': [
                ('WOLF', 0.9, 1, 4),
                ('DEER', 0.70, 0, 3),
                ('SHEEP', 0.55, 0, 2),
                ('CHICKEN', 0.35, 0, 1),
                ('BUTTERFLY', 0.80, 1, 3),
                ('BAT', 0.80, 1, 4),
                ('GOBLIN', 0.15, 0, 2),
                ('BANDIT', 0.04, 0, 1),
                ('WIZARD', 0.25, 1, 2),
                ('FARMER', 0.2, 0, 1),
                ('LUMBERJACK', 0.4, 0, 2),
                ('MINER', 0.7, 1, 3),
                ('TRADER', 0.5, 1, 2),
                ('BLACKSMITH', 0.6, 0, 1),
                ('GUARD', 0.7, 1, 2),
                ('WARRIOR', 0.40, 0, 2),
                ('BLACK_SPIDER', 0.22, 0, 1),
                ('RED_BIRD', 0.55, 0, 2),
            ],
            'LAKE': [
                ('DEER', 0.75, 1, 2),
                ('SHEEP', 0.55, 0, 2),
                ('CHICKEN', 0.65, 1, 2),
                ('BUTTERFLY', 0.90, 1, 4),
                ('BAT', 0.50, 0, 2),
                ('RED_BIRD', 0.85, 1, 3),
                ('WOLF', 0.20, 0, 1),
            ],
        }

        spawn_list = spawn_tables.get(biome_name, [])

        # Distance-based spawn rate reduction: -3% per zone of distance, floor 15%
        _dist = abs(screen_x - self.player['screen_x']) + abs(screen_y - self.player['screen_y'])
        _spawn_factor = max(0.0, 1.0 - _dist * 0.03)

        # Get actual entrance positions - only spawn AT entrances
        entrance_positions = []
        screen = self.screens[screen_key]
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2

        if screen['exits']['top']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, 1, 'top'))

        if screen['exits']['bottom']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, GRID_HEIGHT - 2, 'bottom'))

        if screen['exits']['left']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((1, y, 'left'))

        if screen['exits']['right']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((GRID_WIDTH - 2, y, 'right'))

        if not entrance_positions:
            entrance_positions = [(center_x, center_y, 'center')]

        # Spawn ONE entity per zone update based on spawn chances
        eligible_types = []
        for entity_type, spawn_chance, min_count, max_count in spawn_list:
            adjusted_chance = min(1.0, spawn_chance * 1.5) * _spawn_factor
            if random.random() < adjusted_chance:
                eligible_types.append(entity_type)

        if eligible_types:
            entity_type = random.choice(eligible_types)

            attempts = 0
            while attempts < 30:
                x, y, entrance = random.choice(entrance_positions)

                cell = self.screens[screen_key]['grid'][y][x]
                if not CELL_TYPES[cell]['solid']:
                    position_occupied = False
                    for existing_id in self.screen_entities.get(screen_key, []):
                        if existing_id in self.entities:
                            existing = self.entities[existing_id]
                            if existing.x == x and existing.y == y:
                                position_occupied = True
                                break

                    if not position_occupied:
                        entity_id = self.next_entity_id
                        self.next_entity_id += 1

                        entity = Entity(entity_type, x, y, screen_x, screen_y)
                        if entity_type in _HUMANOID_NPC_TYPES:
                            self._give_random_starting_inventory(entity)
                        self.entities[entity_id] = entity
                        self.screen_entities[screen_key].append(entity_id)

                        break
                attempts += 1

    # -------------------------------------------------------------------------
    # Specific entity spawns
    # -------------------------------------------------------------------------

    def spawn_skeleton(self, near_x, near_y):
        """Spawn a hostile skeleton entity near the specified position"""
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                test_x = near_x + dx
                test_y = near_y + dy
                if 0 <= test_x < GRID_WIDTH and 0 <= test_y < GRID_HEIGHT:
                    screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                    if screen_key in self.screens:
                        cell = self.screens[screen_key]['grid'][test_y][test_x]
                        if not CELL_TYPES[cell].get('solid', False):
                            skeleton = Entity('SKELETON', test_x, test_y,
                                              self.player['screen_x'],
                                              self.player['screen_y'], 1)

                            entity_id = self.next_entity_id
                            self.next_entity_id += 1
                            self.entities[entity_id] = skeleton

                            if screen_key not in self.screen_entities:
                                self.screen_entities[screen_key] = []
                            self.screen_entities[screen_key].append(entity_id)

                            return entity_id

        return None  # No space to spawn skeleton
        return None

    def spawn_quest_entity(self, entity_type, screen_x, screen_y, x, y):
        """Spawn an entity at a specific location for quests.

        Returns:
            entity_id if successful, None if failed
        """
        screen_key = f"{screen_x},{screen_y}"

        if screen_key not in self.screens:
            return None

        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            return None

        cell = self.screens[screen_key]['grid'][y][x]
        if CELL_TYPES[cell].get('solid', False):
            # Try to find nearby empty spot
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    test_x = x + dx
                    test_y = y + dy
                    if 0 <= test_x < GRID_WIDTH and 0 <= test_y < GRID_HEIGHT:
                        test_cell = self.screens[screen_key]['grid'][test_y][test_x]
                        if not CELL_TYPES[test_cell].get('solid', False):
                            x, y = test_x, test_y
                            break
                else:
                    continue
                break
            else:
                return None

        entity = Entity(entity_type, x, y, screen_x, screen_y, level=1)
        entity_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[entity_id] = entity

        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(entity_id)

        return entity_id

    def spawn_runestones_for_screen(self, screen_x, screen_y):
        """Spawn runestones rarely on base biome cells"""
        screen_key = f"{screen_x},{screen_y}"
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        grid = screen['grid']

        runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']

        if random.random() < 0.25:
            num_runes = random.randint(1, 2)

            for _ in range(num_runes):
                for attempt in range(20):
                    x = random.randint(3, GRID_WIDTH - 4)
                    y = random.randint(3, GRID_HEIGHT - 4)
                    cell = grid[y][x]

                    if cell in ['GRASS', 'DIRT', 'SAND', 'STONE']:
                        rune_type = random.choice(runestone_types)

                        if screen_key not in self.dropped_items:
                            self.dropped_items[screen_key] = {}

                        drop_key = (x, y)
                        if drop_key not in self.dropped_items[screen_key]:
                            self.dropped_items[screen_key][drop_key] = {}

                        amount = random.randint(1, 3)
                        self.dropped_items[screen_key][drop_key][rune_type] = \
                            self.dropped_items[screen_key][drop_key].get(rune_type, 0) + amount

                        break

    # -------------------------------------------------------------------------
    # Raid system
    # -------------------------------------------------------------------------

    def check_raid_event(self, screen_key):
        """Flat percent chance per zone update for a raid to trigger."""
        if screen_key not in self.screen_entities:
            return

        human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR', 'WIZARD']
        human_count = 0
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                base_type = self.entities[entity_id].type.replace('_double', '')
                if base_type in human_npc_types:
                    human_count += 1

        if human_count < RAID_POPULATION_THRESHOLD:
            return

        npcs_over_threshold = human_count - RAID_POPULATION_THRESHOLD
        raid_chance = min(RAID_CHANCE_BASE + npcs_over_threshold * 0.005, 0.10)

        # Each house/stone_house/mineshaft in the zone reduces raid chance (established zones safer)
        if screen_key in self.screens:
            grid = self.screens[screen_key]['grid']
            structure_count = sum(
                1 for row in grid for cell in row
                if cell in ('HOUSE', 'STONE_HOUSE', 'MINESHAFT')
            )
            raid_chance = max(0.0, raid_chance - structure_count * 0.01)

        if random.random() < raid_chance:
            self.trigger_raid(screen_key)

    def trigger_raid(self, screen_key):
        """Spawn a raid event in the zone"""
        if screen_key not in self.screens:
            return

        raid_types = [
            ('GOBLIN',      2),
            ('BANDIT',      2),
            ('WOLF',        3),
            ('BLACK_SPIDER', 3),
            ('SKELETON',    2),
            ('TERMITE',     4),
        ]
        raid_type, raid_count = random.choice(raid_types)

        cave_pos = None
        if random.random() < HIDDEN_CAVE_SPAWN_CHANCE:
            cave_pos = self.spawn_hidden_cave(screen_key)

        self.spawn_raid_group(screen_key, raid_type, raid_count, cave_pos)

        self.zone_has_hostiles[screen_key] = True


    def spawn_hidden_cave(self, screen_key):
        """Spawn a hidden cave in the zone, returns (x, y) or None"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        grid = screen['grid']

        # Don't spawn in zones that have a miner — miners manage their own caves
        if screen_key in self.screen_entities:
            for eid in self.screen_entities[screen_key]:
                if eid in self.entities and self.entities[eid].type == 'MINER':
                    return None

        # Enforce 2-cave cap per zone
        cave_count = sum(
            1 for row in grid for cell in row
            if cell in ('CAVE', 'HIDDEN_CAVE')
        )
        if cave_count >= 2:
            return None

        valid_positions = []
        for y in range(2, GRID_HEIGHT - 2):
            for x in range(2, GRID_WIDTH - 2):
                cell = grid[y][x]
                if not CELL_TYPES[cell].get('solid', False) and cell != 'WALL':
                    valid_positions.append((x, y))

        if not valid_positions:
            return None

        cave_x, cave_y = random.choice(valid_positions)
        grid[cave_y][cave_x] = 'HIDDEN_CAVE'

        return (cave_x, cave_y)

    def spawn_raid_group(self, screen_key, entity_type, count, cave_pos):
        """Spawn a group of raiders around cave or random location"""
        if screen_key not in self.screens:
            return

        screen_x, screen_y = map(int, screen_key.split(','))

        if cave_pos:
            center_x, center_y = cave_pos
        else:
            # Pick an entrance position (zone edge or adjacent to cave cell)
            screen = self.screens[screen_key]
            _cx = GRID_WIDTH // 2
            _cy = GRID_HEIGHT // 2
            _positions = []
            exits = screen.get('exits', {})
            if exits.get('top'):    _positions += [(x, 1)              for x in range(_cx - 1, _cx + 2)]
            if exits.get('bottom'): _positions += [(x, GRID_HEIGHT - 2) for x in range(_cx - 1, _cx + 2)]
            if exits.get('left'):   _positions += [(1, y)              for y in range(_cy - 1, _cy + 2)]
            if exits.get('right'):  _positions += [(GRID_WIDTH - 2, y) for y in range(_cy - 1, _cy + 2)]
            for _gy in range(GRID_HEIGHT):
                for _gx in range(GRID_WIDTH):
                    if screen['grid'][_gy][_gx] in ('CAVE', 'HIDDEN_CAVE', 'MINESHAFT'):
                        for _ddx, _ddy in ((-1,0),(1,0),(0,-1),(0,1)):
                            _nx, _ny = _gx + _ddx, _gy + _ddy
                            if 0 < _nx < GRID_WIDTH - 1 and 0 < _ny < GRID_HEIGHT - 1:
                                _positions.append((_nx, _ny))
            if _positions:
                center_x, center_y = random.choice(_positions)
            else:
                center_x, center_y = _cx, _cy

        spawned = 0
        attempts = 0
        max_attempts = count * 10

        while spawned < count and attempts < max_attempts:
            attempts += 1

            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            spawn_x = center_x + dx
            spawn_y = center_y + dy

            if spawn_x < 1 or spawn_x >= GRID_WIDTH - 1:
                continue
            if spawn_y < 1 or spawn_y >= GRID_HEIGHT - 1:
                continue

            cell = self.screens[screen_key]['grid'][spawn_y][spawn_x]
            if CELL_TYPES[cell].get('solid', False):
                continue

            if self.is_entity_at_position(spawn_x, spawn_y, screen_key):
                continue

            entity = Entity(entity_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = entity

            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)

            spawned += 1


    # -------------------------------------------------------------------------
    # Zone threat tracking
    # -------------------------------------------------------------------------

    def check_zone_clear_hostiles(self, screen_key):
        """Check if all hostiles are dead in zone and update flag"""
        if not self.zone_has_hostiles.get(screen_key, False):
            return

        if screen_key not in self.screen_entities:
            return

        has_hostiles = False
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.props.get('hostile', False):
                    has_hostiles = True
                    break

        if not has_hostiles:
            self.zone_has_hostiles[screen_key] = False

    def check_zone_threats(self, screen_key):
        """Efficiently check zone for hostiles and faction conflicts - called once per zone update"""
        if screen_key not in self.screen_entities:
            self.zone_has_hostiles[screen_key] = False
            self.zone_has_faction_conflict[screen_key] = False
            return

        has_hostiles = False
        factions_present = set()

        for entity_id in self.screen_entities[screen_key]:
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]

            if entity.props.get('hostile', False):
                has_hostiles = True

            if hasattr(entity, 'faction') and entity.faction:
                if entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD']:
                    factions_present.add(entity.faction)

        self.zone_has_hostiles[screen_key] = has_hostiles
        self.zone_has_faction_conflict[screen_key] = len(factions_present) > 1

    # -------------------------------------------------------------------------
    # Cave hostile spawning
    # -------------------------------------------------------------------------

    def check_cave_spawn_hostile(self, screen_key):
        """Check each cave in zone for chance to spawn hostile — bats favored in empty caves"""
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        grid = screen['grid']

        caves = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if grid[y][x] in ['CAVE', 'HIDDEN_CAVE']:
                    caves.append((x, y))

        if not caves:
            return

        zone_population = 0
        bat_count = 0
        if screen_key in self.screen_entities:
            for eid in self.screen_entities[screen_key]:
                if eid in self.entities and self.entities[eid].health > 0:
                    zone_population += 1
                    if self.entities[eid].type == 'BAT':
                        bat_count += 1

        for cave_x, cave_y in caves:
            base_chance = CAVE_HOSTILE_SPAWN_CHANCE

            if zone_population < 3:
                spawn_chance = 0.15
            elif zone_population < 6:
                spawn_chance = 0.05
            elif zone_population < 10:
                spawn_chance = base_chance * 2
            else:
                spawn_chance = base_chance

            if bat_count >= 4:
                spawn_chance *= 0.2

            if random.random() < spawn_chance:
                self.spawn_cave_hostile(screen_key, cave_x, cave_y)

    def spawn_cave_hostile(self, screen_key, cave_x, cave_y):
        """Spawn a hostile entity from a cave — bats are most common"""
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        screen_x, screen_y = map(int, screen_key.split(','))

        roll = random.random()
        if roll < 0.40:
            hostile_type = 'BAT'
        elif roll < 0.60:
            hostile_type = 'GOBLIN'
        elif roll < 0.80:
            hostile_type = 'WOLF'
        else:
            hostile_type = 'BANDIT'

        is_flying = ENTITY_TYPES.get(hostile_type, {}).get('flying', False)
        fly_blocked = {'WALL', 'CAVE_WALL', 'DEEP_WATER'}

        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            spawn_x = cave_x + dx
            spawn_y = cave_y + dy

            if not (0 < spawn_x < GRID_WIDTH - 1 and 0 < spawn_y < GRID_HEIGHT - 1):
                continue

            cell = screen['grid'][spawn_y][spawn_x]
            if CELL_TYPES[cell].get('solid', False):
                if not is_flying or cell in fly_blocked:
                    continue

            if self.is_entity_at_position(spawn_x, spawn_y, screen_key):
                continue

            entity = Entity(hostile_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = entity

            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)

            self.zone_has_hostiles[screen_key] = True
            return

    # -------------------------------------------------------------------------
    # Night skeleton spawning
    # -------------------------------------------------------------------------

    def check_night_skeleton_spawn(self, screen_key):
        """Check if skeleton should spawn at night (more likely near dropped items)"""
        if not self.is_night:
            return

        if screen_key not in self.screens:
            return

        zone_population = 0
        if screen_key in self.screen_entities:
            zone_population = len([eid for eid in self.screen_entities[screen_key]
                                    if eid in self.entities and self.entities[eid].health > 0])

        if zone_population >= 20:
            population_modifier = 0.1
        elif zone_population >= 15:
            population_modifier = 0.25
        elif zone_population >= 10:
            population_modifier = 0.5
        elif zone_population >= 5:
            population_modifier = 0.75
        else:
            population_modifier = 1.0

        spawn_chance = NIGHT_SKELETON_SPAWN_CHANCE * population_modifier

        if screen_key in self.dropped_items and self.dropped_items[screen_key]:
            spawn_chance *= 2.0

        if random.random() > spawn_chance:
            return

        screen = self.screens[screen_key]
        screen_x, screen_y = map(int, screen_key.split(','))

        spawn_positions = []

        if screen_key in self.dropped_items and self.dropped_items[screen_key]:
            for drop_pos in self.dropped_items[screen_key].keys():
                if isinstance(drop_pos, tuple):
                    drop_x, drop_y = drop_pos
                else:
                    parts = drop_pos.split(',')
                    drop_x, drop_y = int(parts[0]), int(parts[1])

                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        test_x = drop_x + dx
                        test_y = drop_y + dy
                        if 0 < test_x < GRID_WIDTH - 1 and 0 < test_y < GRID_HEIGHT - 1:
                            cell = screen['grid'][test_y][test_x]
                            if not CELL_TYPES[cell].get('solid', False):
                                if not self.is_entity_at_position(test_x, test_y, screen_key):
                                    spawn_positions.append((test_x, test_y))

        if not spawn_positions:
            for _ in range(10):
                test_x = random.randint(3, GRID_WIDTH - 4)
                test_y = random.randint(3, GRID_HEIGHT - 4)
                cell = screen['grid'][test_y][test_x]
                if not CELL_TYPES[cell].get('solid', False):
                    if not self.is_entity_at_position(test_x, test_y, screen_key):
                        spawn_positions.append((test_x, test_y))
                        break

        if spawn_positions:
            spawn_x, spawn_y = random.choice(spawn_positions)

            skeleton = Entity('SKELETON', spawn_x, spawn_y, screen_x, screen_y, level=1)
            skeleton.props = ENTITY_TYPES['SKELETON'].copy()
            skeleton.props['hostile'] = True
            skeleton.props['attacks_hostile'] = False

            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = skeleton

            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)

            self.zone_has_hostiles[screen_key] = True


    # -------------------------------------------------------------------------
    # Termite spawning
    # -------------------------------------------------------------------------

    def check_termite_spawn(self, screen_key):
        """Check if termite should spawn near trees (prefer FOREST/PLAINS biomes)"""
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        biome = screen.get('biome', 'FOREST')

        if biome == 'FOREST':
            biome_modifier = 2.0
        elif biome == 'PLAINS':
            biome_modifier = 1.0
        else:
            biome_modifier = 0.2

        zone_population = 0
        if screen_key in self.screen_entities:
            zone_population = len([eid for eid in self.screen_entities[screen_key]
                                    if eid in self.entities and self.entities[eid].health > 0])

        if zone_population >= 20:
            population_modifier = 0.1
        elif zone_population >= 15:
            population_modifier = 0.25
        elif zone_population >= 10:
            population_modifier = 0.5
        elif zone_population >= 5:
            population_modifier = 0.75
        else:
            population_modifier = 1.0

        spawn_chance = TERMITE_SPAWN_CHANCE * population_modifier * biome_modifier

        if random.random() > spawn_chance:
            return

        screen_x, screen_y = map(int, screen_key.split(','))

        tree_positions = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in ['TREE1', 'TREE2']:
                    tree_positions.append((x, y))

        if not tree_positions:
            if random.random() > 0.1:
                return

        spawn_positions = []

        if tree_positions:
            for tree_x, tree_y in tree_positions[:10]:
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        test_x = tree_x + dx
                        test_y = tree_y + dy

                        if 0 < test_x < GRID_WIDTH - 1 and 0 < test_y < GRID_HEIGHT - 1:
                            cell = screen['grid'][test_y][test_x]
                            if not CELL_TYPES[cell].get('solid', False):
                                if not self.is_entity_at_position(test_x, test_y, screen_key):
                                    spawn_positions.append((test_x, test_y))
        else:
            for _ in range(10):
                test_x = random.randint(3, GRID_WIDTH - 4)
                test_y = random.randint(3, GRID_HEIGHT - 4)
                cell = screen['grid'][test_y][test_x]
                if not CELL_TYPES[cell].get('solid', False):
                    if not self.is_entity_at_position(test_x, test_y, screen_key):
                        spawn_positions.append((test_x, test_y))
                        break

        if spawn_positions:
            spawn_x, spawn_y = random.choice(spawn_positions)

            termite = Entity('TERMITE', spawn_x, spawn_y, screen_x, screen_y, level=1)
            termite.props = ENTITY_TYPES['TERMITE'].copy()

            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = termite

            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)

            self.zone_has_hostiles[screen_key] = True


    # -------------------------------------------------------------------------
    # Continuous zone population maintenance
    # -------------------------------------------------------------------------

    def check_zone_spawning(self):
        """Check each nearby zone and spawn entities based on population and missing types"""
        player_screen_x = self.player['screen_x']
        player_screen_y = self.player['screen_y']
        player_zone_key = f"{player_screen_x},{player_screen_y}"

        # Check player zone specifically
        if player_zone_key in self.screens:
            entity_count = 0
            types_in_zone = set()
            for eid in self.screen_entities.get(player_zone_key, []):
                if eid in self.entities:
                    entity_count += 1
                    types_in_zone.add(self.entities[eid].type)

        spawns_this_cycle = 0
        max_spawns = 3

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if spawns_this_cycle >= max_spawns:
                    return

                zone_x = player_screen_x + dx
                zone_y = player_screen_y + dy
                screen_key = f"{zone_x},{zone_y}"

                if screen_key not in self.screens:
                    continue

                biome = self.screens[screen_key].get('biome', 'FOREST')

                entity_count = 0
                types_in_zone = set()
                for eid in self.screen_entities.get(screen_key, []):
                    if eid in self.entities:
                        entity_count += 1
                        types_in_zone.add(self.entities[eid].type)

                if entity_count == 0:
                    spawn_chance = 1.0
                elif entity_count < 5:
                    spawn_chance = 1.0 - (entity_count * 0.16)
                else:
                    spawn_chance = 0.10

                roll = random.random()

                if roll < spawn_chance:
                    spawn_tables = {
                        'FOREST': [
                            ('TRADER', 0.05), ('GUARD', 0.05),
                            ('LUMBERJACK', 0.20), ('FARMER', 0.18),
                            ('DEER', 0.15), ('WOLF', 0.10),
                            ('SHEEP', 0.08), ('GOBLIN', 0.03), ('BANDIT', 0.015),
                            ('RED_BIRD', 0.12), ('BUTTERFLY', 0.10), ('BLACK_SPIDER', 0.06)
                        ],
                        'PLAINS': [
                            ('TRADER', 0.05), ('GUARD', 0.05),
                            ('FARMER', 0.25), ('SHEEP', 0.18),
                            ('DEER', 0.12), ('LUMBERJACK', 0.08),
                            ('WOLF', 0.08), ('GOBLIN', 0.03), ('BANDIT', 0.015),
                            ('CHICKEN', 0.14), ('RED_BIRD', 0.10), ('BUTTERFLY', 0.12)
                        ],
                        'DESERT': [
                            ('TRADER', 0.05), ('GUARD', 0.05),
                            ('GOBLIN', 0.10), ('BANDIT', 0.075),
                            ('MINER', 0.18), ('FARMER', 0.10),
                            ('WOLF', 0.08), ('DEER', 0.06), ('SHEEP', 0.03),
                            ('BLACK_SPIDER', 0.08)
                        ],
                        'MOUNTAINS': [
                            ('TRADER', 0.05), ('GUARD', 0.05),
                            ('MINER', 0.22), ('GOBLIN', 0.09),
                            ('WOLF', 0.15), ('LUMBERJACK', 0.10),
                            ('BANDIT', 0.04), ('DEER', 0.04), ('SHEEP', 0.03),
                            ('BLACK_SPIDER', 0.08), ('RED_BIRD', 0.06)
                        ]
                    }

                    spawn_list = spawn_tables.get(biome, spawn_tables['FOREST'])

                    # Pick weighted random type to spawn
                    types = [t[0] for t in spawn_list]
                    weights = [t[1] for t in spawn_list]
                    entity_type = random.choices(types, weights=weights)[0]

                    success = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type=entity_type)

                    if success:
                        spawns_this_cycle += 1

    def spawn_single_entity_at_entrance(self, screen_x, screen_y, biome_name, force_type=None):
        """Spawn a single entity at a zone entrance.

        Args:
            force_type: If provided, spawn this specific entity type instead of choosing randomly
        """
        screen_key = f"{screen_x},{screen_y}"

        # Distance-based spawn rate reduction: -3% per zone of distance, floor 15%
        _dist = abs(screen_x - self.player['screen_x']) + abs(screen_y - self.player['screen_y'])
        _spawn_factor = max(0.0, 1.0 - _dist * 0.03)
        if random.random() > _spawn_factor:
            return None

        spawn_tables = {
            'FOREST': [
                ('DEER', 0.27), ('WOLF', 0.15), ('SHEEP', 0.12), ('CHICKEN', 0.08),
                ('BUTTERFLY', 0.35), ('BAT', 0.22),
                ('FARMER', 0.12), ('LUMBERJACK', 0.15),
                ('TRADER', 0.075), ('GUARD', 0.075),
                ('BANDIT', 0.018), ('GOBLIN', 0.018),
                ('RED_BIRD', 0.12), ('BLACK_SPIDER', 0.04)
            ],
            'PLAINS': [
                ('SHEEP', 0.30), ('DEER', 0.18), ('WOLF', 0.08), ('CHICKEN', 0.18),
                ('BUTTERFLY', 0.35), ('BAT', 0.18),
                ('FARMER', 0.18), ('LUMBERJACK', 0.05),
                ('TRADER', 0.075), ('GUARD', 0.075),
                ('BANDIT', 0.018), ('GOBLIN', 0.018),
                ('RED_BIRD', 0.10)
            ],
            'DESERT': [
                ('SHEEP', 0.15), ('DEER', 0.15), ('WOLF', 0.12), ('CHICKEN', 0.08),
                ('BUTTERFLY', 0.28), ('BAT', 0.22),
                ('GOBLIN', 0.07), ('BANDIT', 0.05), ('MINER', 0.10),
                ('FARMER', 0.07), ('LUMBERJACK', 0.04),
                ('TRADER', 0.09), ('GUARD', 0.06),
                ('BLACK_SPIDER', 0.05)
            ],
            'MOUNTAINS': [
                ('WOLF', 0.27), ('DEER', 0.15), ('SHEEP', 0.10), ('CHICKEN', 0.06),
                ('BUTTERFLY', 0.30), ('BAT', 0.30),
                ('GOBLIN', 0.06), ('BANDIT', 0.03), ('MINER', 0.14),
                ('FARMER', 0.03), ('LUMBERJACK', 0.09),
                ('TRADER', 0.06), ('GUARD', 0.04),
                ('BLACK_SPIDER', 0.05), ('RED_BIRD', 0.08)
            ],
            'LAKE': [
                ('DEER', 0.25), ('SHEEP', 0.18), ('CHICKEN', 0.20),
                ('BUTTERFLY', 0.35), ('BAT', 0.18),
                ('RED_BIRD', 0.28), ('WOLF', 0.08)
            ]
        }

        spawn_list = spawn_tables.get(biome_name, spawn_tables['FOREST'])

        if force_type:
            entity_type = force_type
        else:
            types = [t[0] for t in spawn_list]
            weights = [t[1] for t in spawn_list]
            entity_type = random.choices(types, weights=weights)[0]

        entrance_positions = []
        screen = self.screens[screen_key]
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2

        if screen['exits']['top']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, 1))

        if screen['exits']['bottom']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, GRID_HEIGHT - 2))

        if screen['exits']['left']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((1, y))

        if screen['exits']['right']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((GRID_WIDTH - 2, y))

        if not entrance_positions:
            entrance_positions = [(center_x, center_y)]

        for attempt in range(10):
            x, y = random.choice(entrance_positions)
            cell = screen['grid'][y][x]

            if not CELL_TYPES[cell]['solid']:
                entity_id = self.next_entity_id
                self.next_entity_id += 1

                entity = Entity(entity_type, x, y, screen_x, screen_y)
                if entity_type in _HUMANOID_NPC_TYPES:
                    self._give_random_starting_inventory(entity)
                self.entities[entity_id] = entity

                if screen_key not in self.screen_entities:
                    self.screen_entities[screen_key] = []
                self.screen_entities[screen_key].append(entity_id)

                return True

        return False

    # -------------------------------------------------------------------------
    # Structure evacuation
    # -------------------------------------------------------------------------

    def evacuate_subscreen(self, subscreen_key, parent_screen_key, structure_x, structure_y):
        """Move all entities and items from subscreen back to parent zone"""
        entities_to_evacuate = self.screen_entities.get(subscreen_key, []).copy()

        if not entities_to_evacuate:
            return

        parent_grid = self.screens.get(parent_screen_key, {}).get('grid', [])
        if not parent_grid:
            return

        exit_positions = []

        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_x = structure_x + dx
                check_y = structure_y + dy

                if dx == 0 and dy == 0:
                    continue

                if (0 <= check_y < GRID_HEIGHT and 0 <= check_x < GRID_WIDTH):
                    cell = parent_grid[check_y][check_x]
                    cell_props = CELL_TYPES.get(cell, {})
                    if not cell_props.get('solid', False):
                        exit_positions.append((check_x, check_y))

        if not exit_positions:
            exit_positions = [(structure_x, structure_y)]

        evacuated_count = 0
        for entity_id in entities_to_evacuate:
            if entity_id not in self.entities:
                continue

            entity = self.entities[entity_id]

            exit_x, exit_y = random.choice(exit_positions)

            entity.x = exit_x
            entity.y = exit_y
            entity.world_x = float(exit_x)
            entity.world_y = float(exit_y)

            coords = parent_screen_key.split(',')
            entity.screen_x = int(coords[0]) if len(coords) > 0 else 0
            entity.screen_y = int(coords[1]) if len(coords) > 1 else 0

            entity.in_subscreen = False
            entity.subscreen_key = None

            if parent_screen_key not in self.screen_entities:
                self.screen_entities[parent_screen_key] = []
            if entity_id not in self.screen_entities[parent_screen_key]:
                self.screen_entities[parent_screen_key].append(entity_id)

            evacuated_count += 1

        if subscreen_key in self.screen_entities:
            self.screen_entities[subscreen_key] = []

        if evacuated_count > 0:
            pass  # evacuation complete

    def deinstantiate_structure_zone(self, zone_key):
        """Remove an orphaned structure zone from all registries."""
        # Evict any entities in this zone to the parent overworld zone
        parent_info = self.structure_zones.get(zone_key, {})
        parent_key = parent_info.get('parent_zone')
        if zone_key in self.screen_entities:
            for eid in list(self.screen_entities[zone_key]):
                if eid in self.entities:
                    e = self.entities[eid]
                    if parent_key and parent_key in self.screens:
                        e.screen_x, e.screen_y = map(int, parent_key.split(','))
                        e.in_structure = False
                        e.structure_key = None
                        if parent_key not in self.screen_entities:
                            self.screen_entities[parent_key] = []
                        if eid not in self.screen_entities[parent_key]:
                            self.screen_entities[parent_key].append(eid)
            del self.screen_entities[zone_key]
        # Remove from all zone registries
        self.screens.pop(zone_key, None)
        self.structures.pop(zone_key, None)
        self.instantiated_zones.discard(zone_key)
        self.screen_last_update.pop(zone_key, None)
        self.structure_zones.pop(zone_key, None)
        if parent_key and zone_key in self.zone_structures.get(parent_key, []):
            self.zone_structures[parent_key].remove(zone_key)
        # Remove door_map entries that reference this zone
        for dk in [k for k in self.door_map if k[0] == zone_key or self.door_map[k][0] == zone_key]:
            self.door_map.pop(dk, None)
        # Remove zone_connections entries
        self.zone_connections.pop(zone_key, None)
        if parent_key in self.zone_connections:
            self.zone_connections[parent_key] = [
                c for c in self.zone_connections[parent_key] if c[0] != zone_key
            ]

    def process_house_destruction(self, x, y, screen_key):
        """Handle house/structure destruction: evacuate entities and de-instantiate the zone."""
        # Find structure zone linked to this cell
        target_zone = None
        for zone_key, sz_data in list(self.structure_zones.items()):
            if sz_data.get('parent_zone') == screen_key and sz_data.get('cell') == (x, y):
                target_zone = zone_key
                break
        if target_zone:
            self.deinstantiate_structure_zone(target_zone)
