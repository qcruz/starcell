# Main Branch Prep Checklist

> **READ THIS BEFORE TOUCHING MAIN.**
> This document lists every code change, file removal, and value adjustment required before merging dev → main. Do not skip items. Do not push to main until @qcruz has reviewed this list and given explicit approval.

---

## How to Use This Document

1. Work through every section below before starting a merge.
2. For each item: confirm the current state in dev, decide whether it needs changing, and check it off.
3. Post the completed list to @qcruz for final review.
4. Only after explicit approval: create the merge commit and push.

---

## 1. Player Starting Inventory

**Location:** `game_core.py:2842–2844`

**Current dev behavior:** `new_game()` adds every item in `ITEMS` to the player inventory. This is a dev convenience — the player starts with all tools, weapons, spells, and items unlocked.

**Policy for main:** Replace the "give all items" loop with an explicit starter set:
- `star_spell` (1x) — in magic tab
- `attack`, `block`, `inspect`, `dig`, `sneak`, `talk` (1x each) — in actions tab
- Nothing else — no tools, weapons, consumables, or crafting materials

```python
# REPLACE THE DEV LOOP WITH:
self.inventory.add_item('star_spell', 1)
for _action in ['attack', 'block', 'inspect', 'dig', 'sneak', 'talk']:
    self.inventory.add_item(_action, 1)
```

---

## 2. Starting Follower

**Location:** `game_core.py:2869`

**Current dev behavior:** A random follower type (SHEEP, DEER, WOLF, BAT, GOBLIN, SKELETON, TERMITE) is selected on new_game and spawned after time passage.

**Policy for main:** Player starts with one random peaceful animal follower. Restrict the pool to: `SHEEP`, `DEER`, `RED_BIRD`, `BUTTERFLY`, `CHICKEN`. This introduces the follower system without implying combat NPCs are easy to tame.

```python
# REPLACE the current line in new_game():
self._pending_follower_type = random.choice(['SHEEP', 'DEER', 'WOLF', 'BAT', 'GOBLIN', 'SKELETON', 'TERMITE'])
# WITH:
self._pending_follower_type = random.choice(['SHEEP', 'DEER', 'RED_BIRD', 'BUTTERFLY', 'CHICKEN'])
```

---

## 3. Autopilot Toggle (Shift+A)

**Location:** `game_core.py:1250–1255`, `ui/menus.py:36`, `ui/menus.py:118`

**Policy for main:** No change needed. Autopilot is an intentional main game mechanic, not a dev tool. Keep Shift+A binding and controls text as-is.

---

## 4. Dev Screen (Shift+I)

**Location:** `game_core.py:1184–1186`, `game_core.py:206`, `game_core.py:3021`, `ui/dev_screen.py`

**Current dev behavior:** Shift+I opens the dev info overlay showing internal state, entity counts, tick info, etc.

**Policy for main:** Remove entirely. Delete:
- The `elif event.key == pygame.K_i and Shift: self.show_dev_screen = not self.show_dev_screen` branch in `game_core.py:1184–1186` (Shift+I will fall through to normal inventory open)
- The `self.show_dev_screen = False` init line in `game_core.py:206`
- The `self.draw_dev_screen()` call in `game_core.py:3021`
- `ui/dev_screen.py` — delete the file

---

## 5. Spell Energy Cost + Enchanted Cell Permanence

**Location:** `systems/enchantment.py:64–69`, `ai/actions.py:50–`, `world/zones.py:68`, `ui/hud.py:199–203`

**Policy for main:** Spell energy cost of 3 per cast is correct for main. No change needed.

**Enchanted cell permanence — required fixes before main:**

Enchanted cells must be immutable: no NPC action or world system may alter them. Current protection status:

| System | Protected? | Notes |
|---|---|---|
| Cellular automata (`world/cells.py:140`) | Yes | `is_cell_enchanted` skip in place |
| NPC eating/drinking (`ai/movement.py:1862, 1938`) | Yes | `is_cell_enchanted` skip in place |
| Zone update / biome spread (`world/zones.py:344, 927, 1875`) | Yes | `is_cell_enchanted` skip in place |
| NPC harvest (`ai/actions.py:action_harvest_cell`) | **No** | Missing check — NPCs can chop/mine enchanted cells |
| Zone unload (`world/zones.py:68`) | **No** | `enchanted_cells.pop(zone_key)` purges enchantments from unloaded zones mid-session |

