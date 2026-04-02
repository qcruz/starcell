# ai/movement.py — Pseudo-Code Reference

This document bridges the plain-language guide and the actual code. Each block uses
simplified pseudo-code that mirrors the real structure and variable names.

---

## Class: NpcAiMovementMixin

```
class NpcAiMovementMixin:
    # Mixed into Game. Has access to self.player, self.entities,
    # self.screens, self.structures, self.screen_entities, self.tick, etc.
```

---

## `_npc_footstep_sound(entity, cell_type)`

```
dist = manhattan_distance(entity, player)
if dist > 8: return

volume = sfx_volume * max(0, 1 - dist / 8)
sound_key = CELL_FOOTSTEP_MAP.get(cell_type, 'step_grass')
play_sound(sound_key, volume)
```

---

## `wander_entity(entity)`

```
screen_key = "{entity.screen_x},{entity.screen_y}"

# Rate limiter
speed    = entity.props.get('speed', 5)
interval = max(5, round(1 / (0.034 * speed)))
if (tick - entity.last_move_tick) < interval: return

# Pick random direction, avoid memory lane (last 6 positions)
directions = shuffle([UP, DOWN, LEFT, RIGHT])
for dx, dy in directions:
    nx, ny = entity.x + dx, entity.y + dy

    # Out of bounds → zone crossing (overworld only)
    if nx < 0 or nx >= GRID_WIDTH or ny < 0 or ny >= GRID_HEIGHT:
        if not entity.in_structure:
            try_entity_screen_crossing(entity, dx, dy)
        continue

    if cell_walkable(nx, ny) AND (nx, ny) not in entity.memory_lane[-6:]:
        entity.x, entity.y = nx, ny
        entity.last_move_tick = tick
        update_memory_lane(entity, nx, ny)
        play_footstep_sound(entity, grid[ny][nx])
        entity.moved_this_update = True
        return
```

---

## `move_toward_position(entity, tx, ty, screen_key)`

```
dx_sign = sign(tx - entity.x)   # −1, 0, or +1
dy_sign = sign(ty - entity.y)

# Primary axis = larger gap; secondary = other axis
if abs(tx - entity.x) >= abs(ty - entity.y):
    primary   = (dx_sign, 0)
    secondary = (0, dy_sign)
else:
    primary   = (0, dy_sign)
    secondary = (dx_sign, 0)

perpendicular = [(secondary[1], secondary[0]),
                 (-secondary[1], -secondary[0])]
backward      = (-primary[0], -primary[1])

candidates = [primary, secondary, *perpendicular, backward]

for dx, dy in candidates:
    nx, ny = entity.x + dx, entity.y + dy

    if out_of_bounds(nx, ny):
        if not entity.in_structure:
            try_entity_screen_crossing(entity, dx, dy)
        return

    if not cell_walkable(nx, ny): continue
    if (nx, ny) in reserved_cells:   continue   # another entity moving here this tick
    if (nx, ny) in entity.memory_lane[-6:] AND stuck_counter < 3: continue

    entity.x, entity.y = nx, ny
    reserved_cells[(nx, ny)] = entity_id
    entity.moved_this_update = True
    entity.stuck_counter = 0
    return

entity.stuck_counter += 1
if entity.stuck_counter > STUCK_THRESHOLD:
    entity.memory_lane.clear()
    entity.stuck_counter = 0
```

---

## `_get_exit_toward_zone(entity, target_screen_x, target_screen_y)`

```
# Compare zone coordinates to decide which edge to aim for
dx = target_screen_x - entity.screen_x
dy = target_screen_y - entity.screen_y

if abs(dx) >= abs(dy):
    if dx > 0: return 'east'   # aim for right edge
    else:      return 'west'
else:
    if dy > 0: return 'south'  # aim for bottom edge
    else:      return 'north'
```

---

## `_try_targeting_zone_cross(entity, screen_key)`

```
# Called when entity is near zone boundary while targeting cross-zone
ex = entity.x
ey = entity.y

near_left   = ex <= 1
near_right  = ex >= GRID_WIDTH  - 2
near_top    = ey <= 1
near_bottom = ey >= GRID_HEIGHT - 2

if near_left or near_right or near_top or near_bottom:
    try_entity_zone_transition(entity, screen_key)
```

---

## `_find_valid_entrance_cell(zone_key, entry_x, entry_y)`

```
# Expand outward from expected entry position until walkable cell found
for radius in range(1, 5):
    for dx in range(-radius, radius+1):
        for dy in range(-radius, radius+1):
            nx, ny = entry_x + dx, entry_y + dy
            if in_bounds(nx, ny) AND cell_walkable(zone_key, nx, ny):
                return (nx, ny)
return (entry_x, entry_y)  # fallback
```

