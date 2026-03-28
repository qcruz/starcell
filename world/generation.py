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

    _ZONE_ADJECTIVES = [
        'Red', 'White', 'Black', 'Grey', 'Dark', 'Ancient', 'Twisted', 'Hollow',
        'Silent', 'Crimson', 'Golden', 'Iron', 'Silver', 'Shadow', 'Frost',
        'Ember', 'Verdant', 'Amber', 'Pale', 'Stone', 'Briar', 'Ashen',
    ]
    _ZONE_NOUNS = {
        'FOREST':    ['Oak', 'Pine', 'Ash', 'Elm', 'Thorn', 'Willow', 'Birch', 'Cedar', 'Yew', 'Bramble'],
        'DESERT':    ['Stone', 'Dune', 'Shard', 'Salt', 'Bone', 'Ash', 'Rock', 'Flint', 'Crag', 'Waste'],
        'MOUNTAINS': ['Peak', 'Ridge', 'Crag', 'Summit', 'Shard', 'Spire', 'Tor', 'Boulder', 'Cliff', 'Fang'],
        'PLAINS':    ['Field', 'Hollow', 'Dale', 'Vale', 'Heath', 'Moor', 'Glen', 'Lea', 'Fell', 'Mead'],
        'TUNDRA':    ['Frost', 'Ice', 'Snow', 'Drift', 'Chill', 'Rime', 'Bleak', 'Pale', 'Void', 'Hallow'],
        'SWAMP':     ['Fen', 'Mire', 'Bog', 'Marsh', 'Murk', 'Reed', 'Silt', 'Brine', 'Muck', 'Quag'],
    }
    _ZONE_BIOME_TYPES = {
        'FOREST':    ['Forest', 'Wood', 'Grove', 'Thicket'],
        'DESERT':    ['Desert', 'Wastes', 'Dunes', 'Barrens'],
        'MOUNTAINS': ['Mountains', 'Peaks', 'Highlands', 'Crags'],
        'PLAINS':    ['Plains', 'Fields', 'Vales', 'Downs'],
        'TUNDRA':    ['Tundra', 'Wastes', 'Expanse', 'Flats'],
        'SWAMP':     ['Swamp', 'Fens', 'Marshes', 'Mires'],
    }
    _CAVE_MODIFIERS = [
        'Mysterious', 'Dark', 'Eerie', 'Overgrown', 'Treacherous',
        'Forsaken', 'Ancient', 'Echoing', 'Shadowed', 'Hidden',
    ]
    _FALLBACK_HOUSE_NAMES = [
        "Aldric's House", "Mira's House", "Theron's House", "Edda's House",
        "Corvin's House", "Lena's House", "Bram's House", "Sable's House",
    ]

    def generate_zone_name(self, biome):
        """Generate a procedural zone name for the given biome."""
        adj = random.choice(self._ZONE_ADJECTIVES)
        noun = random.choice(self._ZONE_NOUNS.get(biome, ['Stone']))
        biome_type = random.choice(self._ZONE_BIOME_TYPES.get(biome, ['Land']))
        return f"{adj} {noun} {biome_type}"

    def generate_structure_name(self, structure_type, depth, parent_name, parent_screen_x, parent_screen_y):
        """Generate a name for a structure zone."""
        if structure_type == 'HOUSE_INTERIOR':
            # Try to find an NPC in the parent zone with a name
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            for eid in self.screen_entities.get(parent_key, []):
                e = self.entities.get(eid)
                if e and getattr(e, 'name', None):
                    return f"{e.name}'s House"
            return random.choice(self._FALLBACK_HOUSE_NAMES)
        elif structure_type == 'CAVE':
            if depth == 1:
                modifier = random.choice(self._CAVE_MODIFIERS)
                return f"{parent_name} {modifier} Cave"
            else:
                # Strip "Lvl N" suffix if present, then append new depth
                base = parent_name
                if ' Lvl ' in base:
                    base = base.rsplit(' Lvl ', 1)[0]
                return f"{base} Lvl {depth}"
        return structure_type

    # -------------------------------------------------------------------------
    # Main screen generation
    # -------------------------------------------------------------------------

    def generate_screen(self, sx, sy):
        """Generate a procedural screen"""
        key = f"{sx},{sy}"
        if key in self.screens:
            return self.screens[key]

        # Determine biome — equal chance for all biomes
        biome_name = random.choice(list(BIOMES.keys()))
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
                        row.append('WATER')
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
            'biome': biome_name,
            'name': self.generate_zone_name(biome_name),
            'controlling_faction': None,   # Faction name that controls this zone; persists until displaced
            'biome_domain_id': None,       # ID into self.domains for biome-based domain membership
            'faction_domain_id': None,     # ID into self.domains for faction-based domain membership
        }

        self.screens[key] = screen_data
        self.instantiated_zones.add(key)

        self.screen_last_update[key] = self.tick

        # Assign biome domain — merge with adjacent same-biome zones on generation
        self.update_biome_domain(key)

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

    def generate_structure_zone(self, parent_screen_x, parent_screen_y, cell_x, cell_y, structure_type, depth=1, align_x=None, align_y=None):
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
        stairs_down_pos = None
        if structure_type == 'HOUSE_INTERIOR':
            grid = self.generate_house_interior(depth)
            entrance_pos = (GRID_WIDTH // 2, GRID_HEIGHT - 2)
        elif structure_type == 'CAVE':
            ax = align_x if align_x is not None else cell_x
            ay = align_y if align_y is not None else cell_y
            grid, stairs_down_pos = self.generate_cave_interior(depth, ax, ay)
            entrance_pos = (max(2, min(GRID_WIDTH - 3, ax)), max(2, min(GRID_HEIGHT - 3, ay)))
        else:
            grid = [['FLOOR_WOOD' for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
            entrance_pos = (GRID_WIDTH // 2, GRID_HEIGHT - 2)

        parent_zone_name = self.screens.get(parent_key, {}).get('name', 'Unknown')
        structure_data = {
            'type': structure_type,
            'parent_screen': (parent_screen_x, parent_screen_y),
            'parent_cell': (cell_x, cell_y),
            'grid': grid,
            'biome': structure_type,
            'depth': depth,
            'entrance': entrance_pos,
            'exit': entrance_pos,
            'stairs_down': stairs_down_pos,
            'chests': {},
            'entrances': [(cell_x, cell_y)],
            'entities': [],
            'name': self.generate_structure_name(
                structure_type, depth, parent_zone_name,
                parent_screen_x, parent_screen_y
            ),
        }

        # Register as a full zone (in both dicts for backward-compat metadata lookups)
        self.structures[zone_key] = structure_data
        self.screens[zone_key] = structure_data
        self.instantiated_zones.add(zone_key)
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
            self._spawn_cave_entities(structure_data)

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

        # Place one bed against the top wall (50% blue, 50% white)
        _bed_candidates = [(x, 1) for x in range(2, GRID_WIDTH - 2) if grid[1][x] == 'FLOOR_WOOD']
        if _bed_candidates:
            bx, by = random.choice(_bed_candidates)
            grid[by][bx] = random.choice(['BED_BLUE', 'BED_WHITE'])

        # Place 0-2 furniture items (bookshelf, table, chair, potted plant) on floor
        _furniture_cells = ['BOOKSHELF', 'WOOD_TABLE', 'WOOD_CHAIR', 'SMALL_POTTED_PLANT']
        _furniture_count = random.randint(0, 2)
        _furniture_placed = 0
        _furniture_attempts = 0
        while _furniture_placed < _furniture_count and _furniture_attempts < 30:
            fx = random.randint(2, GRID_WIDTH - 3)
            fy = random.randint(2, GRID_HEIGHT - 4)
            if grid[fy][fx] == 'FLOOR_WOOD':
                grid[fy][fx] = random.choice(_furniture_cells)
                _furniture_placed += 1
            _furniture_attempts += 1

        # Guaranteed water trough placement
        _wt_attempts = 0
        while _wt_attempts < 30:
            wx = random.randint(2, GRID_WIDTH - 3)
            wy = random.randint(2, GRID_HEIGHT - 4)
            if grid[wy][wx] == 'FLOOR_WOOD':
                grid[wy][wx] = 'WATER_TROUGH'
                break
            _wt_attempts += 1

        # Place 0-2 empty crates + 1 guaranteed apple crate in interior corners (against walls)
        _corner_candidates = [
            (1, 1), (2, 1), (1, 2),
            (GRID_WIDTH - 2, 1), (GRID_WIDTH - 3, 1), (GRID_WIDTH - 2, 2),
            (1, GRID_HEIGHT - 3), (2, GRID_HEIGHT - 3),
            (GRID_WIDTH - 2, GRID_HEIGHT - 3), (GRID_WIDTH - 3, GRID_HEIGHT - 3),
        ]
        random.shuffle(_corner_candidates)
        _apple_placed = False
        _crates_placed = 0
        _crate_limit = random.randint(0, 2)
        for cx, cy in _corner_candidates:
            if 0 <= cy < GRID_HEIGHT and 0 <= cx < GRID_WIDTH and grid[cy][cx] == 'FLOOR_WOOD':
                if not _apple_placed:
                    grid[cy][cx] = 'APPLE_CRATE'
                    _apple_placed = True
                elif _crates_placed < _crate_limit:
                    grid[cy][cx] = 'EMPTY_CRATE'
                    _crates_placed += 1
                else:
                    break

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

    def generate_cave_interior(self, depth, entrance_x=None, entrance_y=None):
        """Generate a cave interior layout with fully walled borders.

        entrance_x/y: parent cell coordinates used to align STAIRS_UP position.
        STAIRS_UP is always placed at the aligned position (all depths).
        Returns (grid, stairs_down_pos) where stairs_down_pos is (x, y) or None.
        """
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if y == 0 or y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
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

        # STAIRS_UP: aligned with parent entrance, clamped to interior bounds
        up_x = max(2, min(GRID_WIDTH - 3, entrance_x if entrance_x is not None else GRID_WIDTH // 2))
        up_y = max(2, min(GRID_HEIGHT - 3, entrance_y if entrance_y is not None else GRID_HEIGHT // 2))
        # Clear 3x3 area around stairs to ensure walkability
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                ny, nx = up_y + dy, up_x + dx
                if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                    grid[ny][nx] = 'CAVE_FLOOR'
        grid[up_y][up_x] = 'STAIRS_UP'

        # Scatter a small mushroom cluster (1-3 seeds on CAVE_FLOOR; CA grows the rest)
        _mush_seeds = random.randint(1, 3)
        _mush_placed = 0
        _mush_attempts = 0
        while _mush_placed < _mush_seeds and _mush_attempts < 40:
            mx = random.randint(2, GRID_WIDTH - 3)
            my = random.randint(2, GRID_HEIGHT - 3)
            if grid[my][mx] == 'CAVE_FLOOR':
                grid[my][mx] = 'BLUE_MUSHROOM'
                _mush_placed += 1
            _mush_attempts += 1

        # 20% chance to place a water trough
        if random.random() < 0.20:
            _wt_attempts = 0
            while _wt_attempts < 20:
                wx = random.randint(2, GRID_WIDTH - 3)
                wy = random.randint(2, GRID_HEIGHT - 3)
                if grid[wy][wx] == 'CAVE_FLOOR':
                    grid[wy][wx] = 'WATER_TROUGH'
                    break
                _wt_attempts += 1

        # 70% chance to add STAIRS_DOWN for deeper exploration
        stairs_down_pos = None
        if random.random() < 0.7:
            attempts = 0
            while attempts < 20:
                sx = random.randint(3, GRID_WIDTH - 4)
                sy = random.randint(3, GRID_HEIGHT - 4)
                if grid[sy][sx] == 'CAVE_FLOOR':
                    grid[sy][sx] = 'STAIRS_DOWN'
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            ny, nx = sy + dy, sx + dx
                            if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                                if grid[ny][nx] not in ('STAIRS_DOWN', 'STAIRS_UP'):
                                    grid[ny][nx] = 'CAVE_FLOOR'
                    stairs_down_pos = (sx, sy)
                    break
                attempts += 1

        return grid, stairs_down_pos

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
                grid[y][x] = 'LOCKED_CHEST'
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
                grid[y][x] = 'LOCKED_CHEST'
                structure_data['chests'][(x, y)] = loot_type
                placed += 1

            attempts += 1

    # -------------------------------------------------------------------------
    # House NPC spawn
    # -------------------------------------------------------------------------

    def _spawn_cave_entities(self, structure_data):
        """Spawn bats and spiders in a newly generated cave interior."""
        grid = structure_data['grid']
        # Collect walkable positions away from the entrance
        entrance_x, entrance_y = structure_data.get('entrance', (GRID_WIDTH // 2, GRID_HEIGHT - 2))
        walkable = [
            (x, y) for y in range(1, GRID_HEIGHT - 1) for x in range(1, GRID_WIDTH - 1)
            if not CELL_TYPES.get(grid[y][x], {}).get('solid', False)
            and abs(x - entrance_x) + abs(y - entrance_y) > 4
        ]
        if not walkable:
            return
        random.shuffle(walkable)
        spawned = 0
        for x, y in walkable:
            if spawned >= 4:
                break
            ntype = 'BAT' if random.random() < 0.6 else 'SPIDER'
            chance = 0.35 if ntype == 'BAT' else 0.25
            if random.random() < chance:
                ent = Entity(ntype, x, y, 0, 0, 1)
                eid = self.next_entity_id
                self.next_entity_id += 1
                self.entities[eid] = ent
                structure_data.setdefault('entities', []).append(eid)
                spawned += 1

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
