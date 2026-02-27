import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, ENTITY_TYPES,
    RAID_CHECK_INTERVAL, RAID_CHANCE_BASE, RAID_POPULATION_THRESHOLD,
    HIDDEN_CAVE_SPAWN_CHANCE,
    CAVE_HOSTILE_SPAWN_CHANCE,
    NIGHT_SKELETON_SPAWN_CHANCE,
    TERMITE_SPAWN_CHANCE,
)
from entity import Entity


class SpawningMixin:
    """Handles all entity spawning: initial zone population, raids, cave hostiles,
    night skeletons, termites, runestones, and quest entities."""

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
                ('DEER', 0.5, 1, 2),
                ('WOLF', 0.3, 0, 2),
                ('SHEEP', 0.2, 0, 1),
                ('FARMER', 0.5, 0, 2),
                ('LUMBERJACK', 0.6, 1, 2),
                ('WIZARD', 0.25, 1, 2),
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.5, 0, 1),
                ('GUARD', 1.0, 1, 2),     # Always spawn
                ('BANDIT', 0.2, 0, 1),
                ('GOBLIN', 0.3, 0, 2),
                ('TERMITE', 0.4, 0, 2)    # Termites love forests (trees)
            ],
            'PLAINS': [
                ('SHEEP', 0.6, 1, 3),
                ('DEER', 0.4, 0, 2),
                ('WOLF', 0.2, 0, 1),
                ('FARMER', 0.7, 1, 3),
                ('LUMBERJACK', 0.3, 0, 1),
                ('WIZARD', 0.25, 1, 2),
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.5, 0, 1),
                ('GUARD', 1.0, 1, 2),     # Always spawn
                ('BANDIT', 0.2, 0, 1),
                ('GOBLIN', 0.2, 0, 1),
                ('TERMITE', 0.2, 0, 1)    # Some termites in plains
            ],
            'DESERT': [
                ('SHEEP', 0.2, 0, 1),
                ('DEER', 0.2, 0, 1),
                ('WOLF', 0.2, 0, 1),
                ('GOBLIN', 0.7, 1, 3),
                ('BANDIT', 0.5, 0, 2),
                ('WIZARD', 0.25, 1, 2),
                ('FARMER', 0.3, 0, 1),
                ('LUMBERJACK', 0.2, 0, 1),
                ('MINER', 0.5, 0, 2),
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.4, 0, 1),
                ('GUARD', 1.0, 1, 2)      # Always spawn
            ],
            'MOUNTAINS': [
                ('WOLF', 0.6, 1, 3),
                ('DEER', 0.3, 0, 2),
                ('SHEEP', 0.2, 0, 1),
                ('GOBLIN', 0.6, 1, 3),
                ('BANDIT', 0.3, 0, 2),
                ('WIZARD', 0.25, 1, 2),
                ('FARMER', 0.2, 0, 1),
                ('LUMBERJACK', 0.4, 0, 2),
                ('MINER', 0.7, 1, 3),
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.6, 0, 1),
                ('GUARD', 1.0, 1, 2)      # Always spawn
            ]
        }

        spawn_list = spawn_tables.get(biome_name, [])

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
            adjusted_chance = min(1.0, spawn_chance * 1.5)
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
                        self.entities[entity_id] = entity
                        self.screen_entities[screen_key].append(entity_id)

                        if random.random() < 0.1:
                            print(f"{entity_type} has arrived at [{screen_key}]")
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

                            print(f"A skeleton rises from the bones!")
                            return entity_id

        print("No space to spawn skeleton!")
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
        """Check if a raid event should occur in this zone"""
        if screen_key in self.zone_last_raid_check:
            if self.tick - self.zone_last_raid_check[screen_key] < RAID_CHECK_INTERVAL:
                return

        self.zone_last_raid_check[screen_key] = self.tick

        if screen_key not in self.screen_entities:
            return

        human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR', 'WIZARD']
        human_count = 0
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                base_type = entity.type.replace('_double', '')
                if base_type in human_npc_types:
                    human_count += 1

        if human_count < RAID_POPULATION_THRESHOLD:
            return

        if self.zone_has_hostiles.get(screen_key, False):
            return

        npcs_over_threshold = human_count - RAID_POPULATION_THRESHOLD
        raid_chance = RAID_CHANCE_BASE + (npcs_over_threshold * 0.05)
        raid_chance = min(raid_chance, 0.80)

        if random.random() < raid_chance:
            self.trigger_raid(screen_key)

    def trigger_raid(self, screen_key):
        """Spawn a raid event in the zone"""
        if screen_key not in self.screens:
            return

        raid_types = [
            ('GOBLIN', 2),
            ('BANDIT', 2),
            ('WOLF', 3)
        ]
        raid_type, raid_count = random.choice(raid_types)

        cave_pos = None
        if random.random() < HIDDEN_CAVE_SPAWN_CHANCE:
            cave_pos = self.spawn_hidden_cave(screen_key)

        self.spawn_raid_group(screen_key, raid_type, raid_count, cave_pos)

        self.zone_has_hostiles[screen_key] = True

        print(f"RAID! {raid_count} {raid_type}s attack zone [{screen_key}]!")

    def spawn_hidden_cave(self, screen_key):
        """Spawn a hidden cave in the zone, returns (x, y) or None"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        grid = screen['grid']

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

        print(f"A hidden cave appears at ({cave_x}, {cave_y}) in [{screen_key}]!")
        return (cave_x, cave_y)

    def spawn_raid_group(self, screen_key, entity_type, count, cave_pos):
        """Spawn a group of raiders around cave or random location"""
        if screen_key not in self.screens:
            return

        screen_x, screen_y = map(int, screen_key.split(','))

        if cave_pos:
            center_x, center_y = cave_pos
        else:
            center_x = random.randint(4, GRID_WIDTH - 5)
            center_y = random.randint(4, GRID_HEIGHT - 5)

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

        print(f"Spawned {spawned} {entity_type}s at ({center_x}, {center_y})")

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
            print(f"Zone [{screen_key}] cleared of hostiles!")

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
                if grid[y][x] in ['CAVE', 'HIDDEN_CAVE', 'MINESHAFT']:
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

            print(f"A skeleton rises from the darkness in [{screen_key}]!")

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

            print(f"A termite appears near trees in [{screen_key}]!")

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
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('LUMBERJACK', 0.20), ('FARMER', 0.18),
                            ('DEER', 0.15), ('WOLF', 0.10),
                            ('SHEEP', 0.08), ('GOBLIN', 0.06), ('BANDIT', 0.03)
                        ],
                        'PLAINS': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('FARMER', 0.25), ('SHEEP', 0.18),
                            ('DEER', 0.12), ('LUMBERJACK', 0.08),
                            ('WOLF', 0.08), ('GOBLIN', 0.06), ('BANDIT', 0.03)
                        ],
                        'DESERT': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('GOBLIN', 0.20), ('BANDIT', 0.15),
                            ('MINER', 0.18), ('FARMER', 0.10),
                            ('WOLF', 0.08), ('DEER', 0.06), ('SHEEP', 0.03)
                        ],
                        'MOUNTAINS': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('MINER', 0.22), ('GOBLIN', 0.18),
                            ('WOLF', 0.15), ('LUMBERJACK', 0.10),
                            ('BANDIT', 0.08), ('DEER', 0.04), ('SHEEP', 0.03)
                        ]
                    }

                    spawn_list = spawn_tables.get(biome, spawn_tables['FOREST'])

                    # PRIORITY 1: Spawn missing essential types (TRADER, GUARD)
                    essential_types = ['TRADER', 'GUARD']
                    for essential_type in essential_types:
                        if essential_type not in types_in_zone:
                            success = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type=essential_type)
                            if success:
                                spawns_this_cycle += 1
                                return

                    # PRIORITY 2: Pick weighted random type to spawn
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

        spawn_tables = {
            'FOREST': [
                ('DEER', 0.18), ('WOLF', 0.10), ('SHEEP', 0.05),
                ('FARMER', 0.12), ('LUMBERJACK', 0.15),
                ('TRADER', 0.15), ('GUARD', 0.15),
                ('BANDIT', 0.05), ('GOBLIN', 0.05)
            ],
            'PLAINS': [
                ('SHEEP', 0.20), ('DEER', 0.12), ('WOLF', 0.05),
                ('FARMER', 0.18), ('LUMBERJACK', 0.05),
                ('TRADER', 0.15), ('GUARD', 0.15),
                ('BANDIT', 0.05), ('GOBLIN', 0.05)
            ],
            'DESERT': [
                ('GOBLIN', 0.20), ('BANDIT', 0.14), ('MINER', 0.10),
                ('SHEEP', 0.05), ('DEER', 0.05), ('WOLF', 0.05),
                ('FARMER', 0.07), ('LUMBERJACK', 0.04),
                ('TRADER', 0.18), ('GUARD', 0.12)
            ],
            'MOUNTAINS': [
                ('WOLF', 0.18), ('GOBLIN', 0.16), ('MINER', 0.14),
                ('BANDIT', 0.09), ('DEER', 0.07), ('SHEEP', 0.04),
                ('FARMER', 0.03), ('LUMBERJACK', 0.09),
                ('TRADER', 0.12), ('GUARD', 0.08)
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
                self.entities[entity_id] = entity

                if screen_key not in self.screen_entities:
                    self.screen_entities[screen_key] = []
                self.screen_entities[screen_key].append(entity_id)

                if random.random() < 0.05:
                    print(f"{entity_type} arrived at [{screen_key}]")
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
            print(f"  Evacuated {evacuated_count} entities from destroyed structure")

    def process_house_destruction(self, x, y, screen_key):
        """Handle house destruction with proper NPC/item evacuation"""
        subscreen_key = f"{screen_key}_{x}_{y}_HOUSE_INTERIOR"

        if subscreen_key in self.subscreens:
            self.evacuate_subscreen(subscreen_key, screen_key, x, y)

        if subscreen_key in self.subscreens:
            del self.subscreens[subscreen_key]

        if subscreen_key in self.screen_entities:
            del self.screen_entities[subscreen_key]
