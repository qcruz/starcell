import pygame

from constants import (
    COLORS, ITEMS, CELL_TYPES, QUEST_TYPES,
    CELL_SIZE, SCREEN_HEIGHT, FPS,
)


class InventoryUIMixin:
    """Inventory panel and quest selection UI rendering."""

    # -------------------------------------------------------------------------
    # Inventory panels
    # -------------------------------------------------------------------------

    def draw_inventory_panels(self):
        """Draw inventory panels at bottom left"""
        if not self.inventory.open_menus:
            return

        slot_size = CELL_SIZE
        start_x = 10
        start_y = SCREEN_HEIGHT - 90  # Above UI bar

        # Stack categories vertically from bottom
        categories = ['tools', 'items', 'magic', 'followers', 'crafting']
        category_colors = {
            'tools': (100, 100, 120),
            'items': (80, 120, 80),
            'magic': (120, 80, 120),
            'followers': (120, 100, 80),
            'crafting': (180, 140, 60)  # Gold color for crafting
        }

        y_offset = 0

        for category in categories:
            if category not in self.inventory.open_menus:
                continue

            # Special handling for crafting screen - shows all items+tools+magic
            if category == 'crafting':
                items = self.inventory.get_all_craftable_items()
            else:
                items = self.inventory.get_item_list(category)

            if not items:
                # Show empty category label
                label_text = self.small_font.render(f"{category.upper()} (empty)", True, COLORS['GRAY'])
                self.screen.blit(label_text, (start_x, start_y - y_offset - 15))
                y_offset += 25
                continue

            # Category label
            label_text = self.small_font.render(category.upper(), True, category_colors[category])
            self.screen.blit(label_text, (start_x, start_y - y_offset - 15))

            # Draw items horizontally
            for i, (item_name, count) in enumerate(items):
                slot_x = start_x + i * (slot_size + 2)
                slot_y = start_y - y_offset

                # Background
                pygame.draw.rect(self.screen, COLORS['BLACK'],
                               (slot_x, slot_y, slot_size, slot_size))

                # Selected highlight
                if self.inventory.selected[category] == item_name:
                    pygame.draw.rect(self.screen, COLORS['INV_SELECT'],
                                   (slot_x, slot_y, slot_size, slot_size), 3)
                else:
                    pygame.draw.rect(self.screen, COLORS['INV_BORDER'],
                                   (slot_x, slot_y, slot_size, slot_size), 1)

                # Item sprite or color
                has_sprite = (self.use_sprites and
                             hasattr(self, 'sprite_manager') and
                             item_name in self.sprite_manager.sprites)

                # Also try uppercase version for sprites (TREE1 vs tree1)
                if not has_sprite and self.use_sprites and hasattr(self, 'sprite_manager'):
                    has_sprite = item_name.upper() in self.sprite_manager.sprites
                    if has_sprite:
                        item_name_for_sprite = item_name.upper()
                    else:
                        item_name_for_sprite = item_name
                else:
                    item_name_for_sprite = item_name

                if has_sprite:
                    # Use sprite for item
                    sprite = self.sprite_manager.get_sprite(item_name_for_sprite)
                    self.screen.blit(sprite, (slot_x, slot_y))
                elif item_name in ITEMS:
                    # Fallback to colored rectangle for items
                    item_color = ITEMS[item_name]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))
                elif item_name.upper() in CELL_TYPES:
                    # Fallback for structures (tree1 -> TREE1, house -> HOUSE, etc.)
                    item_color = CELL_TYPES[item_name.upper()]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))
                elif item_name.lower() in CELL_TYPES:
                    # Try lowercase too
                    item_color = CELL_TYPES[item_name.lower()]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))

                # Item count (top-right)
                if count > 1:
                    count_text = self.tiny_font.render(str(count), True, COLORS['WHITE'])
                    count_bg = pygame.Surface((count_text.get_width() + 2, count_text.get_height()))
                    count_bg.fill(COLORS['BLACK'])
                    count_bg.set_alpha(180)
                    self.screen.blit(count_bg, (slot_x + slot_size - count_text.get_width() - 2,
                                                 slot_y + 2))
                    self.screen.blit(count_text, (slot_x + slot_size - count_text.get_width() - 1,
                                                   slot_y + 2))

                # Slot number (top-left)
                num_text = self.tiny_font.render(str((i + 1) % 10), True, COLORS['GRAY'])
                self.screen.blit(num_text, (slot_x + 2, slot_y + 2))

                # Item name label at bottom of slot
                display_name = ITEMS.get(item_name, {}).get('name', item_name)
                name_surf = self.tiny_font.render(display_name, True, COLORS['WHITE'])
                # Clip to slot width
                name_w = min(name_surf.get_width(), slot_size - 2)
                name_h = name_surf.get_height()
                name_bg = pygame.Surface((slot_size, name_h))
                name_bg.fill(COLORS['BLACK'])
                name_bg.set_alpha(180)
                self.screen.blit(name_bg, (slot_x, slot_y + slot_size - name_h))
                self.screen.blit(name_surf, (slot_x + 1, slot_y + slot_size - name_h),
                                 area=pygame.Rect(0, 0, name_w, name_h))

            y_offset += slot_size + 15

    # -------------------------------------------------------------------------
    # Quest selection UI
    # -------------------------------------------------------------------------

    def draw_quest_ui(self):
        """Draw quest selection UI on left side matching inventory format"""
        if not self.quest_ui_open:
            return

        slot_size = CELL_SIZE
        start_x = 10
        # Position above inventory panels - calculate based on how many are open
        base_y = SCREEN_HEIGHT - 90  # Base inventory position

        # Calculate y_offset from open inventory panels
        y_offset = 0
        if self.inventory.open_menus:
            categories = ['tools', 'items', 'magic', 'followers', 'crafting']
            for category in categories:
                if category in self.inventory.open_menus:
                    items = (self.inventory.get_all_craftable_items()
                             if category == 'crafting'
                             else self.inventory.get_item_list(category))
                    y_offset += slot_size + 15

        start_y = base_y - y_offset

        # Quest category label
        quest_color = (200, 150, 100)  # Tan/brown color for quests
        label_text = self.small_font.render("QUESTS", True, quest_color)
        self.screen.blit(label_text, (start_x, start_y - 15))

        # Draw quest slots horizontally
        quest_types = list(QUEST_TYPES.keys())
        for i, quest_type in enumerate(quest_types):
            quest = self.quests[quest_type]
            quest_info = QUEST_TYPES[quest_type]

            slot_x = start_x + i * (slot_size + 2)
            slot_y = start_y

            # Background
            pygame.draw.rect(self.screen, COLORS['BLACK'],
                           (slot_x, slot_y, slot_size, slot_size))

            # Background color based on status
            if quest.status == 'completed':
                bg_color = (50, 100, 50)  # Dark green
            elif quest.cooldown_remaining > 0:
                bg_color = (60, 60, 60)  # Dark gray
            else:
                bg_color = COLORS['BLACK']

            if bg_color != COLORS['BLACK']:
                pygame.draw.rect(self.screen, bg_color,
                               (slot_x + 1, slot_y + 1, slot_size - 2, slot_size - 2))

            # Selected highlight (active quest)
            if quest_type == self.active_quest:
                pygame.draw.rect(self.screen, COLORS['INV_SELECT'],
                               (slot_x, slot_y, slot_size, slot_size), 3)
            else:
                pygame.draw.rect(self.screen, COLORS['INV_BORDER'],
                               (slot_x, slot_y, slot_size, slot_size), 1)

            # Draw quest symbol
            symbol_text = self.font.render(quest_info['symbol'], True, quest_info['color'])
            symbol_rect = symbol_text.get_rect(center=(slot_x + slot_size // 2, slot_y + slot_size // 2))
            self.screen.blit(symbol_text, symbol_rect)

            # Draw completion count in bottom right
            if quest.completed_count > 0:
                count_text = self.tiny_font.render(str(quest.completed_count), True, COLORS['WHITE'])
                count_bg = pygame.Surface((count_text.get_width() + 2, count_text.get_height()))
                count_bg.fill(COLORS['BLACK'])
                count_bg.set_alpha(180)
                self.screen.blit(count_bg, (slot_x + slot_size - count_text.get_width() - 2,
                                           slot_y + slot_size - count_text.get_height()))
                self.screen.blit(count_text, (slot_x + slot_size - count_text.get_width() - 1,
                                             slot_y + slot_size - count_text.get_height()))

            # Draw cooldown timer in top left
            if quest.cooldown_remaining > 0:
                cooldown_sec = quest.cooldown_remaining // FPS
                cooldown_text = self.tiny_font.render(f"{cooldown_sec}s", True, COLORS['WHITE'])
                self.screen.blit(cooldown_text, (slot_x + 2, slot_y + 2))

            # Slot number (for future number key selection)
            num_text = self.tiny_font.render(str((i + 1) % 10), True, COLORS['GRAY'])
            self.screen.blit(num_text, (slot_x + 2, slot_y + slot_size - 12))
