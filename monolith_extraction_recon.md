# Monolith Extraction Recon

**Purpose:** Track what has been extracted from the two legacy monolith files (`game_core.py`, `npc_ai.py`) into modular mixins, what remains, and where each remaining section should land when extracted. The monoliths are not going away — extraction is ongoing and gated by test coverage and review. This doc keeps the gap visible.

---

## Current Mixin Inventory

These files are fully extracted and in production via the `Game` MRO in `main.py`:

| Mixin | File | Responsibility |
|---|---|---|
| SaveLoadMixin | `systems/save_load.py` | Save/load JSON, entity reconciliation |
| CraftingMixin | `systems/crafting.py` | Craft recipes, item pickup/drop, decay, follower spawn |
| CombatMixin | `systems/combat.py` | Player attack, damage, death, respawn, screen-entity reconcile |
| EnchantmentMixin | `systems/enchantment.py` | Star spell, release, legendary name gen, follower release |
| FactionsMixin | `systems/factions.py` | Faction creation, warrior assignment, commander/king promotion |
| SpawningMixin | `systems/spawning.py` | Entity spawning, raids, skeleton/termite/cave hostile spawning |
| WorldGenerationMixin | `world/generation.py` | Zone and interior generation, chest placement, NPC resident spawn |
| ZonesMixin | `world/zones.py` | Zone update loop, biome shifts, keeper assignment, catch-up queue |
| CellsMixin | `world/cells.py` | Cellular automata, rain, weather, day/night cycle, item movement |
| HudMixin | `ui/hud.py` | HUD rendering, entity rendering, attack animations |
| InventoryUIMixin | `ui/inventory_ui.py` | Inventory panel rendering and interaction |
| MenusMixin | `ui/menus.py` | Main menu, pause screen, settings |
| NpcAiActionsMixin | `ai/actions.py` | Primitive NPC actions: chop, mine, plant, till, build, trade (NPC-to-NPC barter, gold-drop trade, N-key recipe panel) |
| NpcAiMovementMixin | `ai/movement.py` | NPC movement: wander, pathfinding, zone cross, merge/split |
| LoreEngineMixin | `lore/engine.py` | Quest text gen, quest completion checks, NPC quest assignment, lore events |

---

## game_core.py — What Remains

`game_core.py` (GameCoreMixin) is the player-side monolith: initialization, input handling, player movement, subscreen transitions, and the main run loop. The methods below have not yet been extracted.

### Run Loop & Init
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `__init__` | 22–219 | No clear home — keep or split into GameInitMixin | Massive initializer; depends on every other mixin being present |
| `run` | 2692–end | Keep in game_core.py | Main loop orchestrator; touching this risks cascading breakage |
| `_auto_debug_shutdown` | 2656–2691 | `debug/` | Already debug-specific; low priority |

### Sprite Loading
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `load_sprites` | 220–523 | `engine/sprite_manager.py` | SpriteManager already exists; partial overlap |

### Player Movement & Targeting
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `move_player` | 1740–1915 | New `player/movement.py` mixin | Large; handles step sound, cell entry, zone cross, follower drag |
| `get_target_cell` | 1916–1956 | `player/movement.py` | Depends on move_player context |
| `is_at_corner` | 856–873 | `ai/movement.py` or `player/movement.py` | Pure geometry — no game state |
| `get_nearest_corner_target` | 874–893 | `ai/movement.py` or `player/movement.py` | Companion to is_at_corner |

### Input Handling
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `handle_input` | 988–1181 | New `ui/input_handler.py` or split into focused methods | Largest single method; dispatches keyboard events; hard to split without breaking |
| `handle_inventory_click` | 1182–1250 | `ui/inventory_ui.py` | UI click logic; natural home already exists |
| `handle_quest_ui_click` | 1251–1301 | `ui/inventory_ui.py` or `lore/engine.py` | Quest panel click |
| `_handle_menu_click` | 1342–1358 | `ui/menus.py` | Already a natural fit |
| `open_npc_trade_window` | ~2039 | `ui/inventory_ui.py` | Trade window setup — Shift+T on inspected NPC; shows NPC inventory with gold prices |
| `handle_npc_trade_click` | ~2066 | `ui/inventory_ui.py` | Trade window click — buys item from NPC for gold |

### Spells
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `cast_rain_spell` | 1359–1368 | `world/cells.py` or `systems/enchantment.py` | Rain is a world-cell event; fits CellsMixin |
| `cast_day_spell` | 1369–1380 | `world/cells.py` | Same — toggles day/night state |

