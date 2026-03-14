import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, BIOMES,
    # Cellular automata rates
    DIRT_TO_GRASS_RATE, GRASS_TO_DIRT_RATE, DIRT_TO_SAND_RATE,
    TREE_GROWTH_RATE, TREE_DECAY_RATE, TREE_CROWD_DECAY_RATE,
    SAND_RECLAIM_RATE, CACTUS_DROUGHT_RATE, TREE_DROUGHT_RATE,
    FLOWER_SPREAD_RATE, FLOWER_DECAY_RATE,
    DEEP_WATER_FORM_RATE, DEEP_WATER_EVAPORATE_RATE,
    WATER_TO_DIRT_RATE, FLOODING_RATE,
    BIOME_SPREAD_RATE,
    GRASS_SAND_DECAY_RATE, DIRT_SAND_SPREAD_RATE,
    GRASS_WATER_ABSORB_RATE, DIRT_WATER_EXTRA_GRASS_RATE,
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

    def apply_cellular_automata(self, screen_x, screen_y, cell_coverage=1.0):
        """Apply cellular automata rules to a screen.

        cell_coverage: fraction of cells to process this cycle (0.0–1.0).
        1.0 = all cells, 0.5 = half skipped at random (player zone default), etc.
        """
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        new_grid = [row[:] for row in screen['grid']]  # shallow copy per row
        biome = screen.get('biome', 'FOREST')

        _tp = getattr(self, 'time_pass_speed', 1.0)

        # Drought modifier: growth slows and decay accelerates the longer it hasn't rained.
        # Full drought severity is reached at 9000 ticks (~2.5 min) without rain.
        drought_ticks = self.tick - self.zone_last_rain.get(key, self.tick)
        drought_severity = min(drought_ticks / 9000.0, 1.0)   # 0.0 = just rained, 1.0 = max drought
        _growth = max(0.1, 1.0 - drought_severity * 0.9) * _tp  # decays to 10% of base at max drought
        _decay  = (1.0 + drought_severity * 0.5) * _tp           # rises to 1.5x base at max drought

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                # Per-cell coverage skip: probability decreases down the priority queue
                if random.random() > cell_coverage:
                    continue

                cell = screen['grid'][y][x]

                if cell in ['WALL', 'HOUSE', 'CAVE', 'CLIFF']:
                    continue

                if self.is_cell_enchanted(x, y, key):
                    continue

                # Zone entrance cells are seeded with the adjacent zone's primary biome cell.
                # Only update if the cell is not already that type; otherwise leave it
                # untouched so normal probabilistic rules govern it from there.
                at_exit, direction = self.is_at_exit(x, y)
                if at_exit:
                    offsets = {'top': (0, -1), 'bottom': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
                    dx, dy = offsets.get(direction, (0, 0))
                    adj_key = f"{screen_x + dx},{screen_y + dy}"
                    if adj_key in self.screens:
                        adj_biome = self.screens[adj_key].get('biome', screen['biome'])
                        _primary = {'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
                                    'MOUNTAINS': 'DIRT', 'LAKE': 'WATER'}
                        target = _primary.get(adj_biome)
                        if target and cell != target:
                            new_grid[y][x] = target
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
                cobblestone_count = self.count_cell_type(neighbors, 'COBBLESTONE')

                total_water = water_count + deep_water_count

                # Dirt → Water (flooding, rain only — highest priority for dirt)
                if cell == 'DIRT' and total_water >= 3 and self.is_raining:
                    if random.random() < min(1.0, FLOODING_RATE * _tp):
                        new_grid[y][x] = 'WATER'

                # Sand → Water (rain flooding — 2x dirt rate; sand absorbs water faster)
                elif cell == 'SAND' and total_water >= 3 and self.is_raining:
                    if random.random() < min(1.0, FLOODING_RATE * 2.0 * _tp):
                        new_grid[y][x] = 'WATER'

                # Dirt → Grass (water >= 2)
                elif cell == 'DIRT' and total_water >= 2:
                    if random.random() < min(1.0, DIRT_TO_GRASS_RATE * _growth):
                        new_grid[y][x] = 'GRASS'

                # Dirt → Grass (water == 1, extra small chance)
                elif cell == 'DIRT' and total_water == 1 and sand_count == 0:
                    if random.random() < min(1.0, DIRT_WATER_EXTRA_GRASS_RATE * _growth):
                        new_grid[y][x] = 'GRASS'

                # Dirt → Sand (any sand neighbor, no water — desertification spread)
                elif cell == 'DIRT' and total_water == 0 and sand_count >= 1:
                    if random.random() < min(1.0, DIRT_SAND_SPREAD_RATE * _decay):
                        new_grid[y][x] = 'SAND'

                # Dirt → Sand (severe drought, no grass at all — original fallback)
                elif cell == 'DIRT' and total_water == 0 and grass_count == 0:
                    if random.random() < min(1.0, DIRT_TO_SAND_RATE * _decay):
                        new_grid[y][x] = 'SAND'

                # Grass → Dirt (sand erosion — desertification edge, higher rate)
                elif cell == 'GRASS' and sand_count >= 1:
                    if random.random() < min(1.0, GRASS_SAND_DECAY_RATE * _decay):
                        new_grid[y][x] = 'DIRT'

                # Grass → Dirt (drought, no water)
                elif cell == 'GRASS' and total_water == 0:
                    if random.random() < min(1.0, GRASS_TO_DIRT_RATE * _decay):
                        new_grid[y][x] = 'DIRT'

                # Tree spread (needs grass, water, no cobblestone, and not desert)
                elif cell == 'GRASS' and biome != 'DESERT' and cobblestone_count == 0 and 1 <= tree_count <= 2 and total_water >= 1:
                    if random.random() < min(1.0, TREE_GROWTH_RATE * _growth):
                        new_grid[y][x] = 'TREE1'

                # Sand → Dirt (any water neighbor — universal rule, supercedes biome-specific rules)
                elif cell == 'SAND' and total_water >= 1:
                    if random.random() < min(1.0, SAND_RECLAIM_RATE * _growth):
                        new_grid[y][x] = 'DIRT'

                # Sand → Dirt (grass neighbor — vegetation slowly reclaims desert edges)
                # Half the water-reclaim rate so deserts don't erode too quickly
                elif cell == 'SAND' and grass_count >= 1:
                    if random.random() < min(1.0, SAND_RECLAIM_RATE * 0.5 * _growth):
                        new_grid[y][x] = 'DIRT'

                # Deep water formation: all 4 cardinal neighbors must be water/deepwater
                elif cell == 'WATER':
                    cardinal_water = sum(
                        1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                        and screen['grid'][y + cdy][x + cdx] in ('WATER', 'DEEP_WATER')
                    )
                    if cardinal_water == 4 and random.random() < min(1.0, DEEP_WATER_FORM_RATE * _tp):
                        new_grid[y][x] = 'DEEP_WATER'
                    elif total_water <= 1 and random.random() < min(1.0, WATER_TO_DIRT_RATE * _decay):
                        new_grid[y][x] = 'DIRT'

                # Deep water evaporation — mirrors formation: requires all 4 cardinal
                # neighbors to be water/deep_water to stay deep; decays quickly otherwise
                elif cell == 'DEEP_WATER':
                    cardinal_water_dw = sum(
                        1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                        and screen['grid'][y + cdy][x + cdx] in ('WATER', 'DEEP_WATER')
                    )
                    if cardinal_water_dw < 4 and random.random() < min(1.0, DEEP_WATER_EVAPORATE_RATE * _decay):
                        new_grid[y][x] = 'WATER'

                # Flower spread
                elif cell == 'GRASS' and 1 <= flower_count <= 2 and total_water >= 1:
                    if random.random() < min(1.0, FLOWER_SPREAD_RATE * _growth):
                        new_grid[y][x] = 'FLOWER'

                # Flower death (overcrowding or drought)
                elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
                    if random.random() < min(1.0, FLOWER_DECAY_RATE * _decay):
                        new_grid[y][x] = 'GRASS'

                # Grass → Water (rain flooding only)
                elif cell == 'GRASS' and total_water >= 1 and self.is_raining:
                    if random.random() < min(1.0, GRASS_WATER_ABSORB_RATE * _tp):
                        new_grid[y][x] = 'WATER'

                # Tree → Grass (drought — mirrors Cactus drought decay; fires when no water and drought is moderate+)
                elif cell.startswith('TREE') and total_water == 0 and drought_severity > 0.5:
                    if random.random() < min(1.0, TREE_DROUGHT_RATE * _decay):
                        new_grid[y][x] = 'GRASS'

                # Tree → Cobblestone (tree stranded inside a cobblestone road — 5+ of 8 neighbors cobblestone)
                # High threshold prevents cascade: edge trees are untouched, only truly embedded ones convert
                elif cell.startswith('TREE') and cobblestone_count >= 5:
                    if random.random() < min(1.0, TREE_DECAY_RATE * _decay):
                        new_grid[y][x] = 'COBBLESTONE'

                # Tree → Grass (near cobblestone road but not embedded — clears treeline)
                elif cell.startswith('TREE') and cobblestone_count > 0:
                    if random.random() < min(1.0, TREE_CROWD_DECAY_RATE * _decay):
                        new_grid[y][x] = 'GRASS'

                # Trees on/near sand decay fast to SAND (desert kills trees)
                elif cell.startswith('TREE') and sand_count >= 1:
                    if random.random() < min(1.0, 0.15 * _decay):
                        new_grid[y][x] = 'SAND'

                # Tree crowding decay — any adjacent tree triggers decay chance
                # Naturally produces checkerboard spacing as isolated trees survive
                elif cell.startswith('TREE') and tree_count >= 1:
                    if random.random() < min(1.0, TREE_CROWD_DECAY_RATE * _decay):
                        new_grid[y][x] = 'GRASS'

                # Cactus → Sand (drought — mirrors tree drought decay in lush biomes)
                elif cell == 'CACTUS' and total_water == 0 and drought_severity > 0.5:
                    if random.random() < min(1.0, CACTUS_DROUGHT_RATE * _decay):
                        new_grid[y][x] = 'SAND'

                # General neighbor-copy: base terrain may adopt a random NSEW neighbor's type
                if new_grid[y][x] == cell and cell in ('GRASS', 'DIRT', 'SAND', 'WATER'):
                    nx, ny = random.choice(((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)))
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                        neighbor = screen['grid'][ny][nx]
                        if neighbor in ('GRASS', 'DIRT', 'SAND', 'WATER') and neighbor != cell:
                            if random.random() < min(1.0, BIOME_SPREAD_RATE * _tp):
                                new_grid[y][x] = neighbor

                # Wood decay to dirt (outside structures)
                elif cell == 'WOOD' and not self.is_near_structure(x, y, key):
                    if random.random() < min(1.0, 0.05 * _tp):
                        new_grid[y][x] = 'DIRT'

                # Planks decay to dirt (outside structures)
                elif cell == 'PLANKS' and not self.is_near_structure(x, y, key):
                    if random.random() < min(1.0, 0.03 * _tp):
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

                    if random.random() < min(1.0, decay_rate * _tp):
                        new_grid[y][x] = 'DIRT'

        # Sync variant_grid for any cells whose type changed
        if 'variant_grid' in screen:
            for vy in range(GRID_HEIGHT):
                for vx in range(GRID_WIDTH):
                    if new_grid[vy][vx] != screen['grid'][vy][vx]:
                        screen['variant_grid'][vy][vx] = self.roll_cell_variant(new_grid[vy][vx])

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

        # Desert: rare puddles (10% chance per tick to attempt one sand→water conversion).
        # Gives ~1-2 puddles over a full rain cycle. No grass — rain doesn't green desert.
        if biome == 'DESERT':
            if random.random() < 0.1:
                x = random.randint(1, GRID_WIDTH - 2)
                y = random.randint(1, GRID_HEIGHT - 2)
                cell = screen['grid'][y][x]
                if cell == 'SAND' and not self.is_cell_enchanted(x, y, key):
                    if random.random() < 0.6:
                        screen['grid'][y][x] = 'WATER'
            return

        water_mult = 1.0
        grass_mult = 1.0
        if biome == 'MOUNTAINS':
            water_mult = 0.6
            grass_mult = 0.3
        elif biome == 'PLAINS':
            water_mult = 1.2
            grass_mult = 1.2

        water_spawns = max(1, int(RAIN_WATER_SPAWNS * water_mult))
        for _ in range(water_spawns):
            x = random.randint(1, GRID_WIDTH - 2)
            y = random.randint(1, GRID_HEIGHT - 2)
            cell = screen['grid'][y][x]
            if cell == 'DIRT' and not self.is_cell_enchanted(x, y, key):
                if random.random() < 0.3:
                    screen['grid'][y][x] = 'WATER'

        grass_spawns = max(1, int(RAIN_GRASS_SPAWNS * grass_mult))
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

        if not self.is_night and old_is_night:
            if hasattr(self, 'sound'):
                self.sound.play_dawn_music()

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
