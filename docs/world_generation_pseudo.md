# world/generation.py + world/zones.py — Pseudo-Code Reference

---

## WorldGenerationMixin (generation.py)

### `generate_zone_name`

```
def generate_zone_name(biome):
    adj       = random.choice(_ZONE_ADJECTIVES)         # 'Red', 'Silent', etc.
    noun      = random.choice(_ZONE_NOUNS[biome])       # biome-specific
    biome_type = random.choice(_ZONE_BIOME_TYPES[biome])
    return f"{adj} {noun} {biome_type}"
    # e.g. "Silent Ash Wood"
```

### `generate_structure_name`

```
def generate_structure_name(structure_type, depth, parent_name, psx, psy):
    if structure_type == 'HOUSE_INTERIOR':
        parent_key = f"{psx},{psy}"
        for eid in screen_entities.get(parent_key, []):
            e = entities.get(eid)
            if e and e.name:
                return f"{e.name}'s House"   # personalized if NPC found
        return random.choice(_FALLBACK_HOUSE_NAMES)

    elif structure_type == 'CAVE':
        if depth == 1:
            return f"{parent_name} {random.choice(_CAVE_MODIFIERS)} Cave"
        else:
            base = parent_name.rsplit(' Lvl ', 1)[0]   # strip prior depth suffix
            return f"{base} Lvl {depth}"
```

---

## `generate_screen` — Overworld Zone Generation

```
def generate_screen(sx, sy):
    key = f"{sx},{sy}"
    if key in self.screens: return screens[key]   # idempotent

    biome_name = random.choice(list(BIOMES.keys()))
    biome = BIOMES[biome_name]

    # --- EXITS ---
    exits = {side: random.random() > 0.5 for side in ('top', 'bottom', 'left', 'right')}

    # Force bidirectional consistency with already-generated neighbors
    for neighbor_key, my_exit, their_exit in [
        (f"{sx},{sy-1}", 'top',    'bottom'),
        (f"{sx},{sy+1}", 'bottom', 'top'),
        (f"{sx-1},{sy}", 'left',   'right'),
        (f"{sx+1},{sy}", 'right',  'left'),
    ]:
        if neighbor_key in screens:
            exits[my_exit] = screens[neighbor_key]['exits'][their_exit]

    # Guarantee ≥ 2 exits
    while sum(exits.values()) < 2:
        exits[random.choice([s for s, v in exits.items() if not v])] = True

    # 50% chance to open a 3rd exit
    if sum(exits.values()) == 2 and random.random() < 0.5:
        exits[random.choice([s for s, v in exits.items() if not v])] = True

    # Push consistency to already-generated neighbors that need a new exit
    for neighbor_key, my_exit, their_exit in [...]:
        if exits[my_exit] and neighbor_key in screens:
            screens[neighbor_key]['exits'][their_exit] = True
            update_screen_exits(neighbor_key)

    # --- GRID ---
    exit_cell = biome_to_exit_cell[biome_name]  # GRASS for FOREST, SAND for DESERT, etc.

    grid = []
    for y in range(GRID_HEIGHT):
        row = []
        for x in range(GRID_WIDTH):
            is_border = (y == 0 or y == GRID_HEIGHT-1 or x == 0 or x == GRID_WIDTH-1)
            if is_border:
                if is_exit_position(x, y, exits):
                    row.append(exit_cell)
                else:
                    row.append('WALL')
            else:
                # Sample from biome probability table
                rand = random.random()
                cell = 'GRASS'
                cumulative = 0
                for terrain, prob in biome.items():
                    cumulative += prob
                    if rand < cumulative:
                        cell = terrain
                        break
                row.append(cell)
        grid.append(row)

    # --- VARIANT GRID ---
    variant_grid = [[roll_cell_variant(grid[y][x]) for x in range(GRID_WIDTH)]
                    for y in range(GRID_HEIGHT)]

    # --- SPECIAL PLACEMENTS ---
    if biome_name != 'LAKE' and random.random() > 0.7:
        grid[random_y][random_x] = random.choice(['HOUSE', 'CAVE'])

    if biome_name == 'DESERT' and random.random() < 0.60:
        place 1–4 RUINED_SANDSTONE_COLUMN on SAND/DIRT cells

    if biome_name != 'LAKE' and random.random() < 0.10:
        grid[center_y ± 3][center_x ± 3] = 'WELL'

    # --- CAVE CHANCE ---
    cave_chance = NATURAL_CAVE_ZONE_CHANCE
    if biome_name == 'MOUNTAINS': cave_chance *= 3
    elif biome_name == 'DESERT':  cave_chance *= 1.5
    if biome_name != 'LAKE' and random.random() < cave_chance:
        solid_cells = [(x,y) for x,y in interior if CELL_TYPES[grid[y][x]]['solid'] and grid[y][x] != 'WALL']
        if solid_cells:
            cx, cy = random.choice(solid_cells)
            grid[cy][cx] = 'CAVE'

    # --- REGISTER ---
    screen_data = {
        'grid': grid, 'variant_grid': variant_grid,
        'exits': exits, 'biome': biome_name,
        'name': generate_zone_name(biome_name),
        'controlling_faction': None,
        'biome_domain_id': None,
        'faction_domain_id': None,
    }
    self.screens[key] = screen_data
    self.instantiated_zones.add(key)

    update_biome_domain(key)
    spawn_entities_for_screen(sx, sy, biome_name)
    spawn_runestones_for_screen(sx, sy)

    return screen_data
```

