import random

# DEBUG: isolation testing flags
# CA_RULES_ENABLED = False disables all CA
# CA_SINGLE_RULE = restrict to one rule group ('sand_to_dirt_water', or None for all)
CA_RULES_ENABLED = True
CA_SINGLE_RULE = None

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, BIOMES,
    # CA master knob and class rates
    CA_BASE_RATE, CA_GROWTH_RATE, CA_DECAY_RATE, CA_SPREAD_RATE, CA_WATER_EVAP_RATE,
    DIRT_TO_GRASS_RATE, GRASS_TO_DIRT_RATE, DIRT_TO_SAND_DROUGHT_RATE,
    GRASS_TO_TREE_RATE, TREE_TO_GRASS_CROWD_RATE,
    SAND_TO_DIRT_WATER_RATE, CACTUS_TO_SAND_DROUGHT_RATE, TREE_TO_GRASS_DROUGHT_RATE,
    GRASS_TO_FLOWER_RATE, FLOWER_TO_GRASS_RATE,
    WATER_TO_DEEP_WATER_RATE, DEEP_WATER_TO_WATER_RATE,
    WATER_TO_BASE_ISOLATED_RATE, DIRT_TO_FLOWER_WATER_RATE, DIRT_TO_WATER_RAIN_RATE,
    SAND_TO_DIRT_STONE_RATE,
    BIOME_BORDER_SPREAD_RATE, TERRAIN_DIFFUSION_RATE,
    GRASS_TO_DIRT_SAND_RATE, DIRT_TO_SAND_SPREAD_RATE,
    GRASS_TO_WATER_RAIN_RATE, DIRT_TO_GRASS_WATER_RATE,
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

    def find_cluster_position(self, screen_key, target_cell, radius=6):
        """Return (x, y) of a free cell near an existing target_cell on screen_key.

        Finds all existing instances of target_cell, picks one at random, then
        collects passable cells within radius tiles.  Returns a random candidate,
        or None if no existing target_cell is present on the screen.
        This is the general-purpose 'place nearby' helper — reuse for any cell
        type that should cluster with its own kind (gravestones, mushrooms, etc.).
        """
        if screen_key not in self.screens:
            return None
        grid = self.screens[screen_key]['grid']
        _NO_PLACE = {'WALL', 'CAVE', 'CLIFF', 'GRAVESTONE', 'BROKEN_GRAVESTONE',
                     'STONE', 'CAVE_WALL', 'IRON_ORE', 'WATER', 'DEEP_WATER'}
        existing = [(x, y) for y in range(GRID_HEIGHT) for x in range(GRID_WIDTH)
                    if grid[y][x] == target_cell]
        if not existing:
            return None
        ox, oy = random.choice(existing)
        candidates = []
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                nx, ny = ox + dx, oy + dy
                if (1 <= nx < GRID_WIDTH - 1 and 1 <= ny < GRID_HEIGHT - 1
                        and grid[ny][nx] not in _NO_PLACE
                        and grid[ny][nx] != target_cell):
                    candidates.append((nx, ny))
        if candidates:
            return random.choice(candidates)
        return None

    # -------------------------------------------------------------------------
    # Cellular automata
    # -------------------------------------------------------------------------

    def apply_cellular_automata(self, screen_x, screen_y, cell_coverage=1.0):
        """Apply cellular automata rules to a screen.

        cell_coverage: fraction of cells to process this cycle (0.0–1.0).
        1.0 = all cells, 0.5 = half skipped at random (player zone default), etc.
        """
        if not CA_RULES_ENABLED:
            return

        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        new_grid = [row[:] for row in screen['grid']]  # shallow copy per row
        biome = screen.get('biome', 'FOREST')
        _biome_base = {'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
                       'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT'}.get(biome, 'GRASS')

        # Debug: log all cell changes in the player zone so we can trace CA rule chains
        _is_player_zone = (screen_x == self.player['screen_x'] and
                           screen_y == self.player['screen_y'])

        _tp = getattr(self, 'time_pass_speed', 1.0)

        # Drought modifier: growth slows and decay accelerates the longer it hasn't rained.
        # Full drought severity is reached at 9000 ticks (~2.5 min) without rain.
        drought_ticks = self.tick - self.zone_last_rain.get(key, self.tick)
        drought_severity = min(drought_ticks / 9000.0, 1.0)   # 0.0 = just rained, 1.0 = max drought
        _growth = max(0.1, 1.0 - drought_severity * 0.9) * _tp  # decays to 10% of base at max drought
        _decay  = (1.0 + drought_severity * 0.5) * _tp           # rises to 1.5x base at max drought

        # ── Zone-wide water count for volume-based decay rule ─────────────────
        # Count WATER (not DEEP_WATER) cells across the full zone grid once per cycle.
        # Used to compute per-cell water decay rate: (count - 4) * BASE_DECAY_RATE.
        # < 4 cells → rate = 0 (small pools are stable); larger bodies drain over time.
        zone_water_count = sum(row.count('WATER') for row in screen['grid'])

        # Biome base cell for water evaporation target (LAKE biome keeps water)
        _water_decay_target = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
        }.get(biome)  # None for LAKE or unknown → rule skipped

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                # Per-cell coverage skip: probability decreases down the priority queue
                if random.random() > cell_coverage:
                    continue

                cell = screen['grid'][y][x]

                if cell in ('WALL', 'HOUSE', 'CAVE', 'CLIFF', 'GRAVESTONE',
                            'BROKEN_GRAVESTONE', 'LOCKED_CHEST', 'OPEN_CHEST',
                            'BOOKSHELF', 'WOOD_CHAIR', 'WOOD_TABLE', 'BED_BLUE',
                            'BED_WHITE', 'WATER_TROUGH', 'SMALL_POTTED_PLANT'):
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
                cave_floor_count = self.count_cell_type(neighbors, 'CAVE_FLOOR')
                dirt_count = self.count_cell_type(neighbors, 'DIRT')
                grass_count = self.count_cell_type(neighbors, 'GRASS')
                tree_count = self.count_cell_type(neighbors, 'TREE')
                sand_count = self.count_cell_type(neighbors, 'SAND')
                flower_count = self.count_cell_type(neighbors, 'FLOWER')
                cobblestone_count = self.count_cell_type(neighbors, 'COBBLESTONE')

                # CAVE_FLOOR counts as water for spread calculations — it is the dried bed of
                # former deep water and should allow water to reform around it.
                total_water = water_count + deep_water_count + cave_floor_count

                # Debug tracer: rule name set by whichever branch fires; logged at end of cell block
                _ca_rule = None

                # Isolation testing: skip all cells that can't trigger the named rule
                if CA_SINGLE_RULE == 'sand_to_dirt_water':
                    if not (cell == 'SAND' and total_water >= 1):
                        continue

                # Dirt → Water (flooding, rain only — highest priority for dirt)
                if cell == 'DIRT' and total_water >= 3 and self.is_raining:
                    if random.random() < min(1.0, DIRT_TO_WATER_RAIN_RATE * _tp):
                        new_grid[y][x] = 'WATER'
                        _ca_rule ='DIRT_TO_WATER_RAIN_RATE'

                # Sand → Water (rain flooding — 2x dirt rate; sand absorbs water faster)
                elif cell == 'SAND' and total_water >= 3 and self.is_raining:
                    if random.random() < min(1.0, DIRT_TO_WATER_RAIN_RATE * 2.0 * _tp):
                        new_grid[y][x] = 'WATER'

                # Dirt → Grass (water >= 2)
                elif cell == 'DIRT' and total_water >= 2:
                    if random.random() < min(1.0, DIRT_TO_GRASS_RATE * _growth):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule ='DIRT_TO_GRASS_RATE'

                # Dirt → Grass (water == 1, extra small chance)
                elif cell == 'DIRT' and total_water == 1 and sand_count == 0:
                    if random.random() < min(1.0, DIRT_TO_GRASS_WATER_RATE * _growth):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule ='DIRT_TO_GRASS_WATER_RATE'

                # Dirt → Flower pattern (at water's edge touching a non-dirt/water cell — forms rocky rim)
                # Disabled in desert: FLOWER_PATTERN decays to SAND in desert, creating an indirect
                # DIRT→FLOWER→SAND chain that erases dirt cells over two CA cycles.
                elif cell == 'DIRT' and total_water >= 1 and biome != 'DESERT':
                    _non_dirt_land = sum(1 for n in neighbors
                                         if n not in ('DIRT', 'WATER', 'DEEP_WATER'))
                    if _non_dirt_land >= 1 and random.random() < min(1.0, DIRT_TO_FLOWER_WATER_RATE * _growth):
                        new_grid[y][x] = random.choice(['FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3'])
                        _ca_rule ='DIRT_TO_FLOWER_WATER_RATE'

                # Dirt → Sand (any sand neighbor, no water — desertification spread, non-desert only)
                elif cell == 'DIRT' and total_water == 0 and sand_count >= 1 and biome != 'DESERT':
                    if random.random() < min(1.0, DIRT_TO_SAND_SPREAD_RATE * _decay):
                        new_grid[y][x] = 'SAND'
                        _ca_rule ='DIRT_TO_SAND_SPREAD_RATE'

                # Dirt → Sand (severe drought, no grass at all — non-desert only)
                elif cell == 'DIRT' and total_water == 0 and grass_count == 0 and biome != 'DESERT':
                    if random.random() < min(1.0, DIRT_TO_SAND_DROUGHT_RATE * _decay):
                        new_grid[y][x] = 'SAND'
                        _ca_rule ='DIRT_TO_SAND_DROUGHT_RATE'

                # Grass → Dirt (sand erosion — desertification edge, higher rate)
                elif cell == 'GRASS' and sand_count >= 1:
                    if random.random() < min(1.0, GRASS_TO_DIRT_SAND_RATE * _decay):
                        new_grid[y][x] = 'DIRT'

                # Grass → Dirt (drought, no water)
                elif cell == 'GRASS' and total_water == 0:
                    if random.random() < min(1.0, GRASS_TO_DIRT_RATE * _decay):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'GRASS_TO_DIRT_RATE'

                # Tree spread (needs grass, water, no cobblestone, and not desert)
                elif cell == 'GRASS' and biome != 'DESERT' and cobblestone_count == 0 and 1 <= tree_count <= 2 and total_water >= 1:
                    if random.random() < min(1.0, GRASS_TO_TREE_RATE * _growth):
                        new_grid[y][x] = 'TREE1'
                        _ca_rule = 'GRASS_TO_TREE_RATE'

                # Sand → Dirt (any water neighbor — universal rule, supercedes biome-specific rules)
                elif cell == 'SAND' and total_water >= 1:
                    if random.random() < min(1.0, SAND_TO_DIRT_WATER_RATE * _growth):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'SAND_TO_DIRT_WATER_RATE'

                # Sand → Dirt (grass neighbor — vegetation slowly reclaims desert edges)
                elif cell == 'SAND' and grass_count >= 1:
                    if random.random() < min(1.0, SAND_TO_DIRT_WATER_RATE * 0.05 * _growth):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'SAND_TO_DIRT_GRASS_RATE'

                # Sand → Dirt (touching stone/cobblestone)
                elif cell == 'SAND' and cobblestone_count >= 1:
                    if random.random() < min(1.0, SAND_TO_DIRT_STONE_RATE * _growth):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'SAND_TO_DIRT_STONE_RATE(cobble)'

                elif cell == 'SAND':
                    _stone_adj = sum(1 for n in neighbors if n == 'STONE')
                    if _stone_adj >= 1 and random.random() < min(1.0, SAND_TO_DIRT_STONE_RATE * _growth):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'SAND_TO_DIRT_STONE_RATE(stone)'

                # Deep water formation: all 4 cardinal neighbors must be water/deep_water/cave_floor
                elif cell == 'WATER':
                    cardinal_water = sum(
                        1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                        and screen['grid'][y + cdy][x + cdx] in ('WATER', 'DEEP_WATER', 'CAVE_FLOOR')
                    )
                    # Stone/cobblestone neighbors slow evaporation (natural grotto walls)
                    _stone_shield = max(0.1, 1.0 - 0.2 * sum(
                        1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                        and screen['grid'][y + cdy][x + cdx] in ('STONE', 'COBBLESTONE')
                    ))
                    if cardinal_water == 4 and random.random() < min(1.0, WATER_TO_DEEP_WATER_RATE * _tp):
                        new_grid[y][x] = 'DEEP_WATER'
                        _ca_rule = 'WATER_TO_DEEP_WATER_RATE'
                    elif total_water <= 1 and random.random() < min(1.0, WATER_TO_BASE_ISOLATED_RATE * _decay * _stone_shield):
                        # Cave floor neighbor means this water is sitting over an eroded deep water bed
                        new_grid[y][x] = 'CAVE_FLOOR' if cave_floor_count >= 1 else 'DIRT'
                        _ca_rule = 'WATER_TO_BASE_ISOLATED_RATE'
                    elif biome != 'LAKE' and zone_water_count > 4:
                        # Volume-based decay: pools > 4 cells drain; ≤ 4 are stable.
                        _wdr = (zone_water_count - 4) * CA_BASE_RATE * _stone_shield
                        if random.random() < min(1.0, _wdr * _decay):
                            new_grid[y][x] = 'CAVE_FLOOR' if cave_floor_count >= 1 else 'DIRT'
                            _ca_rule = 'WATER_VOLUME_DECAY'

                # Deep water evaporation — stable when fully surrounded; decays when exposed.
                # In LAKE biome deep water never evaporates on its own (only via interaction).
                elif cell == 'DEEP_WATER' and biome != 'LAKE':
                    cardinal_water_dw = sum(
                        1 for cdx, cdy in ((0, -1), (0, 1), (-1, 0), (1, 0))
                        if 0 <= x + cdx < GRID_WIDTH and 0 <= y + cdy < GRID_HEIGHT
                        and screen['grid'][y + cdy][x + cdx] in ('WATER', 'DEEP_WATER', 'CAVE_FLOOR')
                    )
                    # Only evaporate when no longer fully surrounded — fully surrounded deep water is stable.
                    if cardinal_water_dw < 4 and random.random() < min(1.0, DEEP_WATER_TO_WATER_RATE * _decay):
                        # Evaporates to regular water; 80% chance the water bed (CAVE_FLOOR) forms instead.
                        new_grid[y][x] = 'CAVE_FLOOR' if random.random() < 0.80 else 'WATER'
                        _ca_rule = 'DEEP_WATER_TO_WATER_RATE'

                # CAVE_FLOOR: stable in actual caves; decays and floods quickly in overworld.
                elif cell == 'CAVE_FLOOR':
                    if _water_decay_target is not None:
                        # Overworld: rain rapidly fills it with water [cross-biome: water formation]
                        if self.is_raining and random.random() < min(1.0, 4 * CA_WATER_EVAP_RATE * _tp):
                            new_grid[y][x] = 'WATER'
                            _ca_rule = 'CAVE_FLOOR_TO_WATER_RAIN'
                        # Overworld: dries back to biome base quickly when no water nearby [cross-biome: water formation]
                        elif not self.is_raining and total_water == 0 and random.random() < min(1.0, 5 * CA_WATER_EVAP_RATE * _decay):
                            new_grid[y][x] = _water_decay_target
                            _ca_rule = 'CAVE_FLOOR_TO_BASE_DRY'
                    # Cave structures: CAVE_FLOOR is permanent — no decay rule

                # Flower spread
                elif cell == 'GRASS' and 1 <= flower_count <= 2 and total_water >= 1:
                    if random.random() < min(1.0, GRASS_TO_FLOWER_RATE * _growth):
                        new_grid[y][x] = 'FLOWER'
                        _ca_rule = 'GRASS_TO_FLOWER_RATE'

                # Flower death (overcrowding or drought)
                elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
                    if random.random() < min(1.0, FLOWER_TO_GRASS_RATE * _decay):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule = 'FLOWER_TO_GRASS_RATE'

                # Grass → Water (rain flooding only)
                elif cell == 'GRASS' and total_water >= 1 and self.is_raining:
                    if random.random() < min(1.0, GRASS_TO_WATER_RAIN_RATE * _tp):
                        new_grid[y][x] = 'WATER'
                        _ca_rule = 'GRASS_TO_WATER_RAIN_RATE'

                # Tree → Grass (drought)
                elif cell.startswith('TREE') and total_water == 0 and drought_severity > 0.5:
                    if random.random() < min(1.0, TREE_TO_GRASS_DROUGHT_RATE * _decay):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule = 'TREE_TO_GRASS_DROUGHT_RATE'

                # Tree → Grass (near cobblestone road)
                elif cell.startswith('TREE') and cobblestone_count > 0:
                    if random.random() < min(1.0, TREE_TO_GRASS_CROWD_RATE * _decay):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule = 'TREE_TO_GRASS_CROWD_RATE(road)'

                # Trees on/near sand decay fast to SAND [biome-specific: desert]
                elif cell.startswith('TREE') and sand_count >= 1:
                    if random.random() < min(1.0, 150 * CA_DECAY_RATE * _decay):
                        new_grid[y][x] = 'SAND'
                        _ca_rule = 'TREE_TO_SAND_DESERT'

                # Tree crowding decay
                elif cell.startswith('TREE') and tree_count >= 1:
                    if random.random() < min(1.0, TREE_TO_GRASS_CROWD_RATE * _decay):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule = 'TREE_TO_GRASS_CROWD_RATE'

                # Cactus → Sand (drought)
                elif cell == 'CACTUS' and total_water == 0 and drought_severity > 0.5:
                    if random.random() < min(1.0, CACTUS_TO_SAND_DROUGHT_RATE * _decay):
                        new_grid[y][x] = 'SAND'
                        _ca_rule = 'CACTUS_TO_SAND_DROUGHT_RATE'

                # Flower pattern decay → biome base cell
                elif cell.startswith('FLOWER_PATTERN'):
                    _fp_base = {'DESERT': 'SAND', 'MOUNTAINS': 'DIRT'}.get(biome, 'GRASS')
                    _fp_near_water = any(
                        0 <= _nx < GRID_WIDTH and 0 <= _ny < GRID_HEIGHT and
                        screen['grid'][_ny][_nx] in ('WATER', 'DEEP_WATER', 'CAVE_FLOOR')
                        for _nx, _ny in ((x, y-1), (x, y+1), (x-1, y), (x+1, y))
                    )
                    _fp_decay_rate = 0.3 * CA_DECAY_RATE if _fp_near_water else 4 * CA_DECAY_RATE
                    if random.random() < min(1.0, _fp_decay_rate * _decay):
                        new_grid[y][x] = _fp_base
                        _ca_rule = 'FLOWER_PATTERN_DECAY'

                # Bush decay → grass when not touching water
                elif cell == 'BUSH':
                    _bush_near_water = any(
                        0 <= _nx < GRID_WIDTH and 0 <= _ny < GRID_HEIGHT and
                        screen['grid'][_ny][_nx] in ('WATER', 'DEEP_WATER', 'CAVE_FLOOR')
                        for _nx, _ny in ((x, y-1), (x, y+1), (x-1, y), (x+1, y))
                    )
                    if not _bush_near_water and random.random() < min(1.0, 3 * CA_DECAY_RATE * _decay):
                        new_grid[y][x] = 'GRASS'
                        _ca_rule = 'BUSH_TO_GRASS'

                # BLUE_MUSHROOM cluster growth
                elif cell == 'CAVE_FLOOR' and _water_decay_target is None:
                    _mush_adj = sum(
                        1 for cdx, cdy in ((0,-1),(0,1),(-1,0),(1,0))
                        if 0 <= x+cdx < GRID_WIDTH and 0 <= y+cdy < GRID_HEIGHT
                        and screen['grid'][y+cdy][x+cdx] == 'BLUE_MUSHROOM'
                    )
                    if 1 <= _mush_adj <= 2 and random.random() < min(1.0, 0.8 * CA_GROWTH_RATE * _growth):
                        new_grid[y][x] = 'BLUE_MUSHROOM'
                        _ca_rule = 'CAVE_FLOOR_TO_BLUE_MUSHROOM'

                # BLUE_MUSHROOM overcrowding
                elif cell == 'BLUE_MUSHROOM':
                    _mush_all = self.count_cell_type(neighbors, 'BLUE_MUSHROOM')
                    if _mush_all >= 5 and random.random() < min(1.0, 2 * CA_DECAY_RATE * _decay):
                        new_grid[y][x] = 'CAVE_FLOOR'
                        _ca_rule = 'BLUE_MUSHROOM_TO_CAVE_FLOOR'

                # Base terrain pressure: any GRASS/SAND/DIRT cell with 3+ neighbors of a different
                # base terrain type has a small chance to convert to that type.
                if new_grid[y][x] == cell and cell in ('GRASS', 'SAND', 'DIRT'):
                    for _t, _n in (('SAND', sand_count), ('GRASS', grass_count), ('DIRT', dirt_count)):
                        if _t != cell and _n >= 3:
                            if random.random() < min(1.0, CA_DECAY_RATE * _decay):
                                new_grid[y][x] = _t
                                _ca_rule = 'BASE_TERRAIN_PRESSURE'
                            break

                # General neighbor-copy: base terrain may adopt a random NSEW neighbor's type
                if new_grid[y][x] == cell and cell in ('GRASS', 'DIRT', 'SAND', 'WATER'):
                    nx, ny = random.choice(((x, y - 1), (x, y + 1), (x - 1, y), (x + 1, y)))
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                        neighbor = screen['grid'][ny][nx]
                        if neighbor in ('GRASS', 'DIRT', 'SAND', 'WATER') and neighbor != cell:
                            if random.random() < min(1.0, TERRAIN_DIFFUSION_RATE * _tp):
                                new_grid[y][x] = neighbor
                                if cell == 'DIRT':
                                    _ca_rule ='neighbor_copy'

                # Player zone cell tracer: log every CA rule firing in the player's current zone
                if _is_player_zone and _ca_rule and new_grid[y][x] != cell:
                    self.bug_catcher.log_ca_mutation(
                        self.tick, key, x, y, cell, new_grid[y][x], _ca_rule, biome
                    )

                # Flower pattern growth: rare overlay on eligible unchanged cells
                # [biome-specific: desert gets 1/5 rate] [cross-biome: water formation edge]
                _fp_rate = 0.003 * CA_GROWTH_RATE if biome == 'DESERT' else 0.015 * CA_GROWTH_RATE
                if new_grid[y][x] == cell and cell in ('GRASS', 'DIRT', 'SAND', 'COBBLESTONE'):
                    if random.random() < _fp_rate * _growth:
                        new_grid[y][x] = random.choice(
                            ['FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3']
                        )

                # Empty crate decay — high rate, reverts to base terrain
                elif cell == 'EMPTY_CRATE':  # [constructed: decay]
                    _ec_base = {'DESERT': 'SAND', 'MOUNTAINS': 'DIRT'}.get(biome, 'GRASS')
                    if random.random() < min(1.0, 80 * CA_BASE_RATE * _tp):
                        new_grid[y][x] = _ec_base

                # Wood decay to dirt (outside structures)
                elif cell == 'WOOD' and not self.is_near_structure(x, y, key):  # [constructed: decay]
                    if random.random() < min(1.0, 50 * CA_BASE_RATE * _tp):
                        new_grid[y][x] = 'DIRT'

                # Planks decay to dirt (outside structures) [constructed: decay]
                elif cell == 'PLANKS' and not self.is_near_structure(x, y, key):
                    if random.random() < min(1.0, 30 * CA_BASE_RATE * _tp):
                        new_grid[y][x] = 'DIRT'

                # Bones decay to biome base cell [constructed: decay]
                elif cell == 'BONES':  # [constructed: decay]
                    _bones_base = {'DESERT': 'SAND', 'MOUNTAINS': 'DIRT'}.get(biome, 'DIRT')
                    if random.random() < min(1.0, 20 * CA_BASE_RATE * _tp):
                        new_grid[y][x] = _bones_base
                        _ca_rule = 'BONES_DECAY'

                # Rain flood spread: any terrain adjacent to water while raining gets a small
                # extra conversion chance. Independent of main elif chain.
                if (self.is_raining and new_grid[y][x] == cell
                        and cell in ('DIRT', 'SAND', 'COBBLESTONE')
                        and total_water >= 1):
                    if random.random() < min(1.0, DIRT_TO_WATER_RAIN_RATE * 0.4 * _tp):
                        new_grid[y][x] = 'WATER'
                        _ca_rule = 'RAIN_FLOOD_SPREAD'

                # Crop decay without rain (drought)
                elif cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                    last_rain = self.zone_last_rain.get(key, 0)
                    ticks_since_rain = self.tick - last_rain

                    has_farmer = any(
                        self.entities[eid].type == 'FARMER'
                        for eid in self.screen_entities.get(key, [])
                        if eid in self.entities
                    )

                    decay_rate = 0.1 * CA_DECAY_RATE
                    if ticks_since_rain > 1200:
                        decay_rate = 1 * CA_DECAY_RATE
                    if ticks_since_rain > 3600:
                        decay_rate = 10 * CA_DECAY_RATE
                    if not has_farmer:
                        decay_rate *= 2.0

                    if random.random() < min(1.0, decay_rate * _tp):
                        new_grid[y][x] = 'DIRT'
                        _ca_rule = 'CROP_DROUGHT_DECAY'

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

        # Desert: puddles form during rain — 22% chance per tick to attempt 1-2
        # sand→water conversions. Also checks cells adjacent to existing water.
        if biome == 'DESERT':
            if random.random() < 0.22:
                for _ in range(2):
                    x = random.randint(1, GRID_WIDTH - 2)
                    y = random.randint(1, GRID_HEIGHT - 2)
                    cell = screen['grid'][y][x]
                    if cell == 'SAND' and not self.is_cell_enchanted(x, y, key):
                        # Higher chance if already adjacent to water
                        adj_water = sum(
                            1 for dx, dy in ((0,1),(0,-1),(1,0),(-1,0))
                            if 0 <= x+dx < GRID_WIDTH and 0 <= y+dy < GRID_HEIGHT
                            and screen['grid'][y+dy][x+dx] in ('WATER', 'DEEP_WATER')
                        )
                        rate = 0.75 if adj_water else 0.4
                        if random.random() < rate:
                            screen['grid'][y][x] = 'WATER'
            # Even in desert, rain quenches thirst (just rarer puddles)
            for eid in self.screen_entities.get(key, []):
                if eid in self.entities:
                    e = self.entities[eid]
                    if e.health > 0 and not getattr(e, 'in_subscreen', False):
                        e.thirst = e.max_thirst
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

        # Rain fills thirst for all living outdoor entities in this zone
        for eid in self.screen_entities.get(key, []):
            if eid in self.entities:
                e = self.entities[eid]
                if e.health > 0 and not getattr(e, 'in_subscreen', False):
                    e.thirst = e.max_thirst

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
