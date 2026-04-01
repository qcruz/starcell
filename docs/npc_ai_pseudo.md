# npc_ai.py — Pseudo-Code Reference

This document bridges the plain-language guide and the actual code. Each block uses
simplified pseudo-code that mirrors the real structure and variable names.

---

## Class: NpcAiMixin

```
class NpcAiMixin:
    # Mixed into Game. Has access to self.player, self.entities,
    # self.screens, self.tick, self.followers, etc.
```

---

## Utilities

### `_same_context_as_player(entity)`
```
player_zone = "{player.screen_x},{player.screen_y}"
entity_zone  = "{entity.screen_x},{entity.screen_y}"
return player_zone == entity_zone
```

### `_apply_walk_cell_effects(entity, screen_key)`
```
cell = grid[entity.y][entity.x]

if SKELETON:
    GRASS → DIRT  (always)

elif TERMITE:
    25% chance:
        GRASS or DIRT → SAND
        DIRT → GRASS

elif BUTTERFLY / RED_BIRD / BAT:
    25% chance: DIRT → GRASS

elif FARMER:
    25% chance:
        SAND → DIRT
        DIRT → SOIL
        SOIL + has_carrot → CARROT1, consume 1 carrot

elif WARRIOR / COMMANDER / KING / BLACKSMITH / WIZARD / LUMBERJACK / MINER:
    25% chance, only on center cross of zone:
        GRASS or SOIL → DIRT
        DIRT → COBBLESTONE
```

### `_try_adjacent_consume(entity, screen_key)`
```
hunger_pct_missing = 1.0 - (entity.hunger / entity.max_hunger)
thirst_pct_missing = 1.0 - (entity.thirst / entity.max_thirst)

want_food  = random() < hunger_pct_missing
want_water = random() < thirst_pct_missing

if not want_food and not want_water: return

for each cell in (own cell + 8 adjacent cells):
    if want_food and cell in entity.food_sources:
        entity.hunger = max
        decay carrot cell one step (50% chance, non-passive grazers only)
        want_food = False

    if want_water and cell in entity.water_sources:
        entity.thirst = max
        15% chance: WATER → DIRT  (evaporation)
        want_water = False

    if neither needed: return
```

---

## Main Update: `update_entity_ai(entity_id, entity)`

```
── GUARDS ────────────────────────────────────────────────────────────────────

if already updated this tick: return             # double-update guard

if not in flee state:
    if random() > (energy / max_energy): go idle, return  # energy gate

entity.moved_this_update = False                 # reset movement flag

if peaceful entity AND hit in last 5 ticks AND has attacker:
    ai_state = 'flee', flee_target = attacker    # immediate flee

if ambient sound timer expired:
    play creature sound, reset timer to 200-600 ticks

if autopilot mode:
    force clear all idle_timer and inspected_npc flags

if player is inspecting this NPC AND NPC is not in combat:
    return                                        # freeze NPC for inspection

if FARMER and carrot_count < 1:
    carrot_count = 1                              # guarantee planting supply

if keeper: resolve_keeper_target()

── INNER STATE MACHINE ───────────────────────────────────────────────────────
update_entity_ai_state(entity_id, entity)        # updates ai_state, current_target

screen_key = "{entity.screen_x},{entity.screen_y}"

── CONSISTENCY GUARD ─────────────────────────────────────────────────────────
if screen_key in structures AND entity.in_structure is False:
    set in_structure = True, structure_key = screen_key
elif screen_key NOT in structures AND entity.in_structure is True:
    set in_structure = False
    move entity registration from old structure bucket to overworld bucket

── OUTER STATE DISPATCH ──────────────────────────────────────────────────────
switch entity.ai_state:

    case 'combat':
        if target == 'player':
            if not same zone as player: go wandering
            elif adjacent (dist==1):
                roll attack_chance → deal damage to player
                flying entity: 40% disengage after hit
            elif dist <= 8: move toward player
            else: lose interest, go wandering

        elif target is entity_id:
            if target dead: go targeting
            if overlapping (dist==0): step to adjacent free cell
            elif adjacent (dist==1):
                face target
                find_and_attack_enemy()
                flying: 40% disengage
            elif dist > 1: go targeting (close gap first)

    case 'flee':
        80% chance: step one cell away from threat
        allow zone crossing while fleeing

        if not recently_attacked AND no hostile within 5 cells:
            go wandering, clear flee_target
        return  # no other actions while fleeing

    case 'exit':
        if keeper: go wandering     # keepers can't exit their anchor zone
        else: seek_zone_exit()

    case 'targeting':
        if current_target == 'player':
            if same zone: move_toward_position(player.x, player.y)
            else: clear target, go wandering

        elif current_target is entity_id:
            if target in different zone: route toward exit facing target zone
            elif same zone: move_toward_position(target.x, target.y)

        elif current_target is cell tuple:
            navigate to cell, handle structure entry when adjacent

    case 'wandering':
        if keeper type 1 or 2:
            if out of range of anchor: move toward anchor
            elif type 2: wander freely within range
            # type 1 holds position
        else:
            wander_entity()

    case 'idle':
        if no target: go wandering immediately
        else:
            dist = distance to current_target
            if dist <= 1:
                face target
                dispatch action based on target_type:
                    'hostile'        → go combat
                    'quest_target'   → award XP, complete quest check, go wandering
                    'food'           → eat, decay cell
                    'water'          → drink, possibly evaporate cell
                    'resource'       → execute behavior_config
                    'special' (clearing) → attack adjacent blocking cell (15% destroy)
            elif dist > 1: go targeting

── POST-BEHAVIOR CLEANUP ─────────────────────────────────────────────────────
decrement spell_cooldown if > 0
decrement action_animation_timer if > 0

if moved this tick AND overworld:
    _apply_walk_cell_effects()
    _try_adjacent_consume()

── ITEM PICKUP ───────────────────────────────────────────────────────────────
if dropped items at entity's position:
    add items to inventory
    if item is gold AND player adjacent: process_npc_trade()
    gain_xp(1)

── STRUCTURE ENTRY ───────────────────────────────────────────────────────────
try_npc_enter_structure()         # opportunistic entry, every tick

── WARRIOR HOME RETURN ───────────────────────────────────────────────────────
every WARRIOR_HOME_RETURN_INTERVAL ticks:
    if not in home zone:
        target nearest exit toward home, go targeting

── FOLLOWER FORMATION ────────────────────────────────────────────────────────
if entity is follower:
    if same screen as player:
        if dist > 2: move toward player immediately, return
        elif dist > 0 AND tick % 30 == 0: nudge closer, return
        else: idle, return
    else: teleport to player screen, return

── BEHAVIOR TICK (every 60 ticks, only if didn't move) ───────────────────────
if tick % 60 == 0 AND not moved:
    if has behavior_config: execute_entity_behavior()
    elif GOBLIN / BANDIT / TERMITE: hostile_structure_behavior()
    if can_place_camp AND random < rate: npc_place_camp()
    if MINER: attempt to mine cave or place mineshaft
    if humanoid (non-lumberjack): random chance to clear nearby tree

── ZONE TRANSITION ───────────────────────────────────────────────────────────
if entity is at an exit cell AND cooldown expired:
    roll travel_rate (autopilot=100%, wolf=60%, targeting=100%, default=30%)
    if roll passes: try_entity_zone_transition()
        on success: reset stuck counter, award travel XP

── SAFETY BOUNDS CHECK ───────────────────────────────────────────────────────
clamp entity.x/y to grid bounds
if entity on solid cell: find nearest walkable cell within 1 step
```

