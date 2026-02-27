import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, BIOMES,
    # Cellular automata rates
    DIRT_TO_GRASS_RATE, GRASS_TO_DIRT_RATE, DIRT_TO_SAND_RATE,
    TREE_GROWTH_RATE, TREE_DECAY_RATE,
    SAND_RECLAIM_RATE,
    FLOWER_SPREAD_RATE, FLOWER_DECAY_RATE,
    DEEP_WATER_FORM_RATE, DEEP_WATER_EVAPORATE_RATE,
    WATER_TO_DIRT_RATE, FLOODING_RATE,
    # Rain
    RAIN_WATER_SPAWNS, RAIN_GRASS_SPAWNS,
    RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX,
    RAIN_DURATION_MIN, RAIN_DURATION_MAX,
    # Day/night
    DAY_LENGTH, NIGHT_LENGTH,
)


class CellsMixin:
    """Handles cellular automata, rain effects, weather cycles, day/night,
    and cell neighbour utilities."""

    # -------------------------------------------------------------------------
    # Neighbour utilities
    # -------------------------------------------------------------------------

    def get_neighbors(self, x, y, screen_key):
        """Get all 8 neighbours of a cell"""
        if screen_key not in self.screens:
            return []

        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                    neighbors.append(self.screens[screen_key]['grid'][ny][nx])
        return neighbors

    def count_cell_type(self, neighbors, cell_type):
        """Count how many neighbours match a cell type (or start with it)"""
        if not neighbors:
            return 0
        return sum(1 for n in neighbors
                   if n == cell_type or (isinstance(n, str) and n.startswith(cell_type)))

    def is_at_exit(self, x, y):
        """Check if position is at a zone exit (2-tile areas)"""
        if y == 0 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'top'
        if y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'bottom'
        if x == 0 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'left'
        if x == GRID_WIDTH - 1 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'right'
        return False, None

    def get_adjacent_screen_biome(self, screen_x, screen_y, direction):
        """Get the biome of an adjacent screen"""
        adj_x, adj_y = screen_x, screen_y
        if direction == 'top':
            adj_y -= 1
        elif direction == 'bottom':
            adj_y += 1
        elif direction == 'left':
            adj_x -= 1
        elif direction == 'right':
            adj_x += 1

        adj_key = f"{adj_x},{adj_y}"
        if adj_key in self.screens:
            return self.screens[adj_key]['biome']

        # Deterministic fallback without generating a full screen
        biome_types = list(BIOMES.keys())
        biome_index = abs(adj_x + adj_y * 3) % len(biome_types)
        return biome_types[biome_index]

    # -------------------------------------------------------------------------
    # Cellular automata
    # -------------------------------------------------------------------------

    def apply_cellular_automata(self, screen_x, screen_y):
        """Apply cellular automata rules to a screen"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        new_grid = [row[:] for row in screen['grid']]  # shallow copy per row

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]

                if cell in ['WALL', 'HOUSE', 'CAVE']:
                    continue

                if self.is_cell_enchanted(x, y, key):
                    continue

                # Cross-zone biome spreading at exits
                at_exit, direction = self.is_at_exit(x, y)
                if at_exit:
                    adj_biome = self.get_adjacent_screen_biome(screen_x, screen_y, direction)
                    if adj_biome != screen['biome'] and random.random() < 0.01:
                        new_grid[y][x] = self.get_common_cell_for_biome(adj_biome)
                        continue

                if x == 0 or x == GRID_WIDTH - 1 or y == 0 or y == GRID_HEIGHT - 1:
                    continue

                neighbors = self.get_neighbors(x, y, key)
                if not neighbors:
                    continue

                water_count = self.count_cell_type(neighbors, 'WATER')
                deep_water_count = self.count_cell_type(neighbors, 'DEEP_WATER')
                dirt_count = self.count_cell_type(neighbors, 'DIRT')
                grass_count = self.count_cell_type(neighbors, 'GRASS')
                tree_count = self.count_cell_type(neighbors, 'TREE')
                sand_count = self.count_cell_type(neighbors, 'SAND')
                flower_count = self.count_cell_type(neighbors, 'FLOWER')

                total_water = water_count + deep_water_count

                # Dirt → Grass (needs water)
                if cell == 'DIRT' and total_water >= 2:
                    if random.random() < DIRT_TO_GRASS_RATE:
                        new_grid[y][x] = 'GRASS'

                # Grass → Dirt (lack of water)
                elif cell == 'GRASS' and total_water == 0:
                    if random.random() < GRASS_TO_DIRT_RATE:
                        new_grid[y][x] = 'DIRT'

                # Dirt → Sand (severe drought)
                elif cell == 'DIRT' and total_water == 0 and (sand_count >= 2 or grass_count == 0):
                    if random.random() < DIRT_TO_SAND_RATE:
                        new_grid[y][x] = 'SAND'

                # Tree spread (needs grass and water)
                elif cell == 'GRASS' and 1 <= tree_count <= 2 and total_water >= 1:
                    if random.random() < TREE_GROWTH_RATE:
                        new_grid[y][x] = 'TREE1'

                # Sand reclamation (water converts sand back to dirt)
                elif cell == 'SAND' and total_water >= 2:
                    if random.random() < SAND_RECLAIM_RATE:
                        new_grid[y][x] = 'DIRT'

                # Deep water formation (lakes)
                elif cell == 'WATER' and water_count >= 4:
                    if random.random() < DEEP_WATER_FORM_RATE:
                        new_grid[y][x] = 'DEEP_WATER'

                # Deep water evaporation
                elif cell == 'DEEP_WATER' and (water_count + deep_water_count) < 2:
                    if random.random() < DEEP_WATER_EVAPORATE_RATE:
                        new_grid[y][x] = 'WATER'

                # Water evaporation (slow decay to dirt without water neighbours)
                elif cell == 'WATER' and total_water <= 1:
                    if random.random() < WATER_TO_DIRT_RATE:
                        new_grid[y][x] = 'DIRT'

                # Flooding (water spreads to dirt when abundant)
                elif cell == 'DIRT' and total_water >= 3:
                    if random.random() < FLOODING_RATE:
                        new_grid[y][x] = 'WATER'

                # Flower spread
                elif cell == 'GRASS' and 1 <= flower_count <= 2 and total_water >= 1:
                    if random.random() < FLOWER_SPREAD_RATE:
                        new_grid[y][x] = 'FLOWER'

                # Flower death (overcrowding or drought)
                elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
                    if random.random() < FLOWER_DECAY_RATE:
                        new_grid[y][x] = 'GRASS'

                # Tree overcrowding death
                elif cell.startswith('TREE') and tree_count >= 4:
                    if random.random() < TREE_DECAY_RATE:
                        new_grid[y][x] = 'GRASS'

                # Dirt invaded by grass or desert
                elif cell == 'DIRT':
                    if grass_count >= 3 and random.random() < 0.001:
                        new_grid[y][x] = 'GRASS'
                    elif sand_count >= 3 and random.random() < 0.001:
                        new_grid[y][x] = 'SAND'

                # Wood decay to dirt (outside structures)
                elif cell == 'WOOD' and not self.is_near_structure(x, y, key):
                    if random.random() < 0.05:
                        new_grid[y][x] = 'DIRT'

                # Planks decay to dirt (outside structures)
                elif cell == 'PLANKS' and not self.is_near_structure(x, y, key):
                    if random.random() < 0.03:
                        new_grid[y][x] = 'DIRT'

                # Crop decay without rain (drought)
                elif cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                    last_rain = self.zone_last_rain.get(key, 0)
                    ticks_since_rain = self.tick - last_rain

                    has_farmer = any(
                        self.entities[eid].type == 'FARMER'
                        for eid in self.screen_entities.get(key, [])
                        if eid in self.entities
                    )

                    decay_rate = 0.0001
                    if ticks_since_rain > 1200:
                        decay_rate = 0.001
                    if ticks_since_rain > 3600:
                        decay_rate = 0.01
                    if not has_farmer:
                        decay_rate *= 2.0

                    if random.random() < decay_rate:
                        new_grid[y][x] = 'DIRT'

        screen['grid'] = new_grid

        self.check_zone_biome_shift(screen_x, screen_y)

    # -------------------------------------------------------------------------
    # Rain
    # -------------------------------------------------------------------------

    def apply_rain(self, screen_x, screen_y):
        """Apply rain effects — convert some cells to water, dirt to grass (biome-specific)"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        self.zone_last_rain[key] = self.tick

        screen = self.screens[key]
        biome = screen.get('biome', 'FOREST')

        rain_multiplier = 1.0
        if biome == 'DESERT':
            rain_multiplier = 0.1
        elif biome == 'MOUNTAINS':
            rain_multiplier = 0.3
        elif biome == 'PLAINS':
            rain_multiplier = 1.2

        water_spawns = int(RAIN_WATER_SPAWNS * rain_multiplier)
        for _ in range(water_spawns):
            x = random.randint(1, GRID_WIDTH - 2)
            y = random.randint(1, GRID_HEIGHT - 2)
            cell = screen['grid'][y][x]
            if cell in ['DIRT', 'SAND'] and not self.is_cell_enchanted(x, y, key):
                if random.random() < 0.3:
                    screen['grid'][y][x] = 'WATER'

        grass_spawns = int(RAIN_GRASS_SPAWNS * rain_multiplier)
        for _ in range(grass_spawns):
            x = random.randint(1, GRID_WIDTH - 2)
            y = random.randint(1, GRID_HEIGHT - 2)
            cell = screen['grid'][y][x]
            if cell == 'DIRT' and not self.is_cell_enchanted(x, y, key):
                if random.random() < 0.4:
                    screen['grid'][y][x] = 'GRASS'

    # -------------------------------------------------------------------------
    # Weather
    # -------------------------------------------------------------------------

    def update_weather(self):
        """Update weather system — rain cycles"""
        self.weather_timer += 1

        if self.weather_timer >= self.weather_cycle:
            self.weather_timer = 0
            self.weather_cycle = random.randint(RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX)
            self.is_raining = True
            self.rain_duration = random.randint(RAIN_DURATION_MIN, RAIN_DURATION_MAX)
            self.rain_timer = 0

        if self.is_raining:
            self.rain_timer += 1
            if self.rain_timer >= self.rain_duration:
                self.is_raining = False
                self.rain_timer = 0

    # -------------------------------------------------------------------------
    # Day / night cycle
    # -------------------------------------------------------------------------

    def update_day_night_cycle(self):
        """Update day/night cycle — equal day and night lengths"""
        self.day_night_timer += 1

        full_cycle = DAY_LENGTH + NIGHT_LENGTH
        if self.day_night_timer >= full_cycle:
            self.day_night_timer = 0

        old_is_night = self.is_night
        self.is_night = self.day_night_timer >= DAY_LENGTH

        if self.is_night and not old_is_night:
            print("Night falls...")
        elif not self.is_night and old_is_night:
            print("Dawn breaks...")

    # -------------------------------------------------------------------------
    # Item logistics
    # -------------------------------------------------------------------------

    def move_items_to_nearest_chest(self):
        """Gradually move dropped items to nearest chests (every 10 seconds)"""
        if self.tick % 600 != 0:
            return

        player_x = self.player['screen_x']
        player_y = self.player['screen_y']

        for dx in range(-2, 3):
            for dy in range(-2, 3):
                zone_key = f"{player_x + dx},{player_y + dy}"

                if zone_key not in self.dropped_items or zone_key not in self.screens:
                    continue

                screen = self.screens[zone_key]
                dropped_in_zone = self.dropped_items[zone_key]

                if not dropped_in_zone:
                    continue

                chests = [
                    (x, y)
                    for y in range(GRID_HEIGHT)
                    for x in range(GRID_WIDTH)
                    if screen['grid'][y][x] == 'CHEST'
                ]

                if not chests:
                    continue

                items_to_move = list(dropped_in_zone.keys())
                if items_to_move and random.random() < 0.05:
                    pile_pos = random.choice(items_to_move)
                    items_in_pile = dropped_in_zone[pile_pos]

                    if not items_in_pile:
                        continue

                    nearest_chest = min(chests,
                                        key=lambda c: abs(c[0] - pile_pos[0]) + abs(c[1] - pile_pos[1]))

                    item_name = random.choice(list(items_in_pile.keys()))

                    chest_key = f"{zone_key}_{nearest_chest[0]}_{nearest_chest[1]}"
                    if chest_key not in self.chest_contents:
                        self.chest_contents[chest_key] = {}

                    self.chest_contents[chest_key][item_name] = \
                        self.chest_contents[chest_key].get(item_name, 0) + 1

                    items_in_pile[item_name] -= 1
                    if items_in_pile[item_name] <= 0:
                        del items_in_pile[item_name]

                    if not items_in_pile:
                        del dropped_in_zone[pile_pos]