---

## `set_grid_cell` (always use this for cell changes)

```
def set_grid_cell(screen, x, y, new_cell):
    screen['grid'][y][x] = new_cell
    screen['variant_grid'][y][x] = roll_cell_variant(new_cell)
    # Keeps gameplay grid and visual variant grid synchronized
```

---

## `update_screen_exits` — Materialize exits dict into border cells

```
def update_screen_exits(sx, sy):
    screen = screens[f"{sx},{sy}"]
    exits = screen['exits']
    border_wall = 'CLIFF' if biome == 'LAKE' else 'WALL'

    for each of the 4 edges:
        for each cell on that edge:
            if cell is at the 2-cell exit position AND exit is open:
                # Use a blend of this biome's cell and neighbor's biome cell
                grid[y][x] = get_common_cell_for_biome(...)
            else:
                grid[y][x] = border_wall
```

---

## `generate_structure_zone` — Interior Zone Creation

```
def generate_structure_zone(parent_sx, parent_sy, cell_x, cell_y, structure_type, depth=1):
    parent_key = f"{parent_sx},{parent_sy}"

    # CAVE depth 1: reuse existing cave for this parent zone
    if structure_type == 'CAVE' and depth == 1:
        if parent_key in zone_cave_systems:
            return zone_cave_systems[parent_key]

    # Assign virtual negative-x coordinate (never reachable by walking)
    sid = self.next_structure_id
    self.next_structure_id += 1
    vx = -(1000 + sid * 10)
    vy = 0
    zone_key = f"{vx},{vy}"

    if zone_key in structures: return zone_key

    # Generate interior grid
    if structure_type == 'HOUSE_INTERIOR':
        grid = generate_house_interior(depth)
        entrance_pos = (GRID_WIDTH//2, GRID_HEIGHT-2)
        stairs_down_pos = None
    elif structure_type == 'CAVE':
        grid, stairs_down_pos = generate_cave_interior(depth, cell_x, cell_y)
        entrance_pos = (clamp(cell_x, 2, GRID_WIDTH-3), clamp(cell_y, 2, GRID_HEIGHT-3))

    structure_data = {
        'type': structure_type,
        'parent_screen': (parent_sx, parent_sy),
        'parent_cell': (cell_x, cell_y),
        'grid': grid,
        'depth': depth,
        'entrance': entrance_pos,
        'exit': entrance_pos,
        'stairs_down': stairs_down_pos,
        'chests': {},
        'entities': [],
        'name': generate_structure_name(structure_type, depth, ...),
    }

    # Dual registration: both structures and screens dicts
    self.structures[zone_key] = structure_data
    self.screens[zone_key]    = structure_data
    self.screen_entities[zone_key] = []
    self.instantiated_zones.add(zone_key)

    # Bidirectional door map
    door_map[(parent_key, cell_x, cell_y)] = (zone_key, entrance_pos.x, entrance_pos.y)
    door_map[(zone_key, entrance_pos.x, entrance_pos.y)] = (parent_key, cell_x, cell_y)

    if structure_type == 'CAVE' and depth == 1:
        zone_cave_systems[parent_key] = zone_key

    # Place chests and spawn entities (interior is ready immediately)
    if structure_type == 'HOUSE_INTERIOR':
        place_house_chests(structure_data)
        if random.random() < 0.5: spawn_house_npc(structure_data)
    elif structure_type == 'CAVE':
        place_cave_chests(structure_data, depth)
        _spawn_cave_entities(structure_data)

    # Fix up entity coords to match virtual zone coordinates
    for eid in structure_data['entities']:
        entities[eid].screen_x = vx
        entities[eid].screen_y = vy
        entities[eid].in_structure = True

    add_zone_connection(parent_key, zone_key, 'structure_entrance', cell_x, cell_y)
    return zone_key
```