---

## Inner State Machine: `update_entity_ai_state(entity_id, entity)`

```
if entity is player OR entity is dead: return

lazy-init: ai_state, current_target, target_type, ai_state_timer, flee_target

── SPECIAL CASE: NOCTURNAL (bats) ────────────────────────────────────────────
if entity is nocturnal:
    if daytime:
        if already in structure: go idle for 5 ticks, return
        else: find nearest enterable structure, target it, return
    # nighttime: fall through to normal hostile behavior

── COUNTERATTACK (reactive, ignores timer) ───────────────────────────────────
if entity was hit recently (counterattack_target set):
    threat_level = attacker's level
    level_ratio  = threat_level / entity.level
    effective_flee = min(flee_chance * level_ratio, 0.95)

    if random() < effective_flee:
        go flee state, flee_target = attacker
    else:
        go combat state, target = attacker
    return

── HOSTILE PROXIMITY CHECK (reactive, ignores timer) ─────────────────────────
if not in combat or flee:
    scan all entities in same zone for enemies
    (enemies = hostile targeting peaceful, or different faction, or different hostile species)
    also check player if entity is hostile and not a follower

    closest_hostile_id   = nearest enemy in zone
    closest_hostile_dist = distance to that enemy

    if enemy within HOSTILE_DETECTION_RANGE (8 cells):
        if entity has combat capability ('hostile' in target_types):
            if dist == 1: go combat, target = enemy
            else:         go targeting, target = enemy
        else:  # non-combat entity (farmer, trader)
            if enemy within half detection range:
                random < flee tendency: go flee

── TIMER DECREMENT ───────────────────────────────────────────────────────────
if ai_state_timer > 0: ai_state_timer -= 1

── KEEPER OVERRIDE (before timer gate) ───────────────────────────────────────
if keeper type 1 or 2 AND not critically hungry/thirsty:
    if target is in different zone: route to exit toward target zone
    elif out of range: go targeting toward anchor position

── TIMER GATE ────────────────────────────────────────────────────────────────
if ai_state_timer > 0: return   # committed to current state, no transitions yet

── SURVIVAL URGENCY ──────────────────────────────────────────────────────────
survival_urgency = average of (hunger_missing%, thirst_missing%)
eff_aggressiveness = aggressiveness + survival_urgency  (capped at 1.0)
if night AND peaceful AND overworld: eff_aggressiveness += 0.4  (shelter urgency)

── STATE TRANSITIONS (only when timer == 0) ──────────────────────────────────

if ai_state == 'idle':
    roll = random()
    if roll < eff_aggressiveness:
        target_type = determine_target_type()
        if found: go targeting, target = resolve(target_type), timer=2
        else:     go wandering, timer=3
    elif roll < eff_aggressiveness + passiveness:
        go wandering, timer=2
    else:
        stay idle, timer = random(2, 4)

elif ai_state == 'wandering':
    clear current_target, clear target_type   # wipe stale state
    roll = random()
    if roll < eff_aggressiveness:
        target_type = determine_target_type()
        if found: go targeting, target = resolve(target_type), timer=2
        else:     stay wandering, timer=3
    elif roll < eff_aggressiveness + idleness:
        go idle, timer = random(2, 4)
    else:
        stay wandering, timer=2

elif ai_state == 'flee':
    clear target_type, reset timer=2   # stay responsive to proximity check above
```

