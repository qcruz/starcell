import random

import pygame

from constants import (
    ITEMS, COLORS, CELL_TYPES,
    GRID_WIDTH, GRID_HEIGHT,
    SCREEN_WIDTH, SCREEN_HEIGHT, CELL_SIZE,
)
from entity import Entity


class CombatMixin:
    """Handles player combat, damage, XP, death/respawn, and attack animations."""

    # -------------------------------------------------------------------------
    # Damage calculation helpers
    # -------------------------------------------------------------------------

    def calculate_magic_damage(self, inventory):
        """Calculate total magic damage and type from runestone inventory"""
        runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
        magic_damage = 0
        magic_type = None

        for rune_type in runestone_types:
            if rune_type in inventory:
                rune_count = inventory[rune_type]
                magic_damage += rune_count * ITEMS[rune_type].get('damage', 3)
                if not magic_type:  # Use first rune type for animation
                    magic_type = ITEMS[rune_type].get('magic_damage')

        return magic_damage, magic_type

    def calculate_weapon_bonus(self, inventory):
        """Calculate bonus damage from weapons/tools in entity inventory.
        Returns the damage of the best weapon found."""
        best_damage = 0
        for item_name, count in inventory.items():
            if count > 0 and item_name in ITEMS:
                item_data = ITEMS[item_name]
                dmg = item_data.get('damage', 0)
                if dmg > best_damage and (item_data.get('is_tool') or item_data.get('is_spell')):
                    best_damage = dmg
        return best_damage

    # -------------------------------------------------------------------------
    # Player attack
    # -------------------------------------------------------------------------

    def player_attack(self):
        """Player attacks with equipped weapon (SPACE when weapon selected)"""
        # Check if weapon selected in tools
        weapon = self.inventory.selected_tool
        if not weapon or 'damage' not in ITEMS.get(weapon, {}):
            return False  # No weapon equipped

        # Attack cooldown (1 second)
        if self.tick - self.player.get('last_attack_tick', 0) < 60:
            return False

        self.player['last_attack_tick'] = self.tick

        # Get target cell
        target = self.get_target_cell()
        if not target:
            return False

        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Get correct entity list based on subscreen state
        if self.player.get('in_subscreen'):
            subscreen_key = self.player.get('subscreen_key')
            entities_list = self.subscreen_entities.get(subscreen_key, []) if subscreen_key else []
        else:
            entities_list = self.screen_entities.get(screen_key, [])

        # Check for entity at target
        for entity_id in entities_list:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.x == check_x and entity.y == check_y:
                    # Friendly-fire guard: peaceful entities are protected when FF is OFF
                    if not self.player.get('friendly_fire', False):
                        if not entity.props.get('hostile', False):
                            print(f"[FF blocked] {entity.type} is peaceful — press V to enable friendly fire")
                            return False
                    # Calculate damage
                    weapon_damage = ITEMS[weapon].get('damage', 0)
                    total_damage = self.player['base_damage'] + weapon_damage

                    # Add magic damage from runestones
                    runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
                    magic_damage = 0
                    magic_type = None
                    for rune_type in runestone_types:
                        if rune_type in self.inventory.items:
                            rune_count = self.inventory.items[rune_type]
                            magic_damage += rune_count * ITEMS[rune_type].get('damage', 3)
                            if not magic_type:  # Use first rune type for animation color
                                magic_type = ITEMS[rune_type].get('magic_damage')

                    total_damage += magic_damage

                    # Apply blocking reduction
                    if entity.combat_state == 'blocking':
                        total_damage *= (1 - entity.block_reduction)

                    entity.take_damage(total_damage, 'player')
                    self.gain_xp(1)

                    # Temp energy cost for attacking
                    self.player['energy'] = max(0, self.player.get('energy', 0) - 2)

                    # Show attack animation (with magic color if applicable)
                    self.show_attack_animation(check_x, check_y, target_entity=entity, magic_type=magic_type)

                    if magic_damage > 0:
                        print(f"Hit {entity.type} for {int(total_damage)} damage ({int(magic_damage)} magic)! HP: {int(entity.health)}/{entity.max_health}")
                    else:
                        print(f"Hit {entity.type} for {int(total_damage)} damage! HP: {int(entity.health)}/{entity.max_health}")
                    return True

        return False

    # -------------------------------------------------------------------------
    # Player damage & XP
    # -------------------------------------------------------------------------

    def player_take_damage(self, damage):
        """Player takes damage with blocking reduction"""
        # Don't take damage if already dead
        if self.state == 'death':
            return

        if self.player['blocking']:
            damage *= 0.1  # 90% reduction when blocking
            self.player['energy'] = max(0, self.player.get('energy', 0) - 5)

        self.player['health'] -= damage
        print(f"Player took {int(damage)} damage! Health: {int(self.player['health'])}/{self.player['max_health']}")

        if self.player['health'] <= 0 and self.state != 'death':
            self.player_death()

    def gain_xp(self, amount):
        """Award XP to player and handle leveling up"""
        self.player['xp'] += amount

        # Check for level up
        while self.player['xp'] >= self.player['xp_to_level']:
            self.player['xp'] -= self.player['xp_to_level']
            self.player['level'] += 1

            # Increase stats on level up
            self.player['max_health'] += 10
            self.player['health'] = self.player['max_health']  # Full heal
            self.player['base_damage'] += 2
            self.player['max_energy'] = self.player.get('max_energy', 100) + 2
            self.player['energy'] = self.player['max_energy']  # Full restore

            # Increase XP required for next level
            self.player['xp_to_level'] = int(self.player['xp_to_level'] * 1.5)

            print(f"LEVEL UP! Now level {self.player['level']}")

    # -------------------------------------------------------------------------
    # Death & respawn
    # -------------------------------------------------------------------------

    def player_death(self):
        """Handle player death - time passage and respawn"""
        print("You died!")
        self.state = 'death'

        # Random years to pass (100-200, reduced from 100-1000)
        years_passed = random.randint(100, 200)
        self.death_years = years_passed
        self.death_start_tick = self.tick
        self.death_ticks_simulated = 0

        # Drop all items at death location
        death_screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        death_pos = (self.player['x'], self.player['y'])

        if death_screen_key not in self.dropped_items:
            self.dropped_items[death_screen_key] = {}
        if death_pos not in self.dropped_items[death_screen_key]:
            self.dropped_items[death_screen_key][death_pos] = {}

        # Drop all inventory items (except magic - spells are permanent)
        for category in ['items', 'tools']:
            inv = getattr(self.inventory, category)
            for item_name, count in list(inv.items()):
                self.dropped_items[death_screen_key][death_pos][item_name] = \
                    self.dropped_items[death_screen_key][death_pos].get(item_name, 0) + count
            inv.clear()

        # Clear inventory selections (but keep magic)
        for cat in ['items', 'tools']:
            if cat in self.inventory.selected:
                self.inventory.selected[cat] = None

    def update_death_screen(self):
        """Update during death - accelerated time passage.

        Focuses on cell-level simulation only (cellular automata + grows_to) for
        the player zone and immediate neighbors. This is sufficient to convert
        DIRT→GRASS reliably without the overhead of full entity AI or zone-level
        systems, which caused frame stalls when run for all 49 instantiated zones.

        NPCs are spawned once right before respawn so they are fresh and alive.
        catch_up_screen is intentionally NOT called — its Tier-2 bulk path converts
        GRASS→DIRT at 10%/call, massively counteracting grows_to DIRT→GRASS (0.3%).
        """
        ticks_to_simulate = self.death_years * 5   # 5 ticks per simulated year
        cycles_per_frame = 10                       # years processed per render frame

        if self.death_ticks_simulated < ticks_to_simulate:
            for _ in range(cycles_per_frame):
                # Weather drives rain → water → DIRT→GRASS via cellular automata
                self.update_weather()

                player_sx = self.player['screen_x']
                player_sy = self.player['screen_y']

                # Cell updates for player zone + 3×3 neighbors only.
                # update_zone_with_coverage is too heavy (entity AI + raid checks
                # + threat checks for all 49 zones) — stalls every frame.
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        zx, zy = player_sx + dx, player_sy + dy
                        zone_key = f"{zx},{zy}"
                        if zone_key not in self.screens:
                            continue
                        screen = self.screens[zone_key]

                        # Rain effect if currently raining
                        if self.is_raining:
                            self.apply_rain(zx, zy)

                        # Cellular automata (handles DIRT→GRASS with water neighbors)
                        self.apply_cellular_automata(zx, zy)

                        # grows_to: unconditional DIRT→GRASS at 0.3%/cell/tick
                        for y in range(1, GRID_HEIGHT - 1):
                            for x in range(1, GRID_WIDTH - 1):
                                cell = screen['grid'][y][x]
                                if cell in CELL_TYPES:
                                    cell_info = CELL_TYPES[cell]
                                    if 'grows_to' in cell_info:
                                        if random.random() < cell_info.get('growth_rate', 0):
                                            self.set_grid_cell(screen, x, y, cell_info['grows_to'])

                self.tick += 1
                self.death_ticks_simulated += 1

                if self.death_ticks_simulated >= ticks_to_simulate:
                    break

        else:
            # Spawn NPCs fresh in nearby zones right before player loads in.
            # Done here (not during simulation) to avoid entity accumulation.
            if not getattr(self, '_time_pass_spawned', False):
                self._time_pass_spawned = True
                player_sx = self.player['screen_x']
                player_sy = self.player['screen_y']
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        zk = f"{player_sx + dx},{player_sy + dy}"
                        if zk in self.screens:
                            zx, zy = player_sx + dx, player_sy + dy
                            biome = self.screens[zk].get('biome', 'FOREST')
                            self.spawn_entities_for_screen(zx, zy, biome)
                print(f"World initialized — {self.death_years} years passed.")

            # Respawn player
            self.respawn_player()

    def respawn_player(self):
        """Respawn player in same zone at a random safe location"""
        # Clear initial generation flag if it exists
        if hasattr(self, 'is_initial_generation'):
            self.is_initial_generation = False

        # Stay in same zone, find a safe spawn point
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Try to find a safe spawn location in current zone
        found_safe_spot = False
        for attempt in range(100):  # Try 100 random positions
            test_x = random.randint(1, GRID_WIDTH - 2)
            test_y = random.randint(1, GRID_HEIGHT - 2)

            if screen_key in self.screens:
                cell = self.screens[screen_key]['grid'][test_y][test_x]
                # Check if cell is walkable (not solid, not water)
                if not CELL_TYPES[cell].get('solid', False) and cell not in ['WATER', 'DEEP_WATER']:
                    self.player['x'] = test_x
                    self.player['y'] = test_y
                    found_safe_spot = True
                    break

        # If no safe spot found, just spawn in center
        if not found_safe_spot:
            self.player['x'] = GRID_WIDTH // 2
            self.player['y'] = GRID_HEIGHT // 2

        # Reset player stats
        self.player['health'] = self.player['max_health']
        self.player['blocking'] = False

        # Reset all quests - clear old targets and cooldowns
        for quest in self.quests.values():
            quest.clear_target()
            quest.status = 'inactive'
            quest.cooldown_remaining = 0

        # Regenerate current screen to reflect time passage
        self.current_screen = self.generate_screen(self.player['screen_x'], self.player['screen_y'])

        # Spawn deferred follower (set in new_game(), skipped during time pass to
        # prevent it being killed by hostile NPCs before the player loads in).
        pending = getattr(self, '_pending_follower_type', None)
        if pending:
            self._pending_follower_type = None
            follower_entity = Entity(pending, self.player['x'] + 1, self.player['y'],
                                     self.player['screen_x'], self.player['screen_y'], level=1)
            follower_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[follower_id] = follower_entity
            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(follower_id)
            self.followers.append(follower_id)
            follower_item = f"{pending.lower()}_{follower_id}"
            self.follower_items[follower_id] = follower_item
            if follower_item not in ITEMS:
                ITEMS[follower_item] = {
                    'color': follower_entity.props['color'],
                    'name': f"{pending.title()} Follower",
                    'is_follower': True,
                    'entity_id': follower_id,
                }
            self.inventory.add_follower(follower_item, 1)
            print(f"{pending} follower spawned (ID: {follower_id})")

        self.state = 'playing'
        # Autopilot grace period: don't engage for 15 seconds after entering game
        self.last_input_tick = self.tick + 900

        # Force immediate quest update to find new targets
        print("Quests reset - seeking new targets...")
        for quest_type, quest in self.quests.items():
            if quest.status == 'inactive':
                success = self.loreEngine(quest)
                if success:
                    print(f"  {quest_type}: Target assigned")
                else:
                    print(f"  {quest_type}: No target found yet")

        print(f"{self.death_years} years have passed...")

    # -------------------------------------------------------------------------
    # Attack animations
    # -------------------------------------------------------------------------

    def show_attack_animation(self, x, y, entity=None, target_entity=None, magic_type=None):
        """Show attack animation at target location (colored for magic)

        Args:
            x, y: Grid coordinates (fallback)
            entity: Attacking entity (for location tracking)
            target_entity: Target entity (for accurate world position)
            magic_type: Type of magic damage for color
        """
        # Use target_entity's world position if available for accurate placement
        if target_entity and hasattr(target_entity, 'world_x'):
            display_x = target_entity.world_x
            display_y = target_entity.world_y
        else:
            # Fallback to grid coordinates
            display_x = float(x)
            display_y = float(y)

        # Track which screen/subscreen this animation belongs to
        if entity:
            location_key = entity.screen_key
        elif self.player.get('in_subscreen'):
            location_key = self.player.get('subscreen_key')
        else:
            location_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        self.attack_animations.append({
            'x': display_x,  # Now using world coordinates
            'y': display_y,
            'start_tick': self.tick,
            'duration': 10,
            'location_key': location_key,
            'magic_type': magic_type
        })

    def draw_attack_animations(self):
        """Draw active attack animations only for current location"""
        # Determine current location
        if self.player.get('in_subscreen'):
            current_location = self.player.get('subscreen_key')
        else:
            current_location = f"{self.player['screen_x']},{self.player['screen_y']}"

        # Magic type color mapping
        magic_colors = {
            'lightning': (100, 149, 237),  # Cornflower blue
            'fire': (255, 69, 0),          # Red-orange
            'ice': (173, 216, 230),        # Light blue
            'poison': (50, 205, 50),       # Lime green
            'shadow': (75, 0, 130)         # Indigo
        }

        for anim in self.attack_animations[:]:
            if self.tick - anim['start_tick'] > anim['duration']:
                self.attack_animations.remove(anim)
                continue

            # Only draw animations for current location
            if anim.get('location_key') != current_location:
                continue

            # Determine color (white for physical, colored for magic)
            if anim.get('magic_type') and anim['magic_type'] in magic_colors:
                color = magic_colors[anim['magic_type']]
            else:
                color = COLORS['WHITE']

            # Draw swipe lines
            x_pos = anim['x'] * CELL_SIZE
            y_pos = anim['y'] * CELL_SIZE

            # Draw diagonal swipe lines
            pygame.draw.line(self.screen, color,
                             (x_pos + 5, y_pos + 10), (x_pos + 35, y_pos + 30), 3)
            pygame.draw.line(self.screen, color,
                             (x_pos + 10, y_pos + 5), (x_pos + 30, y_pos + 35), 3)

    def draw_death_screen(self):
        """Draw death screen with years passing"""
        self.screen.fill(COLORS['BLACK'])

        years_passed = self.death_ticks_simulated // 10
        years_text = f"{years_passed} / {self.death_years} YEARS PASSING..."
        text = self.font.render(years_text, True, (100, 100, 100))
        text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(text, text_rect)
