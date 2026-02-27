"""
LoreEngine — quest targeting, world event generation, and emergent lore.

This module drives the game's personality by:
  • Matching quest targets to player level and world state (loreEngine)
  • Checking quest completion (check_quest_completion / update_quests)
  • Generating secret world events that make zones feel lived-in
    (update_lore / check_secret_entrances)
"""
import random

from constants import (
    QUEST_TYPES, ITEMS,
    GRID_WIDTH, GRID_HEIGHT,
    QUEST_XP_MULTIPLIER,
)


class LoreEngineMixin:

    # -------------------------------------------------------------------------
    # Quest targeting
    # -------------------------------------------------------------------------

    def loreEngine(self, quest):
        """Generate or find quest target for a quest.
        Quest targets are matched to player level (equal to +2 above)."""
        quest_type = quest.quest_type
        quest_info = QUEST_TYPES[quest_type]
        player_level = self.player.get('level', 1)
        min_level = player_level
        max_level = player_level + 2

        # Clear any existing target
        quest.clear_target()

        player_sx = self.player['screen_x']
        player_sy = self.player['screen_y']
        player_zone = f"{player_sx},{player_sy}"

        # For HUNT quests - find hostile NPC near player level
        if quest_type == 'HUNT':
            hostile_entities = []
            for entity_id, entity in self.entities.items():
                if entity.props.get('hostile') and not entity.is_dead:
                    if min_level <= entity.level <= max_level:
                        hostile_entities.append(entity_id)

            # If no level-matched hostiles, accept any hostile
            if not hostile_entities:
                for entity_id, entity in self.entities.items():
                    if entity.props.get('hostile') and not entity.is_dead:
                        hostile_entities.append(entity_id)

            if hostile_entities:
                # Prefer targets not in current zone
                offscreen = [eid for eid in hostile_entities
                            if f"{self.entities[eid].screen_x},{self.entities[eid].screen_y}" != player_zone]
                target_id = random.choice(offscreen if offscreen else hostile_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.type}"
                if entity.name:
                    info = f"L{entity.level} {entity.name} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True
            else:
                # Spawn a hostile in a distant zone at player level
                distant_zones = []
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if abs(dx) + abs(dy) >= 2:
                            distant_zones.append((player_sx + dx, player_sy + dy))

                if distant_zones:
                    target_sx, target_sy = random.choice(distant_zones)
                    screen_key = f"{target_sx},{target_sy}"
                    if screen_key not in self.screens:
                        self.generate_screen(target_sx, target_sy)
                    hostile_types = ['GOBLIN', 'BANDIT', 'WOLF', 'BAT']
                    hostile_type = random.choice(hostile_types)
                    entity_id = self.spawn_quest_entity(hostile_type, target_sx, target_sy,
                                                        random.randint(5, GRID_WIDTH - 5),
                                                        random.randint(5, GRID_HEIGHT - 5))
                    if entity_id:
                        self.entities[entity_id].level = random.randint(min_level, max_level)
                        entity = self.entities[entity_id]
                        info = f"L{entity.level} {entity.type}"
                        quest.set_target('entity', entity_id, info)
                        quest.target_zone = screen_key
                        return True

        # For SLAY quests - find specific enemy type near player level
        elif quest_type == 'SLAY':
            target_types = quest_info['target_types']
            target_entity_type = random.choice(target_types)

            matching_entities = []
            for entity_id, entity in self.entities.items():
                if entity.type == target_entity_type and not entity.is_dead:
                    if min_level <= entity.level <= max_level:
                        matching_entities.append(entity_id)

            # Fallback: any level
            if not matching_entities:
                for entity_id, entity in self.entities.items():
                    if entity.type == target_entity_type and not entity.is_dead:
                        matching_entities.append(entity_id)

            if matching_entities:
                target_id = random.choice(matching_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.type}"
                if entity.name:
                    info = f"L{entity.level} {entity.name} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True
            else:
                distant_zones = []
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if abs(dx) + abs(dy) >= 2:
                            distant_zones.append((player_sx + dx, player_sy + dy))

                if distant_zones:
                    target_sx, target_sy = random.choice(distant_zones)
                    screen_key = f"{target_sx},{target_sy}"
                    if screen_key not in self.screens:
                        self.generate_screen(target_sx, target_sy)
                    entity_id = self.spawn_quest_entity(target_entity_type, target_sx, target_sy,
                                                        random.randint(5, GRID_WIDTH - 5),
                                                        random.randint(5, GRID_HEIGHT - 5))
                    if entity_id:
                        self.entities[entity_id].level = random.randint(min_level, max_level)
                        entity = self.entities[entity_id]
                        info = f"L{entity.level} {entity.type}"
                        quest.set_target('entity', entity_id, info)
                        quest.target_zone = screen_key
                        return True

        # For EXPLORE quests - find specific location
        elif quest_type == 'EXPLORE':
            target_types = quest_info['target_types']
            target_cell_type = random.choice(target_types)

            found_locations = []
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue  # Skip current zone
                sx, sy = map(int, screen_key.split(','))
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell == target_cell_type:
                            found_locations.append((sx, sy, x, y))

            if found_locations:
                # Pick closest
                found_locations.sort(key=lambda loc: abs(loc[0] - player_sx) + abs(loc[1] - player_sy))
                target_loc = found_locations[0]
                info = f"{target_cell_type} at zone ({target_loc[0]},{target_loc[1]})"
                quest.set_target('cell', target_loc, info)
                quest.target_zone = f"{target_loc[0]},{target_loc[1]}"
                return True

        # For GATHER quests - find resource location
        elif quest_type == 'GATHER':
            target_types = quest_info['target_types']
            target_cell_type = random.choice(target_types)

            if target_cell_type == 'TREE':
                search_types = ['TREE1', 'TREE2']
            else:
                search_types = [target_cell_type]

            found_resources = []
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue
                sx, sy = map(int, screen_key.split(','))
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in search_types:
                            found_resources.append((sx, sy, x, y))

            if found_resources:
                found_resources.sort(key=lambda loc: abs(loc[0] - player_sx) + abs(loc[1] - player_sy))
                target_loc = found_resources[0]
                info = f"{target_cell_type} at zone ({target_loc[0]},{target_loc[1]})"
                quest.set_target('cell', target_loc, info)
                quest.target_zone = f"{target_loc[0]},{target_loc[1]}"
                return True

        # For RESCUE quests - find friendly NPC
        elif quest_type == 'RESCUE':
            target_types = quest_info['target_types']
            target_entity_type = random.choice(target_types)

            matching_npcs = []
            for entity_id, entity in self.entities.items():
                if entity.type == target_entity_type and not entity.is_dead:
                    matching_npcs.append(entity_id)

            if matching_npcs:
                target_id = random.choice(matching_npcs)
                entity = self.entities[target_id]
                info = f"{entity.name or entity.type} at ({entity.screen_x},{entity.screen_y})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True

        # For SEARCH quests - find any dropped items across zones
        elif quest_type == 'SEARCH':
            selected_item = self.inventory.get_selected_item_name()

            found_items = []
            for screen_key, items_dict in self.dropped_items.items():
                if screen_key == player_zone:
                    continue
                if not self.is_overworld_zone(screen_key):
                    continue
                try:
                    sx, sy = map(int, screen_key.split(','))
                except (ValueError, AttributeError):
                    continue
                for (cx, cy), item_bag in items_dict.items():
                    for item_name, count in item_bag.items():
                        if count > 0:
                            dist = abs(sx - player_sx) + abs(sy - player_sy)
                            priority = 2
                            if selected_item and item_name == selected_item:
                                priority = 0
                            elif 'rune' in item_name:
                                priority = 1
                            found_items.append((priority, dist, sx, sy, cx, cy, item_name))

            # Also search entity inventories
            for entity_id, entity in self.entities.items():
                if entity.is_dead:
                    continue
                zone_key = f"{entity.screen_x},{entity.screen_y}"
                if zone_key == player_zone:
                    continue
                for item_name, count in entity.inventory.items():
                    if count > 0:
                        dist = abs(entity.screen_x - player_sx) + abs(entity.screen_y - player_sy)
                        priority = 2
                        if selected_item and item_name == selected_item:
                            priority = 0
                        elif 'rune' in item_name:
                            priority = 1
                        found_items.append((priority, dist, entity.screen_x, entity.screen_y, entity.x, entity.y, item_name))

            # Also search chests
            for chest_key, contents in self.chest_contents.items():
                for item_name, count in contents.items():
                    if count > 0:
                        try:
                            zone_part = chest_key.split(':')[0]
                            csx, csy = map(int, zone_part.split(','))
                            dist = abs(csx - player_sx) + abs(csy - player_sy)
                        except (ValueError, IndexError):
                            dist = 10
                            csx, csy = player_sx, player_sy
                        priority = 2
                        if selected_item and item_name == selected_item:
                            priority = 0
                        elif 'rune' in item_name:
                            priority = 1
                        found_items.append((priority, dist, csx, csy, GRID_WIDTH // 2, GRID_HEIGHT // 2, item_name))

            if found_items:
                found_items.sort(key=lambda x: (x[0], x[1]))
                priority, dist, sx, sy, cx, cy, item_name = found_items[0]
                display_name = ITEMS.get(item_name, {}).get('name', item_name)
                info = f"Find {display_name} near ({sx},{sy})"
                quest.set_target('cell', (sx, sy, cx, cy), info)
                quest.target_zone = f"{sx},{sy}"
                return True
            else:
                info = "Searching for items..."
                quest.target_info = info
                explore_dx = random.randint(-3, 3)
                explore_dy = random.randint(-3, 3)
                if explore_dx == 0 and explore_dy == 0:
                    explore_dx = 1
                tsx, tsy = player_sx + explore_dx, player_sy + explore_dy
                quest.set_target('cell', (tsx, tsy, GRID_WIDTH // 2, GRID_HEIGHT // 2), info)
                quest.target_zone = f"{tsx},{tsy}"
                return True

        # For LUMBER quests — find trees to chop
        elif quest_type == 'LUMBER':
            search_types = ['TREE1', 'TREE2']
            pz_key = f"{player_sx},{player_sy}"

            has_local = False
            if pz_key in self.screens:
                for row in self.screens[pz_key]['grid']:
                    for cell in row:
                        if cell in search_types:
                            has_local = True
                            break
                    if has_local:
                        break

            if has_local and random.random() < 0.90:
                quest.target_info = "Chopping trees nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == pz_key:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in search_types:
                            info = f"Travel to chop trees at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = cell
                            quest.target_zone = screen_key
                            return True
            if has_local:
                quest.target_info = "Chopping trees nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for trees..."
            return False

        # For MINE quests — find stone to mine
        elif quest_type == 'MINE':
            pz_key = f"{player_sx},{player_sy}"

            has_local = False
            if pz_key in self.screens:
                for row in self.screens[pz_key]['grid']:
                    for cell in row:
                        if cell == 'STONE':
                            has_local = True
                            break
                    if has_local:
                        break

            if has_local and random.random() < 0.90:
                quest.target_info = "Mining stone nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == pz_key:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell == 'STONE':
                            info = f"Travel to mine stone at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = 'STONE'
                            quest.target_zone = screen_key
                            return True
            if has_local:
                quest.target_info = "Mining stone nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for stone..."
            return False

        # For FARM quests - farmer behavior (harvest, till, plant, build)
        elif quest_type == 'FARM':
            player_zone = f"{player_sx},{player_sy}"
            if player_zone not in self.screens:
                return False
            screen = self.screens[player_zone]

            farm_cells = {'CARROT1', 'CARROT2', 'CARROT3', 'SOIL', 'DIRT', 'TREE1', 'TREE2'}
            has_local = False
            for row in screen['grid']:
                for cell in row:
                    if cell in farm_cells:
                        has_local = True
                        break
                if has_local:
                    break

            if has_local and random.random() < 0.90:
                quest.target_info = "Farming nearby"
                quest.target_zone = player_zone
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in farm_cells:
                            info = f"Travel to farm at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = cell
                            quest.target_zone = screen_key
                            return True
            if has_local:
                quest.target_info = "Farming nearby"
                quest.target_zone = player_zone
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for farm targets..."
            return False

        # For COMBAT_HOSTILE quests — target hostile entities (same as HUNT)
        elif quest_type == 'COMBAT_HOSTILE':
            hostile_entities = [eid for eid, e in self.entities.items()
                                if e.props.get('hostile') and not e.is_dead
                                and min_level <= e.level <= max_level]
            if not hostile_entities:
                hostile_entities = [eid for eid, e in self.entities.items()
                                    if e.props.get('hostile') and not e.is_dead]
            if hostile_entities:
                target_id = random.choice(hostile_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.name or entity.type}"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True

        # For COMBAT_ALL quests — target any entity, hostile or peaceful
        elif quest_type == 'COMBAT_ALL':
            all_targets = [eid for eid, e in self.entities.items()
                           if not e.is_dead and eid != 'player'
                           and min_level <= e.level <= max_level]
            if not all_targets:
                all_targets = [eid for eid, e in self.entities.items()
                               if not e.is_dead and eid != 'player']
            if all_targets:
                target_id = random.choice(all_targets)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.name or entity.type} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True

        return False

    # -------------------------------------------------------------------------
    # Quest completion
    # -------------------------------------------------------------------------

    def check_quest_completion(self):
        """Check if active quest is completed and award XP"""
        if not self.active_quest:
            return

        quest = self.quests[self.active_quest]
        if quest.status != 'active':
            return

        # Prevent rapid re-completion — guard against same-tick completion
        if hasattr(quest, '_last_completed_tick') and quest._last_completed_tick == self.tick:
            return

        completed = False
        xp_reward = 0

        # Check entity-based quests
        if quest.target_entity_id:
            if quest.target_entity_id not in self.entities:
                quest.clear_target()
                return
            else:
                entity = self.entities[quest.target_entity_id]
                if entity.is_dead:
                    if entity.killed_by == 'player':
                        completed = True
                        xp_reward = entity.level * QUEST_XP_MULTIPLIER
                    else:
                        quest.clear_target()
                        return

        # Check cell-based quests (explore/gather/farm/search)
        elif quest.target_cell:
            sx, sy, x, y = quest.target_cell
            player_sx, player_sy = self.player['screen_x'], self.player['screen_y']
            player_x, player_y = self.player['x'], self.player['y']

            if sx == player_sx and sy == player_sy:
                distance = abs(x - player_x) + abs(y - player_y)
                quest_type = self.active_quest

                if quest_type in ('FARM', 'GATHER'):
                    if distance <= 2 and quest._original_cell is not None:
                        screen_key = f"{sx},{sy}"
                        if screen_key in self.screens:
                            grid = self.screens[screen_key]['grid']
                            if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                                current_cell = grid[y][x]
                                if current_cell != quest._original_cell:
                                    completed = True
                                    xp_reward = 10 if quest_type == 'FARM' else 15
                elif quest_type in ('EXPLORE', 'RESCUE', 'SEARCH'):
                    if distance <= 2:
                        completed = True
                        xp_reward = 20

        # Check location-based quests
        elif quest.target_location:
            target_sx, target_sy = quest.target_location
            player_sx, player_sy = self.player['screen_x'], self.player['screen_y']

            if target_sx == player_sx and target_sy == player_sy:
                completed = True
                xp_reward = 30

        if completed:
            quest._last_completed_tick = self.tick
            if xp_reward > 0:
                self.gain_xp(xp_reward)
                tag = " (autopilot)" if self.autopilot else ""
                print(f"Quest [{self.active_quest}] completed{tag}! +{xp_reward} XP")
            quest.complete()

    def update_quests(self):
        """Update quest system — assign targets, check completion, run lore events."""
        # Update cooldowns
        for quest in self.quests.values():
            if quest.cooldown_remaining > 0:
                quest.cooldown_remaining -= 1
                if quest.cooldown_remaining == 0:
                    quest.status = 'inactive'

        # Check for quest completion
        self.check_quest_completion()

        # Assign targets to inactive quests that are off cooldown
        for quest_type, quest in self.quests.items():
            if quest.status == 'inactive' and quest.cooldown_remaining == 0:
                self.loreEngine(quest)

        # Run background lore events (throttled to once every ~10 s)
        self.update_lore()

    # -------------------------------------------------------------------------
    # Lore world events
    # -------------------------------------------------------------------------

    def update_lore(self):
        """Throttled dispatcher for lore-driven world events.
        Called every game tick via update_quests; only acts every ~10 seconds."""
        if self.tick % 600 != 0:
            return

        px, py = self.player['screen_x'], self.player['screen_y']
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                key = f"{px + dx},{py + dy}"
                if key in self.screens:
                    self.check_secret_entrances(key)

    def check_secret_entrances(self, screen_key):
        """~10 % chance: if a zone has 2+ house structures, secretly add a
        mine-shaft entrance in one house's interior corner, connecting it to
        the local cave system at depth 1.

        The MINESHAFT cell placed inside the house interior hooks into the
        existing enter_subscreen / zone_cave_systems machinery — no extra
        wiring needed.  When the player interacts with it they descend into
        (or generate) the cave system for that overworld zone.
        """
        if random.random() >= 0.10:
            return

        if screen_key not in self.screens:
            return

        grid = self.screens[screen_key]['grid']

        # Collect all HOUSE cell positions in the zone
        house_cells = [
            (x, y)
            for y in range(GRID_HEIGHT)
            for x in range(GRID_WIDTH)
            if grid[y][x] == 'HOUSE'
        ]

        if len(house_cells) < 2:
            return  # Need at least two houses for the secret to make narrative sense

        sx, sy = map(int, screen_key.split(','))

        # Pick a random house to receive the secret entrance
        hx, hy = random.choice(house_cells)

        # Find the house's interior subscreen (may not exist yet — generate it)
        house_subscreen = None
        house_subscreen_key = None
        for key, subscreen in self.subscreens.items():
            if (subscreen.get('parent_screen') == (sx, sy) and
                    subscreen.get('parent_cell') == (hx, hy) and
                    subscreen.get('type') == 'HOUSE_INTERIOR'):
                house_subscreen = subscreen
                house_subscreen_key = key
                break

        if house_subscreen is None:
            house_subscreen_key = self.generate_subscreen(sx, sy, hx, hy, 'HOUSE_INTERIOR', depth=1)
            house_subscreen = self.subscreens.get(house_subscreen_key)

        if house_subscreen is None:
            return

        interior = house_subscreen['grid']

        # Bail early if a mine shaft / cave entrance already exists inside
        for row in interior:
            if 'MINESHAFT' in row or 'CAVE' in row:
                return

        # Entrance is fixed at center-bottom of every subscreen
        entrance_x, entrance_y = house_subscreen.get('entrance', (GRID_WIDTH // 2, GRID_HEIGHT - 2))

        # Candidate corners (2-cell inset from walls to stay inside the room)
        corners = [
            (2,              2),
            (GRID_WIDTH - 3, 2),
            (2,              GRID_HEIGHT - 3),
            (GRID_WIDTH - 3, GRID_HEIGHT - 3),
        ]

        # Keep only corners that are:
        #   • clearly away from the entrance (distance > 4)
        #   • currently walkable floor (FLOOR_WOOD or similar)
        WALKABLE = {'FLOOR_WOOD', 'CAVE_FLOOR', 'DIRT', 'PLANKS'}
        candidates = [
            (cx, cy) for cx, cy in corners
            if (abs(cx - entrance_x) + abs(cy - entrance_y) > 4
                and interior[cy][cx] in WALKABLE)
        ]

        if not candidates:
            return

        cx, cy = random.choice(candidates)
        interior[cy][cx] = 'MINESHAFT'

        print(f"[LoreEngine] Secret mine shaft added to house ({hx},{hy}) "
              f"in zone {screen_key} — corner ({cx},{cy})")
