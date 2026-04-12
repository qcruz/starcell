# ai/actions.py — Pseudo-Code Reference

This document bridges the plain-language guide and the actual code. Each block uses
simplified pseudo-code that mirrors the real structure and variable names.

---

## Class: NpcAiActionsMixin

```
class NpcAiActionsMixin:
    # Mixed into Game. Has access to self.screens, self.entities,
    # self.screen_entities, self.player, self.inventory, self.tick, etc.

    _CELL_SOUND   = {'TREE': 'wood_chop', 'PINE': 'wood_chop', ...}
    _ENTITY_SOUND = {'GOBLIN': 'goblin_sound', 'WOLF': 'wolf_sound', ...}
```

---

## `_npc_action_sound(actor, sound_key)`

```
if no sound system: return
if actor is None or 'player': return
if actor.screen != player.screen: return

dist = manhattan(actor, player)
if dist > 4: return

volume = sfx_volume * (1 - dist / 4)   # halves per cell
sound.play_sfx_spatial(sound_key, dist)
```

---

## `action_harvest_cell(actor, screen_key, cell_types, success_rate, result_cell, activity)`

```
is_player = (actor == 'player')
ax, ay    = player.x/y  if is_player  else  actor.x/y

# FARMER special case: collect buried items first
if actor is FARMER:
    for (bx, by) in adjacent_cells(ax, ay):
        if buried_items at (bx, by):
            add to actor.inventory, remove from buried

for dx, dy in [UP, DOWN, LEFT, RIGHT]:
    cx, cy = ax + dx, ay + dy
    cell = grid[cy][cx]
    if cell not in cell_types: continue

    # Animate
    if not is_player:
        actor.face_toward(cx, cy)
        actor.trigger_action_animation()
    show_attack_animation(cx, cy)

    # Sound
    if not is_player:
        play_npc_action_sound(actor, CELL_SOUND.get(cell))

    # XP (every attempt, not just successes)
    if not is_player:
        actor.xp += 1
        if actor.xp >= xp_to_level: actor.level_up()

    # Success roll (boosted during time_pass simulation)
    effective_rate = min(1.0, success_rate * time_pass_speed)
    if random() < effective_rate:

        # Drops from CELL_TYPES config
        for drop in CELL_TYPES[cell]['drops']:
            if random() < drop['chance']:
                if 'item' in drop: add item to actor/player inventory
                if 'cell' in drop: grid[cy][cx] = drop['cell']

        # Harvest shortcut (crops)
        harvest = CELL_TYPES[cell].get('harvest')
        if harvest:
            add harvest['item'] × harvest['amount'] to actor/player inventory

        # Transform cell
        if result_cell:             grid[cy][cx] = result_cell
        elif no drops defined:      grid[cy][cx] = 'GRASS'

        # House collapse consequence
        if cell in ('HOUSE','STONE_HOUSE') AND cell changed:
            on_house_collapsed(screen_key, cx, cy)

        if not is_player and activity:
            actor.level_up_from_activity(activity)
        if not is_player:
            actor.tasks_completed += 1

    return True   # acted on this cell, stop scanning

return False   # nothing adjacent
```

---

## `action_transform_cell(actor, screen_key, cell_types, result_cell, success_rate, activity)`

```
# Same adjacency loop as action_harvest_cell; no drops

for dx, dy in [UP, DOWN, LEFT, RIGHT]:
    cx, cy = ax + dx, ay + dy
    if grid[cy][cx] not in cell_types: continue

    animate, sound, award XP  (same as above)

    if random() < min(1.0, success_rate * time_pass_speed):
        grid[cy][cx] = result_cell
        if activity: actor.level_up_from_activity(activity)
        actor.tasks_completed += 1
    return True

return False
```

---

## `action_place_cell(actor, screen_key, cell_types, result_cell, consume_items, success_rate, activity)`

```
# Item check
if consume_items:
    has_item = any(actor.inventory.get(item) > 0 for item in consume_items)
    if not has_item:
        if is_player OR random() > 0.20:   # NPCs get 20% free-plant fallback
            return False

for dx, dy in [UP, DOWN, LEFT, RIGHT]:
    cx, cy = ax + dx, ay + dy
    if grid[cy][cx] not in cell_types: continue

    animate, award XP

    if random() < min(1.0, success_rate * time_pass_speed):
        grid[cy][cx] = result_cell
        if consume_items:
            remove 1 of first matching item from actor/player inventory
        if activity: actor.level_up_from_activity(activity)
        actor.tasks_completed += 1
    return True

return False
```

