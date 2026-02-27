"""
NPC AI Actions Mixin
Primitive actions NPCs perform: harvesting, transforming, placing cells,
dealing damage, collecting drops, placing camps, and related helpers.
"""
import random
from data import *
from engine import *


class NpcAiActionsMixin:

    def action_harvest_cell(self, actor, screen_key, cell_types, success_rate=0.5,
                            result_cell=None, activity=None):
        """Universal harvest: chop tree, mine rock, harvest crop.
        Checks adjacent cells for matching types, applies drops, transforms cell.
        Works for both entities and player (actor = entity or 'player').
        Returns True if action was performed."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        is_player = (actor == 'player')
        ax = self.player['x'] if is_player else actor.x
        ay = self.player['y'] if is_player else actor.y

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = ax + dx, ay + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            cell = screen['grid'][cy][cx]
            if cell not in cell_types:
                continue

            # Face target + animate
            if not is_player and hasattr(actor, 'update_facing_toward'):
                actor.update_facing_toward(cx, cy)
                actor.trigger_action_animation()
            self.show_attack_animation(cx, cy, entity=None if is_player else actor)

            # XP for entity
            if not is_player:
                actor.xp += 1
                if actor.xp >= actor.xp_to_level:
                    actor.level_up()

            # Success roll
            if random.random() < success_rate:
                # Apply drops from CELL_TYPES
                drops = CELL_TYPES.get(cell, {}).get('drops', [])
                for drop in drops:
                    if random.random() < drop.get('chance', 1.0):
                        if 'item' in drop:
                            if is_player:
                                self.inventory.add_item(drop['item'], drop.get('amount', 1))
                            else:
                                actor.inventory[drop['item']] = actor.inventory.get(
                                    drop['item'], 0) + drop.get('amount', 1)
                        if 'cell' in drop:
                            screen['grid'][cy][cx] = drop['cell']

                # Harvest data (for crops)
                harvest_info = CELL_TYPES.get(cell, {}).get('harvest')
                if harvest_info:
                    item = harvest_info['item']
                    amount = harvest_info['amount']
                    if is_player:
                        self.inventory.add_item(item, amount)
                    else:
                        actor.inventory[item] = actor.inventory.get(item, 0) + amount

                # Transform cell if specified
                if result_cell:
                    screen['grid'][cy][cx] = result_cell
                elif not drops:
                    # Default: turn to GRASS
                    screen['grid'][cy][cx] = 'GRASS'

                # Level-up from activity
                if not is_player and activity:
                    actor.level_up_from_activity(activity, self)

            return True
        return False

    def action_transform_cell(self, actor, screen_key, cell_types, result_cell,
                              success_rate=0.25, activity=None):
        """Transform an adjacent cell type (e.g. DIRT→SOIL, GRASS→COBBLESTONE).
        Returns True if action was performed."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        is_player = (actor == 'player')
        ax = self.player['x'] if is_player else actor.x
        ay = self.player['y'] if is_player else actor.y

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = ax + dx, ay + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            cell = screen['grid'][cy][cx]
            if cell not in cell_types:
                continue

            if not is_player and hasattr(actor, 'update_facing_toward'):
                actor.update_facing_toward(cx, cy)
                actor.trigger_action_animation()
            self.show_attack_animation(cx, cy, entity=None if is_player else actor)

            if not is_player:
                actor.xp += 1
                if actor.xp >= actor.xp_to_level:
                    actor.level_up()

            if random.random() < success_rate:
                screen['grid'][cy][cx] = result_cell
                if not is_player and activity:
                    actor.level_up_from_activity(activity, self)
            return True
        return False

    def action_place_cell(self, actor, screen_key, cell_types, result_cell,
                          consume_items=None, success_rate=0.3, activity=None):
        """Place something on an adjacent cell (e.g. plant seed on SOIL→CARROT1).
        Optionally consumes an item from inventory. Returns True if action was performed."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        is_player = (actor == 'player')

        # Check if actor has required items
        if consume_items:
            has_item = False
            for item_name in consume_items:
                if is_player:
                    if self.inventory.has_item(item_name):
                        has_item = True
                        break
                else:
                    if actor.inventory.get(item_name, 0) > 0:
                        has_item = True
                        break
            # NPCs get a 20% chance to plant even without items (representing stored seeds)
            if not has_item and (is_player or random.random() > 0.2):
                return False

        ax = self.player['x'] if is_player else actor.x
        ay = self.player['y'] if is_player else actor.y

        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = ax + dx, ay + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            if screen['grid'][cy][cx] not in cell_types:
                continue

            if not is_player and hasattr(actor, 'update_facing_toward'):
                actor.update_facing_toward(cx, cy)
                actor.trigger_action_animation()

            if not is_player:
                actor.xp += 1
                if actor.xp >= actor.xp_to_level:
                    actor.level_up()

            if random.random() < success_rate:
                screen['grid'][cy][cx] = result_cell
                # Consume item
                if consume_items:
                    for item_name in consume_items:
                        if is_player:
                            if self.inventory.has_item(item_name):
                                self.inventory.remove_item(item_name, 1)
                                break
                        else:
                            if actor.inventory.get(item_name, 0) > 0:
                                actor.inventory[item_name] -= 1
                                break
                if not is_player and activity:
                    actor.level_up_from_activity(activity, self)
            return True
        return False

    def action_damage(self, attacker, target, amount, damage_type='physical'):
        """Universal damage — entity→entity, entity→player, player→entity.
        Returns actual damage dealt."""
        if target == 'player':
            return self.player_take_damage(amount)
        elif hasattr(target, 'health'):
            actual = min(amount, target.health)
            target.health -= actual
            if target.health <= 0:
                target.is_dead = True
                target.killed_by = 'player' if attacker == 'player' else getattr(attacker, 'type', 'unknown')
            return actual
        return 0

    def action_heal(self, target, amount):
        """Universal heal for entity or player."""
        if target == 'player':
            self.player['health'] = min(self.player['health'] + amount, self.player['max_health'])
        elif hasattr(target, 'health'):
            target.health = min(target.health + amount, target.max_health)

    def execute_npc_behavior(self, entity, screen_key):
        """Data-driven NPC behavior: run through behavior table for entity type."""
        behaviors = NPC_BEHAVIORS.get(entity.type, [])
        for b in behaviors:
            action = b['action']
            rate = b.get('rate', 1.0)

            # Rate check — skip this action most of the time
            if random.random() > rate:
                continue

            if action == 'harvest_cell':
                if self.action_harvest_cell(entity, screen_key, b['cells'],
                                            b.get('success', 0.5),
                                            b.get('result_cell'),
                                            b.get('activity')):
                    return True

            elif action == 'transform_cell':
                if self.action_transform_cell(entity, screen_key, b['cells'],
                                              b['result_cell'],
                                              b.get('success', 0.25),
                                              b.get('activity')):
                    return True

            elif action == 'place_cell':
                if self.action_place_cell(entity, screen_key, b['cells'],
                                          b['result_cell'],
                                          b.get('consume'),
                                          b.get('success', 0.3),
                                          b.get('activity')):
                    return True

            elif action == 'build':
                if self._try_build_structure(entity, screen_key, b):
                    return True

        return False

    def _try_build_structure(self, entity, screen_key, build_params):
        """Try to build a structure from behavior table params."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        structure = build_params['structure']
        cost = build_params.get('cost', {})
        max_count = build_params.get('max_per_zone', 999)
        valid_cells = build_params.get('valid_cells', ['GRASS', 'DIRT'])

        # Check cost
        for item, amount in cost.items():
            if entity.inventory.get(item, 0) < amount:
                return False

        # Count existing structures
        count = sum(1 for row in screen['grid'] for c in row if c == structure)
        if count >= max_count:
            return False

        # Find build spot (prefer near specific cell type)
        prefer_near = build_params.get('prefer_near')
        spots = []
        for by in range(2, GRID_HEIGHT - 3):
            for bx in range(2, GRID_WIDTH - 3):
                if screen['grid'][by][bx] not in valid_cells:
                    continue
                if prefer_near:
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            ny, nx = by + dy, bx + dx
                            if 0 <= ny < GRID_HEIGHT and 0 <= nx < GRID_WIDTH:
                                if screen['grid'][ny][nx] == prefer_near:
                                    spots.append((bx, by))
                                    break
                        if spots and spots[-1] == (bx, by):
                            break
                else:
                    spots.append((bx, by))

        if not spots:
            # Fallback: random spot
            for _ in range(20):
                bx = random.randint(2, GRID_WIDTH - 3)
                by = random.randint(2, GRID_HEIGHT - 3)
                if screen['grid'][by][bx] in valid_cells:
                    spots.append((bx, by))
                    break

        if spots:
            bx, by = random.choice(spots[:10])  # Pick from top candidates
            for item, amount in cost.items():
                entity.inventory[item] -= amount
            screen['grid'][by][bx] = structure
            if build_params.get('activity'):
                entity.level_up_from_activity(build_params['activity'], self)
            name = entity.name if entity.name else entity.type
            print(f"{name} built {structure} at [{screen_key}] ({bx},{by})")
            return True
        return False

    def try_chop_tree(self, entity, screen_key):
        """Try to chop nearby trees"""
        screen = self.screens[screen_key]

        # Count nearby trees for density bonus
        nearby_trees = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if screen['grid'][check_y][check_x] in ['TREE1', 'TREE2']:
                        nearby_trees += 1

        # Calculate chop rate with density bonus
        chop_rate = LUMBERJACK_BASE_CHOP_RATE + (nearby_trees * LUMBERJACK_DENSITY_BONUS)

        # Add level multiplier for lumberjacks (10% increase per level)
        if entity.type == 'LUMBERJACK':
            level_multiplier = 1 + (entity.level * 0.1)
            chop_rate *= level_multiplier

        chop_rate = min(chop_rate, 0.8)  # Cap at 80% (increased to allow level scaling)

        # Try to chop adjacent tree (cardinal directions only)
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            check_x = entity.x + dx
            check_y = entity.y + dy
            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                cell = screen['grid'][check_y][check_x]
                if cell in ['TREE1', 'TREE2']:
                    entity.update_facing_toward(check_x, check_y)
                    entity.trigger_action_animation()
                    self.show_attack_animation(check_x, check_y, entity=entity)

                    # Grant 1 XP for action
                    entity.xp += 1
                    if entity.xp >= entity.xp_to_level:
                        entity.level_up()

                    if random.random() < LUMBERJACK_CHOP_SUCCESS:
                        drops = CELL_TYPES[cell].get('drops', [])
                        # Tool gate: autopilot proxy only collects items if
                        # player has an axe; the cell still transforms either way.
                        is_proxy = entity.props.get('is_autopilot_proxy', False)
                        has_tool = (not is_proxy or
                                    (hasattr(self, 'inventory') and self.inventory.has_item('axe')))
                        for drop in drops:
                            if random.random() < drop['chance']:
                                if 'item' in drop and has_tool:
                                    entity.inventory[drop['item']] = entity.inventory.get(drop['item'], 0) + drop['amount']
                                elif 'cell' in drop:
                                        screen['grid'][check_y][check_x] = drop['cell']
                        entity.level_up_from_activity('chop', self)
                    return

    def try_mine_rock(self, entity, screen_key):
        """Try to mine nearby rocks (similar to chopping trees)"""
        screen = self.screens[screen_key]

        # Count nearby rocks for density bonus
        nearby_rocks = 0
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if screen['grid'][check_y][check_x] == 'STONE':
                        nearby_rocks += 1

        # Calculate mine rate with density bonus (similar to lumberjack)
        mine_rate = LUMBERJACK_BASE_CHOP_RATE + (nearby_rocks * LUMBERJACK_DENSITY_BONUS)
        mine_rate = min(mine_rate, 0.6)  # Cap at 60%

        # Try to mine adjacent rock
        found_rock = False
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    if cell == 'STONE':
                        found_rock = True
                        entity.update_facing_toward(check_x, check_y)
                        entity.trigger_action_animation()
                        self.show_attack_animation(check_x, check_y, entity=entity)

                        # Grant 1 XP for action
                        entity.xp += 1
                        if entity.xp >= entity.xp_to_level:
                            entity.level_up()

                        if random.random() < MINER_MINE_SUCCESS:
                            # Tool gate: proxy only collects stone if player has pickaxe
                            is_proxy = entity.props.get('is_autopilot_proxy', False)
                            has_tool = (not is_proxy or
                                        (hasattr(self, 'inventory') and
                                         (self.inventory.has_item('pickaxe') or self.inventory.has_item('stone_pickaxe'))))

                            # NPC miners can create mineshafts (limited per zone)
                            mineshaft_count = sum(1 for row in screen['grid']
                                                  for c in row if c == 'MINESHAFT')
                            can_create_shaft = (mineshaft_count < MINESHAFT_MAX_PER_ZONE)

                            if can_create_shaft and random.random() < MINER_MINESHAFT_CHANCE:
                                # Create mineshaft entrance
                                screen['grid'][check_y][check_x] = 'MINESHAFT'
                                if has_tool:
                                    entity.inventory['stone'] = entity.inventory.get('stone', 0) + 1
                                print(f"Miner dug a mineshaft at ({check_x}, {check_y})!")
                                entity.level_up_from_activity('mine', self)
                            else:
                                # Mine the rock - convert to dirt, give stone only with tool
                                if has_tool:
                                    entity.inventory['stone'] = entity.inventory.get('stone', 0) + 2
                                screen['grid'][check_y][check_x] = 'DIRT'
                                entity.level_up_from_activity('mine', self)
                        return

        # No rocks nearby - move toward nearest corner to mine
        if not found_rock:
            target_corner = self.get_nearest_corner_target(entity.x, entity.y)
            if target_corner:
                self.move_entity_towards(entity, target_corner[0], target_corner[1])

    def try_plant_seed(self, entity, screen_key):
        """Face and plant on exactly one adjacent SOIL cell. Returns True if acted."""
        has_carrot = entity.inventory.get('carrot', 0) > 0
        has_seeds  = entity.inventory.get('seeds', 0) > 0
        # 20% chance to plant even without inventory items (stored seeds abstraction)
        if not (has_carrot or has_seeds or random.random() < 0.2):
            return False
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = entity.x + dx, entity.y + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            if screen['grid'][cy][cx] != 'SOIL':
                continue
            # Face + animate — entity is already stopped when this fires
            entity.update_facing_toward(cx, cy)
            entity.trigger_action_animation()
            self.show_attack_animation(cx, cy, entity=entity)
            entity.xp += 1
            if entity.xp >= entity.xp_to_level:
                entity.level_up()
            if random.random() < FARMER_PLANT_SUCCESS:
                screen['grid'][cy][cx] = 'CARROT1'
                if has_carrot:
                    entity.inventory['carrot'] -= 1
                elif has_seeds:
                    entity.inventory['seeds'] -= 1
            return True   # acted on this cell; stop scanning
        return False

    def try_harvest_crop(self, entity, screen_key):
        """Face and harvest exactly one adjacent mature crop. Returns True if acted."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = entity.x + dx, entity.y + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            cell = screen['grid'][cy][cx]
            if cell not in ('CARROT3', 'CARROT2'):
                continue
            entity.update_facing_toward(cx, cy)
            entity.trigger_action_animation()
            self.show_attack_animation(cx, cy, entity=entity)
            entity.xp += 1
            if entity.xp >= entity.xp_to_level:
                entity.level_up()
            if random.random() < FARMER_HARVEST_SUCCESS:
                harvest_info = CELL_TYPES[cell].get('harvest')
                if harvest_info:
                    item, amount = harvest_info['item'], harvest_info['amount']
                    entity.inventory[item] = entity.inventory.get(item, 0) + amount
                screen['grid'][cy][cx] = 'SOIL'
                entity.level_up_from_activity('harvest', self)
            return True   # acted; stop scanning
        return False

    def try_till_soil(self, entity, screen_key):
        """Face and till exactly one adjacent GRASS or DIRT cell. Returns True if acted."""
        if screen_key not in self.screens:
            return False
        screen = self.screens[screen_key]
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = entity.x + dx, entity.y + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            if screen['grid'][cy][cx] not in ('GRASS', 'DIRT'):
                continue
            entity.update_facing_toward(cx, cy)
            entity.trigger_action_animation()
            self.show_attack_animation(cx, cy, entity=entity)
            entity.xp += 1
            if entity.xp >= entity.xp_to_level:
                entity.level_up()
            if random.random() < FARMER_TILL_SUCCESS:
                screen['grid'][cy][cx] = 'SOIL'
            return True   # acted; stop scanning
        return False

    def try_clear_tree(self, entity, screen_key):
        """Non-lumberjack NPCs clear trees without collecting wood"""
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Check adjacent cells for trees
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    if cell in ['TREE1', 'TREE2']:
                        # Clear tree - apply drop effects but don't collect wood
                        drops = CELL_TYPES[cell].get('drops', [])
                        for drop in drops:
                            if random.random() < drop['chance']:
                                # Only apply cell transformations (TREE -> GRASS/DIRT)
                                # Don't add wood to inventory
                                if 'cell' in drop:
                                    screen['grid'][check_y][check_x] = drop['cell']
                        return

    def try_build_house(self, entity, screen_key):
        """Try to build a house if entity has enough wood (chance reduced by existing houses)"""
        if entity.inventory.get('wood', 0) >= 10:
            # Count existing houses in zone
            screen = self.screens[screen_key]
            house_count = 0
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if screen['grid'][y][x] == 'HOUSE':
                        house_count += 1

            # Reduce build chance based on house count
            # 0 houses: 100% of base rate
            # 1 house: 50% of base rate
            # 2 houses: 33% of base rate
            # 3+ houses: 25% of base rate
            if house_count == 0:
                build_chance = LUMBERJACK_BUILD_RATE
            else:
                build_chance = LUMBERJACK_BUILD_RATE / (house_count + 1)

            if random.random() < build_chance:
                # Find nearby empty spot
                for dy in range(-2, 3):
                    for dx in range(-2, 3):
                        check_x = entity.x + dx
                        check_y = entity.y + dy
                        if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                            cell = screen['grid'][check_y][check_x]
                            if cell in ['GRASS', 'DIRT']:
                                entity.update_facing_toward(check_x, check_y)
                                entity.trigger_action_animation()
                                self.show_attack_animation(check_x, check_y, entity=entity)

                                # Grant 1 XP for action
                                entity.xp += 1
                                if entity.xp >= entity.xp_to_level:
                                    entity.level_up()

                                if random.random() < LUMBERJACK_BUILD_SUCCESS:
                                    screen['grid'][check_y][check_x] = 'HOUSE'
                                    entity.inventory['wood'] -= 10
                                    entity.level_up_from_activity('build', self)
                                return

    def try_build_path(self, entity, screen_key):
        """Build paths while walking (traders and guards)"""
        screen = self.screens[screen_key]
        cell = screen['grid'][entity.y][entity.x]

        # Calculate center lanes (middle 3 columns and middle 3 rows)
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        in_vertical_lane = abs(entity.x - center_x) <= 1  # Within 1 of center column
        in_horizontal_lane = abs(entity.y - center_y) <= 1  # Within 1 of center row
        in_middle_lanes = in_vertical_lane or in_horizontal_lane

        # Convert current cell to dirt/cobblestone
        if cell == 'GRASS':
            if random.random() < TRADER_PATH_BUILD_RATE:
                screen['grid'][entity.y][entity.x] = 'DIRT'
        elif cell == 'DIRT':
            # Only build cobblestone in middle lanes
            if in_middle_lanes and random.random() < TRADER_COBBLE_RATE:
                screen['grid'][entity.y][entity.x] = 'COBBLESTONE'

    def try_build_forge(self, entity, screen_key):
        """Blacksmith tries to build forge if has enough stone"""
        if entity.inventory.get('stone', 0) >= 15:
            # Count existing forges in zone (max 1 per zone)
            screen = self.screens[screen_key]
            forge_count = 0
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if screen['grid'][y][x] == 'FORGE':
                        forge_count += 1

            # Only build if no forge exists
            if forge_count == 0:
                if random.random() < 0.1:  # 10% chance
                    # Find nearby empty spot
                    for dy in range(-2, 3):
                        for dx in range(-2, 3):
                            check_x = entity.x + dx
                            check_y = entity.y + dy
                            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                cell = screen['grid'][check_y][check_x]
                                if cell in ['GRASS', 'DIRT', 'STONE']:
                                    screen['grid'][check_y][check_x] = 'FORGE'
                                    entity.inventory['stone'] -= 15
                                    entity.level_up_from_activity('build', self)
                                    print(f"{entity.name} built a forge!")
                                    return

    def pickup_dropped_items(self, entity, screen_key):
        """Entity picks up any dropped items at their position"""
        if screen_key not in self.dropped_items:
            return

        drop_key = (entity.x, entity.y)
        if drop_key not in self.dropped_items[screen_key]:
            return

        # Check for runestones and apply damage
        items_at_pos = self.dropped_items[screen_key][drop_key]
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

        # Apply runestone damage
        if total_rune_damage > 0:
            entity.take_damage(total_rune_damage, 'runestone')
            print(f"{entity.name} takes {total_rune_damage} damage from runestones!")

        # Pick up all items at this position
        items_picked_up = 0
        for item_name, amount in list(items_at_pos.items()):
            # Destroy some runestones on pickup
            if item_name in runes_to_destroy:
                destroyed = runes_to_destroy[item_name]
                remaining = amount - destroyed
                if remaining > 0:
                    entity.inventory[item_name] = entity.inventory.get(item_name, 0) + remaining
                    items_picked_up += remaining
                # Don't add destroyed runes
            else:
                # Add to entity inventory (non-rune items)
                entity.inventory[item_name] = entity.inventory.get(item_name, 0) + amount
                items_picked_up += amount

        # NPCs gain XP from picking up items (1 XP per item)
        if items_picked_up > 0 and hasattr(entity, 'xp'):
            entity.xp += items_picked_up

        # Remove from dropped items
        del self.dropped_items[screen_key][drop_key]

    def process_entity_drop(self, entity, screen_key):
        """Process item drops when entity dies"""
        if 'drops' not in entity.props:
            return

        # Get drop position
        drop_x, drop_y = entity.x, entity.y

        # Spawn runestones (rare)
        if random.random() < 0.10:
          self.spawn_runestones_for_screen(drop_x, drop_y)

        # Process each potential drop
        for drop in entity.props['drops']:
            if random.random() < drop['chance']:
                item_name = drop['item']
                amount = drop['amount']

                # Add to dropped items on the screen
                if screen_key not in self.dropped_items:
                    self.dropped_items[screen_key] = {}

                drop_key = f"{drop_x},{drop_y}"
                if drop_key not in self.dropped_items[screen_key]:
                    self.dropped_items[screen_key][drop_key] = {}

                if item_name in self.dropped_items[screen_key][drop_key]:
                    self.dropped_items[screen_key][drop_key][item_name] += amount
                else:
                    self.dropped_items[screen_key][drop_key][item_name] = amount

    def npc_place_camp(self, entity):
        """NPC places a campsite if none exists in the zone"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Check if camp already exists
        for row in screen['grid']:
            for cell in row:
                if cell == 'CAMP':
                    return  # Camp already exists

        # Count houses in zone
        house_count = 0
        for row in screen['grid']:
            for cell in row:
                if cell == 'HOUSE':
                    house_count += 1

        # Find existing camps and decide upgrade/decay
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if screen['grid'][y][x] == 'CAMP':
                    # If more than 5 houses, camps decay to dirt (settlement established)
                    if house_count > 5 and random.random() < 0.05:
                        screen['grid'][y][x] = 'DIRT'
                        if random.random() < 0.1:
                            print(f"Camp decayed at [{screen_key}] - settlement has {house_count} houses")
                        return

                    # Otherwise, chance to upgrade camp to house
                    elif random.random() < 0.02:  # 2% chance
                        screen['grid'][y][x] = 'HOUSE'

                        # Chance to level up from building
                        entity.level_up_from_activity('build', self)

                        name_str = entity.name if entity.name else entity.type
                        print(f"{name_str} upgraded camp to house at [{screen_key}] ({x}, {y})")
                        return

        # Find suitable spot near entity to place new camp
        for _ in range(10):
            place_x = entity.x + random.randint(-2, 2)
            place_y = entity.y + random.randint(-2, 2)

            if 0 <= place_x < GRID_WIDTH and 0 <= place_y < GRID_HEIGHT:
                cell = screen['grid'][place_y][place_x]
                if cell in ['GRASS', 'DIRT', 'SAND']:
                    screen['grid'][place_y][place_x] = 'CAMP'
                    return

    def miner_place_cave(self, entity):
        """Miner creates a cave at zone corners"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Count existing caves in zone
        cave_count = 0
        for row in screen['grid']:
            for cell in row:
                if cell in ['CAVE', 'HIDDEN_CAVE']:
                    cave_count += 1

        # Don't create more than 2 caves per zone
        if cave_count >= 2:
            return

        # Try to place cave at a corner location
        corners = [
            (2, 2),  # Top-left
            (GRID_WIDTH - 3, 2),  # Top-right
            (2, GRID_HEIGHT - 3),  # Bottom-left
            (GRID_WIDTH - 3, GRID_HEIGHT - 3)  # Bottom-right
        ]

        # Shuffle corners to randomize placement
        random.shuffle(corners)

        for corner_x, corner_y in corners:
            # Try positions around the corner
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    place_x = corner_x + dx
                    place_y = corner_y + dy

                    if 0 < place_x < GRID_WIDTH - 1 and 0 < place_y < GRID_HEIGHT - 1:
                        cell = screen['grid'][place_y][place_x]
                        # Can place cave on non-solid ground
                        if cell in ['GRASS', 'DIRT', 'SAND', 'STONE']:
                            screen['grid'][place_y][place_x] = 'CAVE'

                            # Chance to level up from discovery
                            entity.level_up_from_activity('mine', self)

                            name_str = entity.name if entity.name else entity.type
                            print(f"{name_str} discovered a cave at corner ({place_x}, {place_y}) in [{screen_key}]!")
                            return

    def try_npc_trade(self, entity, screen_key):
        """NPC occasionally trades with nearby peaceful NPCs"""
        # Only peaceful NPCs trade
        if entity.props.get('hostile', False):
            return

        # Small chance to initiate trade (2% per update)
        if random.random() > 0.02:
            return

        # Find nearby peaceful NPCs within 3 cells
        if screen_key not in self.screen_entities:
            return

        for other_id in self.screen_entities[screen_key]:
            if other_id not in self.entities:
                continue

            other = self.entities[other_id]

            # Don't trade with self
            if other is entity:
                continue

            # Only trade with peaceful NPCs
            if other.props.get('hostile', False):
                continue

            # Check distance
            dist = abs(other.x - entity.x) + abs(other.y - entity.y)
            if dist > 3:
                continue

            # Found a trading partner - exchange items
            if entity.inventory and other.inventory:
                # Get tradeable items (not magic)
                entity_items = [item for item in entity.inventory.keys()
                               if item not in ITEMS or not ITEMS[item].get('is_spell', False)]
                other_items = [item for item in other.inventory.keys()
                              if item not in ITEMS or not ITEMS[item].get('is_spell', False)]

                if entity_items and other_items:
                    # Each gives one random item to the other
                    entity_gives = random.choice(entity_items)
                    other_gives = random.choice(other_items)

                    # Exchange
                    if entity.inventory[entity_gives] > 0 and other.inventory[other_gives] > 0:
                        entity.inventory[entity_gives] -= 1
                        other.inventory[other_gives] -= 1

                        entity.inventory[other_gives] = entity.inventory.get(other_gives, 0) + 1
                        other.inventory[entity_gives] = other.inventory.get(entity_gives, 0) + 1

                        # Clean up zero entries
                        if entity.inventory[entity_gives] == 0:
                            del entity.inventory[entity_gives]
                        if other.inventory[other_gives] == 0:
                            del other.inventory[other_gives]

                        if entity.name and other.name:
                            print(f"{entity.name} traded {entity_gives} for {other_gives} with {other.name}")
                        return

    def process_npc_trade(self, entity, entity_id, gold_count):
        """Handle trading when NPC picks up gold near player"""
        entity_type = entity.type

        # FARMER / LUMBERJACK / MINER: Simple resource trade
        if entity_type == 'FARMER':
            # Trade carrots for gold
            carrots_to_give = gold_count * 2  # 2 carrots per gold
            self.inventory.add_item('carrot', carrots_to_give)
            print(f"Farmer traded {carrots_to_give} carrots for {gold_count} gold!")

        elif entity_type == 'LUMBERJACK':
            # Trade wood for gold
            wood_to_give = gold_count * 3  # 3 wood per gold
            self.inventory.add_item('wood', wood_to_give)
            print(f"Lumberjack traded {wood_to_give} wood for {gold_count} gold!")

        elif entity_type == 'MINER':
            # Trade stone for gold
            stone_to_give = gold_count * 3  # 3 stone per gold
            self.inventory.add_item('stone', stone_to_give)
            print(f"Miner traded {stone_to_give} stone for {gold_count} gold!")

        # GUARD / GOBLIN: Become follower if enough gold
        elif entity_type in ['GUARD', 'GOBLIN']:
            gold_needed = 10 if entity_type == 'GUARD' else 5
            total_gold = entity.inventory.get('gold', 0)

            if total_gold >= gold_needed:
                # Become follower
                if entity_id not in self.followers:
                    self.followers.append(entity_id)
                    entity.inventory['gold'] = 0  # Clear gold
                    name_str = entity.name if entity.name else entity_type
                    print(f"{name_str} is now following you!")
            else:
                print(f"{entity_type} wants {gold_needed} gold total to follow you (has {total_gold})")

        # TRADER: Show trade recipes UI
        elif entity_type == 'TRADER':
            # Store trader info for UI display
            self.trader_display = {
                'entity_id': entity_id,
                'position': (entity.x, entity.y),
                'recipes': [
                    {'inputs': [('gold', 4), ('carrot', 1)], 'output': ('bone_sword', 1)},
                    {'inputs': [('gold', 3), ('wood', 5)], 'output': ('axe', 1)},
                    {'inputs': [('gold', 2), ('stone', 3)], 'output': ('pickaxe', 1)},
                    {'inputs': [('gold', 5), ('fur', 2)], 'output': ('leather_armor', 1)},
                ]
            }
            self.trader_display_tick = self.tick
            print("Trader is ready to trade! (Move to close menu)")

    def npc_trade_interaction(self):
        """Handle NPC trade interactions with 'n' key"""
        # Check for trader UI - execute trade if available
        if self.trader_display:
            entity_id = self.trader_display['entity_id']
            if entity_id in self.entities:
                trader = self.entities[entity_id]
                # Try to execute first available recipe
                for recipe in self.trader_display['recipes']:
                    can_craft = True
                    for item_name, count in recipe['inputs']:
                        if trader.inventory.get(item_name, 0) < count:
                            can_craft = False
                            break

                    if can_craft:
                        # Remove ingredients from trader
                        for item_name, count in recipe['inputs']:
                            trader.inventory[item_name] -= count

                        # Give output to player
                        output_name, output_count = recipe['output']
                        self.inventory.add_item(output_name, output_count)
                        print(f"Traded for {output_name}!")

                        # Close trader UI
                        self.trader_display = None
                        return

            # No valid trades
            self.trader_display = None
            print("No valid trades available")
            return

        # No active trader display - check for adjacent Trader NPC
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id not in self.entities:
                    continue

                entity = self.entities[entity_id]

                # Check if Trader and adjacent to player
                if entity.type == 'TRADER':
                    distance = abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])
                    if distance <= 1:
                        # Open trader UI
                        self.trader_display = {
                            'entity_id': entity_id,
                            'position': (entity.x, entity.y),
                            'recipes': [
                                {'inputs': [('gold', 4), ('carrot', 1)], 'output': ('bone_sword', 1)},
                                {'inputs': [('gold', 3), ('wood', 5)], 'output': ('axe', 1)},
                                {'inputs': [('gold', 2), ('stone', 3)], 'output': ('pickaxe', 1)},
                                {'inputs': [('gold', 5), ('fur', 2)], 'output': ('leather_armor', 1)},
                            ]
                        }
                        print("Trader menu opened! Press 'N' again to trade, or move away to close.")
                        return

        # No trader nearby
        print("No trader nearby!")
