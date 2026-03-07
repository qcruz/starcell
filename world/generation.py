import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, BIOMES,
    NATURAL_CAVE_ZONE_CHANCE,
)
from entity import Entity


class WorldGenerationMixin:
    """Handles procedural world generation: screens, structures, interiors,
    chest placement, zone connections, and exit management."""

    # -------------------------------------------------------------------------
    # Main screen generation
    # -------------------------------------------------------------------------

    def generate_screen(self, sx, sy):
        """Generate a procedural screen"""
        key = f"{sx},{sy}"
        if key in self.screens:
            return self.screens[key]

        # Determine biome (LAKE at ~3%, others proportionally reduced)
        biome_roll = random.random()
        if biome_roll < 0.58:
            biome_name = 'FOREST'
        elif biome_roll < 0.77:
            biome_name = 'PLAINS'
        elif biome_roll < 0.92:
            biome_name = 'MOUNTAINS'
        elif biome_roll < 0.97:
            biome_name = 'DESERT'
        else:
            biome_name = 'LAKE'
        biome = BIOMES[biome_name]

        # Create exits - check neighboring screens for matching exits
        exits = {
            'top': random.random() > 0.5,
            'bottom': random.random() > 0.5,
            'left': random.random() > 0.5,
            'right': random.random() > 0.5
        }

        # Force exits to match neighboring screens (bidirectional)
        top_neighbor_key = f"{sx},{sy-1}"
        if top_neighbor_key in self.screens:
            exits['top'] = self.screens[top_neighbor_key]['exits']['bottom']

        bottom_neighbor_key = f"{sx},{sy+1}"
        if bottom_neighbor_key in self.screens:
            exits['bottom'] = self.screens[bottom_neighbor_key]['exits']['top']

        left_neighbor_key = f"{sx-1},{sy}"
        if left_neighbor_key in self.screens:
            exits['left'] = self.screens[left_neighbor_key]['exits']['right']

        right_neighbor_key = f"{sx+1},{sy}"
        if right_neighbor_key in self.screens:
            exits['right'] = self.screens[right_neighbor_key]['exits']['left']

        # Ensure at least 2 exits (never isolated zones)
        exit_count = sum(exits.values())
        if exit_count < 2:
            sides = [k for k, v in exits.items() if not v]
            random.shuffle(sides)
            exits[sides[0]] = True
            if len(sides) > 1:
                exits[sides[1]] = True

        # 50% chance for 3rd exit if only have 2
        if sum(exits.values()) == 2 and random.random() < 0.5:
            sides = [k for k, v in exits.items() if not v]
            if sides:
                exits[random.choice(sides)] = True

        # Update neighbors: ensure bidirectional consistency
        if exits['top'] and top_neighbor_key in self.screens:
            self.screens[top_neighbor_key]['exits']['bottom'] = True
            self.update_screen_exits(sx, sy - 1)

        if exits['bottom'] and bottom_neighbor_key in self.screens:
            self.screens[bottom_neighbor_key]['exits']['top'] = True
            self.update_screen_exits(sx, sy + 1)

        if exits['left'] and left_neighbor_key in self.screens:
            self.screens[left_neighbor_key]['exits']['right'] = True
            self.update_screen_exits(sx - 1, sy)

        if exits['right'] and right_neighbor_key in self.screens:
            self.screens[right_neighbor_key]['exits']['left'] = True
            self.update_screen_exits(sx + 1, sy)

        # Generate grid
        exit_cell = {'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
                     'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
                     'LAKE': 'WATER'}.get(biome_name, 'GRASS')
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if biome_name == 'LAKE':
                    is_border = (y == 0 or y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1)
                    is_perimeter = (not is_border and
                                    (y == 1 or y == GRID_HEIGHT - 2 or x == 1 or x == GRID_WIDTH - 2))
                    is_exit = (
                        (y == 0 and exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2) or
                        (y == GRID_HEIGHT - 1 and exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2) or
                        (x == 0 and exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2) or
                        (x == GRID_WIDTH - 1 and exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2)
                    )
                    is_exit_corridor = (
                        (y == 1 and exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2) or
                        (y == GRID_HEIGHT - 2 and exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2) or
                        (x == 1 and exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2) or
                        (x == GRID_WIDTH - 2 and exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2)
                    )
                    if is_border:
                        row.append('WATER' if is_exit else 'CLIFF')
                    elif is_perimeter:
                        row.append('WATER' if is_exit_corridor else 'SAND')
                    else:
                        row.append('WATER')
                elif y == 0 or y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    if (y == 0 and exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                        row.append(exit_cell)
                    elif (y == GRID_HEIGHT - 1 and exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                        row.append(exit_cell)
                    elif (x == 0 and exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                        row.append(exit_cell)
                    elif (x == GRID_WIDTH - 1 and exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                        row.append(exit_cell)
                    else:
                        row.append('WALL')
                else:
                    rand = random.random()
                    cumulative = 0
                    cell_type = 'GRASS'
                    for terrain, prob in biome.items():
                        cumulative += prob
                        if rand < cumulative:
                            cell_type = terrain
                            break
                    row.append(cell_type)
            grid.append(row)

        # Generate variant grid
        variant_grid = []
        for y in range(GRID_HEIGHT):
            variant_row = []
            for x in range(GRID_WIDTH):
                cell = grid[y][x]
                variant = None
                variants = CELL_TYPES.get(cell, {}).get('variants')
                if variants:
                    roll = random.random()
                    cumul = 0
                    for vname, vprob in variants.items():
                        cumul += vprob
                        if roll < cumul:
                            variant = vname if vname != cell else None
                            break
                variant_row.append(variant)
            variant_grid.append(variant_row)

        # 30% chance to place a structure (HOUSE or CAVE) — not in lakes
        if biome_name != 'LAKE' and random.random() > 0.7:
            struct_x = random.randint(2, GRID_WIDTH - 3)
            struct_y = random.randint(2, GRID_HEIGHT - 3)
            struct_type = random.choice(['HOUSE', 'CAVE'])
            grid[struct_y][struct_x] = struct_type

        # Desert: 60% chance to scatter 1-4 ruined sandstone columns
        if biome_name == 'DESERT' and random.random() < 0.60:
            num_columns = random.randint(1, 4)
            for _ in range(num_columns):
                for _attempt in range(20):
                    col_x = random.randint(2, GRID_WIDTH - 3)
                    col_y = random.randint(2, GRID_HEIGHT - 3)
                    if grid[col_y][col_x] in ('SAND', 'DIRT'):
                        grid[col_y][col_x] = 'RUINED_SANDSTONE_COLUMN'
                        break

        # 10% chance to place a WELL near zone centre — not in lakes
        if biome_name != 'LAKE' and random.random() < 0.10:
            well_x = GRID_WIDTH  // 2 + random.randint(-3, 3)
            well_y = GRID_HEIGHT // 2 + random.randint(-3, 3)
            well_x = max(2, min(GRID_WIDTH - 3,  well_x))
            well_y = max(2, min(GRID_HEIGHT - 3, well_y))
            if not CELL_TYPES.get(grid[well_y][well_x], {}).get('solid', False):
                grid[well_y][well_x] = 'WELL'

        screen_data = {
            'grid': grid,
            'variant_grid': variant_grid,
            'exits': exits,
            'biome': biome_name
        }

        self.screens[key] = screen_data
        self.instantiated_zones.add(key)

        self.screen_last_update[key] = self.tick

        # Spawn entities in new screen
        if key not in self.screen_entities:
            self.spawn_entities_for_screen(sx, sy, biome_name)

        # Natural cave formation — uncommon, favors mountains; not in lakes
        if biome_name == 'LAKE':
            self.spawn_runestones_for_screen(sx, sy)
            return screen_data
        cave_chance = NATURAL_CAVE_ZONE_CHANCE
        if biome_name == 'MOUNTAINS':
            cave_chance *= 3
        elif biome_name == 'DESERT':
            cave_chance *= 1.5
        if random.random() < cave_chance:
            valid = [(x, y) for y in range(2, GRID_HEIGHT - 2)
                     for x in range(2, GRID_WIDTH - 2)
                     if CELL_TYPES.get(grid[y][x], {}).get('solid', False)
                     and grid[y][x] != 'WALL']
            if valid:
                cx, cy = random.choice(valid)
                grid[cy][cx] = 'CAVE'

        # Spawn runestones (rare)
        self.spawn_runestones_for_screen(sx, sy)

        return screen_data

    # -------------------------------------------------------------------------
    # Exit and cell helpers
    # -------------------------------------------------------------------------

    def roll_cell_variant(self, cell_type):
        """Roll a variant for a cell type. Returns variant name or None."""
        variants = CELL_TYPES.get(cell_type, {}).get('variants')
        if not variants:
            return None
        roll = random.random()
        cumul = 0
        for vname, vprob in variants.items():
            cumul += vprob
            if roll < cumul:
                return vname if vname != cell_type else None
        return None

    def set_grid_cell(self, screen, x, y, new_cell):
        """Set a grid cell and update its variant. Use instead of direct grid assignment."""
        screen['grid'][y][x] = new_cell
        if 'variant_grid' in screen:
            screen['variant_grid'][y][x] = self.roll_cell_variant(new_cell)

    def update_screen_exits(self, sx, sy):
        """Update a screen's grid walls to match its current exits"""
        key = f"{sx},{sy}"
        if key not in self.screens:
            return

        screen = self.screens[key]
        exits = screen['exits']
        grid = screen['grid']
        biome = screen.get('biome', 'FOREST')
        current_biome_cell = self.get_common_cell_for_biome(biome)
        border_wall = 'CLIFF' if biome == 'LAKE' else 'WALL'

        # Update top edge
        for x in range(GRID_WIDTH):
            if exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
                top_neighbor_key = f"{sx},{sy - 1}"
                if top_neighbor_key in self.screens:
                    adj_biome = self.screens[top_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[0][x] = current_biome_cell if x == GRID_WIDTH // 2 - 1 else adj_cell
                else:
                    grid[0][x] = current_biome_cell
            elif not exits['top'] or not (GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                grid[0][x] = border_wall

        # Update bottom edge
        for x in range(GRID_WIDTH):
            if exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
                bottom_neighbor_key = f"{sx},{sy + 1}"
                if bottom_neighbor_key in self.screens:
                    adj_biome = self.screens[bottom_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[GRID_HEIGHT - 1][x] = current_biome_cell if x == GRID_WIDTH // 2 - 1 else adj_cell
                else:
                    grid[GRID_HEIGHT - 1][x] = current_biome_cell
            elif not exits['bottom'] or not (GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                grid[GRID_HEIGHT - 1][x] = border_wall

        # Update left edge
        for y in range(GRID_HEIGHT):
            if exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
                left_neighbor_key = f"{sx - 1},{sy}"
                if left_neighbor_key in self.screens:
                    adj_biome = self.screens[left_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[y][0] = current_biome_cell if y == GRID_HEIGHT // 2 - 1 else adj_cell
                else:
                    grid[y][0] = current_biome_cell
            elif not exits['left'] or not (GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                grid[y][0] = border_wall

        # Update right edge
        for y in range(GRID_HEIGHT):
            if exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
                right_neighbor_key = f"{sx + 1},{sy}"
                if right_neighbor_key in self.screens:
                    adj_biome = self.screens[right_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[y][GRID_WIDTH - 1] = current_biome_cell if y == GRID_HEIGHT // 2 - 1 else adj_cell
                else:
                    grid[y][GRID_WIDTH - 1] = current_biome_cell
            elif not exits['right'] or not (GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                grid[y][GRID_WIDTH - 1] = border_wall

    def get_common_cell_for_biome(self, biome_name):
        """Get a common cell type for a biome"""
        biome_cells = {
            'FOREST': ['GRASS', 'GRASS', 'DIRT'],
            'PLAINS': ['GRASS', 'GRASS', 'DIRT'],
            'DESERT': ['SAND', 'SAND', 'DIRT'],
            'MOUNTAINS': ['DIRT', 'DIRT', 'GRASS'],
            'LAKE': ['WATER', 'WATER', 'WATER'],
        }
        cells = biome_cells.get(biome_name, ['GRASS', 'DIRT'])
        return random.choice(cells)

    def get_exit_positions(self, direction):
        """Get the two tile positions for a given exit direction"""
        if direction == 'top':
            return [(GRID_WIDTH // 2 - 1, 0), (GRID_WIDTH // 2, 0)]
        elif direction == 'bottom':
            return [(GRID_WIDTH // 2 - 1, GRID_HEIGHT - 1), (GRID_WIDTH // 2, GRID_HEIGHT - 1)]
        elif direction == 'left':
            return [(0, GRID_HEIGHT // 2 - 1), (0, GRID_HEIGHT // 2)]
        elif direction == 'right':
            return [(GRID_WIDTH - 1, GRID_HEIGHT // 2 - 1), (GRID_WIDTH - 1, GRID_HEIGHT // 2)]
        return []

    def get_biome_base_cell(self):
        """Return the primary walkable ground cell for the current zone's biome."""
        biome = 'FOREST'
        if self.current_screen:
            biome = self.current_screen.get('biome', 'FOREST')
        biome_map = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
            'HOUSE_INTERIOR': 'FLOOR_WOOD', 'CAVE': 'CAVE_FLOOR',
        }
        return biome_map.get(biome, 'GRASS')

    # -------------------------------------------------------------------------
    # Subscreen (interior) generation
    # -------------------------------------------------------------------------

    def generate_structure_zone(self, parent_screen_x, parent_screen_y, cell_x, cell_y, structure_type, depth=1):
        """Generate interior for house/cave as a real zone at virtual coordinates.

        Structure zones are assigned coordinates far in the negative-x range
        (x <= -1000) so they exist in the same coordinate system as overworld
        zones but are unreachable by normal walking.  A door_map entry links
        the overworld entrance cell to the structure entrance and back.
        """
        parent_key = f"{parent_screen_x},{parent_screen_y}"

        # For CAVE at depth 1, reuse the existing cave zone for this parent zone
        if structure_type == 'CAVE' and depth == 1:
            if parent_key in self.zone_cave_systems:
                return self.zone_cave_systems[parent_key]

        # Assign real virtual coordinates: far negative x, never reachable by walking
        structure_id = self.next_structure_id
        self.next_structure_id += 1
        vx = -(1000 + structure_id * 10)
        vy = 0
        zone_key = f"{vx},{vy}"

        if zone_key in self.structures:
            return zone_key

        # Generate interior grid
        if structure_type == 'HOUSE_INTERIOR':
            grid = self.generate_house_interior(depth)
        elif structure_type == 'CAVE':
            grid = self.generate_cave_interior(depth)
        else:
            grid = [['FLOOR_WOOD' for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

        entrance_pos = (GRID_WIDTH // 2, GRID_HEIGHT - 2)

        structure_data = {
            'type': structure_type,
            'parent_screen': (parent_screen_x, parent_screen_y),
            'parent_cell': (cell_x, cell_y),
            'grid': grid,
            'biome': structure_type,
            'depth': depth,
            'entrance': entrance_pos,
            'exit': entrance_pos,
            'stairs_down': None,
            'chests': {},
            'entrances': [(cell_x, cell_y)],
            'entities': [],
        }

        # Register as a full zone (in both dicts for backward-compat metadata lookups)
        self.structures[zone_key] = structure_data
        self.screens[zone_key] = structure_data
        self.screen_last_update[zone_key] = self.tick
        if zone_key not in self.screen_entities:
            self.screen_entities[zone_key] = []

        # Door mapping: parent entrance cell ↔ structure zone entrance (bidirectional)
        entrance_x, entrance_y = entrance_pos
        self.door_map[(parent_key, cell_x, cell_y)] = (zone_key, entrance_x, entrance_y)
        self.door_map[(zone_key, entrance_x, entrance_y)] = (parent_key, cell_x, cell_y)

        # For CAVE depth 1: register as the zone's shared cave system
        if structure_type == 'CAVE' and depth == 1:
            self.zone_cave_systems[parent_key] = zone_key

        # Place chests and spawn entities
        if structure_type == 'HOUSE_INTERIOR':
            self.place_house_chests(structure_data)
            if random.random() < 0.5:
                self.spawn_house_npc(structure_data)
        elif structure_type == 'CAVE':
            self.place_cave_chests(structure_data, depth)

        # Register in zone priority system
        if zone_key not in self.structure_zones:
            self.structure_zones[zone_key] = {
                'parent_zone': parent_key,
                'type': structure_type,
                'cell': (cell_x, cell_y)
            }
            if parent_key not in self.zone_structures:
                self.zone_structures[parent_key] = []
            if zone_key not in self.zone_structures[parent_key]:
                self.zone_structures[parent_key].append(zone_key)
            self.add_zone_connection(parent_key, zone_key, 'structure_entrance', cell_x, cell_y)

        # Fix up any entities spawned during placement: give them the zone's coords
        # and register them in screen_entities
        for eid in structure_data.get('entities', []):
            if eid not in self.screen_entities[zone_key]:
                self.screen_entities[zone_key].append(eid)
            if eid in self.entities:
                e = self.entities[eid]
                e.screen_x = vx
                e.screen_y = vy
                e.in_structure = True
                e.structure_key = zone_key

        return zone_key

    def generate_house_interior(self, depth):
        """Generate a house interior layout"""
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    if y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2 + 1:
                        row.append('FLOOR_WOOD')
                    else:
                        row.append('WALL')
                elif y == 0:
                    row.append('WALL')
                else:
                    if random.random() < 0.7:
                        row.append('FLOOR_WOOD')
                    else:
                        row.append('WOOD')
            grid.append(row)

        # Ensure doorway area is accessible
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2] = 'FLOOR_WOOD'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 - 1] = 'FLOOR_WOOD'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 + 1] = 'FLOOR_WOOD'

        # Place 0-3 barrels on random FLOOR_WOOD cells
        num_barrels = random.randint(0, 3)
        placed = 0
        attempts = 0
        while placed < num_barrels and attempts < 40:
            bx = random.randint(2, GRID_WIDTH - 3)
            by = random.randint(2, GRID_HEIGHT - 4)
            if grid[by][bx] == 'FLOOR_WOOD':
                grid[by][bx] = 'BARREL'
                placed += 1
            attempts += 1

        return grid

    def generate_cave_interior(self, depth):
        """Generate a cave interior layout"""
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    if depth == 1 and y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2 + 1:
                        row.append('CAVE_FLOOR')
                    else:
                        row.append('CAVE_WALL')
                elif y == 0:
                    row.append('CAVE_WALL')
                else:
                    rand = random.random()
                    ore_chance = 0.03 if depth == 1 else 0.07
                    stone_chance = 0.15 - ore_chance
                    if rand < ore_chance:
                        row.append('IRON_ORE')
                    elif rand < ore_chance + stone_chance:
                        row.append('STONE')
                    else:
                        row.append('CAVE_FLOOR')
            grid.append(row)

        # Ensure exit area is accessible
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2] = 'CAVE_FLOOR'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 - 1] = 'CAVE_FLOOR'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 + 1] = 'CAVE_FLOOR'

        # Deeper levels get STAIRS_UP
        if depth > 1:
            attempts = 0
            while attempts < 20:
                stairs_x = random.randint(3, GRID_WIDTH - 4)
                stairs_y = random.randint(3, GRID_HEIGHT - 6)
                if grid[stairs_y][stairs_x] == 'CAVE_FLOOR':
                    grid[stairs_y][stairs_x] = 'STAIRS_UP'
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            ny, nx = stairs_y + dy, stairs_x + dx
                            if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                                if grid[ny][nx] not in ['STAIRS_UP']:
                                    grid[ny][nx] = 'CAVE_FLOOR'
                    break
                attempts += 1

        # 70% chance to add STAIRS_DOWN for deeper exploration
        if random.random() < 0.7:
            attempts = 0
            while attempts < 20:
                stairs_x = random.randint(3, GRID_WIDTH - 4)
                stairs_y = random.randint(3, GRID_HEIGHT - 4)
                if grid[stairs_y][stairs_x] == 'CAVE_FLOOR':
                    grid[stairs_y][stairs_x] = 'STAIRS_DOWN'
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            ny, nx = stairs_y + dy, stairs_x + dx
                            if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                                if grid[ny][nx] not in ['STAIRS_DOWN', 'STAIRS_UP']:
                                    grid[ny][nx] = 'CAVE_FLOOR'
                    break
                attempts += 1

        return grid

    # -------------------------------------------------------------------------
    # Chest placement
    # -------------------------------------------------------------------------

    def place_house_chests(self, structure_data):
        """Place chests in house interior"""
        grid = structure_data['grid']
        num_chests = random.randint(1, 2)
        placed = 0
        attempts = 0

        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)

            if grid[y][x] in ['FLOOR_WOOD', 'WOOD'] and y < GRID_HEIGHT - 4:
                grid[y][x] = 'CHEST'
                structure_data['chests'][(x, y)] = 'HOUSE_CHEST'
                placed += 1

            attempts += 1

    def place_cave_chests(self, structure_data, depth):
        """Place chests in cave interior"""
        grid = structure_data['grid']
        num_chests = random.randint(1, 1 + depth)
        placed = 0
        attempts = 0
        loot_type = 'CAVE_DEEP_CHEST' if depth >= 3 else 'CAVE_CHEST'

        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)

            if grid[y][x] == 'CAVE_FLOOR':
                grid[y][x] = 'CHEST'
                structure_data['chests'][(x, y)] = loot_type
                placed += 1

            attempts += 1

    # -------------------------------------------------------------------------
    # House NPC spawn
    # -------------------------------------------------------------------------

    def spawn_house_npc(self, structure_data):
        """Spawn a single NPC (farmer or trader) in a house"""
        grid = structure_data['grid']
        npc_type = random.choice(['FARMER', 'TRADER'])

        attempts = 0
        while attempts < 50:
            x = random.randint(3, GRID_WIDTH - 4)
            y = random.randint(3, GRID_HEIGHT - 6)

            if grid[y][x] in ['FLOOR_WOOD', 'WOOD']:
                entity = Entity(npc_type, x, y, 0, 0, 1)  # coords fixed up by generate_structure_zone
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                self.entities[entity_id] = entity

                structure_data.setdefault('entities', [])
                structure_data['entities'].append(entity_id)

                print(f"Spawned {npc_type} in house")
                return entity_id

            attempts += 1

        return None

    # -------------------------------------------------------------------------
    # Zone connection management
    # -------------------------------------------------------------------------

    def add_zone_connection(self, zone_a, zone_b, connection_type, cell_x=0, cell_y=0):
        """Add a bidirectional connection between two zones."""
        if zone_a not in self.zone_connections:
            self.zone_connections[zone_a] = []
        if zone_b not in self.zone_connections:
            self.zone_connections[zone_b] = []

        existing_a = [(c[0], c[1]) for c in self.zone_connections[zone_a]]
        if (zone_b, connection_type) not in existing_a:
            self.zone_connections[zone_a].append((zone_b, connection_type, cell_x, cell_y))

        existing_b = [(c[0], c[1]) for c in self.zone_connections[zone_b]]
        if (zone_a, connection_type) not in existing_b:
            self.zone_connections[zone_b].append((zone_a, connection_type, cell_x, cell_y))

    def remove_zone_connection(self, zone_a, zone_b):
        """Remove all connections between two zones."""
        if zone_a in self.zone_connections:
            self.zone_connections[zone_a] = [c for c in self.zone_connections[zone_a] if c[0] != zone_b]
        if zone_b in self.zone_connections:
            self.zone_connections[zone_b] = [c for c in self.zone_connections[zone_b] if c[0] != zone_a]

    def register_structure_as_zone(self, parent_zone_key, cell_x, cell_y, structure_type):
        """Register a structure as a proper zone with connections. Returns the structure's zone key."""
        for struct_key, info in self.structure_zones.items():
            if (info['parent_zone'] == parent_zone_key and
                    info['cell'] == (cell_x, cell_y)):
                return struct_key

        struct_id = self.next_structure_zone_id
        self.next_structure_zone_id += 1
        struct_zone_key = f"struct_{struct_id}"

        self.structure_zones[struct_zone_key] = {
            'parent_zone': parent_zone_key,
            'type': structure_type,
            'cell': (cell_x, cell_y)
        }

        if parent_zone_key not in self.zone_structures:
            self.zone_structures[parent_zone_key] = []
        self.zone_structures[parent_zone_key].append(struct_zone_key)

        self.add_zone_connection(parent_zone_key, struct_zone_key, 'structure_entrance', cell_x, cell_y)

        return struct_zone_key