---

## `action_damage(attacker, target, amount, damage_type)`

```
if target == 'player':
    return player_take_damage(amount)
elif target is entity:
    actual = min(amount, target.health)
    target.health -= actual
    if target.health <= 0:
        target.is_dead = True
        target.killed_by = attacker type
    return actual
return 0
```

---

## `action_heal(target, amount)`

```
if target == 'player':
    player.health = min(player.health + amount, player.max_health)
else:
    target.health = min(target.health + amount, target.max_health)
```

---

## `execute_npc_behavior(entity, screen_key)`

```
behaviors = NPC_BEHAVIORS.get(entity.type, [])

for b in behaviors:
    if random() > b['rate']: continue    # rate check, skip most ticks

    if b['action'] == 'harvest_cell':
        if action_harvest_cell(entity, screen_key, b['cells'],
                               b['success'], b['result_cell'], b['activity']):
            return True

    elif b['action'] == 'transform_cell':
        if action_transform_cell(...): return True

    elif b['action'] == 'place_cell':
        if action_place_cell(...): return True

    elif b['action'] == 'build':
        if _try_build_structure(entity, screen_key, b): return True

return False
```

---

## `_try_build_structure(entity, screen_key, build_params)`

```
structure  = build_params['structure']
cost       = build_params.get('cost', {})
max_count  = build_params.get('max_per_zone', 999)
valid_cells = build_params.get('valid_cells', ['GRASS', 'DIRT'])
prefer_near = build_params.get('prefer_near')   # optional proximity preference

# Item check
for item, amount in cost.items():
    if entity.inventory.get(item, 0) < amount: return False

# Cap check
if count(structure in zone grid) >= max_count: return False

# Find candidate spots
spots = []
for (bx, by) in grid (excluding border and entity's own cell):
    if grid[by][bx] not in valid_cells: continue
    if prefer_near:
        if any prefer_near cell within 2-cell radius: spots.append((bx, by))
    else:
        spots.append((bx, by))

if not spots: try 20 random fallback positions

if spots:
    bx, by = random.choice(spots[:10])   # pick from top 10 candidates
    consume costs from entity.inventory
    grid[by][bx] = structure
    if structure is HOUSE/STONE_HOUSE:
        generate_structure_zone(sx, sy, bx, by, 'HOUSE_INTERIOR', depth=1)
    actor.level_up_from_activity(activity)
    return True

return False
```

---

## `try_chop_tree(entity, screen_key)`

```
# Density bonus
nearby_trees = count TREE/PINE/CACTUS/BUSH cells within 5×5 radius
chop_rate = LUMBERJACK_BASE_CHOP_RATE + (nearby_trees * LUMBERJACK_DENSITY_BONUS)
if entity.type == 'LUMBERJACK':
    chop_rate *= 1 + (entity.level * 0.1)   # +10% per level
chop_rate = min(chop_rate, 0.8)

# Quest nav target priority
directions = [UP, DOWN, LEFT, RIGHT]
if entity.quest_nav_target points at adjacent tree:
    move that direction to front of list

for dx, dy in directions:
    cx, cy = entity + (dx, dy)
    if grid[cy][cx] not in ('TREE1', 'TREE2', 'CACTUS', 'BUSH'): continue

    face, animate, sound('wood_chop'), award XP

    if random() < LUMBERJACK_CHOP_SUCCESS:
        # Tool gate for autopilot proxy
        has_tool = (not is_proxy) OR player.has('axe')

        for drop in CELL_TYPES[cell]['drops']:
            if random() < drop['chance']:
                if 'item' in drop AND has_tool: add to entity.inventory
                elif 'cell' in drop: grid[cy][cx] = drop['cell']

        entity.level_up_from_activity('chop')
    return
```

---

## `on_house_collapsed(screen_key, cell_x, cell_y)`

```
# Find the interior structure linked to this house cell
structure_key = find structure where parent_screen == screen and parent_cell == (cell_x, cell_y)
if not found: return

# Find ejection point
eject = nearest walkable cell adjacent to (cell_x, cell_y)

# Eject all entities inside
for eid in screen_entities[structure_key]:
    entity = entities[eid]
    move entity from structure registry to overworld registry
    entity.screen_x/y = parent zone coords
    entity.x/y = eject position
    entity.in_structure = False
    entity.take_damage(35%–50% max_health)   # collapse injury
    entity.ai_state = 'idle', target = None

# Drop chest contents
for chest in structure['chests']:
    contents = chest_contents.pop(chest_key, {})
    surviving = 70% of each item count
    add to dropped_items at eject position
```

