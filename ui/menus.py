import pygame

from constants import (
    COLORS, ITEMS, QUEST_TYPES,
    CELL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    GRID_WIDTH, GRID_HEIGHT,
)

# ── Game Options screen layout ────────────────────────────────────────────────
# Each section is (header_label, [(flag_name, display_label), ...])
_GAME_OPTIONS_SECTIONS = [
    ('CELLULAR AUTOMATA', [
        ('ca_enabled',      'Master CA Toggle'),
        ('ca_tree_spread',  'Tree Spread'),
        ('ca_sand_spread',  'Sand / Desert Spread'),
        ('ca_water_spread', 'Water Flooding'),
        ('ca_grass_growth', 'Grass Growth'),
        ('ca_drought',      'Drought Effects'),
    ]),
    ('ENTITY SPAWNING', [
        ('spawn_goblins',         'Goblins & Bandits'),
        ('spawn_wolves',          'Wolves'),
        ('spawn_bats',            'Bats'),
        ('spawn_skeletons_night', 'Night Skeletons'),
        ('spawn_cave_hostiles',   'Cave Hostiles'),
        ('spawn_termites',        'Termites'),
    ]),
    ('GAME DIFFICULTY', [
        ('hunger_decay',             'Hunger Decay'),
        ('thirst_decay',             'Thirst Decay'),
        ('starvation_damage',        'Starvation Damage'),
        ('old_age_damage',           'Old Age Damage'),
        ('skeleton_daylight_damage', 'Skeleton Daylight Damage'),
    ]),
    ('WORLD EVENTS', [
        ('raids_enabled',   'Raid Events'),
        ('weather_enabled', 'Weather / Rain'),
    ]),
    ('FACTIONS & SOCIETY', [
        ('keeper_assignments', 'Keeper Assignments'),
        ('npc_aging',          'NPC Aging'),
        ('npc_promotions',     'NPC Promotions (Commander/King)'),
        ('faction_wars',       'Faction Wars'),
    ]),
]


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
            "I - Items   T - Tools   M - Magic   R - Actions",
            "F - Followers   C - Crafting   X - Craft",
            "Shift+F - Recruit NPC   Q - Quests   1-9 - Select slot",
            "ESC - Pause",
        ]

        y = 180
        for option in options:
            text = self.small_font.render(option, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 25

        # ── Settings checkboxes ──
        cb_x = SCREEN_WIDTH // 2 - 70
        y += 10

        def draw_checkbox(label, checked, cy):
            box_rect = pygame.Rect(cb_x, cy, 14, 14)
            pygame.draw.rect(self.screen, COLORS['WHITE'], box_rect, 2)
            if checked:
                pygame.draw.line(self.screen, COLORS['WHITE'],
                                 (cb_x + 2, cy + 7), (cb_x + 6, cy + 11), 2)
                pygame.draw.line(self.screen, COLORS['WHITE'],
                                 (cb_x + 6, cy + 11), (cb_x + 12, cy + 3), 2)
            lbl = self.small_font.render(label, True, COLORS['WHITE'])
            self.screen.blit(lbl, (cb_x + 20, cy))
            # Return clickable rect (box + label)
            return pygame.Rect(cb_x, cy, 20 + lbl.get_width(), 16)

        music_rect    = draw_checkbox("Ambient Music",  getattr(self, 'ambient_music_enabled', True), y)
        debug_rect    = draw_checkbox("Debug Prints",   getattr(self, 'debug_prints_enabled',  True), y + 22)
        autosave_rect = draw_checkbox("Autosave (30s)", getattr(self, 'autosave_enabled',      True), y + 44)

        # Store rects for click detection in handle_input
        self._menu_cb_music_rect    = music_rect
        self._menu_cb_debug_rect    = debug_rect
        self._menu_cb_autosave_rect = autosave_rect

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

        # Inventory panels remain accessible while paused (crafting execution is blocked)
        self.draw_inventory_panels()
        self.draw_quest_ui()

        # Pause menu
        title = self.font.render("PAUSED", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 180))

        pause_opts = [
            "P / ESC - Resume",
            "S - Save Game",
            "O - Game Options",
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
    # Game Options screen
    # -------------------------------------------------------------------------

    def draw_game_options(self):
        """Draw the Game Options subscreen (opened from pause menu via O)."""
        opts = getattr(self, 'game_opts', None)
        if opts is None:
            return

        # Base: draw the paused game world + overlay
        self.draw_game()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(180)
        overlay.fill(COLORS['BLACK'])
        self.screen.blit(overlay, (0, 0))

        # Panel geometry
        panel_w = 520
        panel_h = SCREEN_HEIGHT - 100
        panel_x = SCREEN_WIDTH // 2 - panel_w // 2
        panel_y = 50
        pygame.draw.rect(self.screen, (30, 30, 40), (panel_x, panel_y, panel_w, panel_h))
        pygame.draw.rect(self.screen, COLORS['YELLOW'], (panel_x, panel_y, panel_w, panel_h), 2)

        # Title
        title = self.font.render("GAME OPTIONS", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, panel_y + 10))

        hint = self.tiny_font.render("↑↓ / Scroll to navigate  •  Click to toggle  •  O / ESC to close",
                                     True, COLORS['GRAY'])
        self.screen.blit(hint, (SCREEN_WIDTH // 2 - hint.get_width() // 2, panel_y + 36))

        # Scrollable content area
        content_top = panel_y + 58
        content_h = panel_h - 62
        scroll = getattr(self, '_game_opts_scroll', 0)

        # Clip drawing to the content area
        clip_rect = pygame.Rect(panel_x, content_top, panel_w, content_h)
        self.screen.set_clip(clip_rect)

        # Build rows and compute total height so we can clamp scroll
        ROW_H = 24
        HEADER_H = 30
        INDENT = 30
        CB_SIZE = 14
        col_x = panel_x + INDENT
        y = content_top - scroll

        # Collect clickable rects for click handling (screen coords, pre-clip)
        toggle_rects = []

        for header, toggles in _GAME_OPTIONS_SECTIONS:
            # Section header
            hdr = self.small_font.render(header, True, COLORS['CYAN'])
            self.screen.blit(hdr, (col_x, y + 6))
            y += HEADER_H

            for flag_name, label in toggles:
                checked = getattr(opts, flag_name, True)
                row_y = y

                # Checkbox
                box_rect = pygame.Rect(col_x, row_y + (ROW_H - CB_SIZE) // 2, CB_SIZE, CB_SIZE)
                pygame.draw.rect(self.screen, COLORS['WHITE'], box_rect, 2)
                if checked:
                    pygame.draw.line(self.screen, COLORS['WHITE'],
                                     (col_x + 2, row_y + ROW_H // 2 + 1),
                                     (col_x + 5, row_y + ROW_H // 2 + 5), 2)
                    pygame.draw.line(self.screen, COLORS['WHITE'],
                                     (col_x + 5, row_y + ROW_H // 2 + 5),
                                     (col_x + CB_SIZE - 2, row_y + (ROW_H - CB_SIZE) // 2 + 2), 2)

                # Label (dimmed when off)
                lbl_color = COLORS['WHITE'] if checked else COLORS['GRAY']
                lbl = self.small_font.render(label, True, lbl_color)
                self.screen.blit(lbl, (col_x + CB_SIZE + 8, row_y + (ROW_H - lbl.get_height()) // 2))

                # Store full-row clickable rect (unclipped screen coords, adjusted for scroll)
                click_rect = pygame.Rect(col_x, row_y, panel_w - INDENT - 10, ROW_H)
                toggle_rects.append((flag_name, click_rect))

                y += ROW_H

            y += 6  # gap after section

        self.screen.set_clip(None)

        # Draw scroll indicator if content overflows
        total_h = y + scroll - (content_top)
        if total_h > content_h:
            bar_h = max(20, int(content_h * content_h / total_h))
            bar_y = content_top + int(scroll / (total_h - content_h) * (content_h - bar_h))
            pygame.draw.rect(self.screen, COLORS['GRAY'],
                             (panel_x + panel_w - 8, bar_y, 6, bar_h))

        # Clamp and store scroll
        max_scroll = max(0, total_h - content_h)
        self._game_opts_scroll = min(max(0, scroll), max_scroll)
        self._game_opts_total_h = total_h
        self._game_opts_content_h = content_h
        self._game_opts_toggle_rects = toggle_rects

    # -------------------------------------------------------------------------
    # Trader UI
    # -------------------------------------------------------------------------

    def draw_npc_inventory_trade_ui(self):
        """Draw the Shift+T NPC inventory trade window.

        Layout per row: [gold slot] [price] → [item slot]
        Player clicks the item slot to buy it.
        """
        if not self.trader_display or self.trader_display.get('mode') != 'inventory':
            return

        npc_id = self.trader_display['entity_id']
        if npc_id not in self.entities or self.inspected_npc != npc_id:
            self.trader_display = None
            return

        entity = self.entities[npc_id]
        items = self.trader_display['items']

        tx, ty = self.trader_display['position']
        slot_size = CELL_SIZE
        padding = 4

        # Anchor above the NPC (minimum 2 rows tall even when empty)
        row_count = max(len(items), 1)
        ui_x = tx * slot_size
        ui_y = ty * slot_size - (row_count + 1) * (slot_size + padding) - 10

        # Header
        npc_name = entity.name if entity.name else entity.type
        header = self.tiny_font.render(f"{npc_name}'s goods (Shift+T to close)", True, COLORS['WHITE'])
        self.screen.blit(header, (ui_x, ui_y - 14))

        if not items:
            empty_surf = self.tiny_font.render("Nothing to trade.", True, (180, 180, 180))
            self.screen.blit(empty_surf, (ui_x, ui_y))
            return

        for i, entry in enumerate(items):
            row_y = ui_y + i * (slot_size + padding)
            cur_x = ui_x

            # Gold slot (input)
            pygame.draw.rect(self.screen, COLORS['BLACK'], (cur_x, row_y, slot_size, slot_size))
            pygame.draw.rect(self.screen, (200, 170, 50), (cur_x, row_y, slot_size, slot_size), 2)
            gold_label = self.tiny_font.render(str(entry['price']), True, (255, 215, 0))
            gold_g = self.tiny_font.render('g', True, (200, 170, 50))
            self.screen.blit(gold_label, (cur_x + 2, row_y + 2))
            self.screen.blit(gold_g, (cur_x + 2, row_y + slot_size - 12))
            cur_x += slot_size + padding

            # Arrow
            arrow = self.tiny_font.render('→', True, COLORS['WHITE'])
            self.screen.blit(arrow, (cur_x, row_y + slot_size // 2 - 6))
            cur_x += 20

            # Item slot (output — clickable)
            item_name = entry['item']
            count = entity.inventory.get(item_name, 0)
            has_sprite = (self.use_sprites and hasattr(self, 'sprite_manager') and
                          item_name in self.sprite_manager.sprites)
            pygame.draw.rect(self.screen, COLORS['BLACK'], (cur_x, row_y, slot_size, slot_size))
            pygame.draw.rect(self.screen, (0, 200, 100), (cur_x, row_y, slot_size, slot_size), 2)
            if has_sprite:
                self.screen.blit(self.sprite_manager.sprites[item_name], (cur_x, row_y))
            else:
                item_color = ITEMS.get(item_name, {}).get('color', (180, 180, 180))
                pygame.draw.rect(self.screen, item_color,
                                 (cur_x + 4, row_y + 4, slot_size - 8, slot_size - 8))
            # Item name + count
            label = ITEMS.get(item_name, {}).get('name', item_name)
            name_surf = self.tiny_font.render(f"{label} x{count}", True, COLORS['WHITE'])
            self.screen.blit(name_surf, (cur_x + slot_size + 4, row_y + slot_size // 2 - 6))

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
        keys = pygame.key.get_pressed()
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        _ts_idx = self.inventory.selected_tool_slot_idx
        inspect_tool_active = (
            _ts_idx is not None and
            _ts_idx < len(self.inventory.tool_slots) and
            self.inventory.tool_slots[_ts_idx] == 'inspect'
        )
        if not (shift_held or inspect_tool_active):
            return
        if not self.inspected_npc or self.inspected_npc not in self.entities:
            return

        entity = self.entities[self.inspected_npc]

        # Check if still on same screen
        if (entity.screen_x != self.player['screen_x'] or
                entity.screen_y != self.player['screen_y']):
            self.inspected_npc = None
            return

        # Zone key check above (lines 222-225) already ensures entity and player share
        # the same zone (overworld or structure virtual coords). No further context
        # filtering needed — the unified zone model makes in_structure redundant here.

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

        # Keeper status + target info
        if getattr(entity, 'keeper', False):
            ktype = getattr(entity, 'keeper_type', 3)
            ktype_label = {1: 'Guard', 2: 'Patrol', 3: 'Zone'}.get(ktype, 'Keeper')
            kt = getattr(entity, 'keeper_target', None)
            ktarget = getattr(entity, 'keeper_target_pos', None)
            if kt and kt.get('type') == 'entity':
                eid = kt['ref']
                if eid in self.entities:
                    t = self.entities[eid]
                    pct = int((1.0 - t.health / max(t.max_health, 1)) * 100)
                    zone_tag = '' if kt.get('screen') == (entity.screen_x, entity.screen_y) else ' [x-zone]'
                    info_lines.append(f"Keeper {ktype_label}: {t.type}{zone_tag}")
                    info_lines.append(f"  Target HP: {100-pct}% remaining")
                else:
                    info_lines.append(f"Keeper {ktype_label} (target gone)")
            elif kt and kt.get('type') == 'item':
                item_name = getattr(self, 'item_registry', {}).get(kt['ref'], {}).get('name', '?')
                info_lines.append(f"Keeper {ktype_label}: find {item_name}")
                if ktarget:
                    info_lines.append(f"  @({ktarget[0]},{ktarget[1]})")
            elif ktarget:
                info_lines.append(f"Keeper {ktype_label} @({ktarget[0]},{ktarget[1]})")
            else:
                info_lines.append(f"Keeper {ktype_label} (searching)")

        # Quest queue (FARMER etc. with queue system)
        queue = getattr(entity, 'quest_queue', None)
        if queue:
            info_lines.append("Quests:")
            for entry in queue:
                q_label = QUEST_TYPES.get(entry['type'], {}).get('name', entry['type'])
                active_marker = '>' if entry['type'] == getattr(entity, 'quest_focus', None) else ' '
                base_marker = '(base)' if entry.get('base') else ''
                info_lines.append(f" {active_marker}{q_label}{base_marker}")
        elif getattr(entity, 'quest_focus', None):
            # Non-queue NPC: show single quest_focus
            qfocus = entity.quest_focus
            q_label = QUEST_TYPES.get(qfocus, {}).get('name', qfocus)
            assigned = getattr(entity, 'assigned_quest', None)
            prefix = "Quest*" if assigned else "Quest"
            info_lines.append(f"{prefix}: {q_label}")

        # Favor score
        if hasattr(entity, 'favor'):
            favor_val = entity.favor
            favor_label = "Hostile" if favor_val <= -75 else ("Wary" if favor_val < 0 else ("Neutral" if favor_val == 0 else ("Friendly" if favor_val < 60 else "Allied")))
            info_lines.append(f"Favor:{favor_val:+d} ({favor_label})")

        # Faction (if entity has faction)
        if hasattr(entity, 'faction') and entity.faction:
            info_lines.append(f"{entity.faction}")

        # Wizard info (if wizard)
        if entity.type == 'WIZARD':
            if hasattr(entity, 'spell'):
                info_lines.append(f"Spell:{entity.spell}")
            if hasattr(entity, 'alignment'):
                info_lines.append(f"({entity.alignment})")

        # Quest hint (info, not prompt)
        nq = next((n for n in getattr(self, 'npc_quests', [])
                   if n.npc_id == self.inspected_npc), None)
        if nq:
            if nq.quest.status == 'completed':
                info_lines.append("Quest: done!")
            else:
                q_name = QUEST_TYPES.get(nq.quest.quest_type, {}).get('name', nq.quest.quest_type)
                info_lines.append(f"Quest: {q_name}")

        # Draw info lines
        for i, line in enumerate(info_lines):
            text = self.tiny_font.render(line, True, (255, 255, 255))
            self.screen.blit(text, (info_x, info_y + i * line_height))

        # Contextual prompts — shown as a horizontal bar below the info block
        prompts = []
        if nq and nq.quest.status == 'completed':
            prompts.append("Shift+Q:Turn in")
        elif len(getattr(self, 'npc_quests', [])) < 3:
            prompts.append("Shift+Q:Quest")
        if self.active_quest or getattr(self, 'active_npc_quest_npc_id', None):
            prompts.append("Shift+A:Assign")
        if entity.inventory:
            prompts.append("Shift+T:Trade")
        if self.inventory.items:
            prompts.append("Shift+G:Gift")
        prompts.append("Shift+F:Follow")

        if prompts:
            prompt_y = info_y + len(info_lines) * line_height + 4
            px = info_x
            for prompt in prompts:
                surf = self.tiny_font.render(prompt, True, (200, 200, 100))
                self.screen.blit(surf, (px, prompt_y))
                px += surf.get_width() + 8

    # -------------------------------------------------------------------------
    # Cell / item inspect (triggered when Shift held or inspect tool active,
    # no NPC at target)
    # -------------------------------------------------------------------------

    def draw_inspect_target(self):
        """Show cell name, items, and contextual prompts when inspecting a non-NPC cell."""
        # Only draw when player is actively holding Shift or has inspect tool selected
        keys = pygame.key.get_pressed()
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        _ts_idx = self.inventory.selected_tool_slot_idx
        inspect_tool_active = (
            _ts_idx is not None and
            _ts_idx < len(self.inventory.tool_slots) and
            self.inventory.tool_slots[_ts_idx] == 'inspect'
        )
        if not (shift_held or inspect_tool_active):
            return
        target = getattr(self, 'inspect_cell_target', None)
        if not target:
            return
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        grid = (self.current_screen or {}).get('grid')
        if not grid:
            return

        cell = grid[check_y][check_x]
        info_lines = [cell.replace('_', ' ').title()]
        prompts = []

        # Items on the cell
        items_here = {}
        if screen_key in self.dropped_items:
            items_here = self.dropped_items[screen_key].get((check_x, check_y), {})
        if items_here:
            for item_name, count in items_here.items():
                name = ITEMS.get(item_name, {}).get('name', item_name)
                info_lines.append(f"  {name}{f' x{count}' if count > 1 else ''}")
            prompts.append("E:Pickup")

        # Gravestone inscriptions
        if cell == 'GRAVESTONE':
            gs_names = getattr(self, 'gravestone_names', {}).get(screen_key, {}).get((check_x, check_y), [])
            for n in gs_names:
                info_lines.append(f"  {n}")

        # Chest contents
        if cell == 'CHEST':
            chest_key = f"{screen_key}:{check_x},{check_y}"
            contents = (self.chest_contents or {}).get(chest_key, {})
            if contents:
                for item_name, count in contents.items():
                    name = ITEMS.get(item_name, {}).get('name', item_name)
                    info_lines.append(f"  {name}{f' x{count}' if count > 1 else ''}")
            prompts.append("E:Open chest")

        # Enchantable cells
        enchantable = {'STONE', 'TREE', 'IRON_ORE', 'CAVE_WALL', 'WALL'}
        if cell in enchantable:
            prompts.append("L:Enchant")

        # Position panel near the target cell, but clamp to screen
        from constants import CELL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT
        px = min(check_x * CELL_SIZE + CELL_SIZE + 4, SCREEN_WIDTH - 120)
        py = max(check_y * CELL_SIZE, 4)
        line_height = 16

        for i, line in enumerate(info_lines):
            surf = self.tiny_font.render(line, True, (220, 220, 220))
            self.screen.blit(surf, (px, py + i * line_height))

        if prompts:
            prompt_y = py + len(info_lines) * line_height + 4
            ppx = px
            for p in prompts:
                surf = self.tiny_font.render(p, True, (200, 200, 100))
                self.screen.blit(surf, (ppx, prompt_y))
                ppx += surf.get_width() + 8

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

    def draw_quest_arrow(self, quest=None, color=None):
        """Draw directional arrow to quest target.
        If quest/color not provided, falls back to active_quest."""
        if quest is None:
            quest = self.quests[self.active_quest]
        if color is None:
            color = QUEST_TYPES.get(self.active_quest, {}).get('color', (200, 200, 200))

        # If player is in a structure, always point to the exit
        if self.player.get('in_structure'):
            structure = self.structures.get(self.player.get('structure_key'))
            if structure:
                exit_pos = structure.get('exit', structure.get('entrance'))
                if exit_pos:
                    ex, ey = exit_pos
                    px, py = self.player['x'], self.player['y']
                    if px != ex or py != ey:
                        arrow_x = ex * CELL_SIZE + CELL_SIZE // 2
                        arrow_y = (ey - 1) * CELL_SIZE + CELL_SIZE // 2
                        arrow_text = self.font.render("↓", True, color)
                        arrow_rect = arrow_text.get_rect(center=(arrow_x, arrow_y))
                        self.screen.blit(arrow_text, arrow_rect)
                    return

        # Determine target position
        target_screen_x, target_screen_y = None, None
        target_x, target_y = None, None

        if quest.target_entity_id:
            # Find entity — if it's underground, point to the surface entrance
            if quest.target_entity_id in self.entities:
                entity = self.entities[quest.target_entity_id]
                target_screen_x, target_screen_y, target_x, target_y = \
                    self.get_surface_pos_for_entity(entity)
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
            # Target is in different zone — use exits dict to find valid direction
            # exits = {top, bottom, left, right: bool} on current screen
            current_key = f"{player_sx},{player_sy}"
            exits = self.screens.get(current_key, {}).get('exits', {})

            # Build ordered candidate directions by closeness to target
            # Primary: dominant axis toward target. Secondary: other axis.
            # If neither is a valid exit, try remaining directions (north preferred over east).
            if abs(zone_dx) >= abs(zone_dy):
                primary   = ('right', '>', SCREEN_WIDTH - 40, SCREEN_HEIGHT // 2) if zone_dx > 0 \
                            else ('left',  '<', 40,              SCREEN_HEIGHT // 2)
                secondary = ('bottom', 'v', SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100) if zone_dy >= 0 \
                            else ('top',    '^', SCREEN_WIDTH // 2, 40)
            else:
                primary   = ('bottom', 'v', SCREEN_WIDTH // 2, SCREEN_HEIGHT - 100) if zone_dy > 0 \
                            else ('top',    '^', SCREEN_WIDTH // 2, 40)
                secondary = ('right', '>', SCREEN_WIDTH - 40, SCREEN_HEIGHT // 2) if zone_dx >= 0 \
                            else ('left',  '<', 40,              SCREEN_HEIGHT // 2)
            # Remaining directions, north/east preferred on tie
            remaining = [d for d in [('top','^',SCREEN_WIDTH//2,40),
                                      ('right','>',SCREEN_WIDTH-40,SCREEN_HEIGHT//2),
                                      ('bottom','v',SCREEN_WIDTH//2,SCREEN_HEIGHT-100),
                                      ('left','<',40,SCREEN_HEIGHT//2)]
                         if d[0] not in (primary[0], secondary[0])]

            arrow_symbol, arrow_x, arrow_y = '○', SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2
            for side, sym, ax, ay in [primary, secondary] + remaining:
                if exits.get(side, False):
                    arrow_symbol, arrow_x, arrow_y = sym, ax, ay
                    break

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
