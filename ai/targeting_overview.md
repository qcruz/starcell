# StarCell — NPC Targeting Priority System

## Overview

All NPC target selection flows through `determine_target_type()` (`npc_ai.py:2413`).
The new system replaces the current shuffle-and-first-match logic with a **scored priority
stack**. Every tick the function evaluates each priority tier in order, scores candidates,
and returns the single highest-scoring target type string. The existing state machine,
`find_closest_target_by_type()` dispatcher, and per-type finder functions remain unchanged.

---

## Priority Tiers (highest → lowest)

```
1. HOSTILE      — immediate combat threat
2. KEEPER       — anchor maintenance (inverse-distance urgency)
3. QUEST        — active assigned/special quest target (flat priority)
4. SPECIAL      — opportunistic tasks (inventory dump, trade, structure enter/exit)
5. ROLE         — archetype work targets (FARMER→crops, MINER→stone, etc.)
6. RESOURCE     — food and water (urgency scales with depletion)
```

Each tier produces a **score**. The tier with the highest score across the whole stack wins.
Tiers 1–3 can interrupt at any time. Tiers 4–6 use a stickiness lock to prevent rapid
switching (see Stickiness section).

---

## Tier Definitions

### 1. HOSTILE

**Purpose:** Immediate threat response — combat or flee.

```
score = HOSTILE_BASE
      × combat_chance             (from ai_params; 0.0–1.0)
      × (1 / (dist + 1))          (falls off sharply with distance)
      × aggressiveness_mod        (entity.aggressiveness; 0.0–1.0)
```

| Constant | Value |
|---|---|
| HOSTILE_BASE | 120 |

**Conditions:**
- Target must pass `find_closest_hostile_entity()` (existing 8-rule check)
- Entity must have `'hostile' in target_types`; otherwise falls through to flee check
- At `dist ≤ HOSTILE_DETECTION_RANGE` only (existing interrupt range, currently ~8 cells)

**Result string:** `'hostile'`

---

### 2. KEEPER

**Purpose:** Keep NPC anchored to their assigned patrol/guard point. Urgency increases the
farther the NPC drifts from its keeper anchor — so drift is self-correcting.

```
if keeper_type in (1, 2):
    drift = max(0, dist_from_anchor - KEEPER_RANGE[keeper_type])
    score  = KEEPER_BASE[keeper_type] + drift × KEEPER_URGENCY_SCALE
else:
    score  = KEEPER_BASE[keeper_type]   # type 3/4: flat, no urgency ramp
```

| keeper_type | Description | KEEPER_BASE | KEEPER_RANGE | KEEPER_URGENCY_SCALE |
|---|---|---|---|---|
| 1 (guard) | Within 1 cell of anchor | 60 | 1 | 8 |
| 2 (patrol) | Within 5 cells of anchor | 40 | 5 | 5 |
| 3 (zone) | Full zone roam | 20 | ∞ | 0 |
| 4 (domain) | Cross-zone domain | 15 | ∞ | 0 |

**Conditions:**
- `entity.keeper == True`
- `entity.keeper_target_pos is not None`
- Already within anchor range: score = KEEPER_BASE only (no urgency ramp)

**Note:** No distance falloff — a keeper target at distance 50 scores higher than one at 10,
because the whole point is that the NPC must return. Hostile tier still wins at short range
because HOSTILE_BASE × combat_chance typically exceeds KEEPER_BASE for a guard-type NPC.

**Result string:** `'keeper_target'`

---

### 3. QUEST

**Purpose:** Navigate to an active assigned quest target. Flat priority — no distance
weighting. A quest is either active or it isn't.

```
score = QUEST_BASE     (flat, regardless of distance)
```

| Constant | Value |
|---|---|
| QUEST_BASE | 80 |

**Conditions:**
- `entity.quest_target is not None` (a specific target has been assigned)
- Not in survival crisis (low_hunger or low_thirst bypasses — resource tier takes over)
- Target still exists (entity alive, or cell still present)

**Two quest modes (unchanged from current logic):**
- **SPECIFIC** — `quest_target` is a cell tuple or entity ID; navigate to within 2 cells,
  then call `_try_complete_assigned_quest()`, clear target
- **GENERAL** — `quest_target` is None; every ~10 updates, 20% chance to call
  `_assign_specific_quest_target()` and enter SPECIFIC mode