---

## `try_mine_rock(entity, screen_key)`

```
# Density bonus (mirrors try_chop_tree)
nearby_rocks = count STONE/IRON_ORE within 5×5
mine_rate = min(BASE + density_bonus, 0.85)

# Quest nav target priority (same pattern as try_chop_tree)

for dx, dy in directions:
    cell = grid[cy][cx]
    if cell not in ('STONE', 'IRON_ORE', 'CAVE'): continue

    face, animate, sound, award XP (iron_ore gives 2 XP, others 1)

    if random() < MINER_MINE_SUCCESS:
        has_tool = (not is_proxy) OR player.has('pickaxe'/'stone_pickaxe')

        if cell == 'CAVE':
            if mineshaft_count < MINESHAFT_MAX_PER_ZONE:
                grid[cy][cx] = 'MINESHAFT'
                if has_tool: entity.inventory['stone'] += 1
            else:
                grid[cy][cx] = 'STONE'

        elif cell == 'IRON_ORE':
            if has_tool: entity.inventory['iron_ore'] += 1
            grid[cy][cx] = biome_base_cell   # GRASS, DIRT, SAND, or CAVE_FLOOR

        else:  # STONE
            if can_create_shaft AND random() < MINER_MINESHAFT_CHANCE:
                grid[cy][cx] = 'MINESHAFT'
                if has_tool: entity.inventory['stone'] += 1
            else:
                if has_tool: entity.inventory['stone'] += 2
                grid[cy][cx] = 'CAVE_FLOOR' if in cave else 'DIRT'

            # Small chance to dig deeper (max depth 3)
            if in_cave AND random() < 0.05 AND depth < 3:
                generate deeper cave level below this cell
                clear 3×3 around entry for walkability
                grid[cy][cx] = 'STAIRS_DOWN'

        entity.current_target = None   # seek next rock immediately
    return

# No rocks adjacent — navigate toward nearest
priority = {'IRON_ORE': 0, 'STONE': 1, 'CAVE': 2, 'MINESHAFT': 3}
nearest = min(all matching cells, by distance + priority*0.5)
if found:
    entity.current_target = ('cell', nx, ny, cell)
    move_entity_towards(entity, nx, ny)
else:
    move toward nearest corner
```

---

## `try_plant_seed(entity, screen_key)`

```
has_carrot = entity.inventory.get('carrot', 0) > 0
has_seeds  = entity.inventory.get('seeds', 0) > 0
if not (has_carrot or has_seeds or random() < 0.20): return False

for dx, dy in [UP, DOWN, LEFT, RIGHT]:
    cx, cy = entity + (dx, dy)
    if grid[cy][cx] != 'SOIL': continue

    face, animate, award XP

    if random() < min(1.0, FARMER_PLANT_SUCCESS * time_pass_speed):
        grid[cy][cx] = 'CARROT1'
        if has_carrot: entity.inventory['carrot'] -= 1
        elif has_seeds: entity.inventory['seeds'] -= 1
    return True   # acted, stop

return False
```

---

## `try_harvest_crop(entity, screen_key)`

```
# Quest nav target priority (same pattern as try_chop_tree)
directions = [UP, DOWN, LEFT, RIGHT]
if quest_nav_target points at adjacent CARROT3: prioritize that direction

for dx, dy in directions:
    if grid[cy][cx] != 'CARROT3': continue

    face, animate, award XP

    if random() < FARMER_HARVEST_SUCCESS:
        entity.inventory['carrot'] += 2
        grid[cy][cx] = 'CARROT1'   # decay to early stage, not SOIL — farm persists
        level_up_from_activity('harvest')
    return True

return False
```

---

## `try_till_soil(entity, screen_key)`

```
# Quest nav target priority (same pattern)

for dx, dy in directions:
    cell = grid[cy][cx]
    if cell not in ('GRASS', 'DIRT', 'SAND'): continue

    face, animate, award XP

    success = FARMER_TILL_SUCCESS * (0.15 if cell == 'SAND' else 1.0)
    if random() < success:
        grid[cy][cx] = 'SOIL'
    return True

return False
```

---

## `try_clear_tree(entity, screen_key)`

```
# 8-way scan (not just 4 cardinal — wider clearance)
for (dx, dy) in 3×3 around entity:
    if grid[cy][cx] in ('TREE1', 'TREE2', 'CACTUS', 'BUSH'):
        drops = CELL_TYPES[cell]['drops']
        for drop in drops:
            if random() < drop['chance']:
                if 'cell' in drop: grid[cy][cx] = drop['cell']
                # 'item' drops are NOT collected — no wood pickup
        return
```