**Required code fixes:**
1. `ai/actions.py:action_harvest_cell` — add `if self.is_cell_enchanted(cx, cy, screen_key): continue` before the harvest executes (inside the `for dx, dy` loop, after cell type check)
2. `world/zones.py` zone unload — do not pop from `enchanted_cells` on zone unload; enchantments must survive zone cycling. Remove or guard the `self.enchanted_cells.pop(zone_key, None)` line.

**Visual clarity — required for main:**
Current marker is a small golden rect in the top-left corner of the cell (`ui/hud.py:199–203`). Must be replaced with a clearly visible enchantment icon (star/sparkle sprite or distinct overlay) so players can reliably identify enchanted cells at a glance. Exact visual TBD with @qcruz — flag when ready to implement.

---

## 6. Follower Energy Cost (Max Energy Reduction)

**Location:** `systems/enchantment.py:93`

**Current dev behavior:** Each follower added permanently reduces player max_energy by 1 (`max_energy - 1`).

**Policy for main:** Each follower costs 30 max energy while they are a follower. When a follower is released or dies, those 30 points are restored. This is a meaningful resource commitment — a player with 100 max energy can sustain a maximum of 3 followers before being nearly immobilized.

**Required code change:** `systems/enchantment.py:93` — change the reduction from `- 1` to `- 30`. Confirm the release path in the same file restores the matching amount (currently `energy_restored` is computed dynamically — verify it restores the correct 30 per follower level).

---

## 7. Biome Spread Rate

**Location:** `constants.py:125`

**Current dev value:** `BIOME_SPREAD_RATE = 0.004` — noted in comments as "4x increase"

**Policy for main:** Keep at 0.004. No change needed.

---

## 8. Biome Occurrence Rates

**Location:** `world/generation.py:85`, `constants.py:214–217`

**Current state:** Generation already uses `random.choice(list(BIOMES.keys()))` — all biomes spawn at equal probability. The `FOREST_BIOME_CHANCE` / `PLAINS_BIOME_CHANCE` / `MOUNTAINS_BIOME_CHANCE` / `DESERT_BIOME_CHANCE` constants in `constants.py` are stale and unused.

**Policy for main:** Equal biome distribution is correct. No change to generation logic needed. Remove the four stale `*_BIOME_CHANCE` constants from `constants.py` as part of the cleanup pass (section 13).

---

## 9. E-Button Pickup

**Location:** `game_core.py:1226–1228`

**Current dev behavior:** E key calls `pickup_cell_or_items()` — picks up dropped item piles AND raw cells directly into inventory (creative/admin mode).

**Policy for main:**
- **Remove the E key binding entirely** — `pickup_cell_or_items()` is a dev catch-all and has no place in main.
- **Dropped item pickup via Spacebar** — `interact()` (`game_core.py:2207`) should check for dropped items at the target cell as its first step (before attack, before entity targeting). If items are present, pick them up and return.
- **Raw cell pickup requires proper tool** — cells are only obtainable through tool use (axe → wood, pickaxe → stone/iron ore, etc.). No direct cell-to-inventory shortcut exists for the player on main.

**Required code changes:**
1. `game_core.py:1226–1228` — remove the `elif event.key == pygame.K_e:` block entirely.
2. `game_core.py:interact()` — add dropped item pickup as the first check after facing snap, before `player_attack()`: if dropped items exist at the target cell, pick them up and return.
3. `ui/menus.py:116` — update controls text: replace `"E - Pick up"` with the correct spacebar pickup description.

---

## 10. Controls Help Text

**Location:** `ui/menus.py:34–38`, `ui/menus.py:116–120`

**Required for main:** After resolving items 3 and 9 above, update the controls text in both help screens to reflect final key bindings. Remove any dev-only bindings.

---

## 11. Documentation Files

**Policy for main:** Keep all files. All docs — dev planning, design notes, roadmap, bounties, legal, etc. — are welcome on main for anyone to read.

**Required action:** Update `README.md` to include an audience-organized file directory so players, coders, and contributors can immediately find what's relevant to them. See the three-audience structure below — this replaces the existing flat "Quick Links" table.

**README file directory structure:**

```
### For Players
Files to get you set up and playing fast.

### For Coders
Files that explain the game's architecture and code for your own projects.

### For Devs & Contributors
Files explaining the roadmap, bounties, and what's needed next.
```