**Note:** Base role quests (FARM, MINE, LUMBER archetype quests) are the current
`quest_focus` general mode. They live in the ROLE tier below, not here. The QUEST tier
is for player-assigned or LoreEngine-assigned special quests with explicit targets.

**Result string:** `'quest_target'`

---

### 4. SPECIAL

**Purpose:** Opportunistic tasks that don't belong to role or survival. Evaluated as a
shuffled pool but **sticky** — once selected, the chosen special type locks for
`SPECIAL_LOCK_TICKS` before re-evaluation.

**Candidate pool (checked for availability before scoring):**

| Special type | Condition | Notes |
|---|---|---|
| `'chest_dump'` | Inventory ≥ CHEST_DUMP_THRESHOLD items, chest exists in zone | Existing NPC dump logic |
| `'trade'` | Inventory full + TRADER within zone | New — sells to nearby TRADER |
| `'shelter'` | `is_night == True` and not in structure | Night movement |
| `'exit_structure'` | `is_day == True` and `in_structure == True` | Daytime exit |

```
score = SPECIAL_BASE      (flat per eligible candidate)
```

| Constant | Value |
|---|---|
| SPECIAL_BASE | 50 |
| SPECIAL_LOCK_TICKS | 60 |

**Stickiness mechanism:**
- Entity attributes: `_special_target_type` (str or None), `_special_target_lock` (int, ticks remaining)
- On each `determine_target_type()` call:
  - If `_special_target_lock > 0`: decrement, return `_special_target_type` (no re-evaluation)
  - If `_special_target_lock == 0`: evaluate pool, pick one, set lock
- Lock resets to 0 if the special action completes or the condition is no longer met

**Result string:** `'chest_dump'` / `'trade'` / `'shelter'` / `'exit_structure'`

---

### 5. ROLE

**Purpose:** Archetype-specific work. This is the current `quest_focus` general mode behavior.
FARMER seeks crops, MINER seeks stone, LUMBERJACK seeks trees, etc.

```
score = ROLE_BASE
```

| Constant | Value |
|---|---|
| ROLE_BASE | 40 |

**Archetype → target type mapping** (from `NPC_BASE_QUEST` + `target_types`):

| Entity type | Role target type |
|---|---|
| FARMER | `'crop'` |
| LUMBERJACK | `'tree'` |
| MINER | `'stone'` |
| GUARD / WARRIOR | `'patrol'` (keeper-driven; ROLE falls through) |
| BLACKSMITH | `'structure'` (seek forge) |
| WIZARD | `'explore'` (seek unknown cells / rune) |
| TRADER | `'travel'` (seek zone exit) |

**Conditions:**
- Role target type exists in `entity.target_types`
- At least one valid target found by `find_closest_target_by_type()` for the type

**Result string:** type string matching the role (e.g. `'crop'`, `'stone'`, `'tree'`)

---

### 6. RESOURCE

**Purpose:** Food and water. Score scales with urgency — near-zero levels compete with
quest/special/role; full levels barely register.

```
water_urgency = max(0, 1 - (entity.thirst / entity.max_thirst))
food_urgency  = max(0, 1 - (entity.hunger / entity.max_hunger))

water_score = RESOURCE_BASE × water_urgency²   (quadratic — ramps fast near zero)
food_score  = RESOURCE_BASE × food_urgency²
```

| Constant | Value |
|---|---|
| RESOURCE_BASE | 100 |

**Examples (RESOURCE_BASE=100):**
- Thirst at 100% → score = 0 (no pull at all)
- Thirst at 50% → score = 25 (below role/special)
- Thirst at 30% → score = 49 (close to role, still below quest)
- Thirst at 10% → score = 81 (overrides quest and special)
- Thirst at 0% → score = 100 (overrides everything except hostiles)

**Conditions:**
- `'water'` / `'food'` in `entity.target_types`
- Target exists in zone

**Result strings:** `'water'`, `'food'`

---

## Scoring Summary Table

| Tier | Result | Base Score | Modifier |
|---|---|---|---|
| HOSTILE | `'hostile'` | 120 | × combat_chance × (1/dist+1) × aggressiveness |
| KEEPER | `'keeper_target'` | 60–15 | + drift × urgency_scale |
| QUEST | `'quest_target'` | 80 | flat |
| SPECIAL | varies | 50 | flat per eligible type |
| ROLE | varies | 40 | flat |
| RESOURCE (water) | `'water'` | 100 | × urgency² |
| RESOURCE (food) | `'food'` | 100 | × urgency² |