---

## `try_build_path(entity, screen_key)`

```
cell = grid[entity.y][entity.x]
in_center_lanes = (abs(entity.x - GRID_WIDTH//2) <= 1) OR
                  (abs(entity.y - GRID_HEIGHT//2) <= 1)

if cell == 'GRASS' AND random() < TRADER_PATH_BUILD_RATE:
    grid[entity.y][entity.x] = 'DIRT'
elif cell == 'DIRT' AND in_center_lanes AND random() < TRADER_COBBLE_RATE:
    grid[entity.y][entity.x] = 'COBBLESTONE'
```

---

## `pickup_dropped_items(entity, screen_key)`

```
pos_key = (entity.x, entity.y)
if no items at pos_key: return

items = dropped_items[screen_key][pos_key]

# Runestone damage
rune_damage = count runes in items
if rune_damage > 0:
    entity.take_damage(rune_damage, 'runestone')
    destroy 50% of runes

# Add remaining items to entity inventory
for item, amount in items:
    entity.inventory[item] += amount
entity.xp += total_items_picked_up

del dropped_items[screen_key][pos_key]
```

---

## `process_entity_drop(entity, screen_key)`

```
drop_x, drop_y = entity.x, entity.y

# 10% chance to spawn runestones at death location
if random() < 0.10: spawn_runestones(drop_x, drop_y)

# Props loot table
for drop in entity.props.get('drops', []):
    if random() < drop['chance']:
        add_drop(drop['item'], drop['amount'])

# Inventory drops
for item, amount in entity.inventory:
    if is_unique_item(item):
        add_drop(item, amount)          # always survives
    else:
        surviving = sum(1 for _ in range(amount) if random() > 0.40)
        add_drop(item, surviving)       # ~60% survive per item
```

---

## `npc_place_camp(entity)`

```
screen_key = entity.screen_key

# Check if camp already exists → if so, maybe upgrade or decay
for (x, y) in grid where cell == 'CAMP':
    if house_count > 5 AND random() < 0.05:
        grid[y][x] = 'DIRT'     # settlement mature, camp no longer needed
        return
    elif random() < 0.02:
        grid[y][x] = 'HOUSE'    # camp upgrades to house
        level_up_from_activity('build')
        return

# No camp exists — place one near entity
for _ in range(10):
    px, py = entity.x + random(-2,2), entity.y + random(-2,2)
    if grid[py][px] in ('GRASS', 'DIRT', 'SAND'):
        grid[py][px] = 'CAMP'
        entity.inventory.pop('wood', None)
        return
```

---

## `try_place_npc_chest(entity, screen_key)`

```
# Refuse if any chest within 8 cells
if any 'CHEST' cell within 8-cell radius: return False

# Place on first adjacent valid floor cell
for (dx, dy) in 3×3 around entity (skip center):
    cx, cy = entity + (dx, dy)
    if grid[cy][cx] in ('GRASS', 'DIRT', 'SAND', 'FLOOR_WOOD', 'CAVE_FLOOR'):
        grid[cy][cx] = 'CHEST'
        chest_backgrounds[ck] = old_cell   # remember what was here
        # Transfer up to 5 items from entity into chest
        for item in shuffle(entity.inventory)[:5]:
            chest_contents[ck][item] = entity.inventory.pop(item)
        return True

return False
```

---

## `process_npc_trade(entity, entity_id, gold_count)`

```
switch entity.type:
    FARMER:      give player (gold_count * 2) carrots
    LUMBERJACK:  give player (gold_count * 3) wood
    MINER:       give player (gold_count * 3) stone

    GUARD / GOBLIN:
        gold_threshold = 10 if GUARD else 5
        if entity.inventory['gold'] >= threshold:
            followers.append(entity_id)
            entity.inventory['gold'] = 0

    TRADER:
        self.trader_display = { entity_id, recipes: [...] }
```

---

## `try_npc_trade(entity, screen_key)`

```
if entity.hostile: return
if random() > 0.02: return    # 2% chance per tick

for other in same zone (peaceful, within 3 cells, not self):
    entity_items = [non-spell items from entity.inventory]
    other_items  = [non-spell items from other.inventory]
    if both have items:
        A = random.choice(entity_items)
        B = random.choice(other_items)
        entity.inventory[A] -= 1
        other.inventory[B] -= 1
        entity.inventory[B] += 1
        other.inventory[A] += 1
        return
```
