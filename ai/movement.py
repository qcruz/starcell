"""
NPC AI Movement Mixin
Methods for entity movement, pathfinding, zone transitions, subscreen transitions,
and the memory-lane obstacle-avoidance system.
"""
import random
from data import *
from engine import *


class NpcAiMovementMixin:

    def wander_entity(self, entity):
        """Move entity randomly"""
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Check if overlapping with another entity — if so, prioritize unstacking
        is_overlapping = False
        for other_id in self.screen_entities.get(screen_key, []):
            if other_id in self.entities:
                other = self.entities[other_id]
                if other is not entity and other.x == entity.x and other.y == entity.y:
                    is_overlapping = True
                    break

        # Pick random adjacent cell
        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
        random.shuffle(directions)

        # Flying entities bypass most solid cells
        is_flying = entity.props.get('flying', False)
        fly_blocked = {'WALL', 'CAVE_WALL', 'DEEP_WATER'}

        # Get recent positions from memory lane
        recent_positions = set()
        if hasattr(entity, 'memory_lane'):
            recent_positions = set(entity.memory_lane[-6:])

        moved = False
        for dx, dy in directions:
            new_x = entity.x + dx
            new_y = entity.y + dy

            # Out of bounds → attempt seamless zone crossing
            if new_x < 0 or new_x >= GRID_WIDTH or new_y < 0 or new_y >= GRID_HEIGHT:
                old_sk = f"{entity.screen_x},{entity.screen_y}"
                self.try_entity_screen_crossing(entity, new_x, new_y)
                if f"{entity.screen_x},{entity.screen_y}" != old_sk:
                    entity.is_moving = True
                    entity.moved_this_update = True
                    return
                continue

            # Check memory lane — avoid recently visited cells
            if (new_x, new_y) in recent_positions:
                continue

            # Check walkable (flying entities bypass most solids)
            cell = screen['grid'][new_y][new_x]
            if CELL_TYPES[cell].get('solid', False):
                if not is_flying or cell in fly_blocked:
                    continue

            # Check not occupied (skip this check if overlapping — need to unstack)
            if not is_overlapping:
                occupied = False
                for other_id in self.screen_entities.get(screen_key, []):
                    if other_id in self.entities:
                        other = self.entities[other_id]
                        if other is not entity and other.x == new_x and other.y == new_y:
                            occupied = True
                            break

                if occupied:
                    continue

            # MOVE — record old position in memory lane first
            if hasattr(entity, 'memory_lane'):
                entity.memory_lane.append((entity.x, entity.y))
                if len(entity.memory_lane) > entity.max_memory_length:
                    entity.memory_lane.pop(0)

            entity.x = new_x
            entity.y = new_y
            entity.target_x = new_x
            entity.target_y = new_y
            entity.is_moving = True
            entity.stuck_counter = 0
            entity.moved_this_update = True  # Tell behavior system entity is in motion
            # Update facing
            if dx > 0:
                entity.facing = 'right'
            elif dx < 0:
                entity.facing = 'left'
            elif dy > 0:
                entity.facing = 'down'
            elif dy < 0:
                entity.facing = 'up'
            moved = True
            return  # Successfully moved

        # No valid move found — increment stuck counter and clear memory if needed
        if not hasattr(entity, 'stuck_counter'):
            entity.stuck_counter = 0
        entity.stuck_counter += 1

        # After 3+ failed wander attempts, clear half of memory lane to unstick
        if entity.stuck_counter >= 3:
            if hasattr(entity, 'memory_lane') and entity.memory_lane:
                half = len(entity.memory_lane) // 2
                entity.memory_lane = entity.memory_lane[half:]
            entity.stuck_counter = 0

    def move_toward_position(self, entity, target_x, target_y, screen_key):
        """Move entity one step toward target position with obstacle avoidance.

        Direction priority:
          1. Primary axis (largest distance toward target)
          2. Secondary axis (diagonal toward target)
          3. Perpendicular (obstacle avoidance)
          4. Backward (backtracking — last resort)

        Memory lane prevents revisiting the last 6 positions so the entity
        naturally routes around obstacles.  When stuck for 2+ cycles the
        memory is halved; at 4+ cycles it is cleared entirely so the entity
        can backtrack freely.
        """
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Initialize cell reservation system if not exists
        if not hasattr(self, 'reserved_cells'):
            self.reserved_cells = {}
        if not hasattr(self, 'last_reservation_clear_tick'):
            self.last_reservation_clear_tick = 0
        if self.tick > self.last_reservation_clear_tick:
            self.reserved_cells = {}
            self.last_reservation_clear_tick = self.tick

        # Already at target
        if entity.x == target_x and entity.y == target_y:
            return

        # Calculate direction to target
        dx = target_x - entity.x
        dy = target_y - entity.y

        # Build prioritized list of ALL 4 directions:
        # 1. Primary (toward target on dominant axis)
        # 2. Secondary (toward target on minor axis)
        # 3/4. Perpendicular (randomized to avoid wall-hugging)
        # 5. Backward (away from target — allows backtracking around obstacles)
        candidates = []

        if abs(dx) >= abs(dy):
            primary = (1 if dx > 0 else -1, 0)
            backward = (-1 if dx > 0 else 1, 0)
            secondary = (0, 1 if dy > 0 else -1) if dy != 0 else None
            perp1, perp2 = (0, 1), (0, -1)
        else:
            primary = (0, 1 if dy > 0 else -1)
            backward = (0, -1 if dy > 0 else 1)
            secondary = (1 if dx > 0 else -1, 0) if dx != 0 else None
            perp1, perp2 = (1, 0), (-1, 0)

        candidates.append(primary)
        if secondary:
            candidates.append(secondary)
        # Randomize perpendicular order to avoid always hugging one side
        if random.random() < 0.5:
            candidates.extend([perp1, perp2])
        else:
            candidates.extend([perp2, perp1])
        # Backward direction as last resort (allows routing around large obstacles)
        candidates.append(backward)
        # Deduplicate (secondary may equal a perpendicular)
        seen = set()
        deduped = []
        for c in candidates:
            if c not in seen:
                seen.add(c)
                deduped.append(c)
        candidates = deduped

        # Use memory_lane to avoid revisiting recent positions
        recent_positions = set()
        if hasattr(entity, 'memory_lane'):
            recent_positions = set(entity.memory_lane[-6:])

        # Flying entities can pass over most solid cells (trees, houses) but not walls
        is_flying = entity.props.get('flying', False)
        # Cells that even flying entities can't cross
        fly_blocked = {'WALL', 'CAVE_WALL', 'DEEP_WATER'}

        def try_move(move_x, move_y, skip_memory=False):
            """Attempt to move in a direction. Returns True if successful."""
            new_x = entity.x + move_x
            new_y = entity.y + move_y

            if new_x < 0 or new_x >= GRID_WIDTH or new_y < 0 or new_y >= GRID_HEIGHT:
                # Try seamless zone crossing
                old_sk = f"{entity.screen_x},{entity.screen_y}"
                self.try_entity_screen_crossing(entity, new_x, new_y)
                if f"{entity.screen_x},{entity.screen_y}" != old_sk:
                    entity.moved_this_update = True
                    return True
                return False
            cell = screen['grid'][new_y][new_x]
            if CELL_TYPES[cell].get('solid', False):
                if not is_flying or cell in fly_blocked:
                    return False
            if not skip_memory and (new_x, new_y) in recent_positions and (new_x, new_y) != (target_x, target_y):
                return False
            cell_key = (screen_key, new_x, new_y)
            if cell_key in self.reserved_cells:
                return False
            for other_id in self.screen_entities.get(screen_key, []):
                if other_id in self.entities:
                    other = self.entities[other_id]
                    if other is not entity and other.x == new_x and other.y == new_y:
                        return False

            # Execute move
            self.reserved_cells[cell_key] = True
            if hasattr(entity, 'memory_lane'):
                entity.memory_lane.append((entity.x, entity.y))
                if len(entity.memory_lane) > entity.max_memory_length:
                    entity.memory_lane.pop(0)

            entity.stuck_counter = 0  # Reset stuck counter on successful move
            entity.moved_this_update = True  # Tell behavior system entity is in motion
            entity.x = new_x
            entity.y = new_y
            entity.target_x = new_x
            entity.target_y = new_y
            entity.is_moving = True
            if move_x > 0: entity.facing = 'right'
            elif move_x < 0: entity.facing = 'left'
            elif move_y > 0: entity.facing = 'down'
            elif move_y < 0: entity.facing = 'up'
            return True

        # Try all directions respecting memory lane
        for mx, my in candidates:
            if try_move(mx, my):
                return

        # All directions blocked by memory + obstacles
        if not hasattr(entity, 'stuck_counter'):
            entity.stuck_counter = 0
        entity.stuck_counter += 1

        # Progressive memory clearing:
        #   2 cycles (~1s)  → clear half of memory (try alternate routes)
        #   4 cycles (~2s)  → clear ALL memory (full backtrack allowed)
        #   6 cycles (~3s)  → ignore memory entirely for one move (force unstick)
        if entity.stuck_counter >= 6:
            # Nuclear: try any direction ignoring memory
            for mx, my in candidates:
                if try_move(mx, my, skip_memory=True):
                    entity.stuck_counter = 0
                    return
            # Truly walled in — clear memory and wait
            entity.memory_lane = []
            entity.stuck_counter = 0
        elif entity.stuck_counter >= 4:
            entity.memory_lane = []
        elif entity.stuck_counter >= 2:
            if hasattr(entity, 'memory_lane') and entity.memory_lane:
                half = len(entity.memory_lane) // 2
                entity.memory_lane = entity.memory_lane[half:]

    def _get_exit_toward_zone(self, from_sx, from_sy, to_sx, to_sy):
        """Return the (x, y) grid position of the zone exit closest to a target zone.

        Exit cells are at the actual edge: y=0 (top), y=GRID_HEIGHT-1 (bottom),
        x=0 (left), x=GRID_WIDTH-1 (right), centered on the 2-tile corridor.
        """
        zone_dx = to_sx - from_sx
        zone_dy = to_sy - from_sy

        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2

        if abs(zone_dx) >= abs(zone_dy) and zone_dx != 0:
            # Horizontal — aim for left/right edge
            exit_x = (GRID_WIDTH - 1) if zone_dx > 0 else 0
            exit_y = center_y
        else:
            # Vertical — aim for top/bottom edge
            exit_y = (GRID_HEIGHT - 1) if zone_dy > 0 else 0
            exit_x = center_x

        return exit_x, exit_y

    def _try_targeting_zone_cross(self, entity, entity_id):
        """If the entity is at a zone exit, attempt to transition to the next zone.

        Called after a targeting-mode move so entities naturally flow through
        zone boundaries when pursuing a cross-zone target.
        """
        at_exit, _ = self.is_at_exit(entity.x, entity.y)
        if at_exit:
            # Check cooldown
            ticks_since = self.tick - getattr(entity, 'last_zone_change_tick', -9999)
            if ticks_since >= ZONE_CHANGE_COOLDOWN:
                old_zone = f"{entity.screen_x},{entity.screen_y}"
                self.try_entity_zone_transition(entity_id, entity)
                new_zone = f"{entity.screen_x},{entity.screen_y}"
                if old_zone != new_zone:
                    entity.last_zone_change_tick = self.tick
                    entity.memory_lane = []  # Clear memory for fresh zone

    def try_entity_zone_transition(self, entity_id, entity):
        """Attempt to move entity to adjacent zone ONLY through actual entrances"""
        screen_key = f"{entity.screen_x},{entity.screen_y}"

        if screen_key not in self.screens:
            return

        # Check travel cooldown - prevent rapid zone switching
        if not hasattr(entity, 'last_zone_change_tick'):
            entity.last_zone_change_tick = -999  # Initialize if missing

        ticks_since_travel = self.tick - entity.last_zone_change_tick
        if ticks_since_travel < ZONE_CHANGE_COOLDOWN:
            # Too soon since last travel - prevent zone change
            return

        screen = self.screens[screen_key]
        exits = screen['exits']

        # Center coordinates for entrance locations
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2

        transition_target = None
        new_position = None
        exit_cells = []  # Track exit cells to add to memory

        # Top entrance - must be within 1 cell of center exit
        if (exits['top'] and entity.y <= 1 and
            abs(entity.x - center_x) <= 1):  # Must be at center ±1 cell
            transition_target = (entity.screen_x, entity.screen_y - 1)
            new_position = (entity.x, GRID_HEIGHT - 3)
            # Mark cells near top exit
            exit_cells = [(center_x + dx, 0) for dx in range(-2, 3)]
            exit_cells.extend([(center_x + dx, 1) for dx in range(-2, 3)])

        # Bottom entrance - must be within 1 cell of center exit
        elif (exits['bottom'] and entity.y >= GRID_HEIGHT - 2 and
              abs(entity.x - center_x) <= 1):
            transition_target = (entity.screen_x, entity.screen_y + 1)
            new_position = (entity.x, 2)
            # Mark cells near bottom exit
            exit_cells = [(center_x + dx, GRID_HEIGHT - 1) for dx in range(-2, 3)]
            exit_cells.extend([(center_x + dx, GRID_HEIGHT - 2) for dx in range(-2, 3)])

        # Left entrance - must be within 1 cell of center exit
        elif (exits['left'] and entity.x <= 1 and
              abs(entity.y - center_y) <= 1):
            transition_target = (entity.screen_x - 1, entity.screen_y)
            new_position = (GRID_WIDTH - 3, entity.y)
            # Mark cells near left exit
            exit_cells = [(0, center_y + dy) for dy in range(-2, 3)]
            exit_cells.extend([(1, center_y + dy) for dy in range(-2, 3)])

        # Right entrance - must be within 1 cell of center exit
        elif (exits['right'] and entity.x >= GRID_WIDTH - 2 and
              abs(entity.y - center_y) <= 1):
            transition_target = (entity.screen_x + 1, entity.screen_y)
            new_position = (2, entity.y)
            # Mark cells near right exit
            exit_cells = [(GRID_WIDTH - 1, center_y + dy) for dy in range(-2, 3)]
            exit_cells.extend([(GRID_WIDTH - 2, center_y + dy) for dy in range(-2, 3)])

        if transition_target and new_position:
            new_screen_x, new_screen_y = transition_target
            new_x, new_y = new_position
            new_screen_key = f"{new_screen_x},{new_screen_y}"

            # Generate target screen if it doesn't exist
            if new_screen_key not in self.screens:
                self.generate_screen(new_screen_x, new_screen_y)

            # Check if destination is valid
            if new_screen_key in self.screens:
                target_screen = self.screens[new_screen_key]
                target_cell = target_screen['grid'][new_y][new_x]

                if not CELL_TYPES[target_cell].get('solid', False):
                    # Remove from old screen
                    if screen_key in self.screen_entities:
                        if entity_id in self.screen_entities[screen_key]:
                            self.screen_entities[screen_key].remove(entity_id)

                    # Update entity position
                    entity.screen_x = new_screen_x
                    entity.screen_y = new_screen_y
                    entity.x = new_x
                    entity.y = new_y
                    entity.world_x = float(new_x)
                    entity.world_y = float(new_y)

                    # Update travel cooldown
                    entity.last_zone_change_tick = self.tick

                    # Add exit cells to memory lane to prevent immediate return
                    if not hasattr(entity, 'memory_lane'):
                        entity.memory_lane = []
                    for cell in exit_cells:
                        if len(entity.memory_lane) < entity.max_memory_length:
                            entity.memory_lane.append(cell)

                    # Add to new screen
                    if new_screen_key not in self.screen_entities:
                        self.screen_entities[new_screen_key] = []
                    self.screen_entities[new_screen_key].append(entity_id)

    def try_entity_screen_crossing(self, entity, new_x, new_y):
        """Seamlessly transition entity to adjacent zone when they walk through an exit corridor.

        Only triggers at the existing 2-tile-wide exit corridors (center of each edge),
        matching the same corridor geometry used by try_entity_zone_transition.
        """
        # Anti-bounce: prevent an immediate return trip
        if self.tick - getattr(entity, 'last_zone_change_tick', -9999) < NPC_SEAMLESS_CROSS_COOLDOWN:
            return

        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        new_screen_x = entity.screen_x
        new_screen_y = entity.screen_y
        facing_after = entity.facing

        # Verify entity is in the exit corridor for the direction they're stepping.
        # Corridor geometry mirrors is_at_exit(): 2-tile span at each edge center.
        if new_y < 0:
            if not screen['exits']['top'] or not (center_x - 1 <= entity.x <= center_x):
                return
            new_screen_y -= 1
            new_y = GRID_HEIGHT - 2
            facing_after = 'up'
        elif new_y >= GRID_HEIGHT:
            if not screen['exits']['bottom'] or not (center_x - 1 <= entity.x <= center_x):
                return
            new_screen_y += 1
            new_y = 1
            facing_after = 'down'
        elif new_x < 0:
            if not screen['exits']['left'] or not (center_y - 1 <= entity.y <= center_y):
                return
            new_screen_x -= 1
            new_x = GRID_WIDTH - 2
            facing_after = 'left'
        elif new_x >= GRID_WIDTH:
            if not screen['exits']['right'] or not (center_y - 1 <= entity.y <= center_y):
                return
            new_screen_x += 1
            new_x = 1
            facing_after = 'right'
        else:
            return

        # Generate target zone if not yet visited
        new_screen_key = f"{new_screen_x},{new_screen_y}"
        if new_screen_key not in self.screens:
            self.generate_screen(new_screen_x, new_screen_y)
        if new_screen_key not in self.screens:
            return

        # Destination must be walkable
        if CELL_TYPES.get(self.screens[new_screen_key]['grid'][new_y][new_x], {}).get('solid', False):
            return

        # Population cap
        if new_screen_key not in self.screen_entities:
            self.screen_entities[new_screen_key] = []
        if len(self.screen_entities[new_screen_key]) > 15:
            if not self.try_merge_entity(entity, new_screen_key):
                return

        # Locate entity_id
        entity_id = next((eid for eid, e in self.entities.items() if e is entity), None)
        if entity_id is None:
            return

        # Transfer between screen entity lists
        old_sk = entity.screen_key
        if old_sk in self.screen_entities and entity_id in self.screen_entities[old_sk]:
            self.screen_entities[old_sk].remove(entity_id)
        self.screen_entities[new_screen_key].append(entity_id)

        # Update entity state
        entity.x = new_x
        entity.y = new_y
        entity.target_x = new_x
        entity.target_y = new_y
        entity.world_x = float(new_x)
        entity.world_y = float(new_y)
        entity.screen_x = new_screen_x
        entity.screen_y = new_screen_y
        entity.facing = facing_after
        entity.last_zone_change_tick = self.tick
        entity.is_moving = True
        if hasattr(entity, 'memory_lane'):
            entity.memory_lane = []

    def move_entity_towards(self, entity, target_x, target_y):
        """Move entity one step towards target using memory_lane pathfinding"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Stuck target detection - track if entity has same target for too long
        current_target = (target_x, target_y)
        if entity.last_target_position == current_target:
            entity.target_stuck_counter += 1

            # If stuck on same target for too long, add to memory and clear target
            if entity.target_stuck_counter >= TARGET_STUCK_THRESHOLD:
                # Don't blacklist zone exit cells — entity needs to reach them
                is_exit_cell, _ = self.is_at_exit(current_target[0], current_target[1])
                if is_exit_cell:
                    # Clear memory instead to give fresh approach
                    entity.memory_lane = []
                    entity.target_stuck_counter = 0
                    return

                # Add stuck target to memory lane to avoid it
                if current_target not in entity.memory_lane:
                    entity.memory_lane.append(current_target)

                # Clear target-related attributes to force new target selection
                if hasattr(entity, 'target_exit'):
                    entity.target_exit = None
                if hasattr(entity, 'patrol_target'):
                    entity.patrol_target = None

                # Reset counter
                entity.target_stuck_counter = 0
                entity.last_target_position = None

                print(f"{entity.type} stuck on target {current_target}, added to memory and selecting new target")
                return
        else:
            # Target changed - reset counter
            entity.target_stuck_counter = 0
            entity.last_target_position = current_target

        # Rate limit: entities can only move once per 5 ticks minimum
        if not hasattr(entity, 'last_move_tick'):
            entity.last_move_tick = 0

        if self.tick - entity.last_move_tick < 5:
            return  # Too soon to move again

        # Add current position to memory
        current_pos = (entity.x, entity.y)
        if not entity.memory_lane or entity.memory_lane[-1] != current_pos:
            entity.memory_lane.append(current_pos)

        # Detect if stuck in a loop (same position appearing multiple times recently)
        if len(entity.memory_lane) >= 6:
            recent_positions = entity.memory_lane[-6:]
            if recent_positions.count(current_pos) >= 3:
                # Stuck in a loop! Clear all memory and try fresh
                entity.memory_lane = [current_pos]

        # Trim memory to 10 cells (adjustable for NPC intelligence)
        max_memory = getattr(entity, 'max_memory_length', 10)
        if len(entity.memory_lane) > max_memory:
            entity.memory_lane.pop(0)

        # Calculate best move (closest to target, not in memory)
        best_move = None
        best_dist = float('inf')

        # Try all 4 directions
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:  # up, down, left, right
            new_x = entity.x + dx
            new_y = entity.y + dy

            # Check bounds
            if new_x < 0 or new_x >= GRID_WIDTH or new_y < 0 or new_y >= GRID_HEIGHT:
                continue

            # Skip if in recent memory (already visited recently) — only check last 6
            # to match move_toward_position behavior; checking the full lane causes
            # permanent stalls in confined areas like farms
            recent_positions = set(entity.memory_lane[-6:]) if entity.memory_lane else set()
            if (new_x, new_y) in recent_positions:
                continue

            # Check if walkable
            cell = screen['grid'][new_y][new_x]
            if CELL_TYPES[cell]['solid']:
                continue

            # Check if player is there
            if (new_x == self.player['x'] and new_y == self.player['y'] and
                entity.screen_x == self.player['screen_x'] and
                entity.screen_y == self.player['screen_y']):
                continue

            # Check if another entity is at this position (entity collision)
            if self.is_entity_at_position(new_x, new_y, screen_key, exclude_entity=entity):
                continue

            # Calculate distance to target
            dist = abs(new_x - target_x) + abs(new_y - target_y)
            if dist < best_dist:
                best_dist = dist
                best_move = (new_x, new_y)

        # If no valid move found (trapped), clear memory more aggressively
        if best_move is None:
            entity.stuck_counter += 1

            # If stuck for 5+ ticks, force a random move to break free
            if entity.stuck_counter >= 5:
                # Try to move in any random valid direction, ignoring memory
                random_dirs = [(0, -1), (0, 1), (-1, 0), (1, 0)]
                random.shuffle(random_dirs)

                for dx, dy in random_dirs:
                    new_x = entity.x + dx
                    new_y = entity.y + dy

                    if (0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT):
                        cell = screen['grid'][new_y][new_x]
                        if not CELL_TYPES[cell]['solid']:
                            # Valid move found - set as target for smooth movement
                            entity.target_x = new_x
                            entity.target_y = new_y
                            entity.stuck_counter = 0
                            entity.memory_lane = [(new_x, new_y)]  # Clear memory

                            # Crop trampling on stuck movement too (2% chance)
                            if cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                                if random.random() < 0.02:  # 2% chance
                                    screen['grid'][new_y][new_x] = 'DIRT'
                            return

                # Still couldn't move - clear memory and reset counter
                entity.memory_lane = [current_pos]
                entity.stuck_counter = 0
                return

            # Not stuck long enough yet - clear memory progressively
            if len(entity.memory_lane) > 3:
                # Clear half of memory
                entity.memory_lane = entity.memory_lane[len(entity.memory_lane)//2:]
            elif len(entity.memory_lane) > 1:
                # Clear oldest memory
                entity.memory_lane.pop(0)
            return

        # Make the move - validate it's only a single cell in cardinal direction
        if best_move:
            new_x, new_y = best_move

            # SAFETY CHECK: Ensure only single-cell cardinal movement
            dx = new_x - entity.x
            dy = new_y - entity.y

            # Only allow moves that are exactly 1 cell in one direction
            if abs(dx) + abs(dy) == 1:  # Manhattan distance = 1 (cardinal move)
                # FINAL SAFETY CHECK: Ensure destination is not solid
                final_cell = screen['grid'][new_y][new_x]
                if not CELL_TYPES[final_cell]['solid']:
                    # Set as target for smooth movement system
                    entity.target_x = new_x
                    entity.target_y = new_y
                    entity.stuck_counter = 0  # Reset stuck counter on successful move
                    entity.last_move_tick = self.tick  # Record when we moved

                    # Crop trampling - 2% chance to trample crops when walked on
                    if final_cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                        if random.random() < 0.02:  # 2% chance
                            screen['grid'][new_y][new_x] = 'DIRT'
                else:
                    # Target became solid - don't move
                    entity.stuck_counter += 1
            else:
                # Invalid move detected - don't execute it
                print(f"WARNING: Blocked invalid move for {entity.type}: ({entity.x},{entity.y}) -> ({new_x},{new_y})")
                entity.stuck_counter += 1

    def seek_zone_exit(self, entity, entity_id=None):
        """Make entity move towards nearest zone exit"""
        screen_key = f"{entity.screen_x},{entity.screen_y}"

        # Warriors with factions: check for coordinated expansion
        target_direction = None
        if entity.type == 'WARRIOR' and entity.faction:
            expansion_target = self.get_faction_exploration_target(screen_key, entity.faction)
            if expansion_target:
                target_zone_x, target_zone_y, target_direction = expansion_target

        # Find nearest exit (middle of edges)
        exits = [
            (GRID_WIDTH // 2, 0, 'top'),
            (GRID_WIDTH // 2, GRID_HEIGHT - 1, 'bottom'),
            (0, GRID_HEIGHT // 2, 'left'),
            (GRID_WIDTH - 1, GRID_HEIGHT // 2, 'right')
        ]

        # If warrior has a faction target direction, use that exit
        if target_direction:
            target_exit = None
            for exit_x, exit_y, direction in exits:
                if direction == target_direction:
                    target_exit = (exit_x, exit_y)
                    break

            if target_exit:
                closest_exit = target_exit
            else:
                # Fallback to nearest
                closest_exit = None
                closest_dist = float('inf')
                for exit_x, exit_y, direction in exits:
                    dist = abs(entity.x - exit_x) + abs(entity.y - exit_y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_exit = (exit_x, exit_y)
        else:
            # Normal behavior - find nearest exit
            closest_exit = None
            closest_dist = float('inf')

            for exit_x, exit_y, direction in exits:
                dist = abs(entity.x - exit_x) + abs(entity.y - exit_y)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_exit = (exit_x, exit_y)

        if closest_exit:
            # Move towards exit with urgency (triple speed since desperate)
            for _ in range(3):
                self.move_entity_towards(entity, closest_exit[0], closest_exit[1])
                # Check if reached exit (at edge)
                if (entity.x <= 1 or entity.x >= GRID_WIDTH - 2 or
                    entity.y <= 1 or entity.y >= GRID_HEIGHT - 2):
                    # At edge, try to transition
                    self.try_entity_zone_transition(entity_id, entity)
                    break

    def npc_enter_subscreen(self, entity, screen_key, entrance_x, entrance_y, entrance_type):
        """Move NPC into subscreen"""
        entity_id = None
        for eid, e in self.entities.items():
            if e is entity:
                entity_id = eid
                break

        if not entity_id:
            return

        # Check subscreen travel cooldown
        if not hasattr(entity, 'last_subscreen_change_tick'):
            entity.last_subscreen_change_tick = -999

        ticks_since_travel = self.tick - entity.last_subscreen_change_tick
        if ticks_since_travel < ZONE_CHANGE_COOLDOWN:  # Reuse same cooldown
            return

        # Get or create subscreen
        subscreen_type = CELL_TYPES[entrance_type]['subscreen_type']

        if entrance_type == 'CAVE':
            # Use unified cave system
            zone_key = f"{entity.screen_x},{entity.screen_y}"
            if zone_key in self.zone_cave_systems:
                subscreen_key = self.zone_cave_systems[zone_key]
            else:
                # Create new cave system for this zone
                subscreen_key = self.generate_subscreen(entity.screen_x, entity.screen_y, entrance_x, entrance_y, 'CAVE')
                self.zone_cave_systems[zone_key] = subscreen_key
        else:
            # House interior - check if this specific house already has an interior
            temp_key = f"house_{entity.screen_x}_{entity.screen_y}_{entrance_x}_{entrance_y}"

            # Search for existing house interior at this location
            subscreen_key = None
            for key in self.subscreens.keys():
                if temp_key in key or (f"{entity.screen_x},{entity.screen_y}:HOUSE_INTERIOR" in key and
                                       self.subscreens[key].get('entrance_x') == entrance_x and
                                       self.subscreens[key].get('entrance_y') == entrance_y):
                    subscreen_key = key
                    break

            if not subscreen_key:
                # Create new house interior
                subscreen_key = self.generate_subscreen(entity.screen_x, entity.screen_y, entrance_x, entrance_y, 'HOUSE_INTERIOR')
                # Store entrance location for future reference
                if subscreen_key in self.subscreens:
                    self.subscreens[subscreen_key]['entrance_x'] = entrance_x
                    self.subscreens[subscreen_key]['entrance_y'] = entrance_y

        # Move entity into subscreen
        # Remove from overworld entities
        if screen_key in self.screen_entities and entity_id in self.screen_entities[screen_key]:
            self.screen_entities[screen_key].remove(entity_id)

        # Add to subscreen entities
        if subscreen_key not in self.subscreen_entities:
            self.subscreen_entities[subscreen_key] = []
        self.subscreen_entities[subscreen_key].append(entity_id)

        # Update entity state
        entity.in_subscreen = True
        entity.subscreen_key = subscreen_key
        entity.last_subscreen_change_tick = self.tick

        # Add entrance cells to memory lane
        if not hasattr(entity, 'memory_lane'):
            entity.memory_lane = []
        # Mark cells around entrance
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                mem_cell = (entrance_x + dx, entrance_y + dy)
                if len(entity.memory_lane) < entity.max_memory_length:
                    entity.memory_lane.append(mem_cell)

        # Position in subscreen (near entrance)
        entity.x = GRID_WIDTH // 2
        entity.y = GRID_HEIGHT - 2
        entity.world_x = float(entity.x)
        entity.world_y = float(entity.y)

        if entity.name:
            print(f"{entity.name} entered {entrance_type}")

    def npc_exit_subscreen(self, entity):
        """Move NPC back to overworld from subscreen"""
        entity_id = None
        for eid, e in self.entities.items():
            if e is entity:
                entity_id = eid
                break

        if not entity_id:
            return

        # Check subscreen travel cooldown
        if not hasattr(entity, 'last_subscreen_change_tick'):
            entity.last_subscreen_change_tick = -999

        ticks_since_travel = self.tick - entity.last_subscreen_change_tick
        if ticks_since_travel < ZONE_CHANGE_COOLDOWN:  # Reuse same cooldown
            return

        subscreen_key = entity.subscreen_key
        screen_key = f"{entity.screen_x},{entity.screen_y}"

        # Remove from subscreen
        if subscreen_key in self.subscreen_entities and entity_id in self.subscreen_entities[subscreen_key]:
            self.subscreen_entities[subscreen_key].remove(entity_id)

        # Add back to overworld
        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        if entity_id not in self.screen_entities[screen_key]:
            self.screen_entities[screen_key].append(entity_id)

        # Update entity state
        entity.in_subscreen = False
        entity.subscreen_key = None
        entity.last_subscreen_change_tick = self.tick

        # Position near structure (find nearby grass/dirt)
        exit_found = False
        if screen_key in self.screens:
            screen = self.screens[screen_key]
            for dy in range(-2, 3):
                for dx in range(-2, 3):
                    check_x = entity.x + dx
                    check_y = entity.y + dy
                    if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                        cell = screen['grid'][check_y][check_x]
                        if cell in ['GRASS', 'DIRT', 'SAND', 'STONE'] and not CELL_TYPES[cell].get('solid', False):
                            entity.x = check_x
                            entity.y = check_y
                            entity.world_x = float(check_x)
                            entity.world_y = float(check_y)
                            exit_found = True

                            # Add exit area to memory lane
                            if not hasattr(entity, 'memory_lane'):
                                entity.memory_lane = []
                            for mdx in range(-1, 2):
                                for mdy in range(-1, 2):
                                    mem_cell = (check_x + mdx, check_y + mdy)
                                    if len(entity.memory_lane) < entity.max_memory_length:
                                        entity.memory_lane.append(mem_cell)

                            if entity.name:
                                print(f"{entity.name} exited to overworld")
                            return

        # Fallback if no exit found
        if not exit_found:
            entity.world_x = float(entity.x)
            entity.world_y = float(entity.y)

    def update_subscreen_npc_behavior(self, entity_id, entity):
        """Handle NPC behavior when in house/cave subscreens - healing and exit logic"""
        if not entity.in_subscreen or entity.subscreen_key not in self.subscreens:
            return

        subscreen = self.subscreens[entity.subscreen_key]
        subscreen_type = subscreen.get('type', '')

        # HOUSE HEALING LOGIC
        if subscreen_type == 'HOUSE_INTERIOR':
            # Apply accelerated healing in houses
            if entity.health < entity.max_health:
                heal_amount = BASE_HEALING_RATE * HOUSE_HEALING_MULTIPLIER
                entity.health = min(entity.max_health, entity.health + heal_amount)

            # Slowly restore hunger from inventory (if has food)
            if entity.hunger < entity.max_hunger:
                if 'carrot' in entity.inventory and entity.inventory['carrot'] > 0:
                    if random.random() < 0.05:  # 5% chance per update cycle
                        entity.hunger = min(entity.max_hunger, entity.hunger + 20)
                        entity.inventory['carrot'] = max(0, entity.inventory['carrot'] - 1)

            # Check if fully recovered and should exit
            health_full = entity.health >= entity.max_health * 0.95
            hunger_ok = entity.hunger >= entity.max_hunger * 0.7
            thirst_ok = entity.thirst >= entity.max_thirst * 0.7

            if health_full and hunger_ok and thirst_ok:
                # NPC is healthy, time to leave and get back to work
                if random.random() < NPC_SUBSCREEN_EXIT_CHANCE:
                    self.npc_exit_subscreen(entity)

        # CAVE LOGIC (dangerous, no healing)
        elif subscreen_type == 'CAVE':
            # Caves are dangerous - NPCs should flee if injured
            if entity.health < entity.max_health * 0.5:
                # Injured in cave - high chance to flee back to surface
                if random.random() < 0.8:  # 80% chance to exit when injured
                    self.npc_exit_subscreen(entity)

    def move_npc_toward_subscreen_exit(self, entity):
        """Move NPC toward the subscreen exit point (bottom center)"""
        if not entity.in_subscreen or not entity.subscreen_key:
            return

        subscreen_key = entity.subscreen_key
        subscreen = self.subscreens.get(subscreen_key)
        if not subscreen:
            # Also check self.screens for structure zones
            subscreen = self.screens.get(subscreen_key)
        if not subscreen:
            return

        # Exit is at bottom center
        exit_x = GRID_WIDTH // 2
        exit_y = GRID_HEIGHT - 2

        # If already at exit position, try actual exit
        if abs(entity.x - exit_x) <= 1 and entity.y >= exit_y - 1:
            self.try_npc_exit_subscreen(entity)
            return

        # Move toward exit — one step at a time
        dx = exit_x - entity.x
        dy = exit_y - entity.y

        # Prioritize vertical movement (get to bottom first)
        if dy > 0:
            new_y = entity.y + 1
            if 0 <= new_y < GRID_HEIGHT:
                cell = subscreen['grid'][new_y][entity.x]
                if not CELL_TYPES.get(cell, {}).get('solid', False):
                    entity.y = new_y
                    entity.world_y = float(new_y)
                    entity.facing = 'down'
                    return

        # Then horizontal
        if dx != 0:
            step_x = 1 if dx > 0 else -1
            new_x = entity.x + step_x
            if 0 <= new_x < GRID_WIDTH:
                cell = subscreen['grid'][entity.y][new_x]
                if not CELL_TYPES.get(cell, {}).get('solid', False):
                    entity.x = new_x
                    entity.world_x = float(new_x)
                    entity.facing = 'right' if step_x > 0 else 'left'
                    return

    def try_npc_enter_subscreen(self, entity, screen_key):
        """NPC enters subscreen if standing adjacent to entrance (like zone transitions)"""
        # Already in subscreen
        if entity.in_subscreen:
            return

        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Check if standing on or adjacent to an enterable structure
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                check_x = entity.x + dx
                check_y = entity.y + dy

                if not (0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT):
                    continue

                cell = screen['grid'][check_y][check_x]

                # Check if enterable
                if cell not in CELL_TYPES or not CELL_TYPES[cell].get('enterable', False):
                    continue

                # Calculate distance to entrance
                dist = abs(dx) + abs(dy)

                # Must be standing on it or immediately adjacent (like zone transitions)
                if dist <= 1:
                    # Peaceful NPCs can enter houses, miners/hostiles can enter caves
                    peaceful_types = ['FARMER', 'TRADER', 'LUMBERJACK', 'MINER', 'GUARD', 'WARRIOR', 'BLACKSMITH']

                    if cell == 'HOUSE' and entity.type in peaceful_types and not entity.props.get('hostile', False):
                        # Small chance to actually enter when adjacent (10%)
                        if random.random() < 0.1:
                            self.npc_enter_subscreen(entity, screen_key, check_x, check_y, cell)
                            return
                    elif cell == 'CAVE' and (entity.type == 'MINER' or entity.props.get('hostile', False)):
                        # Small chance to actually enter when adjacent (10%)
                        if random.random() < 0.1:
                            self.npc_enter_subscreen(entity, screen_key, check_x, check_y, cell)
                            return

    def try_npc_exit_subscreen(self, entity):
        """NPC tries to exit subscreen back to overworld"""
        if not entity.in_subscreen:
            return

        subscreen_key = entity.subscreen_key
        subscreen = self.subscreens.get(subscreen_key)
        if not subscreen:
            subscreen = self.screens.get(subscreen_key)
        if not subscreen:
            return

        # Find exit (bottom row — any non-solid, non-wall cell)
        exit_positions = []
        for x in range(GRID_WIDTH):
            cell = subscreen['grid'][GRID_HEIGHT - 1][x]
            if not CELL_TYPES.get(cell, {}).get('solid', False):
                exit_positions.append(x)

        # Also check second-to-bottom row if bottom is all walls
        if not exit_positions:
            for x in range(GRID_WIDTH):
                cell = subscreen['grid'][GRID_HEIGHT - 2][x]
                if not CELL_TYPES.get(cell, {}).get('solid', False):
                    exit_positions.append(x)

        if not exit_positions:
            return

        # Move to nearest exit
        nearest_exit = min(exit_positions, key=lambda x: abs(x - entity.x))

        # Check if at exit
        if entity.y == GRID_HEIGHT - 1 and entity.x == nearest_exit:
            self.npc_exit_subscreen(entity)
        else:
            # Move toward exit
            if entity.x < nearest_exit:
                entity.x += 1
            elif entity.x > nearest_exit:
                entity.x -= 1
            elif entity.y < GRID_HEIGHT - 1:
                entity.y += 1

    def try_travel_behavior(self, entity, screen_key):
        """Move entity toward zone exit (used by traders and other traveling NPCs)"""
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]

        # Pick a random exit to travel toward
        if not hasattr(entity, 'travel_target') or entity.travel_target is None:
            exits = []
            if screen['exits']['top']:
                exits.append((GRID_WIDTH // 2, 1))
            if screen['exits']['bottom']:
                exits.append((GRID_WIDTH // 2, GRID_HEIGHT - 2))
            if screen['exits']['left']:
                exits.append((1, GRID_HEIGHT // 2))
            if screen['exits']['right']:
                exits.append((GRID_WIDTH - 2, GRID_HEIGHT // 2))
            if exits:
                entity.travel_target = random.choice(exits)

        if entity.travel_target:
            tx, ty = entity.travel_target
            dist = abs(entity.x - tx) + abs(entity.y - ty)
            if dist <= 1:
                entity.travel_target = None
            else:
                self.move_entity_towards(entity, tx, ty)

    def try_patrol_behavior(self, entity, screen_key):
        """Guard patrol behavior - patrol center lanes"""
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2

        # Pick patrol target if not set
        if not hasattr(entity, 'patrol_target') or entity.patrol_target is None:
            # Patrol in center lanes (vertical or horizontal)
            if random.random() < 0.5:
                # Vertical patrol
                entity.patrol_target = (center_x + random.choice([-1, 0, 1]), random.randint(2, GRID_HEIGHT - 3))
            else:
                # Horizontal patrol
                entity.patrol_target = (random.randint(2, GRID_WIDTH - 3), center_y + random.choice([-1, 0, 1]))

        # Move toward patrol target
        target_x, target_y = entity.patrol_target
        self.move_entity_towards(entity, target_x, target_y)

        # Clear target if reached
        if entity.x == target_x and entity.y == target_y:
            entity.patrol_target = None

    def try_merge_entity(self, entity, screen_key):
        """Try to merge entity with similar entity on screen"""
        for other_id in self.screen_entities.get(screen_key, []):
            # Safety check for None or invalid entity_id
            if other_id is None or other_id not in self.entities:
                continue

            other = self.entities[other_id]

            if entity.can_merge_with(other):
                # Merge into other
                other.merge_with(entity)

                # Remove this entity (it was merged)
                # Find entity_id
                for eid, e in self.entities.items():
                    if e == entity:
                        del self.entities[eid]
                        break

                return True

        return False

    def try_split_double_entity(self, entity_id, entity, screen_key):
        """Split a _double entity back into two singles when zone population is low.

        Returns True if the entity was split (caller should not update it further
        this tick, since the original entity has been modified in-place).
        """
        if not entity.type.endswith('_double'):
            return False

        # Only split when zone has very few entities
        zone_count = len(self.screen_entities.get(screen_key, []))
        SPLIT_POPULATION_THRESHOLD = 3
        if zone_count > SPLIT_POPULATION_THRESHOLD:
            return False

        if random.random() > 0.05:  # 5% chance per update
            return False

        base_type = entity.type.replace('_double', '')

        # Revert this entity to single type
        entity.type = base_type

        # Spawn a second single entity nearby
        from entity import Entity as _Entity
        offset_x = entity.x + random.choice([-1, 1])
        offset_y = entity.y + random.choice([-1, 1])
        offset_x = max(1, min(GRID_WIDTH - 2, offset_x))
        offset_y = max(1, min(GRID_HEIGHT - 2, offset_y))

        new_entity = _Entity(base_type, offset_x, offset_y,
                             entity.screen_x, entity.screen_y,
                             level=max(1, entity.level - 1))

        new_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[new_id] = new_entity

        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(new_id)

        print(f"[Split] {base_type}_double split into two {base_type}s at zone {screen_key}")
        return True

    def teleport_follower_to_player(self, entity_id, entity):
        """Teleport a follower entity to the player's current screen"""
        player_screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        old_screen_key = f"{entity.screen_x},{entity.screen_y}"

        # Remove from old screen
        if old_screen_key in self.screen_entities and entity_id in self.screen_entities[old_screen_key]:
            self.screen_entities[old_screen_key].remove(entity_id)

        # Add to player's screen
        if player_screen_key not in self.screen_entities:
            self.screen_entities[player_screen_key] = []
        if entity_id not in self.screen_entities[player_screen_key]:
            self.screen_entities[player_screen_key].append(entity_id)

        # Update entity position to near player
        entity.screen_x = self.player['screen_x']
        entity.screen_y = self.player['screen_y']
        entity.x = self.player['x']
        entity.y = self.player['y']
        entity.world_x = float(entity.x)
        entity.world_y = float(entity.y)

    def find_closest_food_source(self, entity, screen_key):
        """Find closest food (cell or entity)"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        closest = None
        closest_dist = float('inf')

        # Get food sources from props
        food_sources = entity.props.get('food_sources', [])
        if not food_sources:
            return None

        # Check food cells
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in food_sources:
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, cell)

        # Check edible entities
        if screen_key in self.screen_entities:
            for other_id in self.screen_entities[screen_key]:
                if other_id not in self.entities:
                    continue
                other = self.entities[other_id]
                if other.type in food_sources:
                    dist = abs(other.x - entity.x) + abs(other.y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('entity', other_id)

        return closest

    def find_closest_water_source(self, entity, screen_key):
        """Find closest water cell"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        closest = None
        closest_dist = float('inf')

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if screen['grid'][y][x] == 'WATER':
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, 'WATER')

        return closest

    def find_closest_resource(self, entity, screen_key):
        """Find closest resource (trees, rocks)"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        closest = None
        closest_dist = float('inf')

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in ['TREE1', 'TREE2', 'STONE']:
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, cell)

        return closest

    def find_closest_structure(self, entity, screen_key):
        """Find closest structure"""
        if screen_key not in self.screens:
            return None

        screen = self.screens[screen_key]
        closest = None
        closest_dist = float('inf')

        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in ['HOUSE', 'CAMP', 'FORGE']:
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, cell)

        return closest

    def find_closest_hostile_entity(self, entity, screen_key):
        """Find closest hostile or enemy faction entity"""
        if screen_key not in self.screen_entities:
            return None

        debug = False

        entity_is_hostile = entity.props.get('hostile', False)

        closest = None
        closest_dist = float('inf')

        # Check if the PLAYER is a valid target (hostile entities target player)
        if entity_is_hostile:
            player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
            if screen_key == player_zone and not self.player.get('in_subscreen'):
                player_dist = abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])
                if player_dist < closest_dist:
                    closest_dist = player_dist
                    closest = 'player'

        for other_id in self.screen_entities[screen_key]:
            if other_id not in self.entities:
                continue
            other = self.entities[other_id]

            # Skip self and dead
            if other is entity or not other.is_alive():
                continue

            other_is_hostile = other.props.get('hostile', False)

            # Check if hostile to us
            is_enemy = False
            if entity_is_hostile:
                # Hostile entities attack everyone: non-hostiles AND different hostile species
                if not other_is_hostile:
                    is_enemy = True
                elif other.type != entity.type:
                    is_enemy = True  # Different hostile species fight each other
            elif other_is_hostile:
                # Non-hostile entity sees hostile
                is_enemy = True
            elif (not entity_is_hostile and not other_is_hostile and
                  hasattr(entity, 'faction') and hasattr(other, 'faction') and
                  entity.faction and other.faction and entity.faction != other.faction):
                # Faction-based hostile — only between non-hostile entities
                is_enemy = True

            if is_enemy:
                dist = abs(entity.x - other.x) + abs(entity.y - other.y)
                if dist < closest_dist:
                    closest_dist = dist
                    closest = other_id

        if debug:
            print(f"  [FIND_HOSTILE] Result: {closest}")

        return closest

    def _is_hostile_target(self, entity, target):
        """Check if a target (entity ID, 'player', or tuple) represents a hostile/enemy entity"""
        if target == 'player':
            return entity.props.get('hostile', False)
        if isinstance(target, int) and target in self.entities:
            other = self.entities[target]
            if other is entity:
                return False
            entity_hostile = entity.props.get('hostile', False)
            other_hostile = other.props.get('hostile', False)
            # Hostile vs non-hostile (either direction)
            if entity_hostile and not other_hostile:
                return True
            if not entity_hostile and other_hostile:
                return True
            # Hostile vs different hostile species
            if entity_hostile and other_hostile and other.type != entity.type:
                return True
            # Faction-based hostile (enemy warriors)
            if (not entity_hostile and not other_hostile and
                hasattr(entity, 'faction') and hasattr(other, 'faction') and
                entity.faction and other.faction and entity.faction != other.faction):
                return True
        return False

    def get_target_distance(self, entity, target):
        """Get distance to target"""
        if not target:
            return float('inf')

        if target == 'player':
            player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
            entity_zone = f"{entity.screen_x},{entity.screen_y}"
            if player_zone != entity_zone or self.player.get('in_subscreen'):
                return float('inf')
            return abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])

        if isinstance(target, int):
            # Entity target
            if target not in self.entities:
                return float('inf')
            other = self.entities[target]
            return abs(entity.x - other.x) + abs(entity.y - other.y)
        elif isinstance(target, tuple):
            # Cell target (type, x, y, ...) or raw coords (x, y)
            if len(target) >= 3 and target[0] in ['cell', 'entity']:
                tx, ty = target[1], target[2]
                return abs(entity.x - tx) + abs(entity.y - ty)
            elif len(target) >= 2 and isinstance(target[0], (int, float)):
                # Raw (x, y) tuple
                return abs(entity.x - target[0]) + abs(entity.y - target[1])

        return float('inf')

    def find_and_move_to_food(self, entity):
        """Find food and move towards it"""
        food_sources = entity.props.get('food_sources', [])
        if not food_sources:
            return

        # Get screen_key from entity
        screen_key = f"{entity.screen_x},{entity.screen_y}"

        # Check for food cells nearby
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        closest_food = None
        closest_food_type = None  # Track what type of food it is
        closest_dist = float('inf')

        # Look for food cells
        for food_type in food_sources:
            if food_type in CELL_TYPES:  # It's a cell type
                for y in range(GRID_HEIGHT):
                    for x in range(GRID_WIDTH):
                        if screen['grid'][y][x] == food_type:
                            dist = abs(x - entity.x) + abs(y - entity.y)
                            if dist < closest_dist:
                                closest_dist = dist
                                closest_food = (x, y)
                                closest_food_type = ('cell', food_type)
            else:  # It's an entity type (e.g., SHEEP for wolves)
                for other_id in self.screen_entities.get(screen_key, []):
                    # Safety check for None or invalid entity_id
                    if other_id is None or other_id not in self.entities:
                        continue

                    other = self.entities[other_id]
                    if other.type == food_type and other.is_alive():
                        dist = abs(other.x - entity.x) + abs(other.y - entity.y)
                        if dist < closest_dist:
                            closest_dist = dist
                            closest_food = (other.x, other.y)
                            closest_food_type = ('entity', other_id)

        # If no food found in zone, seek exit to travel
        if closest_food is None:
            entity.no_food_in_zone = True
            self.seek_zone_exit(entity)
            return
        else:
            entity.no_food_in_zone = False

        if closest_food:
            # Urgency-based movement: move multiple steps if health is low
            low_health = entity.health < entity.max_health * 0.5
            critical_health = entity.health < entity.max_health * 0.3

            move_steps = 1
            if critical_health:
                move_steps = 3  # Move 3 cells per update when critical
            elif low_health:
                move_steps = 2  # Move 2 cells per update when low health

            # Move multiple steps towards food
            for _ in range(move_steps):
                self.move_entity_towards(entity, closest_food[0], closest_food[1])
                # Recalculate distance after each move
                closest_dist = abs(entity.x - closest_food[0]) + abs(entity.y - closest_food[1])
                if closest_dist <= 1:
                    break

            # Eat if adjacent
            if closest_dist <= 1:
                food_category, food_identifier = closest_food_type

                if food_category == 'cell':
                    # Eating a cell (grass, crops, etc.)
                    food_x, food_y = closest_food[0], closest_food[1]
                    food_cell = food_identifier

                    # Different food values for different cell sources
                    if food_cell.startswith('CARROT'):
                        food_value = 40  # Crops are nutritious
                    elif food_cell == 'GRASS':
                        food_value = 20  # Grass is less filling
                    else:
                        food_value = 30  # Default

                    entity.eat(food_value)

                    # Consume the food cell (and not enchanted)
                    if not self.is_cell_enchanted(food_x, food_y, screen_key):
                        if screen['grid'][food_y][food_x].startswith('CARROT'):
                            # Carrots decay to DIRT when eaten
                            if random.random() < GRASS_DECAY_ON_EAT:  # Use same rate as grass
                                screen['grid'][food_y][food_x] = 'DIRT'
                            else:
                                screen['grid'][food_y][food_x] = 'SOIL'
                        elif screen['grid'][food_y][food_x] == 'GRASS':
                            if random.random() < GRASS_DECAY_ON_EAT:  # Now 60% chance
                                screen['grid'][food_y][food_x] = 'DIRT'

                elif food_category == 'entity':
                    # Eating another entity (predator behavior)
                    prey_id = food_identifier
                    if prey_id in self.entities:
                        prey = self.entities[prey_id]

                        # Kill and consume the prey
                        food_value = 50  # Meat is very filling
                        entity.eat(food_value)

                        # Kill the prey
                        prey.health = 0
                        # The prey will be removed in the next update cycle

    def find_and_move_to_water(self, entity):
        """Find water and move towards it"""
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        closest_water = None
        closest_dist = float('inf')

        # Look for water cells
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if screen['grid'][y][x] == 'WATER':
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest_water = (x, y)

        # If no water found in zone, seek exit to travel
        if closest_water is None:
            entity.no_food_in_zone = True  # Use same flag
            self.seek_zone_exit(entity)
            return
        else:
            entity.no_food_in_zone = False

        if closest_water:
            # Urgency-based movement: move multiple steps if health is low
            low_health = entity.health < entity.max_health * 0.5
            critical_health = entity.health < entity.max_health * 0.3

            move_steps = 1
            if critical_health:
                move_steps = 3  # Move 3 cells per update when critical
            elif low_health:
                move_steps = 2  # Move 2 cells per update when low health

            # Move multiple steps towards water
            for _ in range(move_steps):
                self.move_entity_towards(entity, closest_water[0], closest_water[1])
                # Recalculate distance after each move
                closest_dist = abs(entity.x - closest_water[0]) + abs(entity.y - closest_water[1])
                if closest_dist <= 1:
                    break

            # Drink if adjacent
            if closest_dist <= 1:
                entity.drink()
                # Water has chance to decay to dirt when drunk
                water_x, water_y = closest_water[0], closest_water[1]
                if not self.is_cell_enchanted(water_x, water_y, screen_key):
                    if random.random() < WATER_DECAY_ON_DRINK:  # 20% chance to decay
                        screen['grid'][water_y][water_x] = 'DIRT'

    def find_nearest_hostile_in_range(self, entity, max_range):
        """Find nearest hostile entity within range"""
        nearest = None
        min_dist = float('inf')

        for eid, other in self.entities.items():
            if eid == entity:
                continue
            if not hasattr(other, 'health') or other.health <= 0:
                continue
            other_config = ENTITY_TYPES.get(other.type.replace('_double', ''), {})
            if not other_config.get('hostile', False):
                continue
            if other.screen_x != entity.screen_x or other.screen_y != entity.screen_y:
                continue

            dist = abs(other.x - entity.x) + abs(other.y - entity.y)
            if dist <= max_range and dist < min_dist:
                min_dist = dist
                nearest = other

        return nearest

    def find_nearest_entity_in_range(self, entity, max_range, exclude_self=True):
        """Find nearest entity within range"""
        nearest = None
        min_dist = float('inf')

        for eid, other in self.entities.items():
            if exclude_self and eid == entity:
                continue
            if not hasattr(other, 'health') or other.health <= 0:
                continue
            if other.screen_x != entity.screen_x or other.screen_y != entity.screen_y:
                continue

            dist = abs(other.x - entity.x) + abs(other.y - entity.y)
            if dist <= max_range and dist < min_dist:
                min_dist = dist
                nearest = other

        return nearest

    def find_nearest_non_faction_entity(self, entity, max_range):
        """Find nearest entity not in same faction"""
        if not entity.faction:
            return None

        nearest = None
        min_dist = float('inf')

        for eid, other in self.entities.items():
            if eid == entity:
                continue
            if not hasattr(other, 'health') or other.health <= 0:
                continue
            if hasattr(other, 'faction') and other.faction == entity.faction:
                continue
            if other.screen_x != entity.screen_x or other.screen_y != entity.screen_y:
                continue

            dist = abs(other.x - entity.x) + abs(other.y - entity.y)
            if dist <= max_range and dist < min_dist:
                min_dist = dist
                nearest = other

        return nearest

    def find_closest_target_by_type(self, entity, target_type, screen_key):
        """Find closest target of specified type"""
        if target_type == 'hostile':
            return self.find_closest_hostile_entity(entity, screen_key)
        elif target_type == 'food':
            return self.find_closest_food_source(entity, screen_key)
        elif target_type == 'water':
            return self.find_closest_water_source(entity, screen_key)
        elif target_type == 'structure':
            return self.find_closest_structure(entity, screen_key)
        elif target_type == 'resource':
            return self.find_closest_resource(entity, screen_key)
        elif target_type == 'crop':
            return self._find_closest_crop(entity, screen_key)
        elif target_type == 'tree':
            return self._find_closest_tree(entity, screen_key)
        elif target_type == 'stone':
            return self._find_closest_stone(entity, screen_key)
        elif target_type == 'any_entity':
            return self._find_closest_any_entity(entity, screen_key)
        elif target_type == 'quest_target':
            # Direct passthrough — entity.quest_target is already the resolved target
            return getattr(entity, 'quest_target', None)
        return None

    # ── Quest-focus target finders ────────────────────────────────────────────

    def _find_closest_crop(self, entity, screen_key):
        """Closest harvestable crop or workable soil (farming quest)."""
        if screen_key not in self.screens:
            return None
        screen = self.screens[screen_key]
        closest, best_score = None, float('inf')
        # Lower priority index = preferred target
        priority = {'CARROT3': 0, 'CARROT2': 1, 'SOIL': 2, 'GRASS': 3, 'DIRT': 3}
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                p = priority.get(cell)
                if p is None:
                    continue
                score = abs(x - entity.x) + abs(y - entity.y) + p * 0.1
                if score < best_score:
                    best_score = score
                    closest = ('cell', x, y, cell)
        return closest

    def _find_closest_tree(self, entity, screen_key):
        """Closest choppable tree (building quest)."""
        if screen_key not in self.screens:
            return None
        screen = self.screens[screen_key]
        closest, closest_dist = None, float('inf')
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if screen['grid'][y][x] in ('TREE1', 'TREE2', 'TREE3'):
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, screen['grid'][y][x])
        return closest

    def _find_closest_stone(self, entity, screen_key):
        """Closest mineable stone (mining quest)."""
        if screen_key not in self.screens:
            return None
        screen = self.screens[screen_key]
        closest, closest_dist = None, float('inf')
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if screen['grid'][y][x] in ('STONE', 'CAVE_WALL'):
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_dist:
                        closest_dist = dist
                        closest = ('cell', x, y, screen['grid'][y][x])
        return closest

    def _find_closest_any_entity(self, entity, screen_key):
        """Closest entity of any kind (combat_all quest) — never returns self."""
        closest_id, closest_dist = None, float('inf')
        for eid in self.screen_entities.get(screen_key, []):
            if eid not in self.entities:
                continue
            other = self.entities[eid]
            if other is entity:
                continue
            dist = abs(other.x - entity.x) + abs(other.y - entity.y)
            if dist < closest_dist:
                closest_dist = dist
                closest_id = eid
        return closest_id