**Cross-tier example — GUARD with hostile nearby:**
- Hostile at dist 2: 120 × 0.90 × 0.33 × 0.95 ≈ **33.8** — may lose to keeper
- Hostile at dist 1: 120 × 0.90 × 0.50 × 0.95 ≈ **51.3** — beats keeper + quest
- Hostile adjacent: 120 × 0.90 × 1.0 × 0.95 ≈ **102.6** — beats everything

**Cross-tier example — FARMER at 50% thirst:**
- Water score: 100 × 0.25 = **25** — below role (40), FARMER keeps harvesting
- Water at 15%: 100 × 0.72 = **72** — above quest (80)? No — still below. Drinks at ~12%
- Water at 10%: 100 × 0.81 = **81** — above quest, NPC goes for water

---

## Entity Attributes (new + existing)

| Attribute | Type | Source | Purpose |
|---|---|---|---|
| `target_types` | list[str] | `ai_params` in ENTITY_TYPES | Which tiers the entity participates in |
| `keeper` | bool | assigned by faction/lore system | Activates keeper tier |
| `keeper_type` | int 0–4 | KEEPER_TYPE_BY_ENTITY | Keeper base score and range |
| `keeper_target_pos` | (x,y) | keeper assignment | Anchor position for keeper tier |
| `quest_target` | tuple/int/None | quest system | Activates quest tier SPECIFIC mode |
| `quest_focus` | str/None | NPC_BASE_QUEST + assignment | Activates quest GENERAL mode / role tier |
| `_special_target_type` | str/None | **new** | Current sticky special target |
| `_special_target_lock` | int | **new** | Ticks remaining on special lock |

---

## Implementation Plan

### Step 1 — Refactor `determine_target_type()` (`npc_ai.py:2413`)

Replace the current body with the scored stack:

```python
def determine_target_type(self, entity):
    screen_key = f"{entity.screen_x},{entity.screen_y}"
    candidates = {}   # {target_type_string: score}

    # ── Tier 1: Hostile ───────────────────────────────────────────────────
    if 'hostile' in entity.target_types:
        closest = self.find_closest_hostile_entity(entity, screen_key)
        if closest:
            dist = self.get_target_distance(entity, closest)
            score = (120
                     * entity.props['ai_params'].get('combat_chance', 0.5)
                     * (1 / (dist + 1))
                     * entity.aggressiveness)
            candidates['hostile'] = score

    # ── Tier 2: Keeper ────────────────────────────────────────────────────
    if getattr(entity, 'keeper', False) and getattr(entity, 'keeper_target_pos', None):
        ktype    = getattr(entity, 'keeper_type', 3) or 3
        kbase    = KEEPER_BASE[ktype]
        krange   = KEEPER_RANGE.get(ktype)
        kscale   = KEEPER_URGENCY_SCALE.get(ktype, 0)
        kpos     = entity.keeper_target_pos
        dist     = abs(entity.x - kpos[0]) + abs(entity.y - kpos[1])
        drift    = max(0, dist - krange) if krange is not None else 0
        candidates['keeper_target'] = kbase + drift * kscale

    # ── Tier 3: Quest ────────────────────────────────────────────────────
    # (existing quest initialization + SPECIFIC/GENERAL mode logic stays here,
    #  extracted into _evaluate_quest_tier(entity, screen_key) helper)
    quest_score = self._evaluate_quest_tier(entity, screen_key)
    if quest_score is not None:
        candidates['quest_target'] = quest_score

    # ── Tier 4: Special (sticky) ─────────────────────────────────────────
    special_score = self._evaluate_special_tier(entity, screen_key)
    if special_score is not None:
        target_type, score = special_score
        candidates[target_type] = score

    # ── Tier 5: Role ─────────────────────────────────────────────────────
    role_type = self._evaluate_role_tier(entity, screen_key)
    if role_type:
        candidates[role_type] = ROLE_BASE

    # ── Tier 6: Resource ─────────────────────────────────────────────────
    for res_type in ('water', 'food'):
        if res_type in entity.target_types:
            if self.find_closest_target_by_type(entity, res_type, screen_key):
                level = entity.thirst if res_type == 'water' else entity.hunger
                maxv  = entity.max_thirst if res_type == 'water' else entity.max_hunger
                urgency = max(0.0, 1 - level / maxv)
                candidates[res_type] = RESOURCE_BASE * urgency * urgency

    if not candidates:
        return None
    return max(candidates, key=candidates.get)
```

