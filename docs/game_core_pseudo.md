# game_core.py — Pseudo-Code Reference

This document bridges the plain-language guide and the actual code. Each block uses
simplified pseudo-code that mirrors the real structure and variable names.

---

## Class: GameCoreMixin

```
class GameCoreMixin:
    # Mixed into Game. Owns game state init, main loop, player movement,
    # input, cell/entity scheduling, and structure navigation.
    # All AI lives in npc_ai.py / ai/. All world gen in world/generation.py.
```

---

## `__init__`

```
def __init__(self):
    # Core state
    self.tick = 0
    self.state = 'menu'          # 'menu' | 'playing' | 'death' | 'time_pass'
    self.time_pass_speed = 1.0   # multiplied by all success rates during fast-forward

    # World data
    self.screens = {}            # {zone_key: grid}  — generated on first visit
    self.screen_entities = {}    # {zone_key: [entity_id, ...]}
    self.structures = {}         # {structure_key: struct_dict}  — virtual zones
    self.entities = {}           # {entity_id: Entity}  — global registry
    self.next_entity_id = 0

    # Player
    self.player = {
        'x': 0, 'y': 0,
        'screen_x': 0, 'screen_y': 0,
        'health': 100, 'max_health': 100,
        'hunger': 100, 'max_hunger': 100,
        'thirst': 100, 'max_thirst': 100,
        'mana': 50, 'max_mana': 50,
        'energy': 100, 'max_energy': 100,
        'level': 1, 'xp': 0,
        'gold': 0,
        'in_structure': False,
        'structure_key': None,
        'origin_zone': None,
        'cave_depth': 0,
        'cave_via_structure': False,
        'facing': 'down',
        'quests': [],
        'equipped': {},          # body slots: weapon, armour, ring, spell
        'inventory': {},         # {item_name: count}
        'item_uid_counter': 0,
        ...
    }

    # Follower tracking
    self.followers = []           # [entity_id, ...]
    self.follower_items = {}      # {entity_id: item_name}
    self._pending_follower_type = None  # deferred spawn until after time-pass

    # World extras
    self.dropped_items = {}       # {zone_key: {(x,y): {item_name: count}}}
    self.chest_contents = {}      # {(x,y,zone_key): {item_name: count}}
    self.chest_backgrounds = {}   # {(x,y,zone_key): cell_type_under_chest}
    self.enchanted_cells = {}     # {(x,y,zone_key): ticks_remaining}
    self.gravestones = {}         # {zone_key: [(x, y, name), ...]}

    # Managers
    self.sound = SoundManager(...)
    self.watchdog = Watchdog(...)
    self.item_uid_counter = 0

    load_sprites()
```

---

## `load_sprites`

```
def load_sprites(self):
    SEARCH_PATHS = [
        '~/StarCell/sprites/',
        '~/Desktop/porn/starcell/sprites/',
        './sprites/',
        ...  # 12+ candidates
    ]

    for each candidate in SEARCH_PATHS:
        if os.path.exists(candidate):
            sprite_dir = candidate
            break

    # Strategy 1: spritesheet
    self.sprites = SpriteManager.load_sprite_sheet(sprite_dir + 'tileset.png')

    # Strategy 2: individual entity PNGs by naming convention
    # e.g. wolf_right_1.png, wolf_right_2.png, wolf_still.png
    self.sprites.create_structure_sprites(sprite_dir)

    # Strategy 3: explicit non-standard filenames
    explicit_sprites = {
        'IRON_ORE':  'ironore.png',
        'WELL':      'well.png',
        'iron_sword': 'sword.png',
        ...
    }
    for key, filename in explicit_sprites.items():
        self.sprites[key] = load_png(sprite_dir + filename)
```

---

## Update Scheduling

### `update_cells`

```
def update_cells(self):
    player_zone = f"{player.screen_x},{player.screen_y}"

    for zone_key, distance in nearby_zones_with_distance():
        if distance == 0 and tick % 60 == 0:
            update_screen_cells(zone_key)
        elif distance == 1 and tick % 180 == 0:
            update_screen_cells(zone_key)
        elif distance == 2 and tick % 600 == 0:
            update_screen_cells(zone_key)
```

### `update_entities`

