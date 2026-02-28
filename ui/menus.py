import pygame

from constants import (
    COLORS, ITEMS, QUEST_TYPES,
    CELL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    GRID_WIDTH, GRID_HEIGHT,
)


class MenusMixin:
    """Main menu, pause screen, trader UI, NPC inspection, item tooltip,
    quest arrow."""

    # -------------------------------------------------------------------------
    # Main menu
    # -------------------------------------------------------------------------

    def draw_menu(self):
        """Draw main menu"""
        self.screen.fill(COLORS['BLACK'])

        title = self.font.render("PROCEDURAL ADVENTURE", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))

        options = [
            "1 - New Game",
            "2 - Continue",
            "Q - Quit",
            "",
            "Controls:",
            "WASD / Arrows - Move",
            "Space - Interact",
            "E - Pick up   D - Drop   P - Place",
            "N - Trade   B - Block   V - Friendly fire",
            "L - Cast spell   K - Reverse spell",
            "Shift+A - Toggle autopilot",
            "I - Items   T - Tools   M - Magic",
            "F - Followers   C - Crafting   X - Craft",
            "Q - Quests   1-9 - Select slot",
            "ESC - Pause",
        ]

        y = 180
        for option in options:
            text = self.small_font.render(option, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 25

    # -------------------------------------------------------------------------
    # Pause screen
    # -------------------------------------------------------------------------

    def draw_paused(self):
        """Draw pause menu overlay"""
        self.draw_game()

        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(COLORS['BLACK'])
        self.screen.blit(overlay, (0, 0))

        # Pause menu
        title = self.font.render("PAUSED", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))

        pause_opts = [
            "P / ESC - Resume",
            "S - Save Game",
            "M - Main Menu",
        ]
        y = 240
        for option in pause_opts:
            text = self.small_font.render(option, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 26

        # Controls reference
        y += 10
        header = self.small_font.render("— Controls —", True, COLORS['YELLOW'])
        self.screen.blit(header, (SCREEN_WIDTH // 2 - header.get_width() // 2, y))
        y += 26

        controls = [
            "WASD / Arrows - Move",
            "Space - Interact   E - Pick up   D - Drop   P - Place",
            "L - Cast spell   K - Reverse spell",
            "Shift+A - Toggle autopilot",
            "N - Trade   B - Block   V - Friendly fire   J - Release follower",
            "I - Items   T - Tools   M - Magic   F - Followers   C - Crafting",
            "X - Craft   Q - Quests   1-9 - Select slot",
        ]
        for line in controls:
            text = self.small_font.render(line, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 22

        # Last git push timestamp
        push_time = getattr(self, 'last_push_time', 'Unknown')
        push_text = self.tiny_font.render(f"Last push: {push_time}", True, COLORS['GRAY'])
        self.screen.blit(push_text, (SCREEN_WIDTH // 2 - push_text.get_width() // 2, y + 10))

    # -------------------------------------------------------------------------
    # Trader UI
    # -------------------------------------------------------------------------

    def draw_trader_ui(self):
        """Draw trader recipe UI above the trader NPC"""
        if not self.trader_display:
            return

        # Close UI if player moved (not adjacent to trader anymore)
        entity_id = self.trader_display['entity_id']
        if entity_id not in self.entities:
            self.trader_display = None
            return

        trader = self.entities[entity_id]
        player_adjacent = (
            trader.screen_x == self.player['screen_x'] and
            trader.screen_y == self.player['screen_y'] and
            abs(trader.x - self.player['x']) + abs(trader.y - self.player['y']) <= 1
        )

        if not player_adjacent:
            self.trader_display = None
            return

        # Check if trader has enough gold + items for any recipe
        recipes = self.trader_display['recipes']
        trader_x, trader_y = self.trader_display['position']

        # Draw above trader
        ui_x = trader_x * CELL_SIZE
        ui_y = trader_y * CELL_SIZE - 100

        slot_size = CELL_SIZE
        padding = 4

        recipes_shown = 0
        for i, recipe in enumerate(recipes):
            # Check if trader has ingredients (just for visual feedback)
            can_craft = True
            for item_name, count in recipe['inputs']:
                if trader.inventory.get(item_name, 0) < count:
                    can_craft = False
                    break

            # Show ALL recipes, not just available ones
            # Draw recipe: inputs + arrow + output
            recipe_y = ui_y - (recipes_shown * (slot_size + padding))
            current_x = ui_x
            recipes_shown += 1

            # Draw input items
            for item_name, count in recipe['inputs']:
                # Draw slot background
                pygame.draw.rect(self.screen, COLORS['BLACK'],
                               (current_x, recipe_y, slot_size, slot_size))
                pygame.draw.rect(self.screen, (100, 100, 100),
                               (current_x, recipe_y, slot_size, slot_size), 2)

                # Draw item icon/letter
                if item_name in self.sprite_manager.sprites:
                    sprite = self.sprite_manager.sprites[item_name]
                    self.screen.blit(sprite, (current_x, recipe_y))
                else:
                    item_letter = item_name[0].upper()
                    text = self.tiny_font.render(item_letter, True, COLORS['WHITE'])
                    text_rect = text.get_rect(center=(current_x + slot_size // 2,
                                                       recipe_y + slot_size // 2))
                    self.screen.blit(text, text_rect)

                # Draw count
                count_text = self.tiny_font.render(str(count), True, COLORS['WHITE'])
                self.screen.blit(count_text, (current_x + slot_size - 12, recipe_y + slot_size - 12))

                current_x += slot_size + padding

            # Draw arrow
            arrow_text = self.font.render("→", True, COLORS['WHITE'])
            self.screen.blit(arrow_text, (current_x, recipe_y + slot_size // 4))
            current_x += slot_size

            # Draw output item
            output_name, output_count = recipe['output']
            pygame.draw.rect(self.screen, COLORS['BLACK'],
                           (current_x, recipe_y, slot_size, slot_size))
            pygame.draw.rect(self.screen, (0, 255, 0),
                           (current_x, recipe_y, slot_size, slot_size), 2)

            if output_name in self.sprite_manager.sprites:
                sprite = self.sprite_manager.sprites[output_name]
                self.screen.blit(sprite, (current_x, recipe_y))
            else:
                output_letter = output_name[0].upper()
                text = self.tiny_font.render(output_letter, True, COLORS['WHITE'])
                text_rect = text.get_rect(center=(current_x + slot_size // 2,
                                                   recipe_y + slot_size // 2))
                self.screen.blit(text, text_rect)

            # Draw output count
            if output_count > 1:
                count_text = self.tiny_font.render(str(output_count), True, COLORS['WHITE'])
                self.screen.blit(count_text, (current_x + slot_size - 12, recipe_y + slot_size - 12))

            # Execute trade if player presses SPACE near this recipe
            # (This will be handled in input handling)

    # -------------------------------------------------------------------------
    # NPC inspection
    # -------------------------------------------------------------------------

    def draw_inspected_npc(self):
        """Draw inspection info to the right of targeted NPC"""
        if not self.inspected_npc or self.inspected_npc not in self.entities:
            return

        entity = self.entities[self.inspected_npc]

        # Check if still on same screen
        if (entity.screen_x != self.player['screen_x'] or
                entity.screen_y != self.player['screen_y']):
            self.inspected_npc = None
            return

        # Check subscreen context - only show if in same subscreen context
        if self.player['in_subscreen']:
            # Player in subscreen - only show entities in SAME subscreen
            if not entity.in_subscreen or entity.subscreen_key != self.player['subscreen_key']:
                self.inspected_npc = None
                return
        else:
            # Player in main zone - don't show entities in subscreens
            if entity.in_subscreen:
                self.inspected_npc = None
                return

        # Position info to the right of the NPC
        npc_screen_x = entity.x * CELL_SIZE
        npc_screen_y = entity.y * CELL_SIZE

        info_x = npc_screen_x + CELL_SIZE + 10  # 10 pixels to the right
        info_y = npc_screen_y
        line_height = 16

        info_lines = []

        # Name
        name = entity.name if entity.name else entity.type
        info_lines.append(f"{name}")

        # Type/Profession
        info_lines.append(f"{entity.type}")

        # Level
        info_lines.append(f"Lv.{entity.level}")

        # XP (show current XP / XP needed for next level)
        if hasattr(entity, 'xp') and hasattr(entity, 'xp_to_level'):
            info_lines.append(f"XP:{entity.xp}/{entity.xp_to_level}")

        # Health
        health_pct = int((entity.health / entity.max_health) * 100)
        info_lines.append(f"HP:{health_pct}%")

        # Hunger
        hunger_pct = int((entity.hunger / entity.max_hunger) * 100)
        info_lines.append(f"Food:{hunger_pct}%")

        # Thirst
        thirst_pct = int((entity.thirst / entity.max_thirst) * 100)
        info_lines.append(f"Water:{thirst_pct}%")

        # Age (if entity has age)
        if hasattr(entity, 'age'):
            info_lines.append(f"Age:{int(entity.age)}y")

        # Faction (if entity has faction)
        if hasattr(entity, 'faction') and entity.faction:
            info_lines.append(f"{entity.faction}")

        # Wizard info (if wizard)
        if entity.type == 'WIZARD':
            if hasattr(entity, 'spell'):
                info_lines.append(f"Spell:{entity.spell}")
            if hasattr(entity, 'alignment'):
                info_lines.append(f"({entity.alignment})")

        # Draw each line (no background box)
        for i, line in enumerate(info_lines):
            text = self.tiny_font.render(line, True, (255, 255, 255))
            self.screen.blit(text, (info_x, info_y + i * line_height))

    # -------------------------------------------------------------------------
    # Dropped item / chest tooltip
    # -------------------------------------------------------------------------

    def draw_targeted_items(self):
        """Show item list when player targets a cell with dropped items or a chest."""
        target = self.get_target_cell()
        if not target:
            return

        tx, ty = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            screen_key = self.player['subscreen_key']

        info_lines = []

        # Check for dropped items
        if screen_key in self.dropped_items:
            cell_key = (tx, ty)
            if cell_key in self.dropped_items[screen_key]:
                items = self.dropped_items[screen_key][cell_key]
                for item_name, count in items.items():
                    name = ITEMS.get(item_name, {}).get('name', item_name)
                    if count > 1:
                        info_lines.append(f"{name} x{count}")
                    else:
                        info_lines.append(name)

        # Check for chest contents
        if self.current_screen and self.current_screen['grid'][ty][tx] == 'CHEST':
            chest_key = f"{screen_key}:{tx},{ty}"
            if chest_key in self.chest_contents and self.chest_contents[chest_key]:
                info_lines.append("-- Chest --")
                for item_name, count in self.chest_contents[chest_key].items():
                    name = ITEMS.get(item_name, {}).get('name', item_name)
                    if count > 1:
                        info_lines.append(f"{name} x{count}")
                    else:
                        info_lines.append(name)

        if not info_lines:
            return

        # Limit display to 8 items
        if len(info_lines) > 8:
            info_lines = info_lines[:7] + [f"...+{len(info_lines) - 7} more"]

        # Draw to the right of target cell
        info_x = tx * CELL_SIZE + CELL_SIZE + 8
        info_y = ty * CELL_SIZE
        line_height = 14

        # Keep on screen
        if info_x + 120 > SCREEN_WIDTH:
            info_x = tx * CELL_SIZE - 128

        for i, line in enumerate(info_lines):
            text = self.tiny_font.render(line, True, (255, 255, 255))
            # Small shadow for readability
            shadow = self.tiny_font.render(line, True, (0, 0, 0))
            self.screen.blit(shadow, (info_x + 1, info_y + i * line_height + 1))
            self.screen.blit(text, (info_x, info_y + i * line_height))

    # -------------------------------------------------------------------------
    # Quest arrow
    # -------------------------------------------------------------------------

    def draw_quest_arrow(self):
        """Draw directional arrow to quest target"""
        quest = self.quests[self.active_quest]

        # If player is in a subscreen, always point to the exit
        if self.player.get('in_subscreen'):
            subscreen = self.subscreens.get(self.player.get('subscreen_key'))
            if subscreen:
                exit_pos = subscreen.get('exit', subscreen.get('entrance'))
                if exit_pos:
                    ex, ey = exit_pos
                    px, py = self.player['x'], self.player['y']
                    if px != ex or py != ey:
                        arrow_x = ex * CELL_SIZE + CELL_SIZE // 2
                        arrow_y = (ey - 1) * CELL_SIZE + CELL_SIZE // 2
                        quest_color = QUEST_TYPES.get(self.active_quest, {}).get('color', (200, 200, 200))
                        arrow_text = self.font.render("EXIT ↓", True, quest_color)
                        arrow_rect = arrow_text.get_rect(center=(arrow_x, arrow_y))
                        self.screen.blit(arrow_text, arrow_rect)
                    return

        # Determine target position
        target_screen_x, target_screen_y = None, None
        target_x, target_y = None, None

        if quest.target_entity_id:
            # Find entity
            if quest.target_entity_id in self.entities:
                entity = self.entities[quest.target_entity_id]
                target_screen_x, target_screen_y = entity.screen_x, entity.screen_y
                target_x, target_y = entity.x, entity.y
        elif quest.target_location:
            target_screen_x, target_screen_y = quest.target_location
            target_x, target_y = GRID_WIDTH // 2, GRID_HEIGHT // 2  # Center of zone
        elif quest.target_cell:
            target_screen_x, target_screen_y, target_x, target_y = quest.target_cell

        if target_screen_x is None:
            return

        # Calculate relative position
        player_sx, player_sy = self.player['screen_x'], self.player['screen_y']
        player_x, player_y = self.player['x'], self.player['y']

        # Calculate zone distance
        zone_dx = target_screen_x - player_sx
        zone_dy = target_screen_y - player_sy
        zone_distance = int((zone_dx**2 + zone_dy**2)**0.5)

        # Check if in same zone
        in_same_zone = (zone_dx == 0 and zone_dy == 0)

        # If in same zone, calculate cell distance
        if in_same_zone:
            cell_dx = target_x - player_x
            cell_dy = target_y - player_y
            cell_distance = int((cell_dx**2 + cell_dy**2)**0.5)

            # Position arrow 1 cell above target, pointing down
            arrow_x = target_x * CELL_SIZE + CELL_SIZE // 2
            arrow_y = (target_y - 1) * CELL_SIZE + CELL_SIZE // 2

            # Always point down at the target
            arrow_symbol = "v"

            distance_text = f"{cell_distance}"
        else:
            # Target is in different zone - calculate zone direction
            cell_dx = zone_dx * GRID_WIDTH
            cell_dy = zone_dy * GRID_HEIGHT

            # Calculate arrow position (at screen edge)
            arrow_x, arrow_y = SCREEN_WIDTH // 2, (SCREEN_HEIGHT - 60) // 2
            arrow_symbol = "○"

            # Determine direction
            if abs(cell_dx) > abs(cell_dy):
                if cell_dx > 0:
                    arrow_symbol = ">"
                    arrow_x = SCREEN_WIDTH - 40
                else:
                    arrow_symbol = "<"
                    arrow_x = 40
            else:
                if cell_dy > 0:
                    arrow_symbol = "v"
                    arrow_y = SCREEN_HEIGHT - 100
                else:
                    arrow_symbol = "^"
                    arrow_y = 40

            distance_text = f"{zone_distance}"

        # Use white color for arrow
        arrow_color = COLORS['WHITE']

        # Draw arrow - slightly larger font (32pt instead of 24pt)
        arrow_font = pygame.font.Font(None, 32)
        arrow_text = arrow_font.render(arrow_symbol, True, arrow_color)
        arrow_rect = arrow_text.get_rect(center=(arrow_x, arrow_y))
        self.screen.blit(arrow_text, arrow_rect)

        # Draw distance below arrow
        dist_render = self.tiny_font.render(distance_text, True, arrow_color)
        dist_rect = dist_render.get_rect(center=(arrow_x, arrow_y + 20))
        self.screen.blit(dist_render, dist_rect)