### Player Actions & NPC Interaction
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `execute_action` | 1381–1384 | `player/actions.py` or keep in game_core.py | Thin dispatcher; not worth a new file alone |
| `do_shove` | 1385–1401 | `player/actions.py` | Player-specific; no NPC equivalent yet |
| `handle_npc_follow_interaction` | 1402–1442 | `ui/inventory_ui.py` or `player/actions.py` | Recruit logic; depends on inspected_npc |
| `handle_npc_quest_interaction` | 1443–1487 | `lore/engine.py` | Quest exchange; natural home |
| `handle_npc_quest_assign` | 1488–1602 | `lore/engine.py` | Quest assignment; same |

### Inventory Controls
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `select_inventory_slot` | 1710–1719 | `ui/inventory_ui.py` | Slot selection |
| `cycle_inventory_slot` | 1720–1739 | `ui/inventory_ui.py` | Slot cycling |

### Interaction Dispatch
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `interact` | 1957–2122 | `player/actions.py` | Large; dispatches to chest, structure, NPC, item |
| `interact_with_chest` | 2506–2548 | `systems/crafting.py` or `player/actions.py` | Chest loot handled in crafting context |

### Structure Transitions
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `enter_structure` | 2123–2208 | `world/zones.py` or new `world/structures.py` | Zone-level transition; fits ZonesMixin |
| `_teleport_followers_with_player` | 2209–2249 | `world/zones.py` | Companion to enter_structure |
| `exit_structure` | 2250–2284 | `world/zones.py` | Paired with enter_structure |
| `descend_cave` | 2285–2338 | `world/zones.py` | Cave depth navigation |
| `ascend_cave` | 2339–2399 | `world/zones.py` | Paired with descend_cave |
| `_exit_secret_cave_entrance` | 2400–2467 | `world/zones.py` | Secret entrance exit |

### Utilities
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `update_cells` | 528–573 | Thin wrapper; keep or inline | Calls zone update pipeline |
| `update_entities` | 574–650 | **Dead code** — defined but never called; all NPC AI runs through `zones.py:probabilistic_zone_updates()`. Remove in next cleanup pass. |
| `remove_entity` | 651–773 | `engine/entity.py` or `systems/combat.py` | Cleanup on death; overlaps CombatMixin |
| `check_follower_integrity` | 774–800 | `systems/combat.py` | Follower health enforcement |
| `check_npc_inspection` | 801–855 | `ui/hud.py` | Inspection panel timeout |
| `is_entity_at_position` | 894–914 | `engine/entity.py` or `ai/movement.py` | Geometry check |
| `update_screen_cells` | 915–987 | `world/zones.py` or `world/cells.py` | Screen refresh |
| `update_enchanted_cells` | 2645–2655 | `systems/enchantment.py` | Enchantment tick |
| `_next_item_uid` | 1603–1607 | `engine/entity.py` or `systems/save_load.py` | UID counter |
| `register_item_target` | 1608–1631 | `lore/engine.py` | Quest item target registration |
| `spawn_cave_entities` | 2468–2505 | `systems/spawning.py` | Cave-spawn bridge; mostly covered by SpawningMixin |
| `new_game` | 2549–2644 | Keep in game_core.py | Full game init; depends on everything |
| `_load_settings`, `_save_settings`, `_apply_settings` | 1302–1341 | `systems/save_load.py` | Settings persistence; natural home |

---

## npc_ai.py — What Remains

`npc_ai.py` (NpcAiMixin) is the entity-side monolith: the AI state machine, behavior dispatch, role behaviors, keeper logic, and combat. Primitive actions and movement have been extracted; the orchestration and role-specific logic remain.

### Core AI Loop (Do Not Extract Until Stable)
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `update_entity_ai` | 27–1019 | Keep in npc_ai.py | Main per-entity AI orchestrator; ~1000 lines; extracting risks cascade |
| `update_entity_ai_state` | 1020–1463 | Keep or extract to npc_ai.py companion | State machine (idle→wander→target→combat→flee); core to all NPC behavior |
| `evaluate_entity_priorities` | 1464–1697 | Keep in npc_ai.py | Priority evaluation; tightly coupled to state machine |
| `determine_target_type` | 2262–2383 | Keep in npc_ai.py | Target assignment; quest/behavior driven |
| `execute_entity_behavior` | 2384–2448 | Keep in npc_ai.py | Behavior dispatch; orchestrates ai/actions.py calls |

### Combat (Candidate for systems/combat.py)
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `find_and_attack_enemy` | 1734–2003 | `systems/combat.py` | NPC-side combat; player-side already there |
| `update_entity_combat_state` | 2232–2261 | `systems/combat.py` | Combat state transitions |

