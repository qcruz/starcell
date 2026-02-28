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
            self.player['max_energy'] = self.player.get('max_energy', 20) + 2
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
        """Update during death - accelerated time passage"""
        ticks_to_simulate = self.death_years * 10  # 10 ticks per "year"
        cycles_per_frame = 5  # Reduced from 10

        if self.death_ticks_simulated < ticks_to_simulate:
            # Minimal updates for performance
            for _ in range(cycles_per_frame):
                # Age all entities (10 ticks = 1 year)
                if self.death_ticks_simulated % 10 == 0:  # Every simulated year
                    current_year = self.death_ticks_simulated // 10

                    entities_to_remove = []
                    for entity_id, entity in list(self.entities.items()):
                        # Age entity (no longer manually apply old age damage here - handled by decay_stats)
                        if entity.type != 'SKELETON':
                            entity.age += 1

                        # Don't manually decay hunger/thirst - let catch_up and entity AI handle it
                        # Entities will eat/drink naturally through behavior updates below

                    # Remove dead entities
                    for entity_id in entities_to_remove:
                        self.remove_entity(entity_id)

                    # Spawn new NPCs more frequently (every 10 years instead of 30)
                    if current_year > 0 and current_year % 10 == 0:
                        # Spawn in more zones (5 instead of 3)
                        zones_to_spawn = random.sample(list(self.instantiated_zones),
                                                       min(5, len(self.instantiated_zones)))

                        for zone_key in zones_to_spawn:
                            parts = zone_key.split(',')
                            zone_x = int(parts[0])
                            zone_y = int(parts[1])

                            # Spawn entities for this zone
                            if zone_key in self.screens:
                                biome = self.screens[zone_key].get('biome', 'FOREST')
                                self.spawn_entities_for_screen(zone_x, zone_y, biome)

                        print(f"Year {current_year}: New NPCs spawned in {len(zones_to_spawn)} zones")

                # Update zones per cycle with entity AI actions
                # During initial generation, update MORE zones and MORE frequently for world building
                if hasattr(self, 'is_initial_generation') and self.is_initial_generation:
                    zones_to_update = random.sample(list(self.instantiated_zones),
                                                    min(8, len(self.instantiated_zones)))  # 8 zones
                    update_chance = 0.5  # 100% chance to update
                    catchup_cycles = 5  # More cycles for building
                    behavior_chance = 0.5  # 80% behavior chance - NPCs actively build/farm/mine
                else:
                    zones_to_update = random.sample(list(self.instantiated_zones),
                                                    min(8, len(self.instantiated_zones)))  # 8 zones
                    update_chance = 0.8  # 80% chance
                    catchup_cycles = 5  # More cycles
                    behavior_chance = 0.3  # 30% behavior chance

                for zone_key in zones_to_update:
                    parts = zone_key.split(',')
                    zone_x = int(parts[0])
                    zone_y = int(parts[1])

                    if random.random() < update_chance:
                        # Use catch_up with configured cycles for cell updates
                        self.catch_up_screen(zone_x, zone_y, catchup_cycles)

                        # CRITICAL: Also run full zone update for farming, building, spawning
                        # This is what creates the world structures
                        self.update_zone_with_coverage(zone_x, zone_y, 1.0, 1.0)

                        # Additionally update entity behaviors in this zone
                        if zone_key in self.screen_entities:
                            for entity_id in list(self.screen_entities[zone_key]):
                                if entity_id in self.entities:
                                    entity = self.entities[entity_id]

                                    # Run special behaviors during time passage
                                    behavior_config = entity.props.get('behavior_config')
                                    if behavior_config and random.random() < behavior_chance:
                                        self.execute_entity_behavior(entity, behavior_config)

                self.tick += 1
                self.death_ticks_simulated += 1

                if self.death_ticks_simulated >= ticks_to_simulate:
                    break
        else:
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

        # Respawn skeleton follower for testing
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        skeleton = Entity('SKELETON', self.player['x'] + 1, self.player['y'],
                          self.player['screen_x'], self.player['screen_y'], level=1)
        skeleton_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[skeleton_id] = skeleton

        # Add to screen entities
        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(skeleton_id)

        # Add to followers
        self.followers.append(skeleton_id)
        self.follower_items[skeleton_id] = 'skeleton_bones'

        # Add to inventory as follower item (use existing skeleton_bones item)
        self.inventory.add_follower('skeleton_bones', 1)

        print(f"Skeleton follower respawned (ID: {skeleton_id})")

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