---

## `try_entity_zone_transition(entity, screen_key)`

```
# Cooldown guard
if entity.zone_transition_cooldown > 0: return False

# Determine target zone
new_sx, new_sy = compute_adjacent_zone(entity)
new_key = "{new_sx},{new_sy}"

# Generate if unvisited
if new_key not in screens:
    generate_screen(new_sx, new_sy)

# Registry update
screen_entities[screen_key].remove(entity_id)
entity.screen_x, entity.screen_y = new_sx, new_sy
screen_entities[new_key].add(entity_id)

# Place at valid entrance cell
entry = _find_valid_entrance_cell(new_key, computed_entry_x, computed_entry_y)
entity.x, entity.y = entry

# Add old exit area to memory lane (prevent bounce)
entity.memory_lane += exit_area_cells[-6:]

entity.zone_transition_cooldown = ZONE_TRANSITION_COOLDOWN
return True
```

---

## `try_entity_screen_crossing(entity, dx, dy)`

```
# Called when wander/move carries entity out of grid bounds

# Keeper type 1 or 2 — anchored, cannot cross
if entity.keeper_type in (1, 2): return

# Anti-bounce cooldown
if entity.zone_transition_cooldown > 0: return

new_sx = entity.screen_x + (1 if dx > 0 else -1 if dx < 0 else 0)
new_sy = entity.screen_y + (1 if dy > 0 else -1 if dy < 0 else 0)
new_key = "{new_sx},{new_sy}"

if new_key not in screens:
    generate_screen(new_sx, new_sy)

# Population cap — merge if overcrowded
same_type_count = count entities of entity.type in new_key
if same_type_count > 15:
    try_merge_entity(entity, new_key)

# Execute crossing
screen_entities[current_key].remove(entity_id)
entity.screen_x, entity.screen_y = new_sx, new_sy
screen_entities[new_key].add(entity_id)
entity.x = wrap_x(entity.x)   # place at opposite edge
entity.y = wrap_y(entity.y)
entity.zone_transition_cooldown = ZONE_TRANSITION_COOLDOWN
```

---

## `move_entity_towards(entity, tx, ty)`

```
# Greedy best-distance approach (legacy)
best_dx, best_dy = 0, 0
best_dist = current_dist(entity, tx, ty)

for dx, dy in [UP, DOWN, LEFT, RIGHT]:
    nx, ny = entity.x + dx, entity.y + dy
    if not walkable(nx, ny): continue
    d = manhattan(nx, ny, tx, ty)
    if d < best_dist:
        best_dist = d
        best_dx, best_dy = dx, dy

if (best_dx, best_dy) != (0, 0):
    entity.x += best_dx
    entity.y += best_dy
    entity.moved_this_update = True

    # Stuck detection
    if (tx, ty) == entity.last_target_position:
        entity.target_stuck_counter += 1
        if entity.target_stuck_counter >= TARGET_STUCK_THRESHOLD (180):
            entity.memory_lane.append((tx, ty))
            entity.target_stuck_counter = 0
    else:
        entity.last_target_position = (tx, ty)
        entity.target_stuck_counter = 0
```

---

## `seek_zone_exit(entity)`

```
screen_key = "{entity.screen_x},{entity.screen_y}"

if entity.in_structure:
    # Structure exit = the stored exit cell
    structure = structures[entity.structure_key]
    ex, ey = structure.get('exit', center_of_grid)
    move_toward_position(entity, ex, ey, entity.structure_key)
    if adjacent_to(ex, ey):
        npc_exit_structure(entity)
else:
    # Overworld exit = nearest exit-flagged cell
    exit_cells = [(x, y) for (x,y) in zone if grid[y][x] is exit]
    nearest = min(exit_cells, by manhattan to entity)
    move_toward_position(entity, nearest.x, nearest.y, screen_key)
```

---

## `npc_enter_structure(entity, screen_key, door_x, door_y, cell_type)`

```
# Resolve structure key (cave → zone_cave_systems lookup; house → house_dict)
struct_key = resolve_structure_key(screen_key, door_x, door_y, cell_type)
if struct_key is None: return False

# Registry move
screen_entities[screen_key].discard(entity_id)
screen_entities[struct_key].add(entity_id)

# Entity flags
entity.in_structure = True
entity.structure_key = struct_key

# Place at entrance
entrance = structures[struct_key].get('entrance', center)
entity.x, entity.y = entrance

# Clear targeting
entity.current_target = None
entity.target_type    = None
entity.ai_state       = 'wandering'

return True
```

---

## `npc_exit_structure(entity)`