---

## `generate_house_interior`

```
def generate_house_interior(depth):
    grid = [[WALL-bordered FLOOR_WOOD/WOOD interior]]

    # Doorway: 3 cells wide at bottom center, always FLOOR_WOOD
    grid[GRID_HEIGHT-2][GRID_WIDTH//2 ± 1] = 'FLOOR_WOOD'
    grid[GRID_HEIGHT-1][GRID_WIDTH//2 ± 1] = 'FLOOR_WOOD'  # exit row

    # Bed against top wall
    bed_candidates = [(x, 1) for x in range(2, GRID_WIDTH-2) if grid[1][x] == 'FLOOR_WOOD']
    bx, by = random.choice(bed_candidates)
    grid[by][bx] = random.choice(['BED_BLUE', 'BED_WHITE'])

    # 0-2 furniture items on random FLOOR_WOOD
    place 0–2 of: BOOKSHELF, WOOD_TABLE, WOOD_CHAIR, SMALL_POTTED_PLANT

    # Guaranteed water trough
    place 1 WATER_TROUGH on any FLOOR_WOOD (up to 30 attempts)

    # Apple crate (guaranteed) + 0-2 empty crates in corner candidates
    for corner_pos in shuffled_corners:
        if not apple_placed: grid[cy][cx] = 'APPLE_CRATE'; apple_placed = True
        elif crates_placed < crate_limit: grid[cy][cx] = 'EMPTY_CRATE'

    # 0-3 barrels on random FLOOR_WOOD
    place 0–3 BARRELs

    return grid
```

---

## `generate_cave_interior`

```
def generate_cave_interior(depth, entrance_x, entrance_y):
    grid = []
    for y, x in all cells:
        if border: row.append('CAVE_WALL')
        else:
            ore_chance   = 0.03 if depth == 1 else 0.07
            stone_chance = 0.15 - ore_chance
            if   rand < ore_chance:               row.append('IRON_ORE')
            elif rand < ore_chance + stone_chance: row.append('STONE')
            else:                                  row.append('CAVE_FLOOR')

    # STAIRS_UP aligned to entrance, 3x3 area cleared
    up_x = clamp(entrance_x, 2, GRID_WIDTH-3)
    up_y = clamp(entrance_y, 2, GRID_HEIGHT-3)
    clear 3x3 around (up_x, up_y) to CAVE_FLOOR
    grid[up_y][up_x] = 'STAIRS_UP'

    # 1-3 mushroom seeds
    place 1–3 BLUE_MUSHROOM on CAVE_FLOOR cells

    # 20% water trough
    if random.random() < 0.20: place WATER_TROUGH on CAVE_FLOOR

    # 70% STAIRS_DOWN at a random interior position, 3x3 cleared
    stairs_down_pos = None
    if random.random() < 0.7:
        sx, sy = random interior CAVE_FLOOR cell
        clear 3x3 around (sx, sy) to CAVE_FLOOR
        grid[sy][sx] = 'STAIRS_DOWN'
        stairs_down_pos = (sx, sy)

    return grid, stairs_down_pos
```