### Quest & Keeper Logic (Candidate for lore/engine.py)
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `_quest_target_as_current` | 2004–2018 | `lore/engine.py` | Quest targeting helper |
| `_try_complete_assigned_quest` | 2103–2142 | `lore/engine.py` | Quest completion; already has a counterpart in LoreEngine |
| `_assign_specific_quest_target` | 2143–2231 | `lore/engine.py` | Quest target seeding |
| `resolve_keeper_target` | 2019–2069 | New `ai/keeper.py` or `lore/engine.py` | Keeper anchor resolution |
| `_set_keeper_target_cell` | 2070–2077 | Same as above | Keeper target setters |
| `_set_keeper_target_entity` | 2078–2089 | Same | |
| `_set_keeper_target_item` | 2090–2102 | Same | |

### Role Behaviors (Candidate for ai/actions.py or ai/roles.py)
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `hostile_structure_behavior` | 2449–2690 | `ai/actions.py` or new `ai/roles.py` | Goblin/bandit structure attacks |
| `farmer_behavior` | 2691–2746 | `ai/actions.py` or `ai/roles.py` | FARMER role dispatch |
| `lumberjack_behavior` | 2747–2852 | `ai/actions.py` or `ai/roles.py` | LUMBERJACK role dispatch |
| `guard_behavior` | 2853–2938 | `ai/actions.py` or `ai/roles.py` | GUARD/WARRIOR role dispatch |
| `trader_behavior` | 2939–3012 | `ai/actions.py` or `ai/roles.py` | TRADER role dispatch |

### Shelter & Transformation
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `npc_seek_shelter` | 3013–3093 | `ai/movement.py` | Movement-based; fits NpcAiMovementMixin |
| `check_npc_transformation` | 3094–3195 | `engine/entity.py` or `systems/spawning.py` | Type-change logic (settlement, warrior→commander) |

### Wizard Behaviors (Candidate for ai/actions.py)
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `try_wizard_seek_rune` | 3196–3250 | `ai/actions.py` | Wizard-specific actions |
| `try_wizard_cast_spell` | 3251–3287 | `ai/actions.py` | Wizard spell casting |
| `try_wizard_explore_cave` | 3288–3304 | `ai/actions.py` | Wizard cave exploration |
| `cast_wizard_spell` | 3305–end | `ai/actions.py` | Spell resolution |

### Utilities
| Method | Lines (approx) | Extraction Target | Notes |
|---|---|---|---|
| `_same_context_as_player` | 13–26 | `engine/entity.py` or keep | Player zone matching check |
| `_try_flying_item_drop` | 1698–1733 | `ai/actions.py` | Flying entity item drop |

---

## Extraction Priority

Ordered by impact and safety. Items marked **Ready** have clear target homes and no structural dependencies that block extraction.

1. **`handle_npc_quest_interaction` + `handle_npc_quest_assign`** → `lore/engine.py`. Quest interaction belongs with quest logic. Medium complexity — depends on `inspected_npc` state. **Ready.**

2. **`find_and_attack_enemy` + `update_entity_combat_state`** → `systems/combat.py`. NPC combat already partially there. Medium complexity — no hard dependencies preventing move. **Ready.**

3. **Role behaviors** (`farmer_behavior`, `lumberjack_behavior`, `guard_behavior`, `trader_behavior`) → new `ai/roles.py`. These are already thin dispatchers calling `ai/actions.py` primitives. Low risk. **Ready.**

4. **Keeper methods** (`resolve_keeper_target`, `_set_keeper_target_*`) → `lore/engine.py` or `ai/keeper.py`. Self-contained. Medium complexity. **On next_up.**

5. **Structure transitions** (`enter_structure`, `exit_structure`, `descend_cave`, `ascend_cave`) → `world/zones.py`. Zone-level transitions; natural home. High complexity — touches many state variables. Requires careful testing.

6. **`handle_inventory_click`, `handle_quest_ui_click`, `select_inventory_slot`, `cycle_inventory_slot`** → `ui/inventory_ui.py`. UI clicks; natural home. Low complexity.

7. **`check_follower_integrity`, `remove_entity`** → `systems/combat.py`. Entity cleanup on death. Medium complexity.

8. **`move_player`** → new `player/movement.py`. Largest remaining chunk. Complex — handles zone crossing, follower drag, sound, cell transitions. Extract only after structure transitions are moved.

9. **`__init__`** — Not extracting. Too many dependencies. Instead, gradually trim it as subsystems own their own init data.

---

## Duplication Hot Spots

Known areas where logic exists in both the monolith and the extracted mixin:

| Monolith Method | Extracted Counterpart | Risk |
|---|---|---|
| `game_core.spawn_cave_entities` | `systems/spawning.py:spawn_cave_entities` | Low — monolith version is a thin bridge; confirm and remove |
| `npc_ai.find_and_attack_enemy` | `systems/combat.py` (player combat only) | Medium — both handle attack resolution; needs unification |
| `npc_ai.check_npc_transformation` | `systems/factions.py:promote_to_commander/king` | Low — transformation logic split between files |

---

*Last updated: 2026-04-12*