**Also clean up `" 2"` duplicate files** — git status shows many asset files with ` 2` and ` 3` suffixes (e.g. `sprites/icons/tile000 2.png`). These are macOS duplicate copies and should not be in main. Confirm they are not referenced in code before deleting.

---

## 12. Debug System — Disabled by Default on Main

**Location:** `game_core.py:12–13, 204–205, 589, 1000, 2812, 2916, 2930, 3008, 3034`

**Current dev behavior:** BugCatcher and Watchdog are always active — logging zone snapshots every cycle, running integrity checks every 300 ticks, and flushing to `debug/bug_catcher.log`. This risks growing log files and background memory pressure on player machines.

**Policy for main:** Debug system is off by default. Gate all BugCatcher and Watchdog calls behind a `DEBUG_MODE` flag so they are completely inert during normal play.

**Required code changes:**
1. Add `DEBUG_MODE = False` to `constants.py` (and the `data/` equivalent if needed).
2. `game_core.py:204–205` — wrap instantiation:
   ```python
   self.bug_catcher = BugCatcher() if DEBUG_MODE else None
   self.watchdog = Watchdog(self.bug_catcher) if DEBUG_MODE else None
   ```
3. Guard every `self.bug_catcher.*` and `self.watchdog.*` call site with `if self.bug_catcher:` / `if self.watchdog:`.
4. The `AUTO_DEBUG` path in `main.py` and `game_core.py` can enable `DEBUG_MODE` at runtime — that path already requires the external `debug/auto_debug.cfg` file which won't exist on player machines.

The `debug/` directory and all its modules stay in the codebase — they are simply dormant unless explicitly enabled.

---

## 13. Print Statements in Game Code

**Required for main:** Run a grep pass to remove or silence all `print()` statements outside of `autopilot.py` and `debug/` before merging to main. These show up in terminal but not in-game, so they're low urgency — but they're messy for release.

```bash
grep -rn "print(" --include="*.py" --exclude-dir=debug . | grep -v autopilot.py
```

Review each result: keep intentional game messages (if any use a proper log channel), remove raw debug prints.

---

## 14. `.gitignore` Check

**Policy for main:** No changes needed. Confirmed correct — all ephemeral debug and system files are already ignored.

---

## 15. Game Balance Review

**Read every value below, compare to how the game feels in your most recent test session, and sign off before merging.** These are the highest-impact variables in the simulation. If any feel wrong, adjust in `constants.py` (and mirror in `data/` if applicable) before the merge.

---

### Player Base Stats (`game_core.py:new_game`)
| Stat | Current Value | Notes |
|---|---|---|
| Starting health | 100 | — |
| Starting energy | 100 | — |
| Base damage | 10 | Before weapon bonus |
| Attack energy cost | 2 per swing | `combat.py:132` |
| Block energy cost | 5 per hit blocked | `combat.py:161` |
| Block damage reduction | 90% | `combat.py:160` |

### Player Level-Up Gains (`systems/combat.py:185–190`)
| Stat | Gain per level | Notes |
|---|---|---|
| Max health | +10 | — |
| Base damage | +2 | — |
| Max energy | +2 | Before follower cost |
| XP to next level | ×1.5 of current | Scales exponentially |

### Follower Cost (`systems/enchantment.py:93`)
| Item | Current | Target for main |
|---|---|---|
| Max energy reduction per follower | 1 | **30** (change required — see item 6) |

---

### Day / Night Cycle (`constants.py:93–95`)
| Variable | Value | Real time at 60 FPS |
|---|---|---|
| DAY_LENGTH | 150 ticks | 2.5 minutes |
| NIGHT_LENGTH | 150 ticks | 2.5 minutes |
| NIGHT_OVERLAY_ALPHA | 40 | Subtle darkness |

---

### Weather (`constants.py:85–90`)
| Variable | Value | Notes |
|---|---|---|
| RAIN_FREQUENCY_MIN | 120 update calls | ~1 min between rains at min |
| RAIN_FREQUENCY_MAX | 2000 update calls | ~16 min max drought |
| RAIN_DURATION_MIN | 30 update calls | — |
| RAIN_DURATION_MAX | 180 update calls | — |
| RAIN_WATER_SPAWNS | 5 cells/tick | Water spawned per rain tick |
| RAIN_GRASS_SPAWNS | 8 cells/tick | Dirt→Grass per rain tick |

---

