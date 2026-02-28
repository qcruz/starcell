import pygame

from constants import (
    COLORS, CELL_TYPES, ITEMS, QUEST_TYPES,
    CELL_SIZE, SCREEN_WIDTH, SCREEN_HEIGHT,
    GRID_WIDTH, GRID_HEIGHT,
    NIGHT_OVERLAY_ALPHA,
)


class HudMixin:
    """Main game renderer — grid, entities, player, HUD bar, overlays."""

    def draw_game(self):
        """Draw game screen"""
        self.screen.fill(COLORS['BLACK'])

        # Draw grid
        if self.current_screen:
            # Determine correct screen key for dropped items
            # If in subscreen, use subscreen_key; otherwise use overworld coordinates
            if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
                screen_key = self.player['subscreen_key']
            else:
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

            # Ensure variant_grid exists (backfill for screens generated before variant system)
            if 'variant_grid' not in self.current_screen:
                vg = []
                for vy in range(len(self.current_screen['grid'])):
                    vrow = []
                    for vx in range(len(self.current_screen['grid'][vy])):
                        c = self.current_screen['grid'][vy][vx]
                        vrow.append(self.roll_cell_variant(c) if hasattr(self, 'roll_cell_variant') else None)
                    vg.append(vrow)
                self.current_screen['variant_grid'] = vg

            for y, row in enumerate(self.current_screen['grid']):
                for x, cell in enumerate(row):
                    # Check if this cell should use layered rendering
                    # ONLY use layering if we have BOTH base terrain AND object sprites
                    use_layered = False
                    base_terrain = None
                    object_sprite = None

                    if cell in ['TREE1', 'TREE2', 'TREE3', 'FLOWER']:
                        # Trees/flowers layer on biome-appropriate walkable ground
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                cell in self.sprite_manager.sprites):
                            biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                            if biome == 'DESERT':
                                base_terrain = 'SAND'
                            elif biome == 'MOUNTAINS':
                                base_terrain = 'DIRT'
                            else:  # FOREST, PLAINS, or unknown
                                base_terrain = 'GRASS'
                            if base_terrain in self.sprite_manager.sprites:
                                object_sprite = cell
                                use_layered = True
                    elif cell in ['CAMP', 'HOUSE', 'CAVE']:
                        # Camp and house layer on biome-appropriate walkable ground
                        if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                            biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                            if biome == 'DESERT':
                                base_terrain = 'SAND'
                            elif biome == 'MOUNTAINS':
                                base_terrain = 'DIRT'
                            else:  # FOREST, PLAINS, or unknown
                                base_terrain = 'GRASS'

                            # Only use layered if base terrain sprite exists
                            if base_terrain in self.sprite_manager.sprites:
                                object_sprite = cell
                                use_layered = True
                    elif cell == 'CHEST':
                        # Chest uses stored background cell (what it replaced)
                        if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                            # Check if we have a stored background for this chest
                            chest_key = f"{screen_key}:{x},{y}"
                            if hasattr(self, 'chest_backgrounds') and chest_key in self.chest_backgrounds:
                                base_terrain = self.chest_backgrounds[chest_key]
                            else:
                                # No stored background - determine from context
                                if self.current_screen and 'parent_screen' in self.current_screen:
                                    # In subscreen - use floor type
                                    subscreen_type = self.current_screen.get('type', 'HOUSE_INTERIOR')
                                    if 'CAVE' in subscreen_type:
                                        base_terrain = 'CAVE_FLOOR'
                                    else:
                                        base_terrain = 'FLOOR_WOOD'
                                else:
                                    # Fallback to biome-appropriate base terrain
                                    biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                    if biome == 'DESERT':
                                        base_terrain = 'SAND'
                                    elif biome == 'MOUNTAINS':
                                        base_terrain = 'STONE'
                                    elif biome == 'PLAINS':
                                        base_terrain = 'GRASS'
                                    else:  # FOREST
                                        base_terrain = 'GRASS'

                            # Only use layered if base terrain sprite exists
                            if base_terrain in self.sprite_manager.sprites:
                                object_sprite = cell
                                use_layered = True
                    elif cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                        # Check if both DIRT and crop sprites exist
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                'DIRT' in self.sprite_manager.sprites and
                                cell in self.sprite_manager.sprites):
                            base_terrain = 'DIRT'
                            object_sprite = cell
                            use_layered = True
                    elif cell == 'STONE':
                        # Stone should layer on appropriate base terrain
                        if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                            if self.current_screen and 'parent_screen' in self.current_screen:
                                # In subscreen - use floor type
                                subscreen_type = self.current_screen.get('type', 'HOUSE_INTERIOR')
                                if 'CAVE' in subscreen_type:
                                    base_terrain = 'CAVE_FLOOR'
                                else:
                                    base_terrain = 'FLOOR_WOOD'
                            else:
                                # In overworld - determine base terrain by biome
                                biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                if biome == 'DESERT':
                                    base_terrain = 'SAND'
                                elif biome == 'MOUNTAINS':
                                    base_terrain = 'DIRT'
                                else:
                                    base_terrain = 'GRASS'

                            # Only use layered if base terrain sprite exists
                            if base_terrain in self.sprite_manager.sprites:
                                object_sprite = cell
                                use_layered = True
                    elif cell == 'IRON_ORE':
                        # Iron ore always appears inside caves — layer on CAVE_FLOOR
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                cell in self.sprite_manager.sprites and
                                'CAVE_FLOOR' in self.sprite_manager.sprites):
                            base_terrain = 'CAVE_FLOOR'
                            object_sprite = cell
                            use_layered = True
                    elif cell == 'CACTUS':
                        # Cactus layers on SAND
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                cell in self.sprite_manager.sprites and
                                'SAND' in self.sprite_manager.sprites):
                            base_terrain = 'SAND'
                            object_sprite = cell
                            use_layered = True
                    elif cell == 'RUINED_SANDSTONE_COLUMN':
                        # Ruined column layers on SAND
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                cell in self.sprite_manager.sprites and
                                'SAND' in self.sprite_manager.sprites):
                            base_terrain = 'SAND'
                            object_sprite = cell
                            use_layered = True
                    elif cell == 'BARREL':
                        # Barrel layers on FLOOR_WOOD inside houses
                        if (self.use_sprites and hasattr(self, 'sprite_manager') and
                                cell in self.sprite_manager.sprites and
                                'FLOOR_WOOD' in self.sprite_manager.sprites):
                            base_terrain = 'FLOOR_WOOD'
                            object_sprite = cell
                            use_layered = True
                    elif cell == 'STONE_HOUSE':
                        # Stone house layers on biome-appropriate ground, like HOUSE
                        if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                            biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                            if biome == 'DESERT':
                                base_terrain = 'SAND'
                            elif biome == 'MOUNTAINS':
                                base_terrain = 'DIRT'
                            else:
                                base_terrain = 'GRASS'
                            if base_terrain in self.sprite_manager.sprites:
                                object_sprite = cell
                                use_layered = True

                    # Layered rendering (when we have both sprites)
                    if use_layered:
                        # Check if base terrain has a valid variant
                        actual_base = base_terrain
                        if self.current_screen and 'variant_grid' in self.current_screen:
                            v = self.current_screen['variant_grid'][y][x]
                            if v and base_terrain in CELL_TYPES:
                                base_variants = CELL_TYPES[base_terrain].get('variants', {})
                                if v in base_variants and v in self.sprite_manager.sprites:
                                    actual_base = v
                                elif v not in base_variants:
                                    # Stale variant — re-roll for base terrain
                                    new_v = self.roll_cell_variant(base_terrain) if hasattr(self, 'roll_cell_variant') else None
                                    self.current_screen['variant_grid'][y][x] = new_v
                                    if new_v and new_v in self.sprite_manager.sprites:
                                        actual_base = new_v

                        # Draw base terrain (or its variant)
                        base_sprite = self.sprite_manager.get_sprite(actual_base)
                        self.screen.blit(base_sprite, (x * CELL_SIZE, y * CELL_SIZE))
                        # Draw object on top
                        obj_sprite = self.sprite_manager.get_sprite(object_sprite)
                        self.screen.blit(obj_sprite, (x * CELL_SIZE, y * CELL_SIZE))

                    # Direct rendering (no layering) - just render the cell itself
                    else:
                        # Check for cell variant sprite
                        sprite_name = cell
                        variant = None
                        if self.current_screen and 'variant_grid' in self.current_screen:
                            v = self.current_screen['variant_grid'][y][x]
                            if v and cell in CELL_TYPES:
                                cell_variants = CELL_TYPES[cell].get('variants', {})
                                if v in cell_variants:
                                    variant = v
                                else:
                                    # Stale variant — cell type changed. Re-roll for new cell.
                                    new_variant = self.roll_cell_variant(cell) if hasattr(self, 'roll_cell_variant') else None
                                    self.current_screen['variant_grid'][y][x] = new_variant
                                    if new_variant:
                                        variant = new_variant
                            elif v is None and cell in CELL_TYPES and CELL_TYPES[cell].get('variants'):
                                # Cell has variants but no variant assigned — roll one
                                new_variant = self.roll_cell_variant(cell) if hasattr(self, 'roll_cell_variant') else None
                                self.current_screen['variant_grid'][y][x] = new_variant
                                if new_variant:
                                    variant = new_variant

                        if cell == 'WALL' and self.current_screen:
                            biome = self.current_screen.get('biome', 'FOREST')
                            sprite_name = f"wall_{biome.lower()}"
                        elif variant:
                            sprite_name = variant

                        has_sprite = (self.use_sprites and
                                     hasattr(self, 'sprite_manager') and
                                     sprite_name in self.sprite_manager.sprites)

                        if has_sprite:
                            # Use sprite directly - NO LABEL
                            sprite = self.sprite_manager.get_sprite(sprite_name)
                            self.screen.blit(sprite, (x * CELL_SIZE, y * CELL_SIZE))
                        else:
                            # Fallback to colored rectangle with border AND label
                            color = CELL_TYPES[cell]['color']
                            pygame.draw.rect(self.screen, color,
                                           (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))
                            # Draw border for non-sprite cells
                            pygame.draw.rect(self.screen, COLORS['BLACK'],
                                           (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE), 1)

                            # Draw label ONLY when no sprite
                            label = CELL_TYPES[cell]['label']
                            text = self.tiny_font.render(label, True, COLORS['WHITE'])
                            text_rect = text.get_rect(center=(
                                x * CELL_SIZE + CELL_SIZE // 2,
                                y * CELL_SIZE + CELL_SIZE // 2
                            ))
                            self.screen.blit(text, text_rect)

                    # Draw enchantment indicator if cell is enchanted
                    if self.is_cell_enchanted(x, y, screen_key):
                        enchant_level = self.enchanted_cells[screen_key].get((x, y), 0)
                        # Draw golden star in corner
                        star_text = self.tiny_font.render('★', True, COLORS['YELLOW'])
                        self.screen.blit(star_text, (x * CELL_SIZE + 2, y * CELL_SIZE + 2))
                        # Draw enchant level number
                        if enchant_level > 1:
                            level_text = self.tiny_font.render(str(enchant_level), True, COLORS['YELLOW'])
                            self.screen.blit(level_text, (x * CELL_SIZE + 12, y * CELL_SIZE + 2))

                    # Draw dropped items (layered over base cell)
                    if screen_key in self.dropped_items:
                        cell_key = (x, y)
                        if cell_key in self.dropped_items[screen_key]:
                            items = self.dropped_items[screen_key][cell_key]
                            item_count = len(items)
                            total_count = sum(items.values())

                            # Empty cells allow full overlay
                            empty_cells = ['GRASS', 'DIRT', 'SAND', 'STONE', 'FLOOR_WOOD', 'CAVE_FLOOR',
                                         'PLANKS', 'WOOD', 'SOIL', 'COBBLESTONE']
                            is_empty_cell = cell in empty_cells

                            if item_count == 1 and total_count == 1 and is_empty_cell:
                                # Single item, single count — show item sprite
                                item_name = list(items.keys())[0]
                                sprite_key = None
                                if self.use_sprites and hasattr(self, 'sprite_manager'):
                                    if item_name in self.sprite_manager.sprites:
                                        sprite_key = item_name
                                    elif item_name in ITEMS and 'sprite_name' in ITEMS[item_name]:
                                        sn = ITEMS[item_name]['sprite_name']
                                        if sn in self.sprite_manager.sprites:
                                            sprite_key = sn
                                    if not sprite_key and item_name.upper() in self.sprite_manager.sprites:
                                        sprite_key = item_name.upper()

                                if sprite_key:
                                    sprite = self.sprite_manager.get_sprite(sprite_key)
                                    self.screen.blit(sprite, (x * CELL_SIZE, y * CELL_SIZE))
                                elif item_name in ITEMS:
                                    item_color = ITEMS[item_name]['color']
                                    overlay_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                                    overlay_surface.fill((*item_color, 180))
                                    self.screen.blit(overlay_surface, (x * CELL_SIZE, y * CELL_SIZE))
                                    item_label = ITEMS[item_name].get('name', item_name)[:3].upper()
                                    text = self.tiny_font.render(item_label, True, COLORS['WHITE'])
                                    text_rect = text.get_rect(center=(
                                        x * CELL_SIZE + CELL_SIZE // 2,
                                        y * CELL_SIZE + CELL_SIZE // 2))
                                    self.screen.blit(text, text_rect)
                            else:
                                # Multiple items or stacks — show itembag sprite
                                has_bag = (self.use_sprites and hasattr(self, 'sprite_manager') and
                                           'itembag' in self.sprite_manager.sprites)
                                if has_bag:
                                    bag_sprite = self.sprite_manager.get_sprite('itembag')
                                    self.screen.blit(bag_sprite, (x * CELL_SIZE, y * CELL_SIZE))
                                else:
                                    # Fallback: brown bag circle
                                    bag_color = (139, 90, 43)
                                    pygame.draw.circle(self.screen, bag_color,
                                                     (x * CELL_SIZE + CELL_SIZE // 2,
                                                      y * CELL_SIZE + CELL_SIZE // 2),
                                                     CELL_SIZE // 3)

            # Draw target highlight
            target = self.get_target_cell()
            if target:
                highlight_x, highlight_y = target
                # Draw semi-transparent yellow overlay
                highlight_surface = pygame.Surface((CELL_SIZE, CELL_SIZE))
                highlight_surface.set_alpha(100)
                highlight_surface.fill(COLORS['YELLOW'])
                self.screen.blit(highlight_surface,
                               (highlight_x * CELL_SIZE, highlight_y * CELL_SIZE))
                # Draw border
                pygame.draw.rect(self.screen, COLORS['YELLOW'],
                               (highlight_x * CELL_SIZE, highlight_y * CELL_SIZE,
                                CELL_SIZE, CELL_SIZE), 3)

            # Draw entities on current screen or subscreen
            entities_to_draw = []

            if self.player.get('in_subscreen'):
                # In subscreen - draw entities that belong to this subscreen
                current_subscreen_key = self.player.get('subscreen_key')
                if current_subscreen_key and current_subscreen_key in self.subscreen_entities:
                    entities_to_draw = self.subscreen_entities[current_subscreen_key]
            else:
                # In overworld - draw entities from current screen
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                if screen_key in self.screen_entities:
                    entities_to_draw = self.screen_entities[screen_key]

            # Draw the entities
            for entity_id in entities_to_draw:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]

                    # Proxy NPC is drawn as the player sprite below.
                    # Still run smooth movement + animation so anim_frame advances
                    # correctly — the player sprite reads these values directly.
                    if self.autopilot and entity_id == getattr(self, 'autopilot_proxy_id', None):
                        entity.update_smooth_movement()
                        entity.update_animation()
                        continue

                    # Update smooth movement
                    entity.update_smooth_movement()

                    # Update animation
                    entity.update_animation()

                    # Calculate pixel position from WORLD coordinates (not grid + offset)
                    pixel_x = entity.world_x * CELL_SIZE
                    pixel_y = entity.world_y * CELL_SIZE

                    # Try to load entity sprite
                    entity_sprite = None
                    is_double = entity.type.endswith('_double')
                    base_type = entity.type.replace('_double', '') if is_double else entity.type

                    if self.use_sprites and hasattr(self, 'sprite_manager'):
                        # Get sprite name (use sprite_name property if available, otherwise use type)
                        sprite_base = entity.props.get('sprite_name', base_type).lower()

                        # Try 3-frame animation first
                        sprite_name = f"{sprite_base}_{entity.facing}_{entity.anim_frame}"
                        if sprite_name in self.sprite_manager.sprites:
                            entity_sprite = self.sprite_manager.get_sprite(sprite_name)
                        else:
                            # Fallback to 2-frame animation (convert still -> 1, keep 1 and 2 as is)
                            if entity.anim_frame == 'still':
                                frame_2frame = '1'
                            else:
                                frame_2frame = entity.anim_frame  # '1' or '2'
                            sprite_name_2frame = f"{sprite_base}_{entity.facing}_{frame_2frame}"
                            if sprite_name_2frame in self.sprite_manager.sprites:
                                entity_sprite = self.sprite_manager.get_sprite(sprite_name_2frame)

                    # Draw entity at smooth sub-cell position
                    if entity_sprite:
                        # Use animated sprite
                        if is_double:
                            # Draw two overlapping sprites for _double entities
                            self.screen.blit(entity_sprite, (pixel_x, pixel_y))
                            self.screen.blit(entity_sprite, (pixel_x + 4, pixel_y + 2))
                        else:
                            self.screen.blit(entity_sprite, (pixel_x, pixel_y))
                    else:
                        # Fallback to circle with symbol
                        entity_color = entity.props['color']
                        if is_double:
                            # Draw two overlapping circles for _double
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2),
                                 int(pixel_y + CELL_SIZE // 2)),
                                CELL_SIZE // 3
                            )
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2 + 4),
                                 int(pixel_y + CELL_SIZE // 2 + 2)),
                                CELL_SIZE // 3
                            )
                        else:
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2),
                                 int(pixel_y + CELL_SIZE // 2)),
                                CELL_SIZE // 3
                            )

                        # Draw symbol
                        symbol_text = self.tiny_font.render(entity.props['symbol'], True, COLORS['WHITE'])
                        symbol_rect = symbol_text.get_rect(center=(
                            int(pixel_x + CELL_SIZE // 2),
                            int(pixel_y + CELL_SIZE // 2)
                        ))
                        self.screen.blit(symbol_text, symbol_rect)

                    # Draw health bar (always visible) at smooth position
                    bar_width = CELL_SIZE - 4
                    bar_height = 4
                    bar_x = int(pixel_x + 2)
                    bar_y = int(pixel_y - 6)

                    # Background
                    pygame.draw.rect(self.screen, COLORS['BLACK'],
                                   (bar_x, bar_y, bar_width, bar_height))
                    # Health
                    health_width = int((entity.health / entity.max_health) * bar_width)
                    pygame.draw.rect(self.screen, (0, 255, 0),
                                   (bar_x, bar_y, health_width, bar_height))

                    # Draw level if > 1
                    if entity.level > 1:
                        level_text = self.tiny_font.render(f"L{entity.level}", True, COLORS['YELLOW'])
                        self.screen.blit(level_text, (int(pixel_x + 2), int(pixel_y + CELL_SIZE - 12)))

                    # Debug: Draw AI state and target info
                    if self.debug_entity_ai:
                        debug_y_offset = CELL_SIZE - 12 if entity.level > 1 else CELL_SIZE - 2

                        # AI State
                        if hasattr(entity, 'ai_state'):
                            state_color = COLORS['WHITE']
                            if entity.ai_state == 'combat':
                                state_color = (255, 0, 0)  # RED
                            elif entity.ai_state == 'targeting':
                                state_color = (255, 165, 0)  # ORANGE
                            elif entity.ai_state == 'wandering':
                                state_color = COLORS['GRAY']
                            elif entity.ai_state == 'idle':
                                state_color = (192, 192, 192)  # LIGHT_GRAY
                            elif entity.ai_state == 'fleeing':
                                state_color = (255, 100, 255)  # PINK

                            state_text = self.tiny_font.render(f"{entity.ai_state[:3].upper()}", True, state_color)
                            self.screen.blit(state_text, (int(pixel_x + 2), int(pixel_y + debug_y_offset + 10)))

                        # Target info
                        target_info = ""
                        if hasattr(entity, 'current_target') and entity.current_target:
                            if isinstance(entity.current_target, int) and entity.current_target in self.entities:
                                target_entity = self.entities[entity.current_target]
                                target_info = f"→{target_entity.type[:3]}"
                            elif entity.current_target == 'player':
                                target_info = "→PLR"
                        elif hasattr(entity, 'target_type') and entity.target_type:
                            target_info = f"?{entity.target_type[:3]}"

                        if target_info:
                            target_text = self.tiny_font.render(target_info, True, COLORS['CYAN'])
                            self.screen.blit(target_text, (int(pixel_x + 24), int(pixel_y + debug_y_offset + 10)))

                    # Draw faction name if entity has one (debug display)
                    if hasattr(entity, 'faction') and entity.faction:
                        # Abbreviate faction name (first letter of each word)
                        faction_abbrev = ''.join([word[0] for word in entity.faction.split()])
                        faction_text = self.tiny_font.render(faction_abbrev, True, COLORS['CYAN'])
                        self.screen.blit(faction_text, (entity.x * CELL_SIZE + 2, entity.y * CELL_SIZE + CELL_SIZE + 2))

            # Debug: Draw memory lanes for traders
            if self.debug_memory_lanes:
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                if screen_key in self.screen_entities:
                    for entity_id in self.screen_entities[screen_key]:
                        if entity_id in self.entities:
                            entity = self.entities[entity_id]
                            # Only show for TRADER entities
                            if entity.type == 'TRADER' or entity.type == 'TRADER_double':
                                # Draw memory lane cells in RED
                                if hasattr(entity, 'memory_lane') and entity.memory_lane:
                                    for mem_x, mem_y in entity.memory_lane:
                                        # Semi-transparent red overlay
                                        mem_surface = pygame.Surface((CELL_SIZE - 4, CELL_SIZE - 4))
                                        mem_surface.set_alpha(100)
                                        mem_surface.fill((255, 0, 0))  # RED
                                        self.screen.blit(mem_surface, (mem_x * CELL_SIZE + 2, mem_y * CELL_SIZE + 2))

                                # Draw target cell in GREEN
                                if hasattr(entity, 'target_exit') and entity.target_exit:
                                    exit_positions = self.get_exit_positions(entity.target_exit)
                                    if exit_positions:
                                        for target_x, target_y in exit_positions:
                                            # Semi-transparent green overlay
                                            target_surface = pygame.Surface((CELL_SIZE - 4, CELL_SIZE - 4))
                                            target_surface.set_alpha(150)
                                            target_surface.fill((0, 255, 0))  # GREEN
                                            self.screen.blit(target_surface, (target_x * CELL_SIZE + 2, target_y * CELL_SIZE + 2))

            # ── Draw player character (or autopilot proxy) ──────────────────
            proxy = (self.entities.get(self.autopilot_proxy_id)
                     if self.autopilot and getattr(self, 'autopilot_proxy_id', None) else None)

            player_sprite = None

            if proxy is not None:
                # ── AUTOPILOT: mirror proxy state exactly ──────────────────
                px = int(proxy.world_x * CELL_SIZE)
                py = int(proxy.world_y * CELL_SIZE)
                facing = proxy.facing
                anim_frame = proxy.anim_frame
                # Consume player is_moving (keep flag clean)
                self.player['is_moving'] = False

            else:
                # ── MANUAL: player-driven animation + lerp ─────────────────
                PLAYER_TICKS_PER_FRAME = 10

                is_moving = self.player.get('is_moving', False)
                keys_held = pygame.key.get_pressed()
                movement_key_held = (keys_held[pygame.K_UP] or keys_held[pygame.K_w] or
                                     keys_held[pygame.K_DOWN] or keys_held[pygame.K_s] or
                                     keys_held[pygame.K_LEFT] or keys_held[pygame.K_a] or
                                     keys_held[pygame.K_RIGHT] or keys_held[pygame.K_d])

                if is_moving:
                    self.player['_move_anim_ticks'] = 12
                else:
                    remaining = self.player.get('_move_anim_ticks', 0)
                    if remaining > 0:
                        self.player['_move_anim_ticks'] = remaining - 1

                should_animate = is_moving or movement_key_held or self.player.get('_move_anim_ticks', 0) > 0

                if should_animate:
                    self.player['anim_timer'] = self.player.get('anim_timer', 0) + 1
                    if self.player['anim_timer'] >= PLAYER_TICKS_PER_FRAME:
                        af = self.player.get('anim_frame', 'still')
                        ns = self.player.get('_next_step', '1')
                        if af == '1':
                            self.player['anim_frame'] = 'still'
                        elif af == 'still':
                            self.player['anim_frame'] = ns
                            self.player['_next_step'] = '1' if ns == '2' else '2'
                        elif af == '2':
                            self.player['anim_frame'] = 'still'
                        else:
                            self.player['anim_frame'] = '1'
                            self.player['_next_step'] = '2'
                        self.player['anim_timer'] = 0
                else:
                    self.player['anim_frame'] = 'still'
                    self.player['anim_timer'] = 0
                    self.player['_next_step'] = '1'

                self.player['is_moving'] = False

                facing = self.player.get('facing', 'down')
                anim_frame = self.player.get('anim_frame', 'still')

                # Lerp world position toward grid position
                target_wx = float(self.player['x'])
                target_wy = float(self.player['y'])
                PLAYER_MOVE_SPEED = 0.057  # 1 cell in ~18 frames, matches move interval
                ARRIVAL_THRESH = 0.01

                if 'world_x' not in self.player:
                    self.player['world_x'] = target_wx
                    self.player['world_y'] = target_wy

                dx_w = target_wx - self.player['world_x']
                dy_w = target_wy - self.player['world_y']
                dist_w = (dx_w ** 2 + dy_w ** 2) ** 0.5

                if dist_w < ARRIVAL_THRESH or dist_w > 2.5:
                    self.player['world_x'] = target_wx
                    self.player['world_y'] = target_wy
                else:
                    step = min(PLAYER_MOVE_SPEED, dist_w)
                    ratio = step / dist_w
                    self.player['world_x'] += dx_w * ratio
                    self.player['world_y'] += dy_w * ratio

                px = int(self.player['world_x'] * CELL_SIZE)
                py = int(self.player['world_y'] * CELL_SIZE)

            # Sprite lookup (same logic as entity draw loop)
            if self.use_sprites and hasattr(self, 'sprite_manager'):
                sprite_name = f"wizard_{facing}_{anim_frame}"
                if sprite_name in self.sprite_manager.sprites:
                    player_sprite = self.sprite_manager.get_sprite(sprite_name)
                else:
                    sprite_name_fallback = f"wizard_{facing}_still"
                    if sprite_name_fallback in self.sprite_manager.sprites:
                        player_sprite = self.sprite_manager.get_sprite(sprite_name_fallback)

            if player_sprite:
                self.screen.blit(player_sprite, (px, py))
            else:
                # Fallback to yellow @ symbol
                pygame.draw.rect(self.screen, COLORS['YELLOW'], (px, py, CELL_SIZE, CELL_SIZE))
                player_text = self.font.render('@', True, COLORS['BLACK'])
                player_rect = player_text.get_rect(center=(px + CELL_SIZE // 2, py + CELL_SIZE // 2))
                self.screen.blit(player_text, player_rect)

            # Draw autopilot indicator
            if self.autopilot:
                auto_text = self.tiny_font.render("AUTO", True, (100, 255, 100))
                self.screen.blit(auto_text, (px - 2, py - 10))

            # Draw attack animations
            self.draw_attack_animations()

            # Draw UI bar at bottom
            ui_y = GRID_HEIGHT * CELL_SIZE
            pygame.draw.rect(self.screen, COLORS['UI_BG'], (0, ui_y, SCREEN_WIDTH, 60))

            info_text = f"HP: {int(self.player['health'])}/{self.player['max_health']} | "
            info_text += f"Magic: {self.player['magic_pool']}/{self.player['max_magic_pool']} | "

            # Show location info
            if self.player.get('in_subscreen'):
                subscreen = self.subscreens.get(self.player['subscreen_key'])
                if subscreen:
                    depth_info = f" (Depth {subscreen['depth']})" if subscreen['type'] == 'CAVE' else ""
                    info_text += f"Location: {subscreen['type']}{depth_info}"
            else:
                info_text += f"Screen: ({self.player['screen_x']}, {self.player['screen_y']}) | "
                info_text += f"Biome: {self.current_screen['biome'] if self.current_screen else 'Unknown'}"

                # Show zone control by faction (majority only)
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                controlling_faction = self.get_zone_controlling_faction(screen_key)
                if controlling_faction:
                    info_text += f" | Controlled by: {controlling_faction}"

            if self.player['blocking']:
                info_text += " | [BLOCKING]"
            if self.player.get('friendly_fire', False):
                info_text += " | [FF ON]"
            text = self.small_font.render(info_text, True, COLORS['WHITE'])
            self.screen.blit(text, (10, ui_y + 5))

            # Draw quest target info on second line
            quest_display = ""
            if self.active_quest and self.active_quest in self.quests:
                quest = self.quests[self.active_quest]
                quest_info = QUEST_TYPES.get(self.active_quest, {})
                quest_name = quest_info.get('name', self.active_quest)
                if quest.status == 'active' and quest.target_info:
                    quest_display = f"Quest [{quest_name}]: {quest.target_info}"
                elif quest.status == 'active':
                    quest_display = f"Quest [{quest_name}]: Tracking..."
                elif quest.status == 'inactive':
                    quest_display = f"Quest [{quest_name}]: Press Q to activate"

            if quest_display:
                quest_color = QUEST_TYPES.get(self.active_quest, {}).get('color', (200, 200, 200))
                quest_text = self.tiny_font.render(quest_display, True, quest_color)
                self.screen.blit(quest_text, (10, ui_y + 22))

            # Show interaction hint based on target cell
            target = self.get_target_cell()
            hint_text = "SPACE: Attack"
            if target and self.current_screen:
                check_x, check_y = target
                cell = self.current_screen['grid'][check_y][check_x]

                if cell == 'STAIRS_UP':
                    hint_text = "SPACE: Exit"
                elif cell == 'STAIRS_DOWN':
                    hint_text = "SPACE: Descend"
                elif cell == 'CHEST':
                    hint_text = "SPACE: Open Chest"
                elif CELL_TYPES.get(cell, {}).get('enterable'):
                    hint_text = "SPACE: Enter"

            controls = f"{hint_text} | B: Block | C: Craft | X: Combine | L: Cast | E: Pickup"
            text = self.tiny_font.render(controls, True, COLORS['WHITE'])
            self.screen.blit(text, (10, ui_y + 42))

            # ── Key reference on right side of bottom bar ──────────────────
            key_ref_x = SCREEN_WIDTH - 340
            key_lines = [
                "WASD/Arrows: Move  SPACE: Interact  ESC: Pause",
                "I/T/M/F: Items/Tools/Magic/Follow  Q: Quests  N: Trade",
                "E: Pickup  P: Place  D: Drop  B: Block  V: FF  C/X: Craft",
            ]
            for i, line in enumerate(key_lines):
                ref_text = self.tiny_font.render(line, True, (160, 160, 170))
                self.screen.blit(ref_text, (key_ref_x, ui_y + 4 + i * 14))

            # Draw rain effect if raining (minimal, just visual indicator)
            if self.is_raining:
                # Draw subtle blue tint overlay
                rain_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 60))
                rain_overlay.set_alpha(60)
                rain_overlay.fill((100, 150, 200))  # Light blue
                self.screen.blit(rain_overlay, (0, 0))

                # Draw "RAIN" indicator in corner
                rain_text = self.small_font.render("🌧 RAIN", True, (150, 200, 255))
                self.screen.blit(rain_text, (SCREEN_WIDTH - 100, 10))

            # Draw night overlay (subtle gray darkness)
            if self.is_night:
                night_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 60))
                night_overlay.set_alpha(NIGHT_OVERLAY_ALPHA)
                night_overlay.fill((40, 40, 50))  # Dark gray-blue
                self.screen.blit(night_overlay, (0, 0))

                # Draw "NIGHT" indicator in corner
                night_text = self.small_font.render("🌙 NIGHT", True, (180, 180, 200))
                self.screen.blit(night_text, (SCREEN_WIDTH - 100, 30))

            # Draw inventory panels
            self.draw_inventory_panels()

            # Draw quest UI if open
            if self.quest_ui_open:
                self.draw_quest_ui()

            # Draw quest arrow if quest is active
            if self.active_quest and self.quests[self.active_quest].status == 'active':
                self.draw_quest_arrow()

            # Draw trader UI if active
            if self.trader_display:
                self.draw_trader_ui()

            # Draw NPC inspection if targeting peaceful NPC
            self.draw_inspected_npc()

            # Draw item list when targeting a cell with dropped items or a chest
            self.draw_targeted_items()
