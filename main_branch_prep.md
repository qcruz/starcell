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

## 1. Player Starting Inventory ✅ DONE

**Applied in dev:** `new_game()` now gives only `star_spell` + action items. Dev all-items loop removed.

---

## 2. Starting Follower ✅ DONE

**Applied in dev:** Pool restricted to `SHEEP`, `DEER`, `RED_BIRD`, `BUTTERFLY`, `CHICKEN`.

---

## 3. Autopilot Toggle (Shift+A)

**Location:** `game_core.py:1250–1255`, `ui/menus.py:36`, `ui/menus.py:118`

**Policy for main:** No change needed. Autopilot is an intentional main game mechanic, not a dev tool. Keep Shift+A binding and controls text as-is.

---

## 4. Dev Screen (Shift+I) ✅ DONE

**Applied in dev:** `DevScreenMixin` removed from MRO and `ui/__init__.py`. `ui/dev_screen.py` deleted. All `show_dev_screen` refs removed from `game_core.py`.

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

**Code fixes — ✅ DONE:**
1. `ai/actions.py:action_harvest_cell` — `is_cell_enchanted` guard added; NPCs cannot harvest enchanted cells.
2. `world/zones.py` zone unload — `enchanted_cells.pop` removed; enchantments survive zone cycling.

**Visual clarity — ⏳ PENDING @qcruz:**
Current marker is a small golden rect in the top-left corner of the cell (`ui/hud.py:199–203`). Must be replaced with a clearly visible enchantment icon (star/sparkle sprite or distinct overlay). Exact visual TBD with @qcruz — flag when ready to implement.

---

## 6. Follower Energy Cost (Max Energy Reduction) ✅ DONE

**Applied in dev:** Cost is 30 per follower. Release, death, and Shift+F paths all correctly restore 30 per enchant level. Follower table in §15 updated accordingly.

---

## 7. Biome Spread Rate

**Location:** `constants.py:125`

**Current dev value:** `BIOME_SPREAD_RATE = 0.004` — noted in comments as "4x increase"

**Policy for main:** Keep at 0.004. No change needed.

---

## 8. Biome Occurrence Rates

**Location:** `world/generation.py:85`, `constants.py:214–217`

**Current state:** Generation already uses `random.choice(list(BIOMES.keys()))` — all biomes spawn at equal probability. The four stale `*_BIOME_CHANCE` constants have been removed from `constants.py`. ✅ DONE

---

## 9. E-Button Pickup

**Location:** `game_core.py:1226–1228`

**Current dev behavior:** E key calls `pickup_cell_or_items()` — picks up dropped item piles AND raw cells directly into inventory (creative/admin mode).

**✅ DONE:** E-key block removed from `game_core.py`. Dropped item pickup already handled in `interact()` (Space). Controls text updated in `ui/menus.py`.

---

## 10. Controls Help Text ✅ DONE

**Applied in dev:** E-key references removed from both help screens in `ui/menus.py`. Space described as the pickup key.

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

**✅ DONE:** `DEBUG_MODE = False` added to `constants.py`. BugCatcher/Watchdog init and all 8 call sites gated behind `DEBUG_MODE`. `AUTO_DEBUG` runtime enable path in `main.py` sets `DEBUG_MODE = True` when `debug/auto_debug.cfg` exists with a truthy value. `debug/` stays in codebase, dormant by default.

---

## 13. Print Statements in Game Code ✅ DONE

**Applied in dev:** All `print()` statements in `game_core.py` and `npc_ai.py` removed or gated behind `DEBUG_MODE`. Sprite load error prints gated; [AutoDebug] and [FREEZE-DETECT] session management prints kept. WARRIOR `if debug:` prints in `npc_ai.py` kept (already gated).

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
| Max energy reduction per follower | **30** | ✅ Applied in dev |

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