```
def update_entities(self):
    dead = []

    for entity_id, entity in self.entities.items():
        if entity.health <= 0:
            dead.append(entity_id)
            continue

        dist = screen_distance(entity, player)

        # Distance-tiered update frequency
        if dist == 0:   should_update = True
        elif dist == 1: should_update = (tick % 60 == 0)
        elif dist == 2: should_update = (tick % 90 == 0)
        else:           should_update = False

        if should_update:
            # Heal boost based on nearby cell type
            nearby_cells = scan_radius(entity.x, entity.y, 2)
            if HOUSE in nearby_cells:   entity.heal_boost = 3.0
            elif CAMP in nearby_cells:  entity.heal_boost = 2.0
            else:                       entity.heal_boost = 1.0

            update_entity_ai(entity_id, entity)

    for entity_id in dead:
        remove_entity(entity_id)
```

### `remove_entity`

```
def remove_entity(self, entity_id):
    entity = self.entities[entity_id]

    # Record cause of death
    if entity.age >= entity.max_age:    cause = 'old_age'
    elif entity.hunger <= 0:            cause = 'starvation'
    elif entity.thirst <= 0:            cause = 'dehydration'
    else:                               cause = 'combat'
    watchdog.log('entity_death', {id: entity_id, cause: cause, type: entity.type})

    # Keeper slot
    if entity.keeper_slot is not None:
        free_keeper_slot(entity.keeper_slot)

    # Quest watchers
    quest_watcher_broadcast('entity_died', entity_id, entity.type)

    # Follower cleanup
    if entity_id in self.followers:
        self.followers.remove(entity_id)
    self.follower_items.pop(entity_id, None)

    # Drop loot
    process_entity_drop(entity_id, entity)

    # Gravestone
    if entity.is_named and entity.type in HUMANOID_TYPES:
        _maybe_spawn_gravestone(entity_id, entity)

    # Remove from registries
    zone_key = f"{entity.screen_x},{entity.screen_y}"
    screen_entities[zone_key].remove(entity_id)
    del self.entities[entity_id]
```

### `_maybe_spawn_gravestone`

```
def _maybe_spawn_gravestone(self, entity_id, entity):
    zone_key = entity's zone
    grid = screens[zone_key]

    # Conditions
    if not entity.is_named: return
    if HOUSE not in any cell in grid: return

    existing = gravestones.get(zone_key, [])

    if len(existing) >= 5:
        # Append name to nearest existing gravestone
        nearest = min(existing, key=lambda g: manhattan(g.x, g.y, entity.x, entity.y))
        nearest.names.append(entity.name)
        return

    # New stone: only near existing cluster (or first one anywhere)
    if existing:
        cluster_center = average position of existing
        if distance(entity, cluster_center) > 6: return   # too far from cluster

    place GRAVESTONE cell at entity's position
    gravestones[zone_key].append((entity.x, entity.y, entity.name))
```

---

## Follower and Inspection

### `check_follower_integrity`

```
def check_follower_integrity(self):
    for entity_id in list(self.followers):
        entity = entities.get(entity_id)
        if entity is None or entity.health <= 0:
            remove from followers + follower_items; continue
        if entity.hostile:
            entity.hostile = False  # force peaceful
        if entity.current_target == 'player':
            entity.current_target = None
            entity.ai_state = 'wandering'
```

### `check_npc_inspection`

```
def check_npc_inspection(self):
    if keys[SHIFT] or inspect_tool_active:
        # Suppress during combat
        hostiles_nearby = [e for e in zone_entities if e.hostile and dist(e, player) <= 2]
        if hostiles_nearby: return

        # Find closest non-hostile NPC within 3 cells
        candidates = non_hostile_entities_within(player, 3)
        if candidates:
            target = nearest(candidates)
            target.idle_timer = 30   # freeze for inspection duration
            self.inspected_npc = target.id
    else:
        self.inspected_npc = None
```

---

## Cell Simulation

### `update_screen_cells`