---

## ZonesMixin (zones.py)

### `_purge_zone`

```
def _purge_zone(zone_key):
    # Remove all entities in zone (+ clean follower lists)
    for eid in screen_entities.get(zone_key, []):
        followers.remove(eid)
        follower_items.pop(eid)
        del entities[eid]
    del screen_entities[zone_key]

    # Remove all zone data
    zone_keepers.pop(zone_key)
    dropped_items.pop(zone_key)
    buried_items.pop(zone_key)
    # chest_contents keys: "zone_key:x,y"
    del chest_contents[k] for k starting with zone_key
    # door_map: tuple keys (zone, x, y)
    del door_map[k] for k where k[0] == zone_key or door_map[k][0] == zone_key
    enchanted_cells.pop(zone_key)
    screens.pop(zone_key)
    instantiated_zones.discard(zone_key)
    screen_last_update.pop(zone_key)
    zone_rain.pop(zone_key)
    zones_deleted += 1
```

---

### `probabilistic_zone_updates`

```
def probabilistic_zone_updates():
    if not time_pass_active and tick % UPDATE_FREQUENCY != 0: return

    update_day_night_cycle()
    move_items_to_nearest_chest()

    # --- NEW ZONE INSTANTIATION ---
    overworld_count = count overworld zones
    inst_chance = NEW_ZONE_INSTANTIATE_CHANCE
    if overworld_count >= ZONE_SOFT_CAP:
        inst_chance *= max(0.02, 1.0 / (1.0 + excess * 0.15))   # soft cap
    if random.random() < inst_chance:
        pick random zone within ±20 of player
        if zone doesn't exist:
            prob = 1.0 / (1.0 + distance * 0.25)    # distance-weighted
            if random.random() < prob: generate_screen(...)

    # --- 600-TICK MAINTENANCE ---
    if tick % 600 == 0:
        cleanup_screen_entities()
        recompute faction control for all overworld zones
        instantiated_zones = set(screens.keys())   # sync
        remove stale door_map entries
        # Clean up structure zones whose entrance cell was destroyed
        for struct_key in structure_zones:
            if entrance cell not in ('HOUSE','STONE_HOUSE','CAVE','MINESHAFT'):
                deinstantiate_structure_zone(struct_key)
        # Zone de-instantiation (distant + idle + empty)
        for zk in overworld zones at distance > 4:
            if idle > 3600 ticks AND no alive entities:
                if random.random() < min(0.9, dist * 0.04):
                    _purge_zone(zk)

    # --- STALENESS HARD TRIM ---
    for zk in overworld zones at distance > 4:
        stale = tick - screen_last_update[zk]
        if stale >= 20000:
            if random.random() < min(1.0, stale / 100000):
                _purge_zone(zk)

    ensure_nearby_zones_exist()
    priority_queue = get_priority_sorted_zones()

    # --- MANDATORY ZONES (player + 4 cardinals + connected structures) ---
    mandatory = {player_zone} | adjacent zones | connected structure zones
    for mz in mandatory:
        update_zone_with_coverage(mz, cell_coverage=0.5, entity_coverage=1.0)

    # --- PRIORITY QUEUE ---
    for position, zone_key in enumerate(priority_queue):
        if zones_updated >= MAX_ZONES_PER_UPDATE: break
        if zone_key in mandatory: continue
        update_chance = max(0.05, (100 - position) / 100.0)
        if random.random() > update_chance: continue
        entity_cov = update_chance
        cell_cov   = update_chance * 0.5
        update_zone_with_coverage(zone_key, cell_cov, entity_cov)

    # Sync player zone rain to self.is_raining for UI/sounds
    self.is_raining = zone_rain[player_zone_key]['is_raining']
```