```
struct_key = entity.structure_key
structure  = structures[struct_key]

depth = structure.get('depth', 1)

if depth > 1:
    # Multi-level cave: exit to level above
    parent_key = structure['parent_structure_key']
    target_entrance = structures[parent_key]['entrance']
    ...
else:
    # Exit to overworld
    parent_screen = structure['parent_screen']
    parent_key    = "{parent_screen[0]},{parent_screen[1]}"
    door_x, door_y = structure.get('parent_cell', center)

    # Place near door in overworld
    entry = _find_valid_entrance_cell(parent_key, door_x + 1, door_y)
    entity.x, entity.y = entry

screen_entities[struct_key].discard(entity_id)
screen_entities[parent_key].add(entity_id)

entity.in_structure  = False
entity.structure_key = None
entity.screen_x, entity.screen_y = parse_key(parent_key)

# Add exit area to memory lane (prevent immediate re-entry)
entity.memory_lane += [(door_x + dx, door_y + dy) for small offsets]
```

---

## `update_structure_npc_behavior(entity)`

```
# Called every tick for in-structure entities

if entity is in a HOUSE:
    # Passive health regeneration
    if entity.health < entity.max_health AND tick % 30 == 0:
        entity.health = min(max_health, health + HEAL_RATE)

elif entity is in a CAVE:
    # Flee if injured and no target
    if entity.health < LOW_HEALTH_THRESHOLD AND entity.current_target is None:
        entity.ai_state = 'exit'
```

---

## `move_npc_toward_structure_exit(entity)`

```
structure = structures[entity.structure_key]
exit_x, exit_y = structure.get('exit', center)

move_toward_position(entity, exit_x, exit_y, entity.structure_key)

if adjacent_to(exit_x, exit_y):
    npc_exit_structure(entity)
```

---

## `try_npc_enter_structure(entity)`

```
screen_key = "{entity.screen_x},{entity.screen_y}"
if entity.in_structure: return

for each adjacent cell (8-way + own cell):
    cell = grid[adj_y][adj_x]

    if cell == 'CAVE' or cell == 'MINESHAFT':
        if entity is nocturnal (bat) AND is_daytime:
            npc_enter_structure(entity, screen_key, adj_x, adj_y, cell)
            return
        if entity is hostile AND has_target_in_structure(entity, screen_key, adj_x, adj_y):
            npc_enter_structure(entity, screen_key, adj_x, adj_y, cell)
            return

    elif cell in ENTERABLE_HOUSE_CELLS:
        if is_night AND entity.props.get('seeks_shelter'):
            npc_enter_structure(entity, screen_key, adj_x, adj_y, cell)
            return
```

---

## `try_npc_exit_structure(entity)`

```
# Called every tick for in-structure entities

if entity should leave (day AND bat, OR fleeing, OR no food):
    move_npc_toward_structure_exit(entity)
    # npc_exit_structure fires inside when adjacent
```

---

## `try_merge_entity(entity_id, screen_key)`

```
# Count same-type entities in zone
same_type = [id for id in screen_entities[screen_key]
             if entities[id].type == entity.type]

if len(same_type) <= 3: return False

# Pick two to merge
a_id, b_id = same_type[0], same_type[1]
a, b = entities[a_id], entities[b_id]

double_type = f"{entity.type}_double"
double = create_entity(double_type, position=a.position, zone=screen_key)
double.level = max(a.level, b.level)

remove_entity(a_id)
remove_entity(b_id)
return True
```

---

## `try_split_double_entity(entity_id, screen_key)`

```
if not entity.type.endswith('_double'): return False

base_type = entity.type.replace('_double', '')
same_type = count non-double entities of base_type in screen_key

if same_type > 2: return False   # zone not underpopulated

# Create two singles near double's position
for i in range(2):
    new_entity = create_entity(base_type, position=nearby(entity), zone=screen_key)
    new_entity.level = entity.level

remove_entity(entity_id)
return True
```

---

## `teleport_follower_to_player(entity, entity_id)`

```
player_key = "{player.screen_x},{player.screen_y}"
entity_key = "{entity.screen_x},{entity.screen_y}"

if entity_key == player_key: return   # already same screen

screen_entities[entity_key].discard(entity_id)
entity.screen_x = player.screen_x
entity.screen_y = player.screen_y
screen_entities[player_key].add(entity_id)

# Place adjacent to player
entity.x = player.x + 1 (or nearest open cell)
entity.y = player.y
```

---

## Target Finders

### `find_closest_food_source(entity, screen_key)`

```
food_sources = entity.props.get('food_sources', [])
grid_to_search = structure_grid if entity.in_structure else overworld_grid

closest = None, closest_dist = inf

for (x, y) in grid:
    if grid[y][x] in food_sources:
        update_closest(('cell', x, y, cell))

if not entity.in_structure:
    for other_id in screen_entities[screen_key]:
        if entities[other_id].type in food_sources:
            update_closest(other_id)

return closest
```