```
def update_screen_cells(self, zone_key):
    grid = screens[zone_key]

    for (x, y) in random_sample_of_cells(grid):
        cell = grid[y][x]

        # Carrot growth
        if cell == CARROT1 and random() < CARROT_GROWTH_RATE:
            multiplier = 1.0
            if cobblestone_within(x, y, 3): multiplier = 50.0
            elif sand_within(x, y, 3):      multiplier = 0.1
            if random() < CARROT_GROWTH_RATE * multiplier:
                grid[y][x] = CARROT2

        elif cell == CARROT2 and random() < CARROT_GROWTH_RATE * multiplier:
            grid[y][x] = CARROT3

        # Cobblestone decay (protected in center lanes and near structures)
        elif cell == COBBLESTONE:
            in_center = abs(x - GRID_WIDTH//2) <= 1 or abs(y - GRID_HEIGHT//2) <= 1
            near_structure = structure_within(x, y, 3)
            if not in_center and not near_structure:
                if random() < COBBLE_DECAY_RATE:
                    grid[y][x] = DIRT

        # Water spread
        elif cell == WATER:
            for neighbor in cardinal_neighbors(x, y):
                if grid[neighbor] == DIRT and random() < WATER_SPREAD_RATE:
                    grid[neighbor] = WATER
                    break  # cap spread per update

        # Grass spread
        elif cell == GRASS:
            for neighbor in cardinal_neighbors(x, y):
                if grid[neighbor] == DIRT and random() < GRASS_SPREAD_RATE:
                    grid[neighbor] = GRASS
                    break
```

---

## Input Handling

### `handle_input`

```
def handle_input(self):
    if autopilot_active:
        drain autopilot_input_queue instead of pygame events
        return

    for event in pygame.event.get():
        if event.type == QUIT: quit()

        if event.type == KEYDOWN:
            key = event.key

            if key in (UP, W):   move_player('up')
            elif key in (DOWN, S): move_player('down')
            elif key in (LEFT, A): move_player('left')
            elif key in (RIGHT, D): move_player('right')

            elif key == SPACE:   interact()
            elif key == L:       player_cast_spell()
            elif key == K:       release_all_enchantments()
            elif key == J:       release_follower()
            elif key == SHIFT:
                if double_tap_detected: toggle_block_lock()
                else:                   block = True
            elif key == V:       friendly_fire = not friendly_fire
            elif key == C:       toggle_crafting_panel()
            elif key == I:       toggle_inventory_panel()
            elif key == T:
                if shift: open_npc_trade_window()   # inspected NPC inventory trade
                else:     toggle_tools_panel()
            elif key == M:       toggle_magic_panel()
            elif key == U:       toggle_actions_panel()
            elif key == G:
                if debug_mode: show_memory_lane()
                else:          gift_item_to_adjacent_npc()
            elif key == F:       toggle_follow_npc()
            elif key == E:       pickup_at_player_cell()
            elif key == N:       npc_trade_interaction()
            elif key == P:       place_item()
            elif key == Q:       toggle_quest_log()
            elif key == D:       drop_item()
            elif key in DIGIT_KEYS: select_tool_slot(key - K_1)

        if event.type == MOUSEBUTTONDOWN:
            if handle_npc_trade_click(event.pos): gain_xp(1)  # inventory trade window
            else:
                handle_inventory_click(event.pos)
                handle_quest_ui_click(event.pos)
```

---

## Player Movement

### `move_player`

```
def move_player(self, direction=None):
    if autopilot_active and autopilot_input_queue:
        direction = autopilot_input_queue.pop(0)

    dx, dy = direction_to_delta(direction)
    nx, ny = player.x + dx, player.y + dy
    zone_key = f"{player.screen_x},{player.screen_y}"

    # Structure exit via bottom edge (house interior)
    if player.in_structure and ny >= GRID_HEIGHT:
        struct = structures[player.structure_key]
        if struct.type == 'house':
            exit_structure()
            return

    # Cave stair exit
    if player.in_structure and grid[ny][nx] == STAIRS_UP:
        ascend_cave()
        return

    # Overworld zone-crossing: only in center corridor
    if not player.in_structure:
        if nx < 0 or nx >= GRID_WIDTH or ny < 0 or ny >= GRID_HEIGHT:
            # Check center-corridor gate
            if direction in ('left', 'right'):
                if abs(player.y - GRID_HEIGHT//2) > 1: return  # outside corridor
            else:
                if abs(player.x - GRID_WIDTH//2) > 1: return
            # Cross zone
            new_sx = player.screen_x + (1 if nx >= GRID_WIDTH else -1 if nx < 0 else 0)
            new_sy = player.screen_y + (1 if ny >= GRID_HEIGHT else -1 if ny < 0 else 0)
            player.screen_x, player.screen_y = new_sx, new_sy
            player.x = nx % GRID_WIDTH
            player.y = ny % GRID_HEIGHT
            ensure_zone_generated(new_sx, new_sy)
            _apply_walk_cell_effects(player, new_zone_key)
            return

    # Collision check (skip for autopilot proxy)
    if not autopilot_active:
        for eid in screen_entities[zone_key]:
            if entities[eid].x == nx and entities[eid].y == ny:
                return   # blocked by entity

    # Cell walkability check
    if CELL_TYPES[grid[ny][nx]]['solid']: return

    player.x, player.y = nx, ny
    player.facing = direction
    _apply_walk_cell_effects(player, zone_key)
    pickup_dropped_items(player, zone_key)
```