### Entity Survival Rates (`constants.py:133–141`)
| Variable | Value | Notes |
|---|---|---|
| HUNGER_DECAY_RATE | 0.02 base | Humanoids get ×6 = 0.12/call |
| THIRST_DECAY_RATE | 0.5 base | Humanoids get ×2 = 1.0/call |
| STARVATION_DAMAGE | 1.0 HP/call | When hunger = 0 |
| DEHYDRATION_DAMAGE | 1.5 HP/call | When thirst = 0 |
| BASE_HEALING_RATE | 1.5 HP/tick | When fed and hydrated |
| CAMP_HEALING_MULTIPLIER | ×2.0 | Near camps |
| HOUSE_HEALING_MULTIPLIER | ×3.0 | Near houses |
| OLD_AGE_DAMAGE | 2.0 HP/update | When age > max_age |
| WATER_DECAY_ON_DRINK | 70% | Chance water cell → dirt when drunk |
| GRASS_DECAY_ON_EAT | 60% | Chance grass → dirt when eaten |

---

### NPC Entity Health Pool (`data/entities.py`, scaled by level)
| NPC Type | Base HP (level 1) | Notes |
|---|---|---|
| SHEEP | 16 | — |
| WOLF | 30 | — |
| DEER | 24 | — |
| FARMER | 64 | — |
| GUARD | 104 | — |
| WARRIOR | 80 | — |
| COMMANDER | 96 | — |
| KING | 120 | Highest peaceful HP |
| TRADER | 56 | — |
| BLACKSMITH | 72 | — |
| WIZARD | 48 | — |
| LUMBERJACK | 80 | — |
| MINER | 88 | — |
| BANDIT | 50 | — |
| GOBLIN | 35 | — |
| SKELETON | 35 | — |
| TERMITE | 25 | — |
| BAT | 10 | Fragile |
| RED_BIRD | 6 | Fragile |
| BUTTERFLY | 3 | Most fragile |
| CHICKEN | 12 | — |
| BLACK_SPIDER | 30 | — |

HP scales linearly with level: level 3 WOLF = 90 HP.

---

### NPC Spawn Tables by Biome (`systems/spawning.py:67–134`)
Format: `(type, chance, min, max)` per zone generation

**FOREST**
| Type | Chance | Min | Max |
|---|---|---|---|
| LUMBERJACK | 0.60 | 1 | 2 |
| RED_BIRD | 0.60 | 1 | 3 |
| DEER | 0.50 | 1 | 2 |
| FARMER | 0.50 | 0 | 2 |
| TRADER | 0.50 | 1 | 2 |
| BLACKSMITH | 0.50 | 0 | 1 |
| GUARD | 0.50 | 1 | 2 |
| BUTTERFLY | 0.50 | 0 | 2 |
| TERMITE | 0.40 | 0 | 2 |
| WOLF | 0.30 | 0 | 2 |
| BLACK_SPIDER | 0.30 | 0 | 2 |
| WIZARD | 0.25 | 1 | 2 |
| GOBLIN | 0.15 | 0 | 2 |
| SHEEP | 0.20 | 0 | 1 |
| BANDIT | 0.10 | 0 | 1 |

**PLAINS**
| Type | Chance | Min | Max |
|---|---|---|---|
| FARMER | 0.70 | 1 | 3 |
| CHICKEN | 0.70 | 1 | 3 |
| SHEEP | 0.60 | 1 | 3 |
| BUTTERFLY | 0.60 | 1 | 3 |
| DEER | 0.40 | 0 | 2 |
| TRADER | 0.50 | 1 | 2 |
| BLACKSMITH | 0.50 | 0 | 1 |
| GUARD | 0.50 | 1 | 2 |
| RED_BIRD | 0.50 | 0 | 2 |
| LUMBERJACK | 0.30 | 0 | 1 |
| WIZARD | 0.25 | 1 | 2 |
| WOLF | 0.20 | 0 | 1 |
| TERMITE | 0.20 | 0 | 1 |
| GOBLIN | 0.10 | 0 | 1 |
| BANDIT | 0.10 | 0 | 1 |

