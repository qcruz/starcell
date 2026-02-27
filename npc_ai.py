"""
StarCell NPC AI System
All entity behavior, decision-making, movement, combat, and actions.
Includes reusable action primitives that both NPCs and autopilot can use.
"""
import random
import math
from constants import *


class NpcAiMixin:
    """Mixin class for NPC AI. Mixed into Game via multiple inheritance."""

    # ══════════════════════════════════════════════════════════════════════
    # ACTION PRIMITIVES — Reusable building blocks for NPC and player actions
    # ══════════════════════════════════════════════════════════════════════

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


    # ══════════════════════════════════════════════════════════════════
    # EXISTING NPC AI METHODS — Extracted from game_logic.py & game_logic_2.py
    # ══════════════════════════════════════════════════════════════════

    def update_entity_ai(self, entity_id, entity):
        """Update entity AI - targeting, pathfinding, actions"""
        # Guard against double-updates in the same tick (can happen with priority queue)
        if not hasattr(entity, 'last_ai_tick'):
            entity.last_ai_tick = -1
        if entity.last_ai_tick == self.tick:
            return  # Already updated this tick
        entity.last_ai_tick = self.tick

        # Reset per-update movement flag so behavior guard is accurate this cycle
        entity.moved_this_update = False
        
        # ── AUTOPILOT SAFETY: force-clear ANY freeze flags on ALL entities ──
        if getattr(self, 'autopilot', False):
            if entity.idle_timer > 0:
                entity.idle_timer = 0
                entity.is_idle = False
            if hasattr(self, 'inspected_npc') and self.inspected_npc is not None:
                self.inspected_npc = None
        
        # FRIENDLY NPCs targeted by player should stop moving (unless under attack)
        if (not getattr(self, 'autopilot', False) and
                not entity.props.get('is_autopilot_proxy', False) and
                hasattr(self, 'inspected_npc') and self.inspected_npc == entity_id and 
                not entity.props.get('hostile', False)):
            if not entity.in_combat:
                return  # Skip AI update - NPC stays still
        
        # UNIFIED AI STATE SYSTEM - Update entity AI state based on parameters
        self.update_entity_ai_state(entity_id, entity)
        
        # Get screen_key for execution
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        
        # Movement cooldown - only move every N ticks based on speed
        if not hasattr(entity, 'move_cooldown'):
            # Initialize with random cooldown to prevent synchronized movement on spawn/load
            base_cooldown = max(1, int(20 / entity.props.get('speed', 1.0)))
            entity.move_cooldown = random.randint(0, base_cooldown)
        
        if entity.move_cooldown > 0:
            entity.move_cooldown -= 1
        
        # EXECUTE BEHAVIOR BASED ON STATE
        if hasattr(entity, 'ai_state'):
            if entity.ai_state == 'combat':
                # Combat - face and attack adjacent target
                if entity.current_target == 'player':
                    # Attacking the player
                    player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
                    if screen_key != player_zone or self.player.get('in_subscreen'):
                        entity.ai_state = 'wandering'
                        entity.current_target = None
                        entity.ai_state_timer = 2
                    else:
                        dist = abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])
                        if dist == 1:
                            # Adjacent — attack player
                            if entity.move_cooldown <= 0:
                                damage = max(1, entity.props.get('strength', 5) + entity.level)
                                self.player_take_damage(damage)
                                entity.move_cooldown = max(1, int(NPC_COMBAT_MOVE_INTERVAL / entity.props.get('speed', 1.0)))
                                entity.in_combat = True
                                # Bat disengage after hitting
                                if entity.props.get('flying', False) and random.random() < 0.4:
                                    entity.ai_state = 'wandering'
                                    entity.current_target = None
                                    entity.in_combat = False
                                    entity.ai_state_timer = 3
                        elif dist <= 8:
                            # Move toward player
                            if entity.move_cooldown <= 0:
                                self.move_toward_position(entity, self.player['x'], self.player['y'], screen_key)
                                entity.move_cooldown = max(1, int(NPC_COMBAT_MOVE_INTERVAL / entity.props.get('speed', 1.0)))
                        else:
                            # Too far — lose interest
                            entity.ai_state = 'wandering'
                            entity.current_target = None
                            entity.in_combat = False
                            entity.ai_state_timer = 2
                elif entity.current_target and isinstance(entity.current_target, int):
                    if entity.current_target in self.entities:
                        target = self.entities[entity.current_target]
                        
                        # DEBUG: Track warrior combat behavior (disabled to reduce spam)
                        # if entity.type == 'WARRIOR':
                        #     dist = abs(entity.x - target.x) + abs(entity.y - target.y)
                        #     print(f"WARRIOR {entity.name} COMBAT: pos=({entity.x},{entity.y}), target_pos=({target.x},{target.y}), dist={dist}, cooldown={entity.move_cooldown}")
                        
                        # Check if target is alive
                        if not target.is_alive():
                            # Target dead - exit combat
                            entity.ai_state = 'targeting'
                            entity.current_target = None
                            entity.ai_state_timer = 1
                            return
                        
                        # Check distance - MUST be adjacent (dist == 1) for combat
                        dist = abs(entity.x - target.x) + abs(entity.y - target.y)
                        
                        if dist == 0:
                            # Overlapping with target - move to adjacent cell
                            for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                                new_x = entity.x + dx
                                new_y = entity.y + dy
                                if (new_x, new_y) != (target.x, target.y):
                                    if screen_key in self.screens:
                                        screen = self.screens[screen_key]
                                        if (0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT):
                                            cell = screen['grid'][new_y][new_x]
                                            if not CELL_TYPES[cell].get('solid', False):
                                                entity.x = new_x
                                                entity.y = new_y
                                                entity.world_x = float(new_x)
                                                entity.world_y = float(new_y)
                                                break
                        
                        elif dist == 1:
                            # Adjacent - perfect for combat
                            # Face target
                            dx = target.x - entity.x
                            dy = target.y - entity.y
                            if abs(dx) > abs(dy):
                                entity.facing = 'right' if dx > 0 else 'left'
                            else:
                                entity.facing = 'down' if dy > 0 else 'up'
                            
                            # Attack (NO MOVEMENT in combat, only attacking)
                            self.find_and_attack_enemy(entity_id, entity)
                            
                            # Bat disengage: high chance to drop combat and wander away
                            if entity.props.get('flying', False):
                                if random.random() < 0.40:  # 40% chance per attack to disengage
                                    entity.ai_state = 'wandering'
                                    entity.current_target = None
                                    entity.ai_state_timer = 3
                        
                        else:
                            # Target not adjacent (dist > 1) - exit combat, return to targeting
                            entity.ai_state = 'targeting'
                            entity.ai_state_timer = 1
                    else:
                        # Target doesn't exist - exit combat
                        entity.ai_state = 'wandering'
                        entity.current_target = None
                        entity.ai_state_timer = 2
                else:
                    # No valid target - exit combat
                    entity.ai_state = 'wandering'
                    entity.current_target = None
                    entity.ai_state_timer = 2
            
            elif entity.ai_state == 'flee':
                # Fleeing - move away from threat every AI update
                threat_x, threat_y = None, None
                if entity.flee_target == 'player':
                    player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
                    if screen_key == player_zone and not self.player.get('in_subscreen'):
                        threat_x, threat_y = self.player['x'], self.player['y']
                elif entity.flee_target and isinstance(entity.flee_target, int):
                    if entity.flee_target in self.entities:
                        threat = self.entities[entity.flee_target]
                        threat_x, threat_y = threat.x, threat.y
                
                if threat_x is not None:
                    dx = entity.x - threat_x
                    dy = entity.y - threat_y
                    if abs(dx) > abs(dy):
                        move_x = 1 if dx > 0 else -1
                        move_y = 0
                    else:
                        move_x = 0
                        move_y = 1 if dy > 0 else -1
                    new_x = entity.x + move_x
                    new_y = entity.y + move_y
                    self.move_toward_position(entity, new_x, new_y, screen_key)
            
            elif entity.ai_state == 'targeting':
                # Moving toward target
                if entity.current_target:
                    if entity.current_target == 'player':
                        # Move toward player
                        player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
                        if screen_key == player_zone and not self.player.get('in_subscreen'):
                            self.move_toward_position(entity, self.player['x'], self.player['y'], screen_key)
                        else:
                            entity.current_target = None
                            entity.ai_state = 'wandering'
                    elif isinstance(entity.current_target, int):
                        # Entity target — check if in same zone
                        if entity.current_target in self.entities:
                            target = self.entities[entity.current_target]
                            target_zone = f"{target.screen_x},{target.screen_y}"
                            if target_zone == screen_key:
                                # Same zone — move directly toward target
                                self.move_toward_position(entity, target.x, target.y, screen_key)
                            else:
                                # Cross-zone: route toward the exit closest to target zone
                                exit_x, exit_y = self._get_exit_toward_zone(
                                    entity.screen_x, entity.screen_y,
                                    target.screen_x, target.screen_y)
                                self.move_toward_position(entity, exit_x, exit_y, screen_key)
                                # If at exit, try to cross
                                self._try_targeting_zone_cross(entity, entity_id)
                        else:
                            entity.current_target = None
                            entity.ai_state = 'wandering'
                    elif isinstance(entity.current_target, tuple):
                        # Cell target — navigate to ADJACENT cell, not onto the cell itself.
                        if len(entity.current_target) >= 3 and entity.current_target[0] in ['cell', 'entity']:
                            tx, ty = entity.current_target[1], entity.current_target[2]
                            dist = abs(entity.x - tx) + abs(entity.y - ty)
                            if dist == 0:
                                # Somehow walked onto the target cell — clear and wander
                                entity.quest_target = None
                                entity.current_target = None
                                entity.ai_state = 'wandering'
                                entity.ai_state_timer = 2
                            elif dist > 1:
                                self.move_toward_position(entity, tx, ty, screen_key)
                                # If at exit, try to cross
                                self._try_targeting_zone_cross(entity, entity_id)
                            # dist == 1: adjacent, let state machine handle idle transition
                        elif len(entity.current_target) >= 2 and isinstance(entity.current_target[0], (int, float)):
                            self.move_toward_position(entity, entity.current_target[0], entity.current_target[1], screen_key)
                            self._try_targeting_zone_cross(entity, entity_id)
            
            elif entity.ai_state == 'wandering':
                # Random movement with natural pauses
                # 60% move, 40% stand still for a beat
                if random.random() < 0.6:
                    self.wander_entity(entity)
            
            elif entity.ai_state == 'idle':
                # Stand still - NO MOVEMENT in idle state
                if not entity.current_target:
                    # No target while idle — switch to wandering immediately
                    entity.ai_state = 'wandering'
                    entity.ai_state_timer = 1
                else:
                    dist = self.get_target_distance(entity, entity.current_target)
                    
                    # Execute action ONLY if target is adjacent (dist <= 1)
                    if dist <= 1:
                        # Face the target before executing action
                        if isinstance(entity.current_target, int) and entity.current_target in self.entities:
                            target_entity = self.entities[entity.current_target]
                            dx = target_entity.x - entity.x
                            dy = target_entity.y - entity.y
                            if abs(dx) > abs(dy):
                                entity.facing = 'right' if dx > 0 else 'left'
                            else:
                                entity.facing = 'down' if dy > 0 else 'up'
                        elif isinstance(entity.current_target, tuple) and len(entity.current_target) >= 3:
                            tx, ty = entity.current_target[1], entity.current_target[2]
                            dx = tx - entity.x
                            dy = ty - entity.y
                            if abs(dx) > abs(dy):
                                entity.facing = 'right' if dx > 0 else 'left'
                            else:
                                entity.facing = 'down' if dy > 0 else 'up'
                        
                        # Execute action based on target type
                        if entity.target_type == 'hostile':
                            # Hostile target while idle — switch to combat
                            entity.ai_state = 'combat'
                            entity.ai_state_timer = 1
                        elif entity.target_type == 'quest_target':
                            # Arrived near specific quest target — award XP and drop back to
                            # general mode.  The actual farming/chopping action fires through
                            # the normal tick%60 behavior path once the entity stops moving.
                            _FOCUS_ACTIVITY = {
                                'farming':        'harvest',
                                'building':       'build',
                                'mining':         'mine',
                                'crafting':       'build',
                                'exploring':      'travel',
                                'combat_hostile': 'kill',
                                'combat_all':     'kill',
                            }
                            focus = getattr(entity, 'quest_focus', 'exploring')
                            entity.level_up_from_activity(_FOCUS_ACTIVITY.get(focus, 'harvest'), self)
                            entity.quest_target   = None   # back to general mode
                            entity.current_target = None
                            entity.ai_state       = 'wandering'
                            entity.ai_state_timer = 2
                        elif entity.target_type == 'food':
                            # Eat food — use behavior_config actions or direct consumption
                            behavior_config = entity.props.get('behavior_config')
                            if behavior_config:
                                self.execute_entity_behavior(entity, behavior_config)
                            else:
                                # Direct food consumption for entities without behavior_config
                                food_sources = entity.props.get('food_sources', [])
                                if isinstance(entity.current_target, tuple) and len(entity.current_target) >= 4:
                                    cell_type = entity.current_target[3]
                                    food_value = 40 if 'CARROT' in cell_type else 20
                                    entity.eat(food_value)
                                    # Consume the food cell
                                    cx, cy = entity.current_target[1], entity.current_target[2]
                                    if screen_key in self.screens:
                                        self.screens[screen_key]['grid'][cy][cx] = 'GRASS'
                                    entity.current_target = None
                        elif entity.target_type == 'water':
                            # Drink water
                            entity.drink(40)
                            entity.current_target = None  # Done drinking, find new goal
                        elif entity.target_type == 'resource':
                            # Harvest resource — use behavior_config
                            behavior_config = entity.props.get('behavior_config')
                            if behavior_config:
                                self.execute_entity_behavior(entity, behavior_config)
                        elif entity.target_type == 'structure':
                            # Near structure — heal boost happens automatically via zone update
                            # Execute any structure-related behavior
                            behavior_config = entity.props.get('behavior_config')
                            if behavior_config:
                                self.execute_entity_behavior(entity, behavior_config)
                        else:
                            # Generic target type — try behavior_config
                            behavior_config = entity.props.get('behavior_config')
                            if behavior_config:
                                self.execute_entity_behavior(entity, behavior_config)
                    elif dist > 1:
                        # Target not adjacent — go back to targeting
                        entity.ai_state = 'targeting'
                        entity.ai_state_timer = 1
        
        # Update wizard spell cooldown
        if hasattr(entity, 'spell_cooldown') and entity.spell_cooldown > 0:
            entity.spell_cooldown -= 1
        
        # Update action animation timer
        if hasattr(entity, 'action_animation_timer') and entity.action_animation_timer > 0:
            entity.action_animation_timer -= 1
        
        # Subscreen behavior - NPCs enter/exit houses and caves
        if entity.in_subscreen:
            # Daytime: non-nocturnal NPCs should actively try to exit structures
            # Nighttime: nocturnal entities should actively try to exit
            wants_to_exit = False
            
            if not self.is_night and not entity.props.get('nocturnal', False):
                # Daytime + not nocturnal = want to be outside working
                wants_to_exit = True
            elif self.is_night and entity.props.get('nocturnal', False):
                # Nighttime + nocturnal = want to be outside hunting
                wants_to_exit = True
            
            if wants_to_exit:
                # Actively move toward exit and leave
                self.try_npc_exit_subscreen(entity)
                if entity.in_subscreen:
                    # Still inside — keep trying to path toward exit
                    self.move_npc_toward_subscreen_exit(entity)
                    return  # Skip normal AI
            else:
                # Low chance to exit anyway (restless NPCs)
                if random.random() < 0.05:
                    self.try_npc_exit_subscreen(entity)
            
            # If still in subscreen after exit attempt, do subscreen behavior
            if entity.in_subscreen:
                # Miners mine in caves, peaceful NPCs rest in houses
                if entity.type == 'MINER' and entity.subscreen_key and 'cave' in entity.subscreen_key.lower():
                    behavior_config = entity.props.get('behavior_config')
                    if behavior_config:
                        self.execute_entity_behavior(entity, behavior_config)
                else:
                    # Rest/wander in subscreen
                    if random.random() < 0.1:
                        self.wander_entity(entity)
                return  # Skip normal overworld AI
        else:
            # In overworld - occasionally try to enter subscreens
            self.try_npc_enter_subscreen(entity, screen_key)
        
        # Warrior home zone return behavior
        if entity.type == 'WARRIOR' and hasattr(entity, 'home_zone'):
            if not hasattr(entity, 'last_home_return_check'):
                entity.last_home_return_check = 0
            
            # Check every WARRIOR_HOME_RETURN_INTERVAL ticks
            if self.tick - entity.last_home_return_check >= WARRIOR_HOME_RETURN_INTERVAL:
                entity.last_home_return_check = self.tick
                
                # If not in home zone, nudge toward it via the AI state machine
                if entity.home_zone:
                    current_zone = f"{entity.screen_x},{entity.screen_y}"
                    if current_zone != entity.home_zone:
                        # Determine direction to home
                        home_x, home_y = map(int, entity.home_zone.split(','))
                        
                        if entity.screen_x < home_x:
                            entity.target_exit = 'right'
                        elif entity.screen_x > home_x:
                            entity.target_exit = 'left'
                        elif entity.screen_y < home_y:
                            entity.target_exit = 'bottom'
                        elif entity.screen_y > home_y:
                            entity.target_exit = 'top'
                        
                        # Set the AI state to targeting with an exit cell so
                        # the state machine moves the warrior instead of
                        # skipping all AI with a bare return.
                        exit_positions = self.get_exit_positions(entity.target_exit) if hasattr(self, 'get_exit_positions') else None
                        if exit_positions:
                            tx, ty = random.choice(exit_positions)
                            entity.current_target = ('cell', tx, ty)
                            entity.target_type = 'resource'
                            entity.ai_state = 'targeting'
                            entity.ai_state_timer = 3
                        # Do NOT return here — let the rest of the AI run so
                        # the warrior can still fight, eat, drink, etc.
        
        # Check if entity is a follower
        is_follower = entity_id in self.followers
        
        # Check if being traded with - make idle during trade
        being_traded_with = (
            self.trader_display and 
            self.trader_display.get('entity_id') == entity_id
        )
        
        if being_traded_with:
            # Force idle during trade (only set once)
            if not entity.is_idle:
                entity.is_idle = True
                entity.idle_timer = 10  # Short idle, refreshed each frame
            return  # Skip all AI
        else:
            # Trade ended - clear forced idle
            if hasattr(entity, 'was_trading'):
                entity.is_idle = False
                entity.idle_timer = 0
                entity.was_trading = False
        
        # Mark if currently trading
        if being_traded_with:
            entity.was_trading = True
        
        # Legacy idle_timer: only used by check_npc_inspection (player-targeted NPCs pause briefly).
        # The random 30% idle roll has been removed — idling is fully handled by the
        # AI state machine (ai_state='idle' / ai_state_timer). Keeping the timer
        # decrement here so inspection-triggered pauses still drain correctly.
        # During autopilot, force-drain any lingering idle timers so NPCs never freeze.
        if not is_follower and entity.idle_timer > 0:
            if getattr(self, 'autopilot', False):
                entity.idle_timer = 0
                entity.is_idle = False
            else:
                entity.idle_timer -= 1
                if entity.idle_timer <= 0:
                    entity.is_idle = False
                else:
                    return  # NPC paused because player is inspecting it
        
        # Followers: check distance to player and follow if too far
        if is_follower:
            # Calculate distance to player
            # Check if on same screen
            if entity.screen_x == self.player['screen_x'] and entity.screen_y == self.player['screen_y']:
                dist_to_player = abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])
                
                # If more than 5 cells away, move towards player
                if dist_to_player > 5:
                    self.move_entity_towards(entity, self.player['x'], self.player['y'])
                    return
            else:
                # Follower is on different screen - teleport to player's screen
                self.teleport_follower_to_player(entity_id, entity)
                return

        # Update combat state for hostile entities (not followers)
        # DISABLED - Now handled by unified AI state machine above
        # if entity.props.get('hostile') and not is_follower:
        #     self.update_entity_combat_state(entity)
        
        is_proxy = entity.props.get('is_autopilot_proxy', False)
        
        # Night behavior: peaceful NPCs seek shelter in houses
        if self.is_night and not is_follower and not is_proxy:
            peaceful_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER',
                              'WARRIOR', 'COMMANDER', 'KING']
            if entity.type in peaceful_types and not entity.in_subscreen:
                if self.npc_seek_shelter(entity):
                    return  # Sheltered, don't wander or do work behaviors
        
        # Daytime: NPCs in subscreens have a chance to leave
        if not self.is_night and entity.in_subscreen and not is_follower and not is_proxy:
            if random.random() < 0.02:  # 2% per update to leave
                self.npc_exit_subscreen(entity)
                return
        
        # PEACEFUL NPC THREAT DETECTION - DISABLED
        # Now handled by the reactive hostile proximity check in update_entity_ai_state
        # which runs for ALL entity types, not just farmers/lumberjacks
        
        # Special NPC behaviors (executed occasionally).
        # Skip for the autopilot proxy (it has its own controlled behavior).
        # Skip when the entity MOVED this AI update cycle — behavior fires mid-step
        # changes entity.facing which confuses smooth interpolation, causing visual jumps.
        # moved_this_update is cleared at the top of update_entity_ai each cycle so it
        # accurately reflects whether a grid step happened in the current AI update.
        moved_this_cycle = getattr(entity, 'moved_this_update', False)
        if self.tick % 60 == 0 and not is_follower and not moved_this_cycle:
            # Execute behavior based on entity's behavior_config
            behavior_config = entity.props.get('behavior_config')
            if behavior_config:
                self.execute_entity_behavior(entity, behavior_config)
            
            # Goblin/Bandit/Termite behavior - attack structures (no config needed)
            elif entity.type in ['GOBLIN', 'BANDIT', 'TERMITE']:
                self.hostile_structure_behavior(entity)
            
            # Human NPCs may place camps
            if behavior_config and behavior_config.get('can_place_camp'):
                if random.random() < NPC_CAMP_PLACE_RATE:
                    self.npc_place_camp(entity)
            
            # Miners may discover/create caves
            if entity.type == 'MINER':
                if random.random() < NPC_CAMP_PLACE_RATE:  # Same rate as camp placement
                    self.miner_place_cave(entity)
            
            # All humanoid NPCs (peaceful and hostile) can clear trees
            # Lumberjacks do this via their normal behavior and collect wood
            # Others just clear trees at lower rate without collecting wood
            humanoid_types = ['FARMER', 'TRADER', 'GUARD', 'MINER', 'WARRIOR', 'BANDIT', 'GOBLIN']
            if entity.type in humanoid_types and entity.type != 'LUMBERJACK':
                if random.random() < NPC_TREE_CLEAR_RATE:
                    self.try_clear_tree(entity, screen_key)
        
        # Normal AI for non-followers
        # Determine target priority - health-based urgency
        low_health = entity.health < entity.max_health * 0.5  # Less than 50% health
        critical_health = entity.health < entity.max_health * 0.3  # Less than 30% health
        
        # Traders and Guards are more focused - only seek food/water when very low
        is_focused_npc = entity.type in ['TRADER', 'GUARD']
        food_threshold = 15 if is_focused_npc else 30
        water_threshold = 15 if is_focused_npc else 30
        
        # Use new intelligent priority evaluation system
        # Counterattack still takes highest priority
        if hasattr(entity, 'wants_counterattack') and entity.wants_counterattack:
            entity.target_priority = 'counterattack'
            entity.target = entity.counterattack_target if hasattr(entity, 'counterattack_target') else None
            entity.wants_counterattack = False
        # If AI state system has already set a priority, use it (don't override with evaluate_entity_priorities)
        elif hasattr(entity, 'target_priority') and entity.target_priority is not None:
            # AI state system already set the priority - keep it!
            # (update_entity_ai_state was called above and set target_priority)
            pass
        else:
            # Fallback: use old priority evaluation system if AI state didn't set one
            priority, target = self.evaluate_entity_priorities(entity, entity_id)
            entity.target_priority = priority
            entity.target = target
        
        # Automatic item pickup for all entities
        
        # Check for dropped items at current position (both key formats)
        if screen_key in self.dropped_items:
                # Try string key format
                pos_key_str = f"{entity.x},{entity.y}"
                # Try tuple key format
                pos_key_tuple = (entity.x, entity.y)
                
                items_picked_up = False
                
                # Check string format
                if pos_key_str in self.dropped_items[screen_key]:
                    items_at_pos = self.dropped_items[screen_key][pos_key_str]
                    
                    # Pick up all items at position
                    for item_name, count in list(items_at_pos.items()):
                        entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                        items_picked_up = True
                        
                        # Check if player is adjacent for trading
                        player_adjacent = (
                            entity.screen_x == self.player['screen_x'] and 
                            entity.screen_y == self.player['screen_y'] and
                            abs(entity.x - self.player['x']) + abs(entity.y - self.player['y']) <= 1
                        )
                        
                        # TRADING: If gold picked up and player nearby, trigger trade
                        if item_name == 'gold' and player_adjacent:
                            self.process_npc_trade(entity, entity_id, count)
                        
                        # 10% chance to log pickup
                        if random.random() < 0.10:
                            name_str = entity.name if entity.name else entity.type
                            print(f"{name_str} picked up {count} {item_name}(s) at [{screen_key}]")
                    
                    # Clear dropped items at this position
                    del self.dropped_items[screen_key][pos_key_str]
                
                # Check tuple format
                if pos_key_tuple in self.dropped_items[screen_key]:
                    items_at_pos = self.dropped_items[screen_key][pos_key_tuple]
                    
                    # Pick up all items at position
                    for item_name, count in list(items_at_pos.items()):
                        entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                        items_picked_up = True
                        
                        # Check if player is adjacent for trading
                        player_adjacent = (
                            entity.screen_x == self.player['screen_x'] and 
                            entity.screen_y == self.player['screen_y'] and
                            abs(entity.x - self.player['x']) + abs(entity.y - self.player['y']) <= 1
                        )
                        
                        # TRADING: If gold picked up and player nearby, trigger trade
                        if item_name == 'gold' and player_adjacent:
                            self.process_npc_trade(entity, entity_id, count)
                        
                        # 10% chance to log pickup
                        if random.random() < 0.10:
                            name_str = entity.name if entity.name else entity.type
                            print(f"{name_str} picked up {count} {item_name}(s) at [{screen_key}]")
                    
                    # Clear dropped items at this position
                    del self.dropped_items[screen_key][pos_key_tuple]
        
        # ========================================================================
        # OLD TARGET_PRIORITY AI SYSTEM - DISABLED
        # This entire section has been replaced by the state machine above
        # Keeping commented for reference but should NOT execute
        # ========================================================================
        """
        # Find and move towards target
        # Execute behavior based on target priority
        if entity.target_priority == 'counterattack':
            # FARMERS/LUMBERJACKS: Flee instead of counterattacking
            if entity.type in ['FARMER', 'LUMBERJACK']:
                # Enter fleeing state
                entity.ai_state = 'fleeing'
                entity.is_fleeing = True
                entity.ai_state_timer = AI_TIMER_BASE * 12
                
                # Move away from attacker
                if hasattr(entity, 'counterattack_target'):
                    target = entity.counterattack_target
                    if target == 'player':
                        if entity.screen_x == self.player['screen_x'] and entity.screen_y == self.player['screen_y']:
                            avoid_x = entity.x + (entity.x - self.player['x'])
                            avoid_y = entity.y + (entity.y - self.player['y'])
                            self.move_entity_towards(entity, avoid_x, avoid_y)
                    elif target in self.entities:
                        attacker = self.entities[target]
                        if entity.screen_x == attacker.screen_x and entity.screen_y == attacker.screen_y:
                            avoid_x = entity.x + (entity.x - attacker.x)
                            avoid_y = entity.y + (entity.y - attacker.y)
                            self.move_entity_towards(entity, avoid_x, avoid_y)
                    
                    # Clear counterattack
                    entity.counterattack_target = None
                    entity.target_priority = None
            # OTHER NPCs: Normal counterattack behavior
            else:
                # Entity wants to counterattack - try to hit back at attacker
                if hasattr(entity, 'counterattack_target'):
                    target = entity.counterattack_target
                    if target == 'player':
                        # Counterattack player
                        if entity.screen_x == self.player['screen_x'] and entity.screen_y == self.player['screen_y']:
                            dist = abs(self.player['x'] - entity.x) + abs(self.player['y'] - entity.y)
                            if dist <= 1:
                                # Adjacent - hit back!
                                damage = entity.strength
                                
                                # Add weapon bonus from inventory
                                damage += self.calculate_weapon_bonus(entity.inventory)
                                
                                # Add magic damage from runestones
                                magic_damage, magic_type = self.calculate_magic_damage(entity.inventory)
                                damage += magic_damage
                                
                                # Peaceful NPCs do minimal damage (25%)
                                if not entity.props.get('hostile', False):
                                    damage *= 0.25
                                # Hostile entities do slightly more damage (1.2x)
                                elif entity.props.get('hostile', True):
                                    damage *= 1.2
                                
                                self.player_take_damage(damage)
                                self.show_attack_animation(self.player['x'], self.player['y'], entity=entity, magic_type=magic_type)
                            else:
                                # Move toward player
                                self.move_entity_towards(entity, self.player['x'], self.player['y'])
                    elif target in self.entities:
                        # Counterattack another entity
                        attacker = self.entities[target]
                        if entity.screen_x == attacker.screen_x and entity.screen_y == attacker.screen_y:
                            dist = abs(attacker.x - entity.x) + abs(attacker.y - entity.y)
                            if dist <= 1:
                                # Adjacent - hit back!
                                damage = entity.strength
                                
                                # Add weapon bonus from inventory
                                damage += self.calculate_weapon_bonus(entity.inventory)
                                
                                # Add magic damage from runestones
                                magic_damage, magic_type = self.calculate_magic_damage(entity.inventory)
                                damage += magic_damage
                                
                                # Peaceful NPCs do minimal damage (25%)
                                if not entity.props.get('hostile', False):
                                    damage *= 0.25
                                # Hostile entities do slightly more damage (1.2x)
                                elif entity.props.get('hostile', True):
                                    damage *= 1.2
                                
                                if attacker.combat_state == 'blocking':
                                    damage *= (1 - attacker.block_reduction)
                                attacker.take_damage(damage, entity_id)
                                self.show_attack_animation(attacker.x, attacker.y, entity=entity, target_entity=attacker, magic_type=magic_type)
                            else:
                                # Move toward attacker
                                self.move_entity_towards(entity, attacker.x, attacker.y)
                    # Clear counterattack after one attempt
                    entity.counterattack_target = None
                    entity.target_priority = 'wander'
        elif entity.target_priority == 'loot':
            # Goblin looting behavior - handled in hostile_structure_behavior
            self.hostile_structure_behavior(entity)
        elif entity.target_priority == 'structure':
            # Goblin structure attacking - handled in hostile_structure_behavior
            self.hostile_structure_behavior(entity)
        elif entity.target_priority == 'attack':
            # Attack specific target
            if entity.target:
                if isinstance(entity.target, int):
                    # Attack entity
                    self.find_and_attack_enemy(entity_id, entity)
                elif isinstance(entity.target, tuple) and len(entity.target) == 3:
                    # Attack structure
                    self.hostile_structure_behavior(entity)
            else:
                # No specific target, search for enemies
                self.find_and_attack_enemy(entity_id, entity)
        elif entity.target_priority == 'food':
            self.find_and_move_to_food(entity)
        elif entity.target_priority == 'water':
            self.find_and_move_to_water(entity)
        elif entity.target_priority == 'explore':
            # ALL entities head toward zone exits when exploring
            # Traders and Guards do this most of the time, others rarely
            if entity.type == 'GUARD':
                # Guards patrol center lanes while heading to exits
                self.try_patrol_behavior(entity, f"{entity.screen_x},{entity.screen_y}")
            else:
                # All others (including Traders) use travel behavior
                self.try_travel_behavior(entity, f"{entity.screen_x},{entity.screen_y}")
        elif entity.target_priority == 'enemy':
            # Try to find and attack enemies
            self.find_and_attack_enemy(entity_id, entity)
            
            # If still in targeting mode and no enemy found, Warriors should explore
            # (find_and_attack_enemy doesn't move them if no enemy, so handle movement here)
            if (hasattr(entity, 'ai_state') and entity.ai_state == 'targeting' and 
                entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD'] and
                not entity.in_combat):
                # No enemy in current zone - move toward zone exit to search other zones
                self.seek_zone_exit(entity, entity_id)
        elif entity.target_priority == 'defend':
            # Move to target and patrol/guard
            if entity.target:
                # entity.target can be either (x, y) tuple or entity_id
                if isinstance(entity.target, tuple) and len(entity.target) == 2:
                    target_x, target_y = entity.target
                    dist = abs(entity.x - target_x) + abs(entity.y - target_y)
                    if dist > 1:
                        self.move_entity_towards(entity, target_x, target_y)
                    else:
                        # At target - patrol around it
                        self.wander_entity(entity)
                elif isinstance(entity.target, (int, str)):
                    # Target is an entity - get its position
                    if entity.target in self.entities:
                        target_entity = self.entities[entity.target]
                        dist = abs(entity.x - target_entity.x) + abs(entity.y - target_entity.y)
                        if dist > 1:
                            self.move_entity_towards(entity, target_entity.x, target_entity.y)
                        else:
                            # At target - patrol around it
                            self.wander_entity(entity)
                    else:
                        # Target entity doesn't exist - wander
                        entity.target = None
                        self.wander_entity(entity)
                else:
                    # Invalid target format
                    entity.target = None
                    self.wander_entity(entity)
            else:
                self.wander_entity(entity)
        else:
            # Wander or special behaviors
            if entity.type == 'TRADER':
                self.try_travel_behavior(entity, f"{entity.screen_x},{entity.screen_y}")
            elif entity.type == 'GUARD':
                self.try_patrol_behavior(entity, f"{entity.screen_x},{entity.screen_y}")
            else:
                self.wander_entity(entity)
        """
        # ========================================================================
        # END OF DISABLED OLD AI SYSTEM
        # ========================================================================
        
        # Check for zone transition AFTER movement/priority execution
        # Only trigger if entity is actually at an exit
        if not is_follower:
            at_exit, _ = self.is_at_exit(entity.x, entity.y)
            
            if at_exit:
                # Check cooldown - prevent rapid zone hopping
                ticks_since_last_change = self.tick - entity.last_zone_change_tick
                if ticks_since_last_change < ZONE_CHANGE_COOLDOWN:
                    # Still on cooldown - can't change zones yet
                    pass
                else:
                    # Cooldown expired - can travel
                    can_travel = True
                    
                    # Transition rate: 30% for normal NPCs, 100% for autopilot proxy
                    is_proxy_entity = entity.props.get('is_autopilot_proxy', False)
                    travel_rate = 1.0 if is_proxy_entity else 0.3
                    
                    # Entities in targeting state with cross-zone target also always cross
                    if entity.ai_state == 'targeting' and entity.current_target:
                        travel_rate = 1.0
                    
                    if can_travel and random.random() < travel_rate:
                        old_zone = f"{entity.screen_x},{entity.screen_y}"
                        self.try_entity_zone_transition(entity_id, entity)
                        new_zone = f"{entity.screen_x},{entity.screen_y}"
                        
                        # If successfully traveled
                        if old_zone != new_zone:
                            # Update cooldown timer
                            entity.last_zone_change_tick = self.tick
                            
                            # Reset stuck target tracking on zone change
                            entity.target_stuck_counter = 0
                            entity.last_target_position = None
                            
                            # Chance to level up from traveling
                            entity.level_up_from_activity('travel', self)
                            
                            # Entity traveled to new zone (silent)
        
        # SAFETY CHECK: Validate entity position after all AI logic
        player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
        debug = (screen_key == player_zone) and entity.type == 'WARRIOR'
        
        if screen_key in self.screens:
            # Check bounds
            if not (0 <= entity.x < GRID_WIDTH and 0 <= entity.y < GRID_HEIGHT):
                # Entity is out of bounds - reset to safe position
                entity.x = max(1, min(GRID_WIDTH - 2, entity.x))
                entity.y = max(1, min(GRID_HEIGHT - 2, entity.y))
                entity.world_x = float(entity.x)
                entity.world_y = float(entity.y)
            
            # Check if standing on solid cell (flying entities are exempt from most solids)
            current_cell = self.screens[screen_key]['grid'][entity.y][entity.x]
            is_flying = entity.props.get('flying', False)
            fly_blocked = {'WALL', 'CAVE_WALL', 'DEEP_WATER'}
            if CELL_TYPES[current_cell]['solid'] and (not is_flying or current_cell in fly_blocked):
                if debug:
                    print(f"  [SAFETY] Warrior@({entity.x},{entity.y}) on SOLID cell {current_cell}, searching for safe cell...")
                # Entity is on solid cell - find nearest walkable cell
                found_safe = False
                for dy in range(-1, 2):
                    for dx in range(-1, 2):
                        check_x = entity.x + dx
                        check_y = entity.y + dy
                        if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                            check_cell = self.screens[screen_key]['grid'][check_y][check_x]
                            if not CELL_TYPES[check_cell]['solid']:
                                entity.x = check_x
                                entity.y = check_y
                                entity.world_x = float(check_x)
                                entity.world_y = float(check_y)
                                found_safe = True
                                break
                    if found_safe:
                        break
    
    def update_entity_ai_state(self, entity_id, entity):
        """Clean probabilistic AI state machine.
        
        Every update: observe surroundings, check for reactive state changes, 
        then handle current state logic. Timer gates state TRANSITIONS only
        (idle↔wandering↔targeting), not reactive checks or in-state behavior.
        """
        
        # Skip player and dead entities
        if entity_id == 'player' or not entity.is_alive():
            return
        
        # Initialize AI attributes if missing
        if not hasattr(entity, 'ai_state'):
            entity.ai_state = 'wandering'
        if not hasattr(entity, 'current_target'):
            entity.current_target = None
        if not hasattr(entity, 'target_type'):
            entity.target_type = None
        if not hasattr(entity, 'ai_state_timer'):
            entity.ai_state_timer = random.randint(0, 3)  # Small random offset
        if not hasattr(entity, 'flee_target'):
            entity.flee_target = None
        
        # Get traits from entity
        aggressiveness = entity.aggressiveness
        passiveness = entity.passiveness
        idleness = entity.idleness
        flee_chance = getattr(entity, 'flee_chance', 0.50)
        combat_chance = getattr(entity, 'combat_chance', 0.50)
        
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        
        # === BAT / NOCTURNAL BEHAVIOR ===
        if entity.props.get('nocturnal', False):
            if not self.is_night:
                # DAYTIME: Bats seek shelter — enter structures and go idle
                if entity.in_subscreen:
                    # Already sheltered — stay idle
                    entity.ai_state = 'idle'
                    entity.ai_state_timer = 5
                    return
                else:
                    # Find nearest enterable structure and move toward it
                    if screen_key in self.screens:
                        scr = self.screens[screen_key]
                        closest_struct = None
                        closest_dist = float('inf')
                        for cy in range(GRID_HEIGHT):
                            for cx in range(GRID_WIDTH):
                                c = scr['grid'][cy][cx]
                                if CELL_TYPES.get(c, {}).get('enterable', False):
                                    d = abs(entity.x - cx) + abs(entity.y - cy)
                                    if d < closest_dist:
                                        closest_dist = d
                                        closest_struct = (cx, cy)
                        if closest_struct:
                            entity.ai_state = 'targeting'
                            entity.current_target = ('cell', closest_struct[0], closest_struct[1], 'structure')
                            entity.target_type = 'structure'
                            entity.ai_state_timer = 3
                        else:
                            entity.ai_state = 'idle'
                            entity.ai_state_timer = 5
                    return
            else:
                # NIGHTTIME: Bats emerge from structures
                if entity.in_subscreen and random.random() < 0.15:
                    if hasattr(self, 'npc_exit_subscreen'):
                        self.npc_exit_subscreen(entity)
        
        # DEBUG: Only for player's current zone
        player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
        debug = (screen_key == player_zone)
        
        # Show all entities in player zone periodically (every 10 seconds, disabled by default)
        # if debug and self.tick % 600 == 0:
        #     nearby_hostiles = []
        #     ...
        
        # =====================================================================
        # REACTIVE CHECKS - run every update, override current state
        # =====================================================================
        
        # === ATTACK RESPONSE - Instant state change when attacked ===
        if hasattr(entity, 'wants_counterattack') and entity.wants_counterattack:
            # NPC promotion check (only for peaceful NPCs level 2+)
            peaceful_npc_types = ['FARMER', 'TRADER', 'LUMBERJACK', 'MINER', 'WIZARD']
            if entity.type in peaceful_npc_types and entity.level >= 2 and entity.counterattack_target in self.entities:
                attacker = self.entities[entity.counterattack_target]
                if attacker.props.get('hostile', False):
                    promotion_chance = 0.05  # 5% flat chance to become warrior when attacked
                    if random.random() < promotion_chance:
                        old_name = entity.name
                        old_type = entity.type
                        entity.type = 'WARRIOR'
                        entity.props = ENTITY_TYPES['WARRIOR']
                        entity.max_health = entity.props['max_health'] * entity.level
                        entity.health = entity.max_health
                        entity.strength = entity.props['strength'] * entity.level
                        self.assign_warrior_faction(entity, screen_key)
                        print(f"{old_name} ({old_type} L{entity.level}) became a WARRIOR!")
                        aggressiveness = entity.aggressiveness
                        flee_chance = getattr(entity, 'flee_chance', 0.05)
                        combat_chance = getattr(entity, 'combat_chance', 0.95)
            
            # Roll flee vs combat
            entity.wants_counterattack = False
            if random.random() < flee_chance:
                entity.ai_state = 'flee'
                entity.flee_target = entity.counterattack_target
                entity.current_target = None
                entity.ai_state_timer = 3
                if entity.type == 'WARRIOR':
                    pass  # Warriors fleeing is normal behavior
            else:
                entity.ai_state = 'combat'
                entity.current_target = entity.counterattack_target
                entity.target_type = 'hostile'
                entity.ai_state_timer = 3
                if entity.type == 'WARRIOR':
                    pass  # Warriors entering combat is normal behavior
            return
        
        # === HOSTILE PROXIMITY CHECK - all states except combat/flee ===
        # Entities notice nearby hostiles and react based on their traits
        if entity.ai_state not in ('combat', 'flee'):
            closest_hostile_id = None
            closest_hostile_dist = float('inf')
            
            entity_is_hostile = entity.props.get('hostile', False)
            
            # Check other entities
            for other_id in self.screen_entities.get(screen_key, []):
                if other_id not in self.entities:
                    continue
                other = self.entities[other_id]
                if other is entity or not other.is_alive():
                    continue
                
                other_is_hostile = other.props.get('hostile', False)
                
                # Determine if enemy
                is_enemy = False
                if entity_is_hostile:
                    # Hostile entities attack everyone: non-hostiles AND other hostile types
                    if not other_is_hostile:
                        is_enemy = True  # Attack peaceful NPCs
                    elif other.type != entity.type:
                        is_enemy = True  # Attack different hostile species
                elif other_is_hostile:
                    # Non-hostile entity sees hostile — it's an enemy
                    is_enemy = True
                elif (hasattr(entity, 'faction') and hasattr(other, 'faction') and
                      entity.faction and other.faction and entity.faction != other.faction):
                    # Faction-based hostile — enemy warriors
                    is_enemy = True
                
                if is_enemy:
                    dist = abs(entity.x - other.x) + abs(entity.y - other.y)
                    if dist < closest_hostile_dist:
                        closest_hostile_dist = dist
                        closest_hostile_id = other_id
            
            # Check player as potential target (hostile entities target the player)
            if entity_is_hostile:
                player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
                if screen_key == player_zone and not self.player.get('in_subscreen'):
                    player_dist = abs(entity.x - self.player['x']) + abs(entity.y - self.player['y'])
                    if player_dist < closest_hostile_dist:
                        closest_hostile_dist = player_dist
                        closest_hostile_id = 'player'
            
            # React if hostile is within detection range
            if closest_hostile_id is not None and closest_hostile_dist <= HOSTILE_DETECTION_RANGE:
                # Only react if entity has hostile in its target_types (combat-capable)
                target_types = entity.props.get('ai_params', {}).get('target_types', [])
                has_combat_capability = 'hostile' in target_types
                
                if has_combat_capability:
                    if closest_hostile_dist <= 1:
                        # Adjacent — enter combat directly
                        entity.ai_state = 'combat'
                        entity.current_target = closest_hostile_id
                        entity.target_type = 'hostile'
                        entity.ai_state_timer = 3
                        return
                    else:
                        # Not adjacent — target the hostile (move toward it)
                        entity.ai_state = 'targeting'
                        entity.current_target = closest_hostile_id
                        entity.target_type = 'hostile'
                        entity.ai_state_timer = 3
                        return
                else:
                    # Non-combat entity (farmer, trader, etc) — flee
                    if closest_hostile_dist <= HOSTILE_DETECTION_RANGE // 2:
                        # Only flee if hostile is fairly close
                        if random.random() < (1.0 - combat_chance):  # Use flee tendency
                            entity.ai_state = 'flee'
                            entity.flee_target = closest_hostile_id
                            entity.current_target = None
                            entity.ai_state_timer = 3
                            return
        
        # =====================================================================
        # STATE-SPECIFIC LOGIC - runs every update
        # =====================================================================
        
        # Decrement timer (1 per AI update, so 1 = one UPDATE_FREQUENCY cycle)
        if entity.ai_state_timer > 0:
            entity.ai_state_timer -= 1
        
        # === TARGETING STATE ===
        if entity.ai_state == 'targeting':
            # Find target if we don't have one
            if not entity.current_target and entity.target_type:
                target = self.find_closest_target_by_type(entity, entity.target_type, screen_key)
                if target:
                    entity.current_target = target
                    if debug and entity.type == 'WARRIOR':
                        print(f"  -> [{entity.type}] Found target: {target}")
                else:
                    if debug and entity.type == 'WARRIOR':
                        print(f"  -> [{entity.type}] NO target found for type={entity.target_type}, switching to wandering")
                    entity.ai_state = 'wandering'
                    entity.current_target = None
                    entity.target_type = None
                    entity.ai_state_timer = 5  # Wander for a while before retrying
                    return
            
            # Have a target — check distance
            if entity.current_target:
                dist = self.get_target_distance(entity, entity.current_target)
                
                # Check if target is a hostile/enemy entity
                target_is_hostile = self._is_hostile_target(entity, entity.current_target)
                
                if debug and target_is_hostile and entity.type == 'WARRIOR':
                    print(f"  -> [{entity.type}] Targeting hostile entity, dist={dist}")
                
                # Adjacent to hostile → enter combat
                if target_is_hostile and dist <= 1:
                    if isinstance(entity.current_target, int) and entity.current_target in self.entities:
                        target_entity = self.entities[entity.current_target]
                        if target_entity.is_alive():
                            entity.ai_state = 'combat'
                            entity.ai_state_timer = 3
                            if debug and entity.type == 'WARRIOR':
                                print(f"  -> [{entity.type}] ENTERING COMBAT with {target_entity.type}!")
                            return
                        else:
                            entity.current_target = None
                            entity.ai_state = 'wandering'
                            entity.ai_state_timer = 2
                            return
                
                # Adjacent to non-hostile target → enter idle (perform action)
                elif not target_is_hostile and dist <= 1:
                    entity.ai_state = 'idle'
                    entity.ai_state_timer = 2
                    return
                
                # Target is valid but dead/gone — clear it
                if isinstance(entity.current_target, int):
                    if entity.current_target not in self.entities or not self.entities[entity.current_target].is_alive():
                        entity.current_target = None
                        entity.ai_state = 'wandering'
                        entity.ai_state_timer = 2
                        return
            else:
                # No target — switch to wandering
                entity.ai_state = 'wandering'
                entity.ai_state_timer = 2
                return
        
        # === COMBAT STATE ===
        if entity.ai_state == 'combat':
            if entity.current_target and isinstance(entity.current_target, int):
                if entity.current_target in self.entities and self.entities[entity.current_target].is_alive():
                    target_entity = self.entities[entity.current_target]
                    dist = abs(entity.x - target_entity.x) + abs(entity.y - target_entity.y)
                    if dist > 1:
                        # Target moved away — chase
                        entity.ai_state = 'targeting'
                        entity.ai_state_timer = 1
                        return
                    # else: stay in combat (attack handled in update_entity_ai)
                else:
                    # Target dead or invalid
                    entity.ai_state = 'wandering'
                    entity.current_target = None
                    entity.ai_state_timer = 2
                    return
            else:
                entity.ai_state = 'wandering'
                entity.current_target = None
                entity.ai_state_timer = 2
                return
        
        # =====================================================================
        # TIMER-BASED STATE TRANSITIONS (only when timer expired)
        # =====================================================================
        if entity.ai_state_timer > 0:
            return
        
        if entity.ai_state == 'idle':
            roll = random.random()
            if roll < aggressiveness:
                target_type = self.determine_target_type(entity)
                if target_type:
                    entity.ai_state = 'targeting'
                    entity.target_type = target_type
                    entity.current_target = None
                    entity.ai_state_timer = 2
                else:
                    # Nothing to target — wander instead
                    entity.ai_state = 'wandering'
                    entity.current_target = None
                    entity.ai_state_timer = 3
            elif roll < aggressiveness + passiveness:
                entity.ai_state = 'wandering'
                entity.current_target = None
                entity.ai_state_timer = 2
            else:
                entity.ai_state_timer = random.randint(2, 4)  # Stay idle with variable duration
        
        elif entity.ai_state == 'wandering':
            roll = random.random()
            if roll < aggressiveness:
                # Try to find something to target
                target_type = self.determine_target_type(entity)
                if target_type:
                    entity.ai_state = 'targeting'
                    entity.target_type = target_type
                    entity.current_target = None
                    entity.ai_state_timer = 2
                else:
                    # Nothing to target — keep wandering longer
                    entity.ai_state_timer = 3
            elif roll < aggressiveness + idleness:
                entity.ai_state = 'idle'
                entity.ai_state_timer = random.randint(2, 4)  # Variable idle duration
            else:
                entity.ai_state_timer = 2  # Keep wandering
        
        elif entity.ai_state == 'flee':
            # Done fleeing — wander
            entity.ai_state = 'wandering'
            entity.flee_target = None
            entity.ai_state_timer = 2
    
    def evaluate_entity_priorities(self, entity, entity_id):
        """Evaluate all possible actions and choose best based on weights and distance"""
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        if screen_key not in self.screens:
            return 'wander', None
        
        screen = self.screens[screen_key]
        is_follower = entity_id in self.followers
        
        # Build list of possible actions with scores
        actions = []
        
        # CHECK ADJACENT CELLS FIRST for immediate opportunities/threats
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    
                    # Adjacent enemy - very high priority for hostile entities
                    for other_id in self.screen_entities.get(screen_key, []):
                        if other_id in self.entities:
                            other = self.entities[other_id]
                            if other.x == check_x and other.y == check_y:
                                # Check if enemy
                                is_enemy = (entity.props.get('hostile') and not other.props.get('hostile')) or \
                                          (not entity.props.get('hostile') and other.props.get('hostile'))
                                if is_enemy and entity.priority_weights['attack'] > 0:
                                    actions.append(('attack', other_id, 1.0, entity.priority_weights['attack'] * 5.0))  # 5x bonus for adjacent
                    
                    # Adjacent food
                    food_sources = entity.props.get('food_sources', [])
                    if cell in food_sources and entity.hunger < 70:
                        actions.append(('food', (check_x, check_y), 1.0, entity.priority_weights['food'] * 3.0))
                    
                    # Adjacent water
                    water_sources = entity.props.get('water_sources', [])
                    if cell in water_sources and entity.thirst < 70:
                        actions.append(('water', (check_x, check_y), 1.0, entity.priority_weights['water'] * 3.0))
                    
                    # Adjacent structure (for goblins)
                    if entity.type == 'GOBLIN' and cell in ['CAMP', 'HOUSE']:
                        actions.append(('attack', (check_x, check_y, 'structure'), 1.0, entity.priority_weights['attack'] * 2.0))
        
        # SCAN FULL ZONE for targets
        # Water need
        if entity.thirst < 50 and entity.priority_weights['water'] > 0:
            water_sources = entity.props.get('water_sources', [])
            closest_water_dist = float('inf')
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if screen['grid'][y][x] in water_sources:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist < closest_water_dist:
                            closest_water_dist = dist
            if closest_water_dist < float('inf'):
                # Score based on distance and urgency
                urgency = (50 - entity.thirst) / 50.0  # 0 to 1
                distance_factor = max(0.1, 1.0 - (closest_water_dist / 20.0))
                score = entity.priority_weights['water'] * urgency * distance_factor
                actions.append(('water', None, closest_water_dist, score))
        
        # Food need
        if entity.hunger < 50 and entity.priority_weights['food'] > 0:
            food_sources = entity.props.get('food_sources', [])
            closest_food_dist = float('inf')
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    cell = screen['grid'][y][x]
                    if cell in food_sources:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist < closest_food_dist:
                            closest_food_dist = dist
            if closest_food_dist < float('inf'):
                urgency = (50 - entity.hunger) / 50.0
                distance_factor = max(0.1, 1.0 - (closest_food_dist / 20.0))
                score = entity.priority_weights['food'] * urgency * distance_factor
                actions.append(('food', None, closest_food_dist, score))
        
        # Attack targets (enemies in zone) - scan all and pick closest
        # GUARDS: Prioritize this MASSIVELY over everything else
        if entity.priority_weights['attack'] > 0 and not is_follower:
            closest_enemy = None
            closest_enemy_dist = float('inf')
            closest_faction_enemy = None
            closest_faction_dist = float('inf')
            
            for other_id in self.screen_entities.get(screen_key, []):
                if other_id in self.entities:
                    other = self.entities[other_id]
                    is_enemy = (entity.props.get('hostile') and not other.props.get('hostile')) or \
                              (not entity.props.get('hostile') and other.props.get('hostile'))
                    
                    # Check for faction warfare (warriors vs warriors of different factions)
                    is_faction_enemy = False
                    if entity.type == 'WARRIOR' and other.type == 'WARRIOR':
                        if entity.faction and other.faction and entity.faction != other.faction:
                            is_faction_enemy = True
                    
                    if is_enemy:
                        dist = abs(other.x - entity.x) + abs(other.y - entity.y)
                        if dist < closest_enemy_dist:
                            closest_enemy_dist = dist
                            closest_enemy = other_id
                    elif is_faction_enemy:
                        dist = abs(other.x - entity.x) + abs(other.y - entity.y)
                        if dist < closest_faction_dist:
                            closest_faction_dist = dist
                            closest_faction_enemy = other_id
            
            # Add attack action for closest enemy if found (hostile creatures - highest priority)
            if closest_enemy is not None:
                distance_factor = max(0.1, 1.0 - (closest_enemy_dist / 30.0))
                score = entity.priority_weights['attack'] * distance_factor
                
                # GUARDS: Boost attack priority to 10x if enemy found
                if entity.type == 'GUARD':
                    score *= 10.0
                
                actions.append(('attack', closest_enemy, closest_enemy_dist, score))
            
            # Add faction warfare attack (slightly lower priority than hostile creatures)
            if closest_faction_enemy is not None:
                distance_factor = max(0.1, 1.0 - (closest_faction_dist / 30.0))
                # Faction warfare priority: 80% of normal attack priority
                score = entity.priority_weights['attack'] * distance_factor * 0.8
                actions.append(('attack', closest_faction_enemy, closest_faction_dist, score))
        
        # Goblin special: loot and structures
        if entity.type == 'GOBLIN':
            # Check for dropped items
            if screen_key in self.dropped_items and self.dropped_items[screen_key]:
                closest_loot_dist = float('inf')
                for pos_key in self.dropped_items[screen_key].keys():
                    if isinstance(pos_key, tuple):
                        x, y = pos_key
                    else:
                        parts = pos_key.split(',')
                        x, y = int(parts[0]), int(parts[1])
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < closest_loot_dist:
                        closest_loot_dist = dist
                if closest_loot_dist < float('inf'):
                    distance_factor = max(0.2, 1.0 - (closest_loot_dist / 25.0))
                    score = 0.4 * distance_factor  # High priority for goblins
                    actions.append(('loot', None, closest_loot_dist, score))
            
            # Check for structures
            closest_structure_dist = float('inf')
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    if screen['grid'][y][x] in ['CAMP', 'HOUSE']:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist < closest_structure_dist:
                            closest_structure_dist = dist
            if closest_structure_dist < float('inf'):
                distance_factor = max(0.1, 1.0 - (closest_structure_dist / 30.0))
                score = 0.3 * distance_factor
                actions.append(('structure', None, closest_structure_dist, score))
        
        # Explore (move to zone exit) - all entities can explore
        if entity.priority_weights['explore'] > 0 and not is_follower:
            # Base explore score - higher level entities explore more
            score = entity.priority_weights['explore']
            
            # TRADERS: Massively boost exploration - they should ALWAYS be traveling
            if entity.type == 'TRADER' or entity.type == 'TRADER_double':
                score *= 20.0  # 20x boost - overwhelms everything except critical needs
            
            # GUARDS: Boost exploration if no enemies in zone
            if entity.type == 'GUARD' or entity.type == 'GUARD_double':
                has_enemies = False
                for other_id in self.screen_entities.get(screen_key, []):
                    if other_id in self.entities:
                        other = self.entities[other_id]
                        if other.props.get('hostile'):
                            has_enemies = True
                            break
                
                # If no enemies, boost explore to move to next zone
                if not has_enemies:
                    score *= 15.0  # 15x boost when zone is clear
            
            # Crowding bonus - peaceful NPCs want to leave if too many of same type
            if not entity.props.get('hostile'):
                same_type_count = 0
                for other_id in self.screen_entities.get(screen_key, []):
                    if other_id in self.entities:
                        other = self.entities[other_id]
                        if other.type == entity.type:
                            same_type_count += 1
                
                # Each duplicate adds 20% to explore score (not level)
                # So 2 farmers = +20%, 3 farmers = +40%, etc.
                if same_type_count > 1:
                    crowding_bonus = (same_type_count - 1) * 0.2
                    score += crowding_bonus
            
            # WARRIOR FACTION EXPANSION: If 2+ warriors of same faction in zone, explore together
            if entity.type == 'WARRIOR' and entity.faction:
                # Count warriors of same faction in zone
                same_faction_count = 0
                for other_id in self.screen_entities.get(screen_key, []):
                    if other_id in self.entities:
                        other = self.entities[other_id]
                        if other.type == 'WARRIOR' and other.faction == entity.faction:
                            same_faction_count += 1
                
                # If 2+ warriors of same faction, boost exploration to expand territory
                if same_faction_count >= 2:
                    # Check if zone is already controlled by this faction
                    controlling_faction = self.get_zone_controlling_faction(screen_key)
                    if controlling_faction == entity.faction:
                        # We control this zone, explore to expand
                        score *= 10.0  # Strong urge to expand territory
            
            actions.append(('explore', None, 0, score))
        
        # Wander (default low-priority action)
        if entity.priority_weights['wander'] > 0:
            score = entity.priority_weights['wander'] * 0.5  # Base wander score
            actions.append(('wander', None, 0, score))
        
        # Choose best action based on score
        if actions:
            actions.sort(key=lambda a: a[3], reverse=True)  # Sort by score
            best_action = actions[0]
            return best_action[0], best_action[1]  # Return (priority, target)
        
        return 'wander', None
    
    def find_and_attack_enemy(self, entity_id, entity):
        """Find enemies and attack them"""
        # Only skip combat if actively fleeing
        if hasattr(entity, 'ai_state') and entity.ai_state in ('fleeing', 'flee'):
            return  # Fleeing entities don't attack
        
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        
        closest_enemy = None
        closest_enemy_id = None
        closest_dist = float('inf')
        
        # Warriors scan full zone more aggressively - no distance limit
        is_warrior = entity.type in ['WARRIOR', 'COMMANDER', 'KING']
        
        # Find enemies on current screen
        for other_id in self.screen_entities.get(screen_key, []):
            if other_id == entity_id:
                continue
            
            # Safety check for None or invalid entity_id
            if other_id is None or other_id not in self.entities:
                continue
            
            other = self.entities[other_id]
            
            # Determine if this is an enemy
            is_enemy = False
            
            # Rule 1: Hostiles ALWAYS attack peaceful entities (highest priority)
            if entity.props.get('hostile', False) and not other.props.get('hostile', False):
                is_enemy = True
            # Rule 2: Peaceful entities with attacks_hostile attack hostile entities
            elif entity.props.get('attacks_hostile') and other.props.get('hostile'):
                is_enemy = True
            # Rule 3: Warriors/Guards target ALL hostile entities
            elif entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD'] and other.props.get('hostile', False):
                is_enemy = True
            # Rule 4: Same faction members are allies (only if both peaceful)
            elif entity.faction and other.faction and entity.faction == other.faction:
                if not entity.props.get('hostile', False) and not other.props.get('hostile', False):
                    is_enemy = False
            # Rule 5: Faction warfare - different factions are hostile
            elif entity.faction and other.faction and entity.faction != other.faction:
                is_enemy = True
            # Rule 6: Same creature type are friendly (unless different factions)
            elif entity.type == other.type:
                is_enemy = False
            # Rule 7: Predator-prey relationships
            elif entity.type in other.props.get('food_sources', []):
                is_enemy = True
            # Rule 8: Different types with no faction = potentially hostile
            elif entity.type != other.type and not entity.faction and not other.faction:
                if entity.props.get('hostile') or other.props.get('hostile'):
                    is_enemy = True
            
            if is_enemy:
                dist = abs(other.x - entity.x) + abs(other.y - entity.y)
                if dist < closest_dist:
                    closest_dist = dist
                    closest_enemy = other
                    closest_enemy_id = other_id
        
        # Check for player as potential enemy (only if in same subscreen state)
        if entity.props.get('hostile'):
            # Check if both entity and player are in same screen/subscreen
            entity_in_subscreen = hasattr(entity, 'in_subscreen') and entity.in_subscreen
            player_in_subscreen = self.player.get('in_subscreen', False)
            
            # Only attack if both in same state (both in overworld or both in same subscreen)
            can_attack_player = False
            if not entity_in_subscreen and not player_in_subscreen:
                # Both in overworld
                if entity.screen_x == self.player['screen_x'] and entity.screen_y == self.player['screen_y']:
                    can_attack_player = True
            elif entity_in_subscreen and player_in_subscreen:
                # Both in subscreen - check if same subscreen
                entity_subscreen = getattr(entity, 'subscreen_key', None)
                player_subscreen = self.player.get('subscreen_key', None)
                if entity_subscreen == player_subscreen:
                    can_attack_player = True
            
            if can_attack_player:
                player_dist = abs(self.player['x'] - entity.x) + abs(self.player['y'] - entity.y)
                if player_dist < closest_dist:
                    closest_dist = player_dist
                    closest_enemy = 'player'
                    closest_enemy_id = 'player'
        
        if closest_enemy:
            # DO NOT SET STATES - state machine handles all state transitions
            # This function ONLY attacks and shows animations
            
            # Determine if entity should flee (non-combat NPCs)
            is_combat_npc = entity.props.get('hostile', False) or entity.props.get('attacks_hostile', False) or entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD']
            
            # Non-combat NPCs flee from threats
            if not is_combat_npc:
                entity.is_fleeing = True
                entity.in_combat = False
                # Movement now handled by state machine (flee state)
                # DO NOT move here - would conflict with state machine movement
                
                # Occasional counterattack (10% chance when adjacent)
                if closest_dist <= 1 and random.random() < 0.1:
                    if closest_enemy == 'player':
                        damage = entity.strength * 0.25  # Weak counterattack
                        self.player_take_damage(damage)
                        self.show_attack_animation(self.player['x'], self.player['y'], entity=entity)
                    else:
                        damage = entity.strength * 0.25
                        magic_damage, magic_type = self.calculate_magic_damage(entity.inventory)
                        damage += magic_damage
                        if closest_enemy.combat_state == 'blocking':
                            damage *= (1 - closest_enemy.block_reduction)
                        closest_enemy.take_damage(damage, entity_id)
                        self.show_attack_animation(closest_enemy.x, closest_enemy.y, entity=entity, target_entity=closest_enemy, magic_type=magic_type)
                return
            
            # Combat NPCs face off and stand still
            entity.is_fleeing = False
            entity.in_combat = True
            entity.combat_target = closest_enemy_id
            
            # Update facing direction toward target
            if closest_enemy == 'player':
                dx = self.player['x'] - entity.x
                dy = self.player['y'] - entity.y
            else:
                dx = closest_enemy.x - entity.x
                dy = closest_enemy.y - entity.y
            
            # Set facing based on direction to target (prioritize larger distance)
            if abs(dx) > abs(dy):
                entity.facing = 'right' if dx > 0 else 'left'
            elif abs(dy) > abs(dx):
                entity.facing = 'down' if dy > 0 else 'up'
            else:
                # Equal distance, prioritize vertical
                if dy != 0:
                    entity.facing = 'down' if dy > 0 else 'up'
                else:
                    entity.facing = 'right' if dx > 0 else 'left'
            
            # If adjacent, stand still and attack
            if closest_dist <= 1:
                # STAND STILL - no movement, only attack
                # Combat entities lock in position when adjacent to enemy
                
                if closest_enemy == 'player':
                    damage = entity.strength
                    
                    # Add weapon bonus from inventory
                    damage += self.calculate_weapon_bonus(entity.inventory)
                    
                    # Add magic damage from runestones
                    magic_damage, magic_type = self.calculate_magic_damage(entity.inventory)
                    damage += magic_damage
                    
                    # Hostile entities do more damage (1.2x)
                    if entity.props.get('hostile', True):
                        damage *= 1.2
                    
                    self.player_take_damage(damage)
                    self.show_attack_animation(self.player['x'], self.player['y'], entity=entity, magic_type=magic_type)
                else:
                    damage = entity.strength
                    
                    # Add weapon bonus from inventory
                    damage += self.calculate_weapon_bonus(entity.inventory)
                    
                    # Add magic damage from runestones
                    magic_damage, magic_type = self.calculate_magic_damage(entity.inventory)
                    damage += magic_damage
                    
                    # Hostile entities do more damage (1.2x)
                    if entity.props.get('hostile', True):
                        damage *= 1.2
                    
                    # Apply blocking reduction
                    if closest_enemy.combat_state == 'blocking':
                        damage *= (1 - closest_enemy.block_reduction)
                    closest_enemy.take_damage(damage, entity_id)
                    self.show_attack_animation(closest_enemy.x, closest_enemy.y, entity=entity, target_entity=closest_enemy, magic_type=magic_type)
                    
                    # Grant XP from hit: only target's level
                    xp_gain = closest_enemy.level
                    entity.xp += xp_gain
                    if entity.xp >= entity.xp_to_level:
                        entity.level_up()
                    
                    # Auto meat consumption for combat entities (Warriors/Guards/Commanders/Kings)
                    if entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD']:
                        low_health = entity.health < entity.max_health * 0.5
                        low_hunger = entity.hunger < entity.max_hunger * 0.3
                        
                        if (low_health or low_hunger) and 'meat' in entity.inventory and entity.inventory['meat'] > 0:
                            # Consume meat: heal 25% max health and restore hunger
                            entity.inventory['meat'] -= 1
                            heal_amount = entity.max_health * 0.25
                            entity.health = min(entity.max_health, entity.health + heal_amount)
                            entity.hunger = min(entity.max_hunger, entity.hunger + 50)
                            print(f"{entity.name or entity.type} consumed meat and healed {int(heal_amount)} HP!")
                    
                    # Check if enemy died and handle king promotion
                    if not closest_enemy.is_alive():
                        # Commander killing a king is promoted to king
                        if entity.type == 'COMMANDER' and closest_enemy.type == 'KING' and entity.faction:
                            old_name = entity.name
                            entity.type = 'KING'
                            entity.props = ENTITY_TYPES['KING']
                            entity.max_health = entity.props['max_health'] * entity.level
                            entity.strength = entity.props['strength'] * entity.level
                            
                            # Full restore
                            entity.health = entity.max_health
                            entity.hunger = entity.max_hunger
                            entity.thirst = entity.max_thirst
                            
                            print(f"{old_name} slew a KING and claims the throne of {entity.faction}!")
            else:
                # Not adjacent - movement handled by state machine (targeting state)
                # DO NOT set states here
                # Check if low health - let state machine handle flee decision
                if entity.health < entity.max_health * 0.3 and random.random() < 0.4:
                    # Mark as fleeing for other systems, but don't change state
                    entity.is_fleeing = True
                    entity.in_combat = False
                # Normal pursuit movement handled by state machine (targeting state)
        else:
            # No enemy found in current zone
            entity.in_combat = False
            entity.combat_target = None
            entity.is_fleeing = False
            
            # Wandering handled by state machine
    
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
            
            # Check bounds - allow edge cells but not out of grid
            if new_x < 0 or new_x >= GRID_WIDTH or new_y < 0 or new_y >= GRID_HEIGHT:
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

    def _assign_specific_quest_target(self, entity, screen_key):
        """Pick a specific quest target cell/entity for a 'specific' quest cycle.
        Only called ~20% of the time every 10 AI updates.  Stores result in
        entity.quest_target; if nothing suitable found, quest_target stays None (general mode)."""
        focus = getattr(entity, 'quest_focus', None)
        if not focus:
            return

        target = None

        if focus == 'farming':
            target = self._find_closest_crop(entity, screen_key)
            if target is None and entity.level >= 5:
                for dsx, dsy in [(1, 0), (-1, 0), (0, 1), (0, -1)]:
                    adj = f"{entity.screen_x + dsx},{entity.screen_y + dsy}"
                    target = self._find_closest_crop(entity, adj)
                    if target:
                        break

        elif focus == 'building':
            target = self._find_closest_tree(entity, screen_key)
            if target is None:
                target = self.find_closest_structure(entity, screen_key)

        elif focus == 'mining':
            target = self._find_closest_stone(entity, screen_key)

        elif focus == 'crafting':
            target = self.find_closest_structure(entity, screen_key)

        elif focus == 'exploring':
            exits = [
                (GRID_WIDTH // 2, 1),
                (GRID_WIDTH // 2, GRID_HEIGHT - 2),
                (1,               GRID_HEIGHT // 2),
                (GRID_WIDTH - 2,  GRID_HEIGHT // 2),
            ]
            ex, ey = random.choice(exits)
            target = ('cell', ex, ey, 'EXIT')

        elif focus == 'combat_hostile':
            target = self.find_closest_hostile_entity(entity, screen_key)

        elif focus == 'combat_all':
            target = self._find_closest_any_entity(entity, screen_key)
            if target is None:
                exits = [
                    (GRID_WIDTH // 2, 1),
                    (GRID_WIDTH // 2, GRID_HEIGHT - 2),
                    (1,               GRID_HEIGHT // 2),
                    (GRID_WIDTH - 2,  GRID_HEIGHT // 2),
                ]
                ex, ey = random.choice(exits)
                target = ('cell', ex, ey, 'EXIT')

        # Never assign the entity's own cell as a target
        if isinstance(target, tuple) and len(target) >= 3 and target[0] == 'cell':
            if (target[1], target[2]) == (entity.x, entity.y):
                target = None

        entity.quest_target = target
    
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
    
    def update_entity_combat_state(self, entity):
        """Update entity combat state (blocking/evading/attacking)"""
        # Hostile entities are aggressive - mostly attacking
        if entity.props.get('hostile'):
            # Hostile entities mostly attack
            if self.tick - entity.last_state_change > random.randint(60, 180):  # 1-3 seconds
                if entity.type == 'SKELETON':
                    entity.combat_state = 'attacking'  # Always attacking
                    entity.last_state_change = self.tick
                elif entity.type in ['WOLF', 'BANDIT']:
                    states = ['attacking', 'blocking']
                    weights = [0.85, 0.15]  # 85% attacking, 15% blocking
                    entity.combat_state = random.choices(states, weights)[0]
                    entity.last_state_change = self.tick
                elif entity.type == 'GOBLIN':
                    states = ['attacking', 'blocking']
                    weights = [0.75, 0.25]  # 75% attacking, 25% blocking
                    entity.combat_state = random.choices(states, weights)[0]
                    entity.last_state_change = self.tick
                else:
                    states = ['attacking', 'blocking']
                    weights = [0.80, 0.20]  # Default: mostly attacking
                    entity.combat_state = random.choices(states, weights)[0]
                    entity.last_state_change = self.tick
        
        # Peaceful entities flee when threatened (evading state)
        else:
            entity.combat_state = 'evading'
            entity.last_state_change = self.tick

    def determine_target_type(self, entity):
        """Determine what to target based on needs and available targets in zone"""
        low_hunger = entity.hunger < entity.max_hunger * 0.3
        low_thirst = entity.thirst < entity.max_thirst * 0.3
        low_health = entity.health < entity.max_health * 0.5
        
        screen_key = f"{entity.screen_x},{entity.screen_y}"

        # ── Quest-focus system ────────────────────────────────────────────────
        # Two modes:
        #   SPECIFIC  — entity.quest_target is a cell tuple; navigate to it,
        #               complete on proximity (dist ≤ 2), then switch to general.
        #   GENERAL   — entity.quest_target is None; fall through to default NPC
        #               behavior (action_harvest_cell / wander etc. as normal).
        #               Every ~10 AI updates, 20% chance to assign a specific target.
        #               Survival needs (extreme hunger/thirst) preempt both modes.
        # ─────────────────────────────────────────────────────────────────────
        quest_focus = getattr(entity, 'quest_focus', None)
        if quest_focus and not low_hunger and not low_thirst:

            # Initialise update counter
            if not hasattr(entity, '_quest_update_counter'):
                entity._quest_update_counter = 0
            entity._quest_update_counter += 1

            specific = getattr(entity, 'quest_target', None)

            if specific is not None:
                # SPECIFIC MODE — check proximity; complete early if within 2 cells
                if isinstance(specific, tuple) and len(specific) >= 3 and specific[0] == 'cell':
                    tx, ty = specific[1], specific[2]
                    dist = abs(entity.x - tx) + abs(entity.y - ty)
                    if dist <= 2:
                        # Close enough — treat as completed, drop back to general
                        entity.quest_target = None
                        entity._quest_update_counter = 0
                        # Fall through to general / default behavior this cycle
                    else:
                        # Still heading there
                        return 'quest_target'
                elif isinstance(specific, int):
                    # Entity target — still alive and reachable?
                    if specific in self.entities and self.entities[specific].is_alive():
                        dist = self.get_target_distance(entity, specific)
                        if dist <= 2:
                            entity.quest_target = None
                            entity._quest_update_counter = 0
                        else:
                            return 'quest_target'
                    else:
                        entity.quest_target = None
                        entity._quest_update_counter = 0

            # GENERAL MODE — every ~10 updates, 20% chance to assign a specific target
            if entity.quest_target is None and entity._quest_update_counter >= 10:
                entity._quest_update_counter = 0
                if random.random() < 0.20:
                    self._assign_specific_quest_target(entity, screen_key)
                    if entity.quest_target is not None:
                        return 'quest_target'   # new specific target just assigned

            # Still in general mode — return None so the entity wanders and lets
            # the tick%60 execute_npc_behavior handle the actual work actions.
            if entity.quest_target is None:
                return None
        # ─────────────────────────────────────────────────────────────────────
        
        # Priority: survival needs (only if target exists in zone)
        if low_thirst and 'water' in entity.target_types:
            if self.find_closest_target_by_type(entity, 'water', screen_key):
                return 'water'
        if low_hunger and 'food' in entity.target_types:
            if self.find_closest_target_by_type(entity, 'food', screen_key):
                return 'food'
        if low_health and 'structure' in entity.target_types:
            if self.find_closest_target_by_type(entity, 'structure', screen_key):
                return 'structure'
        
        # Specialty targets — pick randomly but verify existence
        specialty = [t for t in entity.target_types if t not in ['food', 'water', 'structure']]
        if specialty:
            random.shuffle(specialty)
            for t in specialty:
                if self.find_closest_target_by_type(entity, t, screen_key):
                    return t
        
        # Fall back to any available target type
        all_types = list(entity.target_types)
        random.shuffle(all_types)
        for t in all_types:
            if self.find_closest_target_by_type(entity, t, screen_key):
                return t
        
        # Nothing available at all
        return None
    
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
    
    def execute_entity_behavior(self, entity, behavior_config):
        """Consolidated behavior system - executes actions based on behavior_config"""
        actions = behavior_config.get('actions', [])
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        
        if screen_key not in self.screens:
            return
        
        # Randomly pick ONE action to attempt (prevents doing multiple actions per update)
        if actions:
            action = random.choice(actions)
            if action == 'harvest':
                self.try_harvest_crop(entity, screen_key)
                return  # Only one action per update
            elif action == 'till':
                self.try_till_soil(entity, screen_key)
                return
            elif action == 'plant':
                self.try_plant_seed(entity, screen_key)
                return
            elif action == 'chop_trees':
                self.try_chop_tree(entity, screen_key)
                return
            elif action == 'mine_rocks':
                self.try_mine_rock(entity, screen_key)
                return
            elif action == 'build_house':
                self.try_build_house(entity, screen_key)
                return
            elif action == 'build_forge':
                self.try_build_forge(entity, screen_key)
                return
            elif action == 'travel':
                self.try_travel_behavior(entity, screen_key)
                return
            elif action == 'build_path':
                self.try_build_path(entity, screen_key)
                return
            elif action == 'patrol':
                self.try_patrol_behavior(entity, screen_key)
                return
            elif action == 'cast_spell':
                self.try_wizard_cast_spell(entity, screen_key)
                return
            elif action == 'explore_cave':
                self.try_wizard_explore_cave(entity, screen_key)
                return
            elif action == 'seek_rune':
                self.try_wizard_seek_rune(entity, screen_key)
                return
        
        # If no actions or action didn't succeed, try secondary behaviors
        # All peaceful NPCs can occasionally trade with nearby NPCs
        if not entity.props.get('hostile', False):
            self.try_npc_trade(entity, screen_key)
        
        # Wander if configured
        if behavior_config.get('wander_when_idle'):
            self.wander_entity(entity)
    
    # Helper methods for specific actions
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
    
    def hostile_structure_behavior(self, entity):
        """Goblins and bandits attack camps and houses, pick up items, and place loot chests
        Termites attack trees and structures"""
        # Determine which screen the entity is actually in
        if hasattr(entity, 'in_subscreen') and entity.in_subscreen and entity.subscreen_key:
            screen_key = entity.subscreen_key
            if screen_key not in self.subscreens:
                return
            screen = self.subscreens[screen_key]
        else:
            screen_key = entity.screen_key
            if screen_key not in self.screens:
                return
            screen = self.screens[screen_key]
        
        did_action = False  # Track if we did something
        
        # TERMITE BEHAVIOR - prioritize trees and structures
        if entity.type == 'TERMITE':
            # Priority 1: Attack adjacent trees (cardinal directions only)
            for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
                check_x = entity.x + dx
                check_y = entity.y + dy
                
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    
                    # Attack trees - high chance
                    if cell in ['TREE1', 'TREE2']:
                        entity.update_facing_toward(check_x, check_y)
                        entity.trigger_action_animation()
                        self.show_attack_animation(check_x, check_y, entity=entity)
                        if random.random() < 0.15:  # 15% chance
                            screen['grid'][check_y][check_x] = 'DIRT'  # Trees decay to dirt when termites destroy them
                            # Termite eats the tree
                            entity.hunger = min(entity.max_hunger, entity.hunger + 30)
                            if random.random() < 0.1:
                                print(f"Termite consumed a tree at [{screen_key}]")
                        return  # Only one action per update
                    
                    # Attack wooden structures - medium chance
                    elif cell in ['CAMP', 'HOUSE']:
                        entity.update_facing_toward(check_x, check_y)
                        entity.trigger_action_animation()
                        self.show_attack_animation(check_x, check_y, entity=entity)
                        if cell == 'CAMP' and random.random() < 0.08:  # 8% chance
                            screen['grid'][check_y][check_x] = 'GRASS'
                            entity.hunger = min(entity.max_hunger, entity.hunger + 15)
                            if random.random() < 0.2:
                                print(f"Termite destroyed a camp at [{screen_key}]")
                        elif cell == 'HOUSE' and random.random() < 0.03:  # 3% chance
                            screen['grid'][check_y][check_x] = 'GRASS'
                            entity.hunger = min(entity.max_hunger, entity.hunger + 20)
                            print(f"Termite destroyed a house at [{screen_key}]!")
                        return  # Only one action per update
            
            # Priority 2: Move toward nearest tree or structure
            nearest_target_x, nearest_target_y = None, None
            nearest_dist = float('inf')
            
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    cell = screen['grid'][y][x]
                    if cell in ['TREE1', 'TREE2', 'CAMP', 'HOUSE']:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist < nearest_dist:
                            nearest_dist = dist
                            nearest_target_x, nearest_target_y = x, y
            
            if nearest_target_x is not None and nearest_dist > 1:
                self.move_entity_towards(entity, nearest_target_x, nearest_target_y)
                return
            
            # No targets found - wander
            self.wander_entity(entity)
            return
        
        # GOBLIN/BANDIT BEHAVIOR (original code)
        # PRIORITY 1: Pick up items from ground (goblins are looters)
        if entity.type == 'GOBLIN' and screen_key in self.dropped_items and self.dropped_items[screen_key]:
            # Check for items at current position first
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    check_x = entity.x + dx
                    check_y = entity.y + dy
                    if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                        pos_key_str = f"{check_x},{check_y}"
                        pos_key_tuple = (check_x, check_y)
                        
                        # Check both key formats
                        for pos_key in [pos_key_str, pos_key_tuple]:
                            if pos_key in self.dropped_items[screen_key]:
                                items_at_pos = self.dropped_items[screen_key][pos_key]
                                
                                # Pick up all items
                                for item_name, count in list(items_at_pos.items()):
                                    entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                                
                                # Clear the drop
                                del self.dropped_items[screen_key][pos_key]
                                did_action = True
                                
                                # Move toward this position if not already there
                                if dx != 0 or dy != 0:
                                    self.move_entity_towards(entity, check_x, check_y)
                                    return  # Moving toward loot
            
            # If we picked up items, we're done for this tick
            if did_action:
                return
            
            # Items exist but not adjacent - move toward closest
            closest_loot_x, closest_loot_y = None, None
            closest_loot_dist = float('inf')
            for pos_key in self.dropped_items[screen_key].keys():
                if isinstance(pos_key, tuple):
                    x, y = pos_key
                else:
                    parts = pos_key.split(',')
                    x, y = int(parts[0]), int(parts[1])
                dist = abs(x - entity.x) + abs(y - entity.y)
                if dist < closest_loot_dist:
                    closest_loot_dist = dist
                    closest_loot_x, closest_loot_y = x, y
            
            if closest_loot_x is not None:
                self.move_entity_towards(entity, closest_loot_x, closest_loot_y)
                return  # Moving toward loot
        
        # PRIORITY 2: Place chest with loot (goblins hoard treasure)
        if entity.type == 'GOBLIN' and entity.inventory and random.random() < 0.005:  # 0.5% chance
            # Find empty adjacent spot
            for dy in range(-1, 2):
                for dx in range(-1, 2):
                    if dx == 0 and dy == 0:
                        continue
                    check_x = entity.x + dx
                    check_y = entity.y + dy
                    if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                        cell = screen['grid'][check_y][check_x]
                        # Check if valid placement location (ground/floor cells)
                        if cell in ['GRASS', 'DIRT', 'SAND', 'FLOOR_WOOD', 'CAVE_FLOOR']:
                            # Store the background cell before placing chest
                            background_cell = cell
                            
                            # Place chest
                            screen['grid'][check_y][check_x] = 'CHEST'
                            chest_key = f"{screen_key}:{check_x},{check_y}"
                            
                            # Add goblin's inventory to chest
                            chest_loot = dict(entity.inventory)
                            
                            # Add some default treasure
                            chest_loot['gold'] = chest_loot.get('gold', 0) + random.randint(5, 15)
                            if random.random() < 0.3:
                                chest_loot['wood'] = chest_loot.get('wood', 0) + random.randint(2, 5)
                            if random.random() < 0.2:
                                chest_loot['stone'] = chest_loot.get('stone', 0) + random.randint(1, 3)
                            
                            # Store in chest system with background cell info
                            if not hasattr(self, 'chest_contents'):
                                self.chest_contents = {}
                            if not hasattr(self, 'chest_backgrounds'):
                                self.chest_backgrounds = {}
                            
                            self.chest_contents[chest_key] = chest_loot
                            self.chest_backgrounds[chest_key] = background_cell  # Store background for rendering
                            
                            # Clear goblin inventory
                            entity.inventory.clear()
                            
                            print(f"Goblin placed a treasure chest at [{screen_key}]")
                            return
        
        # PRIORITY 3: Attack adjacent structures
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_x = entity.x + dx
                check_y = entity.y + dy
                
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    
                    # Attack camps - higher chance
                    if cell == 'CAMP' and random.random() < 0.05:  # 5% chance
                        entity.update_facing_toward(check_x, check_y)
                        entity.trigger_action_animation()
                        self.show_attack_animation(check_x, check_y, entity=entity)
                        screen['grid'][check_y][check_x] = 'GRASS'
                        if random.random() < 0.2:
                            name_str = entity.name if entity.name else entity.type
                            print(f"{name_str} destroyed a camp at [{screen_key}]")
                        return
                    
                    # Attack houses - very low chance
                    elif cell == 'HOUSE' and random.random() < 0.01:  # 1% chance
                        entity.update_facing_toward(check_x, check_y)
                        entity.trigger_action_animation()
                        self.show_attack_animation(check_x, check_y, entity=entity)
                        screen['grid'][check_y][check_x] = 'GRASS'
                        name_str = entity.name if entity.name else entity.type
                        print(f"{name_str} destroyed a house at [{screen_key}]!")
                        return
        
        # PRIORITY 4: Move toward nearest structure if found
        nearest_structure_x, nearest_structure_y = None, None
        nearest_dist = float('inf')
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in ['CAMP', 'HOUSE']:
                    dist = abs(x - entity.x) + abs(y - entity.y)
                    if dist < nearest_dist:
                        nearest_dist = dist
                        nearest_structure_x, nearest_structure_y = x, y
        
        # Move toward structure if found
        if nearest_structure_x is not None and nearest_dist > 1:
            self.move_entity_towards(entity, nearest_structure_x, nearest_structure_y)
            return
        
        # NO TARGETS FOUND - This goblin should explore to find new zones with targets
        # Don't just stand idle - the priority system should handle this by giving
        # them 'explore' priority on the next evaluation, so just wander this tick
        self.wander_entity(entity)
    
    def farmer_behavior(self, entity):
        """Farmer AI: harvest crops, till soil, plant crops"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        
        # Check adjacent cells for crops to harvest
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_x = entity.x + dx
                check_y = entity.y + dy
                
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    
                    # Harvest mature crops (CARROT2, CARROT3)
                    if cell in ['CARROT2', 'CARROT3']:
                        harvest_data = CELL_TYPES[cell].get('harvest')
                        if harvest_data and random.random() < FARMER_HARVEST_RATE:
                            item = harvest_data['item']
                            amount = harvest_data['amount']
                            entity.inventory[item] = entity.inventory.get(item, 0) + amount
                            screen['grid'][check_y][check_x] = 'SOIL'
                            
                            # Chance to level up from harvesting
                            entity.level_up_from_activity('harvest', self)
                            
                            # 5% chance to log action
                            if random.random() < 0.05:
                                name_str = entity.name if entity.name else "Farmer"
                                print(f"{name_str} harvested {amount} {item}(s) at [{screen_key}]")
                            return
                    
                    # Till grass or dirt to soil
                    if cell in ['GRASS', 'DIRT'] and random.random() < FARMER_TILL_RATE:
                        screen['grid'][check_y][check_x] = 'SOIL'
                        
                        # 5% chance to log action
                        if random.random() < 0.05:
                            print(f"Farmer tilled soil at [{screen_key}]")
                        return
                    
                    # Plant crops on soil
                    if cell == 'SOIL' and random.random() < FARMER_PLANT_RATE:
                        # Check if has carrot in inventory
                        if entity.inventory.get('carrot', 0) > 0:
                            entity.inventory['carrot'] -= 1
                            screen['grid'][check_y][check_x] = 'CARROT1'
                            
                            # 5% chance to log action
                            if random.random() < 0.05:
                                print(f"Farmer planted crops at [{screen_key}]")
                            return
    
    def lumberjack_behavior(self, entity):
        """Lumberjack AI: chop trees, build houses"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        
        # Count nearby trees
        nearby_trees = 0
        for dy in range(-3, 4):
            for dx in range(-3, 4):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if screen['grid'][check_y][check_x].startswith('TREE'):
                        nearby_trees += 1
        
        # Chopping probability scales with tree density
        base_chop_chance = 0.1
        tree_density_bonus = min(nearby_trees * 0.02, 0.3)  # Up to 30% bonus
        chop_chance = base_chop_chance + tree_density_bonus
        
        # Check adjacent cells for trees
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                check_x = entity.x + dx
                check_y = entity.y + dy
                
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    
                    # Chop trees with density-based probability
                    if cell.startswith('TREE') and random.random() < chop_chance:
                        # Add wood to inventory
                        wood_amount = 2 if cell == 'TREE1' else 3
                        entity.inventory['wood'] = entity.inventory.get('wood', 0) + wood_amount
                        screen['grid'][check_y][check_x] = 'GRASS'
                        
                        # Chance to level up from chopping
                        entity.level_up_from_activity('chop', self)
                        return
        
        # Count houses in current screen
        house_count = 0
        for row in screen['grid']:
            for cell in row:
                if cell == 'HOUSE':
                    house_count += 1
        
        # Build house if less than 3 and has enough wood
        if house_count < 3 and entity.inventory.get('wood', 0) >= 10 and random.random() < LUMBERJACK_BUILD_RATE:
            # First, try to find spots near cobblestone (preferred)
            cobble_spots = []
            for build_y in range(2, GRID_HEIGHT - 3):
                for build_x in range(2, GRID_WIDTH - 3):
                    cell = screen['grid'][build_y][build_x]
                    if cell in ['GRASS', 'DIRT']:
                        # Check if cobblestone is nearby (within 2 cells)
                        has_nearby_cobble = False
                        for dy in range(-2, 3):
                            for dx in range(-2, 3):
                                check_x = build_x + dx
                                check_y = build_y + dy
                                if (0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT):
                                    if screen['grid'][check_y][check_x] == 'COBBLESTONE':
                                        has_nearby_cobble = True
                                        break
                            if has_nearby_cobble:
                                break
                        
                        if has_nearby_cobble:
                            cobble_spots.append((build_x, build_y))
            
            # If cobblestone spots found, prefer those (75% chance)
            if cobble_spots and random.random() < 0.75:
                build_x, build_y = random.choice(cobble_spots)
                # Double-check cell is still valid (not stone/solid)
                if screen['grid'][build_y][build_x] in ['GRASS', 'DIRT']:
                    entity.inventory['wood'] -= 10
                    screen['grid'][build_y][build_x] = 'HOUSE'
                    
                    # Chance to level up from building
                    entity.level_up_from_activity('build', self)
                    
                    name_str = entity.name if entity.name else "Lumberjack"
                    print(f"{name_str} built a house at [{screen_key}] ({build_x}, {build_y})")
                    return
            
            # Otherwise, build anywhere suitable
            for _ in range(20):
                build_x = random.randint(2, GRID_WIDTH - 3)
                build_y = random.randint(2, GRID_HEIGHT - 3)
                
                cell = screen['grid'][build_y][build_x]
                if cell in ['GRASS', 'DIRT']:
                    entity.inventory['wood'] -= 10
                    screen['grid'][build_y][build_x] = 'HOUSE'
                    
                    # Chance to level up from building
                    entity.level_up_from_activity('build', self)
                    
                    name_str = entity.name if entity.name else "Lumberjack"
                    print(f"{name_str} built a house at [{screen_key}] ({build_x}, {build_y})")
                    return
    
    def guard_behavior(self, entity):
        """Guard AI: Patrol center lanes, build cobblestone, hunt hostiles"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        
        # Path building on center lanes (same as traders but guards stay on patrol)
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        
        near_horizontal_line = abs(entity.y - center_y) <= 3
        near_vertical_line = abs(entity.x - center_x) <= 3
        
        # Build paths while patrolling
        if near_horizontal_line or near_vertical_line:
            current_cell = screen['grid'][entity.y][entity.x]
            
            # Convert grass/soil to dirt
            if current_cell in ['GRASS', 'SOIL'] and random.random() < TRADER_PATH_BUILD_RATE:
                screen['grid'][entity.y][entity.x] = 'DIRT'
            
            # Upgrade dirt to cobblestone (guards help establish safe roads)
            elif current_cell == 'DIRT' and random.random() < TRADER_COBBLE_RATE:
                on_horizontal_center = abs(entity.y - center_y) <= 2
                on_vertical_center = abs(entity.x - center_x) <= 2
                
                if on_horizontal_center or on_vertical_center:
                    screen['grid'][entity.y][entity.x] = 'COBBLESTONE'
        
        # Combat focus: Scan zone for hostile entities
        if screen_key in self.screen_entities:
            hostile_found = None
            min_dist = float('inf')
            
            for eid in self.screen_entities[screen_key]:
                if eid in self.entities:
                    other = self.entities[eid]
                    if other.props.get('hostile'):
                        dist = abs(entity.x - other.x) + abs(entity.y - other.y)
                        if dist < min_dist:
                            min_dist = dist
                            hostile_found = other
            
            # If hostile found, move to attack
            if hostile_found:
                # 5% chance to log engagement
                if min_dist <= 10 and random.random() < 0.05:
                    name_str = entity.name if entity.name else "Guard"
                    print(f"{name_str} engaging {hostile_found.type} at [{screen_key}]")
                
                self.move_entity_towards(entity, hostile_found.x, hostile_found.y)
                return  # Don't patrol while in combat
        
        # Patrol behavior: Move along center lanes
        if not hasattr(entity, 'patrol_target') or entity.patrol_target is None:
            # Choose patrol point on center lanes
            patrol_points = [
                (center_x, 5),              # Top center
                (center_x, GRID_HEIGHT - 6), # Bottom center
                (5, center_y),              # Left center
                (GRID_WIDTH - 6, center_y)  # Right center
            ]
            entity.patrol_target = random.choice(patrol_points)
        
        # Move toward patrol point
        if entity.patrol_target:
            target_x, target_y = entity.patrol_target
            dist = abs(entity.x - target_x) + abs(entity.y - target_y)
            
            if dist <= 2:
                # Reached patrol point, choose new one immediately
                patrol_points = [
                    (center_x, 5),
                    (center_x, GRID_HEIGHT - 6),
                    (5, center_y),
                    (GRID_WIDTH - 6, center_y)
                ]
                # Don't choose the same point
                available_points = [p for p in patrol_points if p != entity.patrol_target]
                entity.patrol_target = random.choice(available_points) if available_points else random.choice(patrol_points)
            else:
                # Move toward patrol point
                self.move_entity_towards(entity, target_x, target_y)
    
    def trader_behavior(self, entity):
        """Trader AI: Travel between zone exits, build paths (cellular automata)"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        
        # Path building: Only build paths when reasonably aligned with exits
        # This ensures paths go through the middle of zones, not random wandering
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        
        # Check if trader is near horizontal or vertical centerlines (±3 cells tolerance)
        near_horizontal_line = abs(entity.y - center_y) <= 3
        near_vertical_line = abs(entity.x - center_x) <= 3
        
        # Only build paths when aligned with main thoroughfares
        if near_horizontal_line or near_vertical_line:
            current_cell = screen['grid'][entity.y][entity.x]
            
            # Convert grass/soil to dirt (wearing down path)
            if current_cell in ['GRASS', 'SOIL'] and random.random() < TRADER_PATH_BUILD_RATE:
                screen['grid'][entity.y][entity.x] = 'DIRT'
            
            # Upgrade dirt to cobblestone - ONLY in exact center lanes (±2 cells)
            elif current_cell == 'DIRT' and random.random() < TRADER_COBBLE_RATE:
                # Stricter alignment check for cobblestone (±2 instead of ±3)
                on_horizontal_center = abs(entity.y - center_y) <= 2
                on_vertical_center = abs(entity.x - center_x) <= 2
                
                # Only create cobblestone if on one of the main center lanes
                if on_horizontal_center or on_vertical_center:
                    screen['grid'][entity.y][entity.x] = 'COBBLESTONE'
        
        # Travel behavior: Move toward zone exits
        if not hasattr(entity, 'target_exit') or entity.target_exit is None:
            # Choose a random exit to head toward
            available_exits = []
            if screen['exits']['top']:
                available_exits.append(('top', GRID_WIDTH // 2, 1))
            if screen['exits']['bottom']:
                available_exits.append(('bottom', GRID_WIDTH // 2, GRID_HEIGHT - 2))
            if screen['exits']['left']:
                available_exits.append(('left', 1, GRID_HEIGHT // 2))
            if screen['exits']['right']:
                available_exits.append(('right', GRID_WIDTH - 2, GRID_HEIGHT // 2))
            
            if available_exits:
                entity.target_exit = random.choice(available_exits)
        
        # Move toward target exit
        if entity.target_exit:
            exit_name, target_x, target_y = entity.target_exit
            
            # Check if reached exit
            dist_to_exit = abs(entity.x - target_x) + abs(entity.y - target_y)
            if dist_to_exit <= 1:
                # At exit - try to cross to next zone
                entity.seeking_exit = True
                entity.target_exit = None  # Will choose new exit in next zone
            else:
                # Move toward exit
                self.move_entity_towards(entity, target_x, target_y)
        
        # Check for NPC transformation (e.g., trader settlement)
        transformation = self.check_npc_transformation(entity_id, entity)
        if transformation:
            return  # NPC transformed, skip normal behavior this tick
    
    def npc_seek_shelter(self, entity):
        """NPCs seek shelter (house/camp) at night and enter idle state when there"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return False
        
        screen = self.screens[screen_key]
        
        # Initialize idle state if not present
        if not hasattr(entity, 'is_idle'):
            entity.is_idle = False
        
        # Check for threats - break idle state
        if entity.is_idle:
            # Check for hostiles nearby
            has_threat = False
            if screen_key in self.screen_entities:
                for eid in self.screen_entities[screen_key]:
                    if eid in self.entities:
                        other = self.entities[eid]
                        if other.props.get('hostile'):
                            dist = abs(entity.x - other.x) + abs(entity.y - other.y)
                            if dist <= 5:  # Threat within 5 cells
                                has_threat = True
                                break
            
            # Break idle if threatened or low resources (nighttime check disabled)
            if has_threat or entity.hunger < 30 or entity.thirst < 30:
                entity.is_idle = False
                return False
            
            # Stay idle - don't move
            return True
        
        # Find nearest shelter (HOUSE preferred, then CAMP)
        nearest_house = None
        nearest_camp = None
        min_house_dist = float('inf')
        min_camp_dist = float('inf')
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                dist = abs(entity.x - x) + abs(entity.y - y)
                
                if cell == 'HOUSE' and dist < min_house_dist:
                    min_house_dist = dist
                    nearest_house = (x, y)
                elif cell == 'CAMP' and dist < min_camp_dist:
                    min_camp_dist = dist
                    nearest_camp = (x, y)
        
        # Move toward nearest shelter (prefer house)
        if nearest_house and min_house_dist <= 15:
            if min_house_dist <= 1:
                # Adjacent to house — enter it
                hx, hy = nearest_house
                self.npc_enter_subscreen(entity, screen_key, hx, hy, 'HOUSE')
                entity.is_idle = True
                return True
            else:
                entity.is_idle = False
                self.move_entity_towards(entity, nearest_house[0], nearest_house[1])
                return True
        
        elif nearest_camp and min_camp_dist <= 15:
            if min_camp_dist <= 2:
                entity.is_idle = True
                return True
            else:
                entity.is_idle = False
                self.move_entity_towards(entity, nearest_camp[0], nearest_camp[1])
                return True
        
        # No shelter nearby - not idle
        entity.is_idle = False
        return False  # No shelter found or too far
    
    def check_npc_transformation(self, entity_id, entity):
        """General function to check if NPC should transform to new type
        
        Returns True if transformation occurred, False otherwise
        """
        entity_type = entity.type
        
        # Check if this entity type has transformation config
        if entity_type not in NPC_TRANSFORMATION_CONFIG:
            return False
        
        config = NPC_TRANSFORMATION_CONFIG[entity_type]
        
        # Check transformation chance
        if random.random() >= config['transform_rate']:
            return False
        
        # Handle different transformation logic types
        logic_type = config.get('transform_logic', 'simple')
        
        if logic_type == 'settlement':
            # Settlement logic - transform based on zone needs
            screen_key = entity.screen_key
            if screen_key not in self.screen_entities:
                return False
            
            # Analyze zone composition
            types_in_zone = set()
            for other_id in self.screen_entities[screen_key]:
                if other_id != entity_id and other_id in self.entities:
                    types_in_zone.add(self.entities[other_id].type)
            
            # Determine which types are needed
            possible_types = config['possible_types']
            zone_need_weights = config['zone_need_weights']
            base_weights = config['base_weights']
            
            # Select weights based on zone needs
            weights = base_weights.copy()
            
            # Check for specific needs
            has_workers = any(t in types_in_zone for t in possible_types)
            if not has_workers:
                weights = zone_need_weights.get('no_workers', base_weights)
            else:
                for worker_type in possible_types:
                    if worker_type not in types_in_zone:
                        need_key = f'need_{worker_type.lower()}'
                        if need_key in zone_need_weights:
                            weights = zone_need_weights[need_key]
                            break
            
            # Weighted random selection
            roll = random.random()
            cumulative = 0.0
            new_type = None
            for npc_type, weight in weights.items():
                cumulative += weight
                if roll < cumulative:
                    new_type = npc_type
                    break
            
            if not new_type:
                return False
            
            # Perform transformation
            old_name = entity.name if entity.name else entity_type
            entity.type = new_type
            entity.props = ENTITY_TYPES[new_type]
            
            # Reset AI state for new role
            entity.ai_state = 'wandering'
            if hasattr(entity, 'target_exit'):
                entity.target_exit = None
            if hasattr(entity, 'seeking_exit'):
                entity.seeking_exit = False
            entity.movement_pattern = 'wander'
            
            # Update ai_params from new type
            ai_params = entity.props.get('ai_params', {})
            entity.aggressiveness = ai_params.get('aggressiveness', 0.30)
            entity.passiveness = ai_params.get('passiveness', 0.20)
            entity.idleness = ai_params.get('idleness', 0.15)
            entity.target_types = ai_params.get('target_types', ['water', 'food'])
            
            print(f"{old_name} has settled as a {new_type} in [{screen_key}]!")
            return True
        
        # Add other logic types here as needed (e.g., 'promotion', 'corruption', etc.)
        
        return False
    
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

    def try_entity_screen_crossing(self, entity, new_x, new_y):
        """Try to move entity to adjacent screen"""
        screen_key = entity.screen_key
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        new_screen_x = entity.screen_x
        new_screen_y = entity.screen_y
        
        # Determine which screen to move to
        if new_y < 0 and screen['exits']['top']:
            new_screen_y -= 1
            new_y = GRID_HEIGHT - 2
        elif new_y >= GRID_HEIGHT and screen['exits']['bottom']:
            new_screen_y += 1
            new_y = 1
        elif new_x < 0 and screen['exits']['left']:
            new_screen_x -= 1
            new_x = GRID_WIDTH - 2
        elif new_x >= GRID_WIDTH and screen['exits']['right']:
            new_screen_x += 1
            new_x = 1
        else:
            return  # Can't cross
        
        # Generate target screen if needed
        new_screen_key = f"{new_screen_x},{new_screen_y}"
        if new_screen_key not in self.screens:
            self.generate_screen(new_screen_x, new_screen_y)
        
        # Check population limit
        if new_screen_key not in self.screen_entities:
            self.screen_entities[new_screen_key] = []
        
        entity_count = len(self.screen_entities[new_screen_key])
        
        # Try to merge if too crowded
        if entity_count > 15:
            merged = self.try_merge_entity(entity, new_screen_key)
            if merged:
                return
            else:
                # Too crowded, can't enter
                return
        
        # Move entity to new screen
        old_screen_key = entity.screen_key
        if old_screen_key in self.screen_entities:
            entity_id = None
            for eid, e in self.entities.items():
                if e == entity:
                    entity_id = eid
                    break
            
            if entity_id and entity_id in self.screen_entities[old_screen_key]:
                # Check if destination cell in new screen is walkable
                if new_screen_key in self.screens:
                    dest_cell = self.screens[new_screen_key]['grid'][new_y][new_x]
                    if CELL_TYPES[dest_cell]['solid']:
                        # Destination is blocked, don't cross
                        return
                
                # Move is valid
                self.screen_entities[old_screen_key].remove(entity_id)
                self.screen_entities[new_screen_key].append(entity_id)
                
                entity.x = new_x
                entity.y = new_y
                entity.screen_x = new_screen_x
                entity.screen_y = new_screen_y
    
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
    
    def try_wizard_seek_rune(self, entity, screen_key):
        """Wizard moves toward nearest magic rune in dropped items (local zone or cross-zone)."""
        rune_names = {'magic_rune', 'fire_rune', 'lightning_rune', 'ice_rune', 'poison_rune', 'shadow_rune'}
        
        # Check local zone for dropped runes
        if screen_key in self.dropped_items:
            best_pos = None
            best_dist = 999
            for (ix, iy), items in self.dropped_items[screen_key].items():
                for item_name in items:
                    if item_name in rune_names:
                        dist = abs(entity.x - ix) + abs(entity.y - iy)
                        if dist < best_dist:
                            best_dist = dist
                            best_pos = (ix, iy)
            
            if best_pos:
                if best_dist <= 1:
                    # Adjacent — pick it up
                    for item_name, count in self.dropped_items[screen_key][best_pos].items():
                        entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                    del self.dropped_items[screen_key][best_pos]
                    return
                else:
                    # Move toward it
                    self.move_entity_towards(entity, best_pos[0], best_pos[1])
                    return
        
        # No local runes — try cross-zone: find nearest zone with runes and head to exit
        best_zone = None
        best_zone_dist = 999
        for sk, items_dict in self.dropped_items.items():
            if sk == screen_key:
                continue
            try:
                sx, sy = map(int, sk.split(','))
            except (ValueError, AttributeError):
                continue
            for pos, items in items_dict.items():
                if any(n in rune_names for n in items):
                    dist = abs(entity.screen_x - sx) + abs(entity.screen_y - sy)
                    if dist < best_zone_dist:
                        best_zone_dist = dist
                        best_zone = (sx, sy)
                    break
        
        if best_zone:
            # Head toward the exit leading to that zone
            exit_x, exit_y = self._get_exit_toward_zone(
                entity.screen_x, entity.screen_y, best_zone[0], best_zone[1])
            entity.current_target = ('cell', exit_x, exit_y)
            entity.target_type = 'resource'
            entity.ai_state = 'targeting'
            entity.ai_state_timer = 3
    
    def try_wizard_cast_spell(self, entity, screen_key):
        """Wizard casts spell on nearby target"""
        if entity.spell_cooldown > 0:
            return
        
        # Safety check: ensure wizard has spell and alignment (for backward compatibility with old saves)
        if not hasattr(entity, 'spell') or entity.spell is None:
            entity.spell = random.choice(['heal', 'fireball', 'lightning', 'ice', 'enchant'])
        if not hasattr(entity, 'alignment') or entity.alignment is None:
            entity.alignment = 'peaceful' if random.random() < 0.75 else 'hostile'
        
        spell_data = WIZARD_SPELLS[entity.spell]
        target = None
        
        # Find target based on alignment
        if entity.alignment == 'hostile':
            target = self.find_nearest_entity_in_range(entity, WIZARD_SPELL_RANGE, exclude_self=True)
        elif entity.alignment == 'peaceful':
            if spell_data['hostile_only']:
                target = self.find_nearest_hostile_in_range(entity, WIZARD_SPELL_RANGE)
            else:
                target = self.find_nearest_entity_in_range(entity, WIZARD_SPELL_RANGE, exclude_self=False)
        
        # Faction logic overrides
        if entity.faction:
            target = self.find_nearest_non_faction_entity(entity, WIZARD_SPELL_RANGE)
        
        if target:
            entity.update_facing_toward(target.x, target.y)
            entity.trigger_action_animation()
            # Get spell color for animation
            spell_data = WIZARD_SPELLS[entity.spell]
            magic_type = entity.spell if spell_data['type'] == 'damage' else None
            self.show_attack_animation(target.x, target.y, entity=entity, target_entity=target, magic_type=magic_type)
            self.cast_wizard_spell(entity, target, screen_key)
            entity.spell_cooldown = WIZARD_SPELL_COOLDOWN
    
    def try_wizard_explore_cave(self, entity, screen_key):
        """Wizard explores caves"""
        if random.random() > WIZARD_CAVE_EXPLORE_CHANCE:
            return
        
        screen = self.screens[screen_key]
        # Find nearby cave
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                check_x = entity.x + dx
                check_y = entity.y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    cell = screen['grid'][check_y][check_x]
                    if cell in ['CAVE', 'HIDDEN_CAVE']:
                        self.move_entity_towards(entity, check_x, check_y)
                        return
    
    def cast_wizard_spell(self, caster, target, screen_key):
        """Cast a wizard spell on target"""
        spell_name = caster.spell
        spell_data = WIZARD_SPELLS[spell_name]
        
        if spell_data['type'] == 'heal':
            target.heal(spell_data['amount'])
        elif spell_data['type'] == 'damage':
            target.take_damage(spell_data['amount'], caster)
            if target.health <= 0 and hasattr(caster, 'xp'):
                caster.xp += target.level * 10
        elif spell_data['type'] == 'enchant':
            cell_key = (target.screen_x, target.screen_y, target.x, target.y)
            self.enchanted_cells[cell_key] = True  # Just mark as enchanted, no duration
    
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