---

## Interact

### `interact`

```
def interact(self):
    tx, ty = get_target_cell()   # cell in facing direction
    zone_key = player's zone
    cell = grid[ty][tx]

    # 1. Attack
    for entity in adjacent_entities_at(tx, ty):
        if is_hostile_to_player(entity):
            player_melee_attack(entity)
            return

    # 2. Pick up dropped items
    items_at_player_pos = dropped_items.get(zone_key, {}).get((player.x, player.y))
    if items_at_player_pos:
        collect_items(items_at_player_pos)
        return

    # 3. Cell interaction by type
    if cell == STAIRS_UP:    ascend_cave(); return
    if cell == STAIRS_DOWN:  descend_cave(); return

    if cell == CHEST:
        open_chest_panel(tx, ty, zone_key); return

    if cell in (WELL, WATER):
        player.thirst = player.max_thirst
        play_sound('drink')
        if cell == WATER and random() < 0.15: grid[ty][tx] = DIRT
        return

    if CELL_TYPES[cell].get('enterable'):
        enter_structure(tx, ty); return

    # Tool-gated interactions
    equipped = player['equipped'].get('weapon')
    if equipped == 'axe' and cell in TREE_CELLS:
        action_harvest_cell(actor='player', cell_types=TREE_CELLS, ...)
        return
    if equipped == 'pickaxe' and cell in ROCK_CELLS:
        action_harvest_cell(actor='player', cell_types=ROCK_CELLS, ...)
        return
    if equipped == 'pickaxe' and cell == STONE:
        descend_cave(); return  # dig down with pickaxe on stone
    if equipped == 'hoe' and cell in TILLABLE_CELLS:
        action_transform_cell(actor='player', cell_types=TILLABLE_CELLS, result_cell=SOIL)
        return

    # Bare-hand interactions
    if cell == CARROT3:
        action_harvest_cell(actor='player', cell_types=[CARROT3], ...)
        return
    if cell == SOIL and 'carrot' in player.inventory:
        action_place_cell(actor='player', cell_types=[SOIL], result_cell=CARROT1, item='carrot')
        return
    if cell in (GRASS, DIRT) and 'bones' in player.inventory:
        place_bones(tx, ty)
        return
```

---

## Structure Navigation

### `enter_structure`

```
def enter_structure(self, door_x, door_y):
    zone_key = player's current zone
    struct_key = get_or_generate_structure(door_x, door_y, zone_key)
    struct = structures[struct_key]

    player['in_structure'] = True
    player['structure_key'] = struct_key
    player['origin_zone'] = zone_key
    player['origin_door'] = (door_x, door_y)
    player['cave_depth'] = 0

    # Move player to structure entrance
    player['screen_x'], player['screen_y'] = parse_zone_key(struct_key)
    player['x'], player['y'] = struct['entrance']

    # Teleport followers
    for fid in self.followers:
        entities[fid].screen_x, entities[fid].screen_y = player['screen_x'], player['screen_y']
        entities[fid].x, entities[fid].y = struct['entrance']

    self._pending_structure_entry = True
```

### `exit_structure`