### `find_closest_water_source(entity, screen_key)`

```
water_sources = entity.props.get('water_sources', ['WATER'])
grid_to_search = structure_grid if entity.in_structure else overworld_grid

# Identical pattern to food — scan grid for matching cell types
return closest ('cell', x, y, cell) or None
```

### `find_hostile_in_connected_structures(entity, screen_key)`

```
for each (cx, cy) in zone where grid[cy][cx] in ('CAVE', 'MINESHAFT'):
    sub_key = resolve_structure_key(screen_key, cx, cy)
    for other_id in screen_entities[sub_key]:
        other = entities[other_id]
        if is_enemy(entity, other):
            door_dist = manhattan(entity, cx, cy)
            update_closest(other_id, door_dist, (cx, cy))

return (closest_id, closest_door_dist, closest_door_pos)
```

### `find_closest_hostile_entity(entity, screen_key)`

```
# Three-tier hostility check:
# 1. hostile vs non-hostile (either direction)
# 2. hostile vs different-species hostile
# 3. different-faction non-hostiles

if entity.hostile:
    check player as target (same zone)

for other_id in screen_entities[screen_key]:
    other = entities[other_id]
    if is_enemy(entity, other):
        update_closest(other_id)

# Also check connected cave structures
sub_id, sub_dist, door = find_hostile_in_connected_structures(entity, screen_key)
if sub_id and sub_dist < closest_dist:
    entity.target_door = door
    return sub_id

return closest_id
```

### `find_closest_target_by_type(entity, target_type, screen_key)`

```
switch target_type:
    'hostile'         → find_closest_hostile_entity()
    'food'            → find_closest_food_source()
    'water'           → find_closest_water_source()
    'shelter'         → _find_nearest_shelter()
    'structure'       → find_closest_structure()
    'resource'        → find_closest_resource()
    'any_entity'      → _find_closest_any_entity()
    'role'            → check ROLE_CELL_PRIORITY, then ROLE_CELL_TARGETS
    'travel'          → return exit cell if in_structure, else None
    'quest_target'    → return entity.quest_target directly
    'clearing_action' → _find_clearing_target()
    'trade'           → None (stub)
```

### `find_closest_eligible_target(entity, screen_key, target_list)`

```
target_set = frozenset(target_list)

def scan(zone_key):
    search grid cells and screen_entities for any type in target_set
    return nearest ('cell', x, y, cell) or entity_id

if entity.in_structure:
    result = scan(entity.structure_key)
    if result: return result
    # Target not in structure — return exit so entity navigates out
    exit_pos = structures[entity.structure_key].get('exit', center)
    if scan(parent_overworld_key):
        return ('cell', exit_pos.x, exit_pos.y, 'EXIT')
    return None

return scan(screen_key)
```

---

## `npc_seek_shelter(entity)` — Legacy

```
if entity.in_structure: return False

screen_key = "{entity.screen_x},{entity.screen_y}"

if entity.is_idle:
    # Break idle if threatened or starving
    if nearby_hostile_within(5) OR hunger < 30 OR thirst < 30:
        entity.is_idle = False
        return False
    return True   # stay idle

# Find nearest house or camp
nearest_house = min(HOUSE cells in zone, by distance)
nearest_camp  = min(CAMP  cells in zone, by distance)

if nearest_house AND dist <= 15:
    if dist <= 1:
        npc_enter_structure(entity, ..., 'HOUSE')
        entity.is_idle = True
    else:
        move_entity_towards(entity, house.x, house.y)
    return True

elif nearest_camp AND dist <= 15:
    if dist <= 2: entity.is_idle = True
    else:         move_entity_towards(entity, camp.x, camp.y)
    return True

entity.is_idle = False
return False
```

---

## `find_and_move_to_food(entity)` — Legacy

```
screen_key = "{entity.screen_x},{entity.screen_y}"

# Scan zone for food cells and prey entities
closest_food, closest_food_type = None, None

for food_type in entity.food_sources:
    if food_type is a cell type:
        scan grid, update closest
    else:   # prey entity type
        scan screen_entities, update closest

if not found:
    entity.no_food_in_zone = True
    seek_zone_exit(entity)
    return

# Urgency-based multi-step move
move_steps = 3 if critical_health else 2 if low_health else 1
for _ in range(move_steps):
    move_entity_towards(entity, food_x, food_y)
    if adjacent: break

if adjacent:
    if cell food:
        entity.eat(entity.max_hunger)
        decay food cell (50% carrot, GRASS_DECAY_ON_EAT% grass)
    elif entity prey:
        prey.health = 0
        entity.eat(50)
```
