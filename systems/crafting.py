import random

from constants import CELL_TYPES, ITEM_DECAY_CONFIG, ITEM_TO_CELL, ITEMS, RECIPES
from constants import GRID_WIDTH, GRID_HEIGHT


class CraftingMixin:
    """Handles crafting, item drops, pickup, placement, and dropped-item decay."""

    # -------------------------------------------------------------------------
    # Crafting
    # -------------------------------------------------------------------------

    def try_craft(self, item1, item2):
        """Try to craft two items together"""
        recipe_key = tuple(sorted([item1, item2]))

        if recipe_key in RECIPES:
            recipe = RECIPES[recipe_key]

            # Check if we have required items
            can_craft = True
            for item, amount in recipe['consumes'].items():
                if not self.inventory.has_item(item, amount):
                    can_craft = False
                    break

            if can_craft:
                # Consume items
                for item, amount in recipe['consumes'].items():
                    self.inventory.remove_item(item, amount)

                # Produce result
                self.inventory.add_item(recipe['result'], recipe['produces'])

    def attempt_craft(self):
        """Attempt to craft items using selections from any menu + crafting screen (X key)"""
        # Need something selected in crafting screen
        crafting_item = self.inventory.selected_crafting
        if not crafting_item:
            print("Select an item in crafting screen (C) first!")
            return

        # Find what's selected in other menus (items, tools, or magic)
        other_item = None
        other_category = None
        for category in ['items', 'tools', 'magic']:
            selected = self.inventory.selected.get(category)
            if selected:
                other_item = selected
                other_category = category
                break

        if not other_item:
            print("Select an item from Items (I), Tools (T), or Magic (M) menu!")
            return

        # Check both orderings of the recipe
        recipe1 = (crafting_item, other_item)
        recipe2 = (other_item, crafting_item)

        result = None
        if recipe1 in RECIPES:
            result = RECIPES[recipe1]
        elif recipe2 in RECIPES:
            result = RECIPES[recipe2]

        if not result:
            print(f"No recipe for {crafting_item} + {other_item}")
            return

        # Check if we have both items
        if not self.inventory.has_item(crafting_item):
            print(f"Don't have {crafting_item}!")
            return

        if not self.inventory.has_item(other_item):
            print(f"Don't have {other_item}!")
            return

        # Craft the item!
        # Remove ingredients
        self.inventory.remove_item(crafting_item, 1)
        self.inventory.remove_item(other_item, 1)

        # Special case: skeleton_bones spawns a skeleton follower immediately
        if result == 'skeleton_bones':
            skeleton_id = self.spawn_skeleton(self.player['x'], self.player['y'])
            if skeleton_id:
                # Add to followers list
                self.followers.append(skeleton_id)
                # Enchant it (level 1)
                self.enchanted_entities[skeleton_id] = 1
                # Add to follower inventory
                follower_name = f"skeleton_{skeleton_id}"
                skeleton = self.entities[skeleton_id]
                if follower_name not in ITEMS:
                    ITEMS[follower_name] = {
                        'color': skeleton.props['color'],
                        'name': 'Skeleton Follower',
                        'is_follower': True,
                        'entity_id': skeleton_id
                    }
                self.inventory.add_follower(follower_name, 1)
                print(f"Skeleton summoned and bound to your will!")
        else:
            # Normal crafting - add result to appropriate inventory
            self.inventory.add_item(result, 1)
            print(f"Crafted {ITEMS[result]['name']}!")

        # Update selections after crafting
        # If crafting_item was depleted, select the newly crafted item in crafting screen
        if not self.inventory.has_item(crafting_item):
            self.inventory.selected['crafting'] = result
        # If crafting_item still exists (had multiple), keep it selected

        # Update the other category selection
        if not self.inventory.has_item(other_item):
            # Other item is gone, try to select the result if it's in that category
            # Otherwise select the next available item in that category
            category_inv = getattr(self.inventory, other_category)
            if result in category_inv:
                self.inventory.selected[other_category] = result
            else:
                if category_inv:
                    self.inventory.selected[other_category] = list(category_inv.keys())[0]
                else:
                    self.inventory.selected[other_category] = None
        # If other_item still exists, keep it selected

    # -------------------------------------------------------------------------
    # Item drops & decay
    # -------------------------------------------------------------------------

    def handle_drops(self, cell_type, x, y):
        """Handle cell drops based on probabilities"""
        if cell_type not in CELL_TYPES:
            return

        cell_info = CELL_TYPES[cell_type]
        if 'drops' not in cell_info:
            return

        rand = random.random()
        cumulative = 0

        for drop in cell_info['drops']:
            cumulative += drop.get('chance', 0)
            if rand < cumulative:
                if 'item' in drop:
                    self.inventory.add_item(drop['item'], drop.get('amount', 1))
                if 'cell' in drop:
                    self.current_screen['grid'][y][x] = drop['cell']
                break

    def decay_dropped_items(self, screen_x, screen_y):
        """General function to decay dropped items based on item decay configuration"""
        screen_key = f"{screen_x},{screen_y}"

        if screen_key not in self.dropped_items or screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        cells_to_update = []

        # Check each position with dropped items
        for cell_pos, items in list(self.dropped_items[screen_key].items()):
            x, y = cell_pos
            current_cell = screen['grid'][y][x]

            # Process each item type at this position
            for item_name, item_count in list(items.items()):
                # Check if this item type has decay config
                if item_name not in ITEM_DECAY_CONFIG:
                    continue

                config = ITEM_DECAY_CONFIG[item_name]

                # Calculate decay chance (base rate * item count)
                decay_chance = config['decay_rate'] * item_count

                if random.random() < decay_chance:
                    # Decay one item
                    items[item_name] -= 1
                    if items[item_name] <= 0:
                        del items[item_name]

                    # Remove empty items dict
                    if not items:
                        del self.dropped_items[screen_key][cell_pos]

                    # Determine decay result based on current cell type
                    decay_results = config['decay_results']

                    # Get results for this cell type, or default
                    results = decay_results.get(current_cell, decay_results.get('default', [(None, 1.0)]))

                    # Weighted random selection of result
                    roll = random.random()
                    cumulative = 0.0
                    for result_cell, weight in results:
                        cumulative += weight
                        if roll < cumulative:
                            if result_cell is not None:
                                cells_to_update.append((x, y, result_cell))
                            break

        # Apply cell updates
        for x, y, new_cell in cells_to_update:
            self.set_grid_cell(screen, x, y, new_cell)

    def consolidate_dropped_items(self, screen_key):
        """Merge ALL dropped items within 3-cell range into the largest nearby pile.
        Runs every zone update. Very aggressive — items should never sit adjacent."""

        if screen_key not in self.dropped_items:
            return

        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        grid = screen['grid']
        items = self.dropped_items[screen_key]

        if len(items) <= 1:
            return

        # Multi-pass: keep merging until stable
        changed = True
        passes = 0
        while changed and passes < 5:
            changed = False
            passes += 1
            positions = list(items.keys())

            for pos in positions:
                if pos not in items:
                    continue

                ix, iy = pos
                my_count = sum(items[pos].values())

                # Find the best neighbor to merge with (within 3 cells)
                best_target = None
                best_count = -1
                best_dist = 999

                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = ix + dx, iy + dy
                        if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                            continue
                        neighbor_key = (nx, ny)
                        if neighbor_key not in items or neighbor_key == pos:
                            continue
                        neighbor_count = sum(items[neighbor_key].values())
                        dist = abs(dx) + abs(dy)
                        # Merge smaller into larger; if equal, merge into closer
                        if (neighbor_count > best_count or
                                (neighbor_count == best_count and dist < best_dist)):
                            cell = grid[ny][nx]
                            if not CELL_TYPES.get(cell, {}).get('solid', False):
                                best_target = neighbor_key
                                best_count = neighbor_count
                                best_dist = dist

                # Merge: smaller pile goes into larger, or into closer if equal
                if best_target:
                    if my_count <= best_count:
                        # Merge pos into best_target
                        for item_name, count in items[pos].items():
                            items[best_target][item_name] = items[best_target].get(item_name, 0) + count
                        del items[pos]
                        changed = True
                    elif my_count > best_count:
                        # Merge best_target into pos
                        for item_name, count in items[best_target].items():
                            items[pos][item_name] = items[pos].get(item_name, 0) + count
                        del items[best_target]
                        changed = True

    # -------------------------------------------------------------------------
    # Player item interactions (pickup / place / drop)
    # -------------------------------------------------------------------------

    def pickup_items(self, x, y):
        """Pick up dropped items from cell"""
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if screen_key not in self.dropped_items:
            return

        cell_key = (x, y)
        if cell_key in self.dropped_items[screen_key]:
            items_at_pos = self.dropped_items[screen_key][cell_key]
            runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']

            total_rune_damage = 0
            runes_to_destroy = {}

            for rune_type in runestone_types:
                if rune_type in items_at_pos:
                    rune_count = items_at_pos[rune_type]
                    # Damage = number of runes of this type
                    total_rune_damage += rune_count
                    # 50% of runes destroyed on pickup
                    destroyed = max(1, int(rune_count * 0.5))
                    runes_to_destroy[rune_type] = destroyed

            # Apply runestone damage to player
            if total_rune_damage > 0:
                self.player_take_damage(total_rune_damage)
                print(f"Player takes {total_rune_damage} damage from runestones!")

            # Pick up items
            for item_name, count in items_at_pos.items():
                # Destroy some runestones on pickup
                if item_name in runes_to_destroy:
                    destroyed = runes_to_destroy[item_name]
                    remaining = count - destroyed
                    if remaining > 0:
                        self.inventory.add_item(item_name, remaining)
                else:
                    self.inventory.add_item(item_name, count)

            del self.dropped_items[screen_key][cell_key]

    def drop_item(self, item_name, x, y):
        """Drop item onto cell (works in both overworld and subscreens)"""
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            screen_key = self.player['subscreen_key']
        if screen_key not in self.dropped_items:
            self.dropped_items[screen_key] = {}

        cell_key = (x, y)
        if cell_key not in self.dropped_items[screen_key]:
            self.dropped_items[screen_key][cell_key] = {}

        self.dropped_items[screen_key][cell_key][item_name] = \
            self.dropped_items[screen_key][cell_key].get(item_name, 0) + 1

    def pickup_cell_or_items(self):
        """Pick up cell EXACTLY as it is (creative/admin mode) or dropped items.
        Inside structures: cannot pick up base floor cells (except in mines).
        Picking up placed items inside structures restores the structure floor."""
        target = self.get_target_cell()
        if not target:
            return

        target_x, target_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        in_subscreen = self.player.get('in_subscreen', False)
        subscreen_key = self.player.get('subscreen_key')

        # Determine the correct screen key for subscreens
        if in_subscreen and subscreen_key:
            screen_key = subscreen_key

        # Check if cell is enchanted - cannot pick up enchanted cells
        if self.is_cell_enchanted(target_x, target_y, screen_key):
            cell_type = self.current_screen['grid'][target_y][target_x]
            if cell_type == 'WATER':
                print("Drank from enchanted water!")
                return
            print("Cannot pick up enchanted cell!")
            return

        # First try to pick up dropped items from ground
        if screen_key in self.dropped_items:
            cell_key = (target_x, target_y)
            if cell_key in self.dropped_items[screen_key]:
                for item_name, count in self.dropped_items[screen_key][cell_key].items():
                    self.inventory.add_item(item_name, count)
                del self.dropped_items[screen_key][cell_key]
                return

        # Pick up the cell EXACTLY as it is
        cell_type = self.current_screen['grid'][target_y][target_x]

        # Determine structure floor type (what to restore when picking up)
        structure_floor = None
        is_mine = False
        if in_subscreen and subscreen_key:
            subscreen = self.subscreens.get(subscreen_key)
            if subscreen:
                stype = subscreen.get('type', '')
                if stype == 'HOUSE_INTERIOR':
                    structure_floor = 'FLOOR_WOOD'
                elif stype == 'CAVE':
                    structure_floor = 'CAVE_FLOOR'
                    is_mine = True  # Caves/mines allow base cell pickup

        # Inside structures (non-mine): block pickup of base floor/wall cells
        if structure_floor and not is_mine:
            blocked_cells = {'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'WALL',
                             'STAIRS_UP', 'STAIRS_DOWN'}
            if cell_type in blocked_cells:
                print("Cannot pick up structural elements!")
                return

        # Create direct cell-to-item mapping for exact pickup
        exact_pickup_map = {
            'GRASS': 'grass', 'DIRT': 'dirt', 'SOIL': 'soil', 'SAND': 'sand',
            'WATER': 'water_bucket', 'DEEP_WATER': 'deep_water_bucket',
            'STONE': 'stone', 'TREE1': 'tree1', 'TREE2': 'tree2',
            'WALL': 'wall', 'HOUSE': 'house', 'CAVE': 'cave',
            'MINESHAFT': 'mineshaft', 'CAMP': 'camp', 'CHEST': 'chest',
            'CARROT1': 'carrot1', 'CARROT2': 'carrot2', 'CARROT3': 'carrot3',
            'FLOWER': 'flower', 'WOOD': 'wood', 'PLANKS': 'planks',
            'MEAT': 'meat', 'FUR': 'fur', 'BONES': 'bones'
        }

        if cell_type in exact_pickup_map:
            item_name = exact_pickup_map[cell_type]
            self.inventory.add_item(item_name, 1)

            # Replace cell: inside structures → restore structure floor, else biome base
            base = self.get_biome_base_cell()
            if structure_floor:
                self.current_screen['grid'][target_y][target_x] = structure_floor
            elif cell_type in ['CARROT1', 'CARROT2', 'CARROT3']:
                self.current_screen['grid'][target_y][target_x] = 'SOIL'
            else:
                self.current_screen['grid'][target_y][target_x] = base

    def place_selected_item(self):
        """Place selected item as a cell in the world, or as an overlay if no cell mapping.
        Inside structures, non-structural items are always placed as overlays
        to preserve the structure floor."""
        target = self.get_target_cell()
        if not target:
            return

        target_x, target_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        in_subscreen = self.player.get('in_subscreen', False)

        # Cannot place on enchanted cells
        if self.is_cell_enchanted(target_x, target_y, screen_key):
            print("Cannot place on enchanted cell!")
            return

        # Structural items that replace grid cells even inside structures
        structural_items = {'wall', 'house', 'cave', 'mineshaft', 'chest'}

        # Find which category has an item selected
        for category in ['items', 'tools', 'magic', 'followers']:
            selected = self.inventory.get_selected_item(category)
            if selected:
                if not self.inventory.has_item(selected):
                    continue

                # Inside structures: non-structural items always go as overlays
                if in_subscreen and selected not in structural_items and selected in ITEM_TO_CELL:
                    self.inventory.remove_item(selected, 1)
                    if in_subscreen and self.player.get('subscreen_key'):
                        sk = self.player['subscreen_key']
                    else:
                        sk = screen_key
                    if sk not in self.dropped_items:
                        self.dropped_items[sk] = {}
                    cell_key = (target_x, target_y)
                    if cell_key not in self.dropped_items[sk]:
                        self.dropped_items[sk][cell_key] = {}
                    self.dropped_items[sk][cell_key][selected] = \
                        self.dropped_items[sk][cell_key].get(selected, 0) + 1
                    return
                elif selected in ITEM_TO_CELL:
                    # Overworld: place as a grid cell (replaces the cell)
                    cell_type = ITEM_TO_CELL[selected]
                    self.current_screen['grid'][target_y][target_x] = cell_type
                    self.inventory.remove_item(selected, 1)
                    return
                else:
                    # No cell mapping — place as overlay
                    self.inventory.remove_item(selected, 1)
                    self.drop_item(selected, target_x, target_y)
                    return

    def drop_selected_item(self):
        """Drop currently selected item"""
        target = self.get_target_cell()
        if not target:
            return

        # Find which category has an item selected
        for category in ['items', 'tools', 'magic', 'followers']:
            selected = self.inventory.get_selected_item(category)
            if selected:
                if self.inventory.remove_item(selected, 1):
                    self.drop_item(selected, target[0], target[1])
                break