---

### `update_zone_with_coverage` (per-zone tick, key sections)

```
def update_zone_with_coverage(zone_x, zone_y, cell_coverage, entity_coverage):
    _decay_factor = 1.0 + distance_from_player * 0.02  # distant zones decay faster

    # Zone-level events
    check_zone_threats(); check_raid_event(); check_cave_spawn_hostile()
    check_night_skeleton_spawn(); check_termite_spawn()
    decay_dropped_items(); decay_items_to_buried(); decay_buried_items()
    consolidate_dropped_items(); consolidate_chests(); assign_zone_keepers()

    # Per-zone rain (independent cycle per zone)
    zone_rain[zone_key]['weather_timer'] += 1
    if timer >= cycle:
        start rain for random duration
        reset timer and cycle

    # Temporarily set self.is_raining = this zone's rain state for apply_cellular_automata
    apply_cellular_automata(zone_x, zone_y, cell_coverage)

    # --- CELL LOOP ---
    for (x, y) in interior cells:
        if enchanted: skip

        # CHEST: decay with contents, revert background when empty
        if cell == 'CHEST':
            if contents exist: 0.5% chance dump to dropped_items, revert background
            else: immediately revert background

        # Data-driven growth/decay from CELL_TYPES
        if 'grows_to' in cell_info:
            if random() < growth_rate * time_pass_speed:
                set_grid_cell(screen, x, y, cell_info['grows_to'])
        elif 'degrades_to' in cell_info:
            rate = degrade_rate
            # Carrot decay modifiers: 50x near cobblestone, 10x near sand
            if cell in CARROT_CELLS:
                if cobblestone_adjacent: rate *= 50
                elif sand_adjacent:      rate *= 10
            # Cobblestone: protect center lanes and cells near structures
            if cell == 'COBBLESTONE':
                if in_center_lane or near_structure: continue
            if random() < rate * time_pass_speed * _decay_factor:
                set_grid_cell(screen, x, y, cell_info['degrades_to'])
                if old_cell == 'HOUSE': process_house_destruction(...)

    # Desert rock/ore formation
    if biome == 'DESERT':
        SAND → STONE at DESERT_ROCK_FORMATION_RATE * time_pass_speed
        STONE → IRON_ORE at DESERT_ORE_FORMATION_RATE * time_pass_speed

    # Biome reversion
    for (x, y) in interior cells:
        if cell in foreign_revert_targets[biome]:
            native_adj = count native-biome cardinal neighbors
            revert_rate = 0.12 if native_adj >= 3  # stranded — fast
                        = 0.035 if native_adj == 2
                        = 0.003 if native_adj <= 1   # edge — slow
            if cell == 'SAND' and not DESERT and zone_is_raining: revert_rate = max(0.08, ...)
            if random() < revert_rate: grid[y][x] = base_cell

    # Native cells spread to adjacent non-native/non-protected cells
    if cell in native_cells and random() < 0.005:
        spread to one random adjacent cell

    # --- ENTITY LOOP ---
    for entity in zone_entities:
        entity.age += 1 (every 600 ticks / time_pass_speed)
        entity.decay_stats()
        for _ in range(_extra_decay + _pop_extra): entity.decay_stats()  # distance/crowd penalty
        if random() < 0.25 and inventory: consume random item stack (heal if food)
        if SKELETON and not is_night: entity.health -= SKELETON_DAYLIGHT_DAMAGE
        heal_boost = HOUSE_HEALING_MULTIPLIER if HOUSE within 3  # 3x
                   = CAMP_HEALING_MULTIPLIER  if CAMP within 3   # 2x
                   = 1.0 otherwise
        if not recently_attacked: entity.regenerate_health(heal_boost)
        # Energy regen: idle=+2, stationary=+1, moving=0
        update_entity_ai(entity_id, entity)

    # Entity inventory overflow → chest
    if any stack > 20:
        try fill adjacent existing CHEST (70% chance)
        else if no CHEST within 5 cells: place new CHEST (60%)

    # Entity consolidation (every 300 ticks)
    if zone has > 2 of same base type:
        merge pairs → _double (1.5x health, 1.3x strength)

    # Faction revolution (0.05% chance)
    if 3+ faction warriors: all switch to new faction

    # Faction raid (0.1% chance on zones with 8+ humanoids)
    spawn 3 raiders from raiding faction at zone entrances
    kill lowest-level NPC

    # Population maintenance (every 300 ticks)
    if no TRADER: spawn TRADER first
    elif no GUARD: spawn GUARD
    elif no WARRIOR: 50% spawn WARRIOR
    if traders/guards can fill missing farmer/lumberjack/miner roles: convert type

    # Empty distant zones: purge if no alive entities, no structures, no drops
    if distance > 4 and empty: _purge_zone(zone_key)
```