### Step 2 — Extract helper methods

| Helper | Purpose | Source |
|---|---|---|
| `_evaluate_quest_tier(entity, screen_key)` | Returns `QUEST_BASE` or None; contains all existing quest init, SPECIFIC/GENERAL mode, `_assign_specific_quest_target()` call | Extracted from `determine_target_type()` lines 2421–2506 |
| `_evaluate_special_tier(entity, screen_key)` | Returns `(type_string, score)` or None; manages stickiness lock, evaluates chest_dump/trade/shelter/exit pool | New |
| `_evaluate_role_tier(entity, screen_key)` | Returns role target type string or None; replaces lines 2500–2506 | Refactored from existing general-mode fallthrough |

### Step 3 — Add scoring constants to `constants.py`

```python
KEEPER_BASE          = {1: 60, 2: 40, 3: 20, 4: 15}
KEEPER_URGENCY_SCALE = {1: 8,  2: 5,  3: 0,  4: 0}
ROLE_BASE            = 40
QUEST_BASE           = 80
SPECIAL_BASE         = 50
SPECIAL_LOCK_TICKS   = 60
RESOURCE_BASE        = 100
```

### Step 4 — Add `chest_dump` and `trade` to `find_closest_target_by_type()` dispatcher

Currently these aren't target type strings; the chest dump path is triggered differently.
Wire them in as new elif branches pointing to existing finder logic.

### Step 5 — Initialise new entity attributes

In `entity.py` init (or first-access in `determine_target_type()`):
- `_special_target_type = None`
- `_special_target_lock = 0`

### Step 6 — Update `target_types` in `data/entities.py` / `constants.py`

Add `'trade'` to TRADER's `target_types` list. Other entities get it only if they can trade.

---

## What Does NOT Change

- `find_closest_target_by_type()` dispatcher (ai/movement.py:2010) — add cases, no rewrites
- Individual target finders (`find_closest_food_source`, `find_closest_hostile_entity`, etc.)
- The 8-rule enemy detection in `find_and_attack_enemy()`
- State machine: `idle → targeting → combat` flow
- Keeper assignment: `assign_zone_keepers()`, `resolve_keeper_target()`, `_set_keeper_target_*`
- Quest assignment: `_try_complete_assigned_quest()`, `_assign_specific_quest_target()`
- Entity props and `ai_params` structure (only adding to constants, not changing shape)

---

## Current Code → New Tier Mapping

| Current code path | New tier |
|---|---|
| `determine_target_type()` lines 2509–2518 (survival priority checks) | Tier 6 Resource |
| `determine_target_type()` lines 2520–2526 (specialty shuffle) | Tier 5 Role |
| `determine_target_type()` lines 2528–2533 (fallback shuffle) | Tier 6 Resource fallback |
| `determine_target_type()` lines 2421–2506 (quest focus system) | Tier 3 Quest |
| `update_entity_ai()` lines 1290–1332 (hostile detection interrupt) | Tier 1 Hostile (folded in) |
| `update_entity_ai()` lines 1460–1521 (keeper target mode) | Tier 2 Keeper (folded in) |
| Night shelter / daytime exit blocks in `update_entity_ai()` lines 669–680 | Tier 4 Special |

---

## Open Questions (resolve before implementation)

1. **Should WARRIOR/GUARD hostile score ignore distance entirely?** Their `combat_chance=0.90`
   and `aggressiveness=0.95` already produce a very high hostile score at close range.
   The current full-zone scan for warriors could become a modifier (`zone_scan_bonus`).

2. **Keeper vs. Quest interaction:** If an NPC has both a keeper anchor AND an active quest
   target, keeper type 1 (base 60) loses to quest (flat 80) unless drift is high. Is this
   correct? A door guard shouldn't abandon their post for a quest. May need
   `keeper_overrides_quest` flag on keeper type 1.

3. **Special tier — `trade` target type:** The new NPC-to-trader trade system (next_up item 3)
   needs to be implemented before this target type is live. Wire the type but leave the
   finder returning None until that system is built.

4. **RESOURCE_BASE=100 quadratic vs. QUEST_BASE=80 flat:** At 10% thirst, resource score is
   81 — just above quest. Is it desirable for a nearly-dead NPC to abandon a quest to drink?
   Probably yes. But review thresholds once quest system is fully exercised.