```
def exit_structure(self):
    origin_zone = player['origin_zone']
    door_x, door_y = player['origin_door']

    player['in_structure'] = False
    player['structure_key'] = None
    player['cave_depth'] = 0
    player['cave_via_structure'] = False

    sx, sy = parse_zone_key(origin_zone)
    player['screen_x'], player['screen_y'] = sx, sy

    # Place near door
    exit_pos = find_walkable_near(door_x, door_y, screens[origin_zone])
    player['x'], player['y'] = exit_pos

    # Teleport followers
    for fid in self.followers:
        entities[fid].screen_x, entities[fid].screen_y = sx, sy
        entities[fid].x, entities[fid].y = exit_pos

    # Prevent immediate re-entry
    player_memory_lane.append(exit_pos)
```

### `descend_cave`

```
def descend_cave(self):
    current_depth = player['cave_depth']
    parent_key = player['structure_key'] or player['origin_zone']

    # Generate next level if needed
    next_struct_key = get_or_generate_cave_level(parent_key, current_depth + 1)

    player['cave_depth'] += 1
    player['screen_x'], player['screen_y'] = parse_zone_key(next_struct_key)
    player['structure_key'] = next_struct_key
    player['x'], player['y'] = structures[next_struct_key]['entrance']
```

### `ascend_cave`

```
def ascend_cave(self):
    if player['cave_depth'] <= 1:
        if player['cave_via_structure']:
            _exit_secret_cave_entrance()
        else:
            exit_structure()
    else:
        # Go up one level
        parent_key = structures[player['structure_key']]['parent_key']
        player['cave_depth'] -= 1
        player['screen_x'], player['screen_y'] = parse_zone_key(parent_key)
        player['structure_key'] = parent_key
        player['x'], player['y'] = structures[parent_key]['stairs_up_pos']
```

### `_exit_secret_cave_entrance`

```
def _exit_secret_cave_entrance(self):
    # Cave was entered via MINESHAFT inside a house — must return to that house interior
    origin_struct = player.get('pre_cave_structure_key')

    if origin_struct and origin_struct in structures:
        # Return to house interior
        player['structure_key'] = origin_struct
        player['screen_x'], player['screen_y'] = parse_zone_key(origin_struct)
        player['x'], player['y'] = structures[origin_struct]['mineshaft_exit_pos']
        player['cave_depth'] = 0
    else:
        # Fallback: return to overworld
        exit_structure()
```

---

## `new_game`

```
def new_game(self):
    # Reset all state
    self.tick = 0
    self.entities.clear()
    self.screens.clear()
    self.screen_entities.clear()
    self.structures.clear()
    self.dropped_items.clear()
    self.chest_contents.clear()
    self.followers.clear()
    self.follower_items.clear()   # purge stale entries from previous session

    # Reset player to defaults
    self.player = default_player_dict()

    # Generate starting zone
    generate_starting_world()

    # Defer follower spawn until after time-pass simulation
    self._pending_follower_type = 'SKELETON'   # spawned after world aging completes

    # Trigger world aging (150–250 simulated years)
    self.time_pass_years = random.randint(150, 250)
    self.state = 'death'   # death screen / time-pass cutscene begins
```

---

## `run` — Main Loop

```
def run(self):
    clock = pygame.time.Clock()

    while True:
        handle_input()
        move_player()
        check_follower_integrity()
        sound.update()
        check_npc_inspection()

        if tick % 600 == 0:
            reconcile_screen_entities()     # heal zone-bucket desync

        if tick % 300 == 0:
            # Freeze detector
            if tick == self._last_freeze_check_tick:
                watchdog.log('freeze_detected', {tick: tick})
            self._last_freeze_check_tick = tick

        if tick % 60 == 0:
            # Passive regen
            player.health = min(max_health, health + regen_rate)
            player.mana   = min(max_mana,   mana   + mana_regen)

        update_quests()
        update_enchanted_cells()
        update_cells()          # distance-throttled cell automata
        # NOTE: update_entities() is dead code — all NPC AI runs through
        # zones.py probabilistic_zone_updates(), NOT called here.

        watchdog.update(tick, self)

        # Autosave every 30s real time
        if time.time() - last_autosave > 30:
            save_game()
            last_autosave = time.time()

        _auto_debug_shutdown()   # check session timer for observation runs

        tick += 1
        draw()
        clock.tick(60)           # cap at 60 FPS
```
