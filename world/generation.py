import random

from constants import (
    GRID_WIDTH, GRID_HEIGHT,
    CELL_TYPES, BIOMES,
    NATURAL_CAVE_ZONE_CHANCE,
)
from entity import Entity


class WorldGenerationMixin:
    """Handles procedural world generation: screens, subscreens, interiors,
    chest placement, zone connections, and exit management."""

    # -------------------------------------------------------------------------
    # Main screen generation
    # -------------------------------------------------------------------------

    def generate_screen(self, sx, sy):
        """Generate a procedural screen"""
        key = f"{sx},{sy}"
        if key in self.screens:
            return self.screens[key]

        # Determine biome
        biome_roll = random.random()
        if biome_roll < 0.6:
            biome_name = 'FOREST'
        elif biome_roll < 0.8:
            biome_name = 'PLAINS'
        elif biome_roll < 0.95:
            biome_name = 'MOUNTAINS'
        else:
            biome_name = 'DESERT'
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
                     'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT'}.get(biome_name, 'GRASS')
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if y == 0 or y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
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

        # 30% chance to place a structure (HOUSE or CAVE)
        if random.random() > 0.7:
            struct_x = random.randint(2, GRID_WIDTH - 3)
            struct_y = random.randint(2, GRID_HEIGHT - 3)
            struct_type = random.choice(['HOUSE', 'CAVE'])
            grid[struct_y][struct_x] = struct_type

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

        # Natural cave formation — uncommon, favors mountains
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
                grid[0][x] = 'WALL'

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
                grid[GRID_HEIGHT - 1][x] = 'WALL'

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
                grid[y][0] = 'WALL'

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
                grid[y][GRID_WIDTH - 1] = 'WALL'

    def get_common_cell_for_biome(self, biome_name):
        """Get a common cell type for a biome"""
        biome_cells = {
            'FOREST': ['GRASS', 'GRASS', 'DIRT'],
            'PLAINS': ['GRASS', 'GRASS', 'DIRT'],
            'DESERT': ['SAND', 'SAND', 'DIRT'],
            'MOUNTAINS': ['DIRT', 'DIRT', 'GRASS'],
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

    def generate_subscreen(self, parent_screen_x, parent_screen_y, cell_x, cell_y, structure_type, depth=1):
        """Generate interior for house/cave (caves share one system per zone at depth 1)"""
        # For CAVE at depth 1, check if zone already has a cave system
        if structure_type == 'CAVE' and depth == 1:
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            if parent_key in self.zone_cave_systems:
                return self.zone_cave_systems[parent_key]

        # Create unique subscreen key
        subscreen_id = self.next_subscreen_id
        self.next_subscreen_id += 1
        subscreen_key = f"{parent_screen_x},{parent_screen_y}:{structure_type}:{subscreen_id}"

        if subscreen_key in self.subscreens:
            return subscreen_key

        # Generate interior grid
        if structure_type == 'HOUSE_INTERIOR':
            grid = self.generate_house_interior(depth)
        elif structure_type == 'CAVE':
            grid = self.generate_cave_interior(depth)
        else:
            grid = [['FLOOR_WOOD' for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]

        subscreen_data = {
            'type': structure_type,
            'parent_screen': (parent_screen_x, parent_screen_y),
            'parent_cell': (cell_x, cell_y),
            'grid': grid,
            'biome': structure_type,
            'depth': depth,
            'entrance': (GRID_WIDTH // 2, GRID_HEIGHT - 2),
            'exit': (GRID_WIDTH // 2, GRID_HEIGHT - 2),
            'stairs_down': None,
            'chests': {},
            'entrances': [(cell_x, cell_y)]
        }

        self.subscreens[subscreen_key] = subscreen_data

        # For caves at depth 1, register as zone's cave system
        if structure_type == 'CAVE' and depth == 1:
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            self.zone_cave_systems[parent_key] = subscreen_key

        # Place chests and spawn entities
        if structure_type == 'HOUSE_INTERIOR':
            self.place_house_chests(subscreen_data)
            if random.random() < 0.5:
                self.spawn_house_npc(subscreen_data)
        elif structure_type == 'CAVE':
            self.place_cave_chests(subscreen_data, depth)

        # Register structure as a zone in the priority system
        parent_key = f"{parent_screen_x},{parent_screen_y}"
        self.screens[subscreen_key] = subscreen_data
        self.screen_last_update[subscreen_key] = self.tick

        if subscreen_key not in self.structure_zones:
            self.structure_zones[subscreen_key] = {
                'parent_zone': parent_key,
                'type': structure_type,
                'cell': (cell_x, cell_y)
            }
            if parent_key not in self.zone_structures:
                self.zone_structures[parent_key] = []
            if subscreen_key not in self.zone_structures[parent_key]:
                self.zone_structures[parent_key].append(subscreen_key)
            self.add_zone_connection(parent_key, subscreen_key, 'structure_entrance', cell_x, cell_y)

        return subscreen_key

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
                    if random.random() < 0.15:
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

    def place_house_chests(self, subscreen_data):
        """Place chests in house interior"""
        grid = subscreen_data['grid']
        num_chests = random.randint(1, 2)
        placed = 0
        attempts = 0

        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)

            if grid[y][x] in ['FLOOR_WOOD', 'WOOD'] and y < GRID_HEIGHT - 4:
                grid[y][x] = 'CHEST'
                subscreen_data['chests'][(x, y)] = 'HOUSE_CHEST'
                placed += 1

            attempts += 1

    def place_cave_chests(self, subscreen_data, depth):
        """Place chests in cave interior"""
        grid = subscreen_data['grid']
        num_chests = random.randint(1, 1 + depth)
        placed = 0
        attempts = 0
        loot_type = 'CAVE_DEEP_CHEST' if depth >= 3 else 'CAVE_CHEST'

        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)

            if grid[y][x] == 'CAVE_FLOOR':
                grid[y][x] = 'CHEST'
                subscreen_data['chests'][(x, y)] = loot_type
                placed += 1

            attempts += 1

    # -------------------------------------------------------------------------
    # House NPC spawn
    # -------------------------------------------------------------------------

    def spawn_house_npc(self, subscreen_data):
        """Spawn a single NPC (farmer or trader) in a house"""
        grid = subscreen_data['grid']
        npc_type = random.choice(['FARMER', 'TRADER'])

        attempts = 0
        while attempts < 50:
            x = random.randint(3, GRID_WIDTH - 4)
            y = random.randint(3, GRID_HEIGHT - 6)

            if grid[y][x] in ['FLOOR_WOOD', 'WOOD']:
                entity = Entity(npc_type, x, y, 0, 0, 1)
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                self.entities[entity_id] = entity

                if 'entities' not in subscreen_data:
                    subscreen_data['entities'] = []
                subscreen_data['entities'].append(entity_id)

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