**DESERT**
| Type | Chance | Min | Max |
|---|---|---|---|
| MINER | 0.50 | 0 | 2 |
| TRADER | 0.50 | 1 | 2 |
| GUARD | 0.50 | 1 | 2 |
| BLACK_SPIDER | 0.40 | 0 | 2 |
| BLACKSMITH | 0.40 | 0 | 1 |
| GOBLIN | 0.35 | 0 | 2 |
| FARMER | 0.30 | 0 | 1 |
| BANDIT | 0.25 | 0 | 2 |
| WIZARD | 0.25 | 1 | 2 |
| WOLF | 0.20 | 0 | 1 |
| LUMBERJACK | 0.20 | 0 | 1 |
| SHEEP | 0.20 | 0 | 1 |
| DEER | 0.20 | 0 | 1 |

**MOUNTAINS**
| Type | Chance | Min | Max |
|---|---|---|---|
| MINER | 0.70 | 1 | 3 |
| WOLF | 0.60 | 1 | 3 |
| BLACKSMITH | 0.60 | 0 | 1 |
| BLACK_SPIDER | 0.50 | 0 | 2 |
| TRADER | 0.50 | 1 | 2 |
| GUARD | 0.50 | 1 | 2 |
| LUMBERJACK | 0.40 | 0 | 2 |
| DEER | 0.30 | 0 | 2 |
| GOBLIN | 0.30 | 0 | 2 |
| RED_BIRD | 0.30 | 0 | 1 |
| WIZARD | 0.25 | 1 | 2 |
| FARMER | 0.20 | 0 | 1 |
| SHEEP | 0.20 | 0 | 1 |
| BANDIT | 0.15 | 0 | 2 |

**LAKE** — no spawns.

---

### Night / Event Spawns (`constants.py:306–309`)
| Variable | Value | Notes |
|---|---|---|
| NIGHT_SKELETON_SPAWN_CHANCE | 1% per zone per night tick | Higher near dropped items |
| CAVE_HOSTILE_SPAWN_CHANCE | 0.5% per cave per update | — |
| TERMITE_SPAWN_CHANCE | 0.1% per zone per update | Near trees |
| SKELETON_DAYLIGHT_DAMAGE | 1 HP per update | Daytime skeleton damage |

---

### Raid System (`constants.py:220–231`)
| Variable | Value | Notes |
|---|---|---|
| RAID_CHANCE_BASE | 2% per zone update | Scales with population |
| RAID_POPULATION_THRESHOLD | 4 entities | Minimum to trigger |
| HIDDEN_CAVE_SPAWN_CHANCE | 20% | Cave spawned during raid |
| WARRIOR_PROMOTION_CHANCE | 60% | Highest level entity → WARRIOR after raid clear |
| KEEPER_ASSIGNMENT_RATE | 2% per zone update | Vacant keeper slot fill rate |

---

### NPC Behavior Rates (`constants.py:144–196`)
| Variable | Value | Notes |
|---|---|---|
| FARMER_HARVEST_RATE | 0.30 | Prob to attempt harvest/tick |
| FARMER_HARVEST_SUCCESS | 0.40 | Success rate when attempted |
| FARMER_TILL_RATE | 0.10 | Prob to till |
| FARMER_TILL_SUCCESS | 0.25 | — |
| FARMER_PLANT_RATE | 0.50 | Prob to plant |
| FARMER_PLANT_SUCCESS | 0.30 | — |
| LUMBERJACK_BASE_CHOP_RATE | 0.50 | Base chop attempt rate |
| LUMBERJACK_CHOP_SUCCESS | 0.85 | High — fast visible work |
| LUMBERJACK_BUILD_RATE | 0.05 | Prob to build house per tick |
| LUMBERJACK_BUILD_SUCCESS | 0.35 | — |
| MINER_MINE_SUCCESS | 0.50 | — |
| GOBLIN_CAMP_ATTACK_RATE | 0.05 | Per tick vs camps |
| GOBLIN_HOUSE_ATTACK_RATE | 0.01 | Per tick vs houses |
| NPC_CAMP_PLACE_RATE | 0.01 | Per second |
| PEACEFUL_NPC_MIGRATE_RATE | 0.05 | Leave zone if duplicate type |
| ENHANCED_SETTLEMENT_RATE | 0.25 | Settlement boost when zone needs role |
| NPC_PEACEFUL_WANDER_CHANCE | 0.60 | Wander while idle |
| NPC_TREE_CLEAR_RATE | 0.05 | Non-lumberjacks clear trees |

---