---

### `catch_up_screen`

```
def catch_up_screen(sx, sy, cycles_missed):
    key = f"{sx},{sy}"
    cycles_missed = min(cycles_missed, MAX_CYCLES_TO_SIMULATE)

    if cycles_missed < 5:
        # Tier 1: accurate — run CA each missed cycle
        for _ in range(cycles_missed): apply_cellular_automata(sx, sy)
    else:
        # Tier 2: bulk CA with cached neighbor counts
        neighbor_cache = precompute_neighbor_counts(key)
        for (x, y) in interior cells:
            new_cell, change_prob = apply_bulk_ca_rules(cell, neighbor_cache, cycles_missed)
            if random() < change_prob: set_grid_cell(screen, x, y, new_cell)

    consolidate_dropped_items(key)
    catch_up_entities(sx, sy, cycles_missed)
    screen_last_update[key] = self.tick
```

---

### `calculate_zone_priority`

```
def calculate_zone_priority(zone_key):
    N = max(1, len(screens))   # total zones

    distance_score    = N * 1.0          if zone_key == player_zone
                      = N * 0.9          if distance == 0 (same-coord structure)
                      = N * (0.5/dist)   otherwise

    staleness_score   = (tick - last_update) / 30.0  # uncapped

    connection_score  = N * 0.4  if connected to player zone
                      = N * 0.2  if connected to player-adjacent zone
                      = 0.0      otherwise

    structure_score   = N * 0.15  if structure zone
                      = N * 0.05  if zone contains structures
                      = 0.0       otherwise

    quest_score       = N * 0.2  if zone is active quest target

    return sum of all five scores
```

---

### `update_biome_domain`

```
def update_biome_domain(zone_key):
    # Leave old domain; check for split if domain shrank
    old_domain.zones.discard(zone_key)
    if old_domain has 0 zones: delete it
    elif old_domain split: _check_biome_domain_contiguity(old_domain_id)

    # Find same-biome exit-connected neighbors
    for each cardinal neighbor connected by open exit in both directions:
        if neighbor.biome == this.biome:
            collect their domain_ids

    if no same-biome neighbors:
        create new single-zone domain
        return

    # Pick largest surviving domain; absorb all others into it
    surviving = largest neighbor domain
    for other in remaining neighbor domains:
        surviving.zones |= other.zones
        for zk in other.zones: screens[zk].biome_domain_id = surviving.id
        del other
    surviving.zones.add(zone_key)
    screen.biome_domain_id = surviving.id
    screen.name = surviving.name
```