---

## `determine_target_type(entity)` — Target Scoring

```
screen_key = entity's current zone
scores = {}

# Each tier adds a score if the condition is met.
# Higher urgency = higher score. Highest scorer wins.

TIER 1 — quest targets
    if entity has active quest AND quest cell/entity exists in zone:
        scores['quest_target'] += priority_weight * urgency

TIER 2 — role targets (MINER seeks MINESHAFT, etc.)
    if entity has quest_focus AND role cell exists in zone:
        scores['role'] += weight

TIER 3 — food
    food_urgency = 1.0 - (hunger / max_hunger)
    if food_urgency > threshold AND food_source exists in zone:
        scores['food'] += food_urgency * weight

TIER 4 — water
    water_urgency = 1.0 - (thirst / max_thirst)
    if water_urgency > threshold AND water_source exists in zone:
        scores['water'] += water_urgency * weight

TIER 5 — hostile
    if 'hostile' in entity.target_types:
        player_in_zone = _same_context_as_player(entity)
        hostile_in_zone = any hostile entity in zone within detection range
        if player_in_zone OR hostile_in_zone:
            score based on how dangerous the threat is, entity's aggressiveness

TIER 6 — shelter (night only)
    if is_night AND entity is peaceful AND not in structure:
        scores['shelter'] += night_urgency * weight

TIER 7 — special (clearing, etc.)
    if humanoid AND there is a blocking cell nearby:
        scores['special'] += small weight

return type with highest score, or None if all scores are 0
```

---

## `find_and_attack_enemy(entity_id, entity)`

```
candidates = []
for each entity in same zone:
    if enemy (hostile flag logic same as proximity check above):
        candidates.append((entity_id, distance, threat_score))

if player in same zone AND entity is hostile AND entity is not follower:
    candidates.append(('player', player_distance, player_threat))

sort candidates by (distance, -threat_score)
best_target = candidates[0] if any within range

if best_target:
    if adjacent (dist==1):
        damage = (strength / 5) + weapon_bonus + magic_bonus
        if hostile entity: damage *= 1.2
        target.take_damage(damage, attacker=entity_id)
        gain_item_xp for weapon
        gain_xp(1)
        show_attack_animation()
    else:
        move toward best_target  # will attack next tick when adjacent
```

---

## `execute_entity_behavior(entity, behavior_config)`

```
# behavior_config is a dict from data/entities.py, e.g.:
# {'can_mine': True, 'can_chop': True, 'deposits_to_chest': True, ...}

if can_mine AND adjacent to stone/ore:
    action_mine_cell()

elif can_chop AND adjacent to tree:
    action_chop_tree()

elif can_harvest AND adjacent to crop:
    action_harvest_cell()

elif can_build AND has build materials:
    action_build_structure()

elif can_plant AND has seeds AND on tillable soil:
    action_plant_crop()

if deposits_to_chest AND inventory over threshold AND adjacent to chest:
    deposit inventory to chest
```

---

## `check_npc_transformation(entity_id, entity)`

```
transform_config = NPC_TRANSFORMATION_CONFIG.get(entity.type)
if none: return

for each rule in transform_config:
    if entity meets rule conditions (level, xp, tick, etc.):
        new_type = rule.new_type
        new_props = ENTITY_TYPES[new_type]
        entity.type = new_type
        entity.props = new_props
        preserve: level, health, inventory, faction, home_zone
        reset: ai_state, current_target, target_type
        break  # only transform once
```

---

## `cast_wizard_spell(caster, target, screen_key)`

```
spell_name = caster.spell
spell_data = SPELLS[spell_name]

if spell is damage type:
    raw_damage = spell_data.damage + item_xp_bonus
    target.take_damage(raw_damage)

elif spell is freeze type:
    target.ai_state = 'idle'
    target.ai_state_timer = spell_data.duration

elif spell is heal type:
    caster.health = min(max_health, health + spell_data.amount)

show_spell_animation(target.x, target.y, spell_type)
caster.spell_cooldown = spell_data.cooldown
caster.gain_item_xp('spell_scroll')
```