### NPC Movement & AI Timing (`constants.py:155–164`)
| Variable | Value | Notes |
|---|---|---|
| NPC_BASE_MOVE_INTERVAL | 180 ticks (3s) | — |
| NPC_MOVE_VARIANCE | ±60 ticks (1s) | — |
| NPC_COMBAT_MOVE_INTERVAL | 18 ticks (0.3s) | Fast in combat |
| AI_STATE_IDLE_DURATION | 90 ticks (1.5s) | — |
| AI_STATE_WANDER_DURATION | 120 ticks (2s) | — |
| AI_STATE_TARGETING_DURATION | 180 ticks (3s) | — |
| AI_STATE_COMBAT_DURATION | 120 ticks (2s) | — |

---

### Combat (`constants.py:167–172`)
| Variable | Value | Notes |
|---|---|---|
| HEALTH_LOW_THRESHOLD | 50% | NPC considers fleeing |
| HEALTH_CRITICAL_THRESHOLD | 30% | Flee/fight decision |
| COMBAT_FLEE_CHANCE | 40% | At critical health |
| COMBAT_DISENGAGE_CHANCE | 5% | Per combat tick |
| HOSTILE_DETECTION_RANGE | 8 cells | — |

---

### World Building Rates (`constants.py:199–228`)
| Variable | Value | Notes |
|---|---|---|
| TRADER_PATH_BUILD_RATE | 0.60 | Dirt road creation while walking |
| TRADER_COBBLE_RATE | 0.25 | Dirt → cobblestone upgrade |
| NATURAL_CAVE_ZONE_CHANCE | 8% | Cave on zone generation |
| MINER_MINESHAFT_CHANCE | 3% per mine action | NPC-created mineshafts |
| MINESHAFT_MAX_PER_ZONE | 2 | NPC mineshaft cap |
| MINER_WELL_BUILD_RATE | 2% per action | Well creation |
| CAMP_UPGRADE_CHANCE | 0.1% per update | Camp → house |
| HOUSE_DECAY_RATE | 0.01% per update | Natural house decay |

---

### Quest System (`constants.py:98–99`, `data/entities.py`)
| Variable | Value | Notes |
|---|---|---|
| QUEST_COOLDOWN | 300 ticks (5s) | After completion before new target |
| QUEST_XP_MULTIPLIER | ×10 | XP = target_level × 10 |
| NPC_QUEST_QUEUE_MAX | 3 | Max quests per NPC |
| NPC_QUEST_UNLOCK_CHANCE | 10% per level-up | New quest focus unlock |
| NPC_QUEST_UNLOCK_CHANCE_CMBT_ALL | 3% per level-up | Combat-all unlock (lower) |
| NPC_QUEST_FOCUS_SWITCH_CHANCE | 10% | Per level-up |

---

### Item Sinks & Decay
| System | Rate | Notes |
|---|---|---|
| Dropped item decay | 1% per item per zone update | `crafting.py:ITEM_DECAY_RATE` |
| Item → buried | 0.03% per item per update | Distance-scaled |
| Buried item destruction | 0.01% per update | Unique items never destroyed |
| Chest decay (overworld) | 0.1% per update | 40% contents destroyed; survivors drop |
| Water decay on drink | 70% | `constants.py:WATER_DECAY_ON_DRINK` |
| Grass decay on eat | 60% | `constants.py:GRASS_DECAY_ON_EAT` |

---

### Cell Growth / Decay Rates (CA) — Summary (`constants.py:107–130`)
| Variable | Value |
|---|---|
| BIOME_SPREAD_RATE | 0.004 |
| TREE_GROWTH_RATE | 0.0001 |
| TREE_DECAY_RATE (crowded) | 0.0005 |
| TREE_DROUGHT_RATE | 0.0003 |
| FLOWER_SPREAD_RATE | 0.0001 |
| FLOODING_RATE (rain only) | 0.015 |
| WATER_TO_DIRT_RATE | 0.02 |
| DEEP_WATER_FORM_RATE | 0.05 |
| GRASS_TO_DIRT_RATE | 0.00001 |
| DIRT_TO_GRASS_RATE | 0.0001 |
| SAND_RECLAIM_RATE | 0.05 |
| DIRT_SAND_SPREAD_RATE | 0.008 |

---

## Merge Command (only after full checklist signed off)

```bash
git checkout main
git merge dev --no-ff -m "Release: merge dev → main (YYYY-MM-DD)"
# Remove dev-only files listed in section 11
git push origin main
```

**Do not run this until @qcruz gives explicit approval.**
