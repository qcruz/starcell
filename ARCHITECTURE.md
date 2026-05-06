# StarCell — Architecture Overview

A quick-start map of how the codebase is structured, how systems connect, and what to know before writing your first line of code.

---

## How the Game Class Works

StarCell uses Python multiple inheritance to compose one `Game` object from ~15 mixins. Every mixin has full access to `self.entities`, `self.screens`, `self.player`, etc. — there is no argument-passing between systems.

**MRO (Method Resolution Order)** — left takes precedence over right:

```
Game(
    HudMixin, InventoryUIMixin, MenusMixin,          # ui/       — rendering
    WorldGenerationMixin, ZonesMixin, CellsMixin,    # world/    — world sim
    SaveLoadMixin, CraftingMixin, CombatMixin,       # systems/  — game rules
    EnchantmentMixin, FactionsMixin, SpawningMixin,  # systems/
    NpcAiActionsMixin, NpcAiMovementMixin,           # ai/       — NPC actions and movement
    LoreEngineMixin,                                 # lore/     — world events
    GameCoreMixin, NpcAiMixin, AutopilotMixin,       # legacy monoliths (being extracted)
)
```

The legacy monolith files (`game_core.py`, `npc_ai.py`) are at the bottom of the MRO — any method in the modular files above overrides them automatically. New code goes in the modular files; the monoliths shrink over time.

---

## Directory Layout

```
starcell/
  main.py            — Entry point. Defines Game class (MRO chain above).
  constants.py       — Legacy all-in-one data file. Still used by npc_ai.py, game_core.py.
  entity.py          — Entity class, Inventory, SpriteManager (root level).

  data/              — Modular data tables
    settings.py      — Screen size, FPS, grid constants
    cells.py         — CELL_TYPES, COLORS, CELL_PICKUP, ITEM_TO_CELL
    items.py         — ITEMS, RECIPES, LOOT_TABLES
    entities.py      — ENTITY_TYPES, NPC_BEHAVIORS
    factions.py      — Faction definitions
    quests.py        — QUEST_TYPES
    spells.py        — SPELL_TYPES

  systems/           — Self-contained game systems
    save_load.py     — SaveLoadMixin
    crafting.py      — CraftingMixin (crafting, item placement, interact)
    combat.py        — CombatMixin (player attack, take damage, death, respawn)
    enchantment.py   — EnchantmentMixin (star spell, keeper, summon, transform)
    factions.py      — FactionsMixin (faction assignment, domains)
    spawning.py      — SpawningMixin (per-zone NPC and item spawning)

  world/             — World simulation
    generation.py    — WorldGenerationMixin (zone + cave generation)
    zones.py         — ZonesMixin (probabilistic_zone_updates — the NPC AI entry point)
    cells.py         — CellsMixin (cellular automata)

  ui/                — Rendering
    hud.py           — HudMixin (main game view, entity sprites, HUD)
    inventory.py     — InventoryUIMixin (all inventory panels)
    menus.py         — MenusMixin (main menu, pause, death screen)

  ai/                — NPC behaviour primitives
    actions.py       — NpcAiActionsMixin (chop, mine, harvest, build, trade)
    movement.py      — NpcAiMovementMixin (pathfinding, zone transitions, structure entry/exit)

  lore/              — World event generation
    engine.py        — LoreEngineMixin (keeper assignment, zone name generation, migration events)

  docs/              — Plain-language and pseudocode guides for major source files
  debug/             — Watchdog, BugCatcher, session logs, bug report
```

---

## Key Data Structures

| Name | Type | What it holds |
|---|---|---|
| `self.entities` | `{entity_id: Entity}` | Every entity in the world, indexed by integer ID |
| `self.screens` | `{zone_key: dict}` | Cell grid + metadata for every generated zone |
| `self.screen_entities` | `{zone_key: [entity_id, ...]}` | Which entities are in which zone (source of truth for rendering) |
| `self.structures` | `{structure_key: dict}` | Virtual zone metadata for caves, houses, mineshafts |
| `self.player` | `dict` | Player position, stats, inventory, flags |
| `self.followers` | `[entity_id, ...]` | Entity IDs currently following the player |
| `self.follower_items` | `{entity_id: item_name}` | Maps each follower to the item that summoned it |

Zone keys are strings: `f"{screen_x},{screen_y}"`. Structure zones use large negative x values (e.g. `"-1000,5"`) so they never collide with overworld keys.

---

## How a Tick Flows

```
game.run() loop (60 FPS)
  │
  ├── handle_input()              ← keyboard / mouse events (game_core.py)
  ├── move_player()               ← apply queued movement (game_core.py)
  ├── check_follower_integrity()  ← safety net (game_core.py)
  ├── sound.update()              ← fade-outs, queued tracks
  ├── check_npc_inspection()      ← Shift-held overlay (game_core.py)
  ├── reconcile_screen_entities() ← every 600 ticks: repair zone desync (game_core.py)
  ├── update_quests()             ← check completion (game_core.py)
  ├── update_enchanted_cells()    ← decrement timers (enchantment.py)
  ├── update_cells()              ← cellular automata by zone distance (game_core.py)
  ├── probabilistic_zone_updates()  ← NPC AI for all entities (world/zones.py)  <-- HERE
  ├── watchdog.update()           ← snapshot cycle (debug/)
  ├── autosave()                  ← every 30 s real time
  └── draw()                      ← HUD render (ui/hud.py)
```

**NPC AI entry point** is `world/zones.py:probabilistic_zone_updates`. It iterates zones near the player, calls `update_entity_ai(entity_id, entity)` from `npc_ai.py`, which calls the state machine (`update_entity_ai_state`), which calls action primitives from `ai/actions.py` and movement from `ai/movement.py`.

---

## The Dual-Import Pattern — Read This Before Adding Data

This is the most common contributor mistake. **Both of these must be updated** when you add a new cell type, item, or recipe:

1. **`data/cells.py`** (or `data/items.py`, `data/entities.py`, etc.) — the modular data file
2. **`constants.py`** — the legacy monolith that still feeds `npc_ai.py` and `game_core.py`

The `data/` modules are imported via `data/__init__.py` which re-exports with `from data.X import *`. The monolith `constants.py` is imported separately via `from constants import *`. They are not linked — you must update both manually.

If you add to `data/cells.py` only, `npc_ai.py` will not see the new cell type and will fall through to default behavior. If you add to `constants.py` only, the modular systems in `ai/`, `world/`, and `systems/` won't see it.

**Checklist for any new cell type:**
- [ ] Add to `CELL_TYPES` in `data/cells.py`
- [ ] Add color to `COLORS` in `data/cells.py`
- [ ] Add to `CELL_TYPES` in `constants.py` (same entry)
- [ ] Add sprite PNG to `sprites/` if applicable
- [ ] Add sprite loading entry in `game_core.py:load_sprites`

**Checklist for any new item:**
- [ ] Add to `ITEMS` in `data/items.py`
- [ ] Add to `ITEMS` in `constants.py`
- [ ] Add to `RECIPES` in both if craftable

---

## Key Patterns

**`actor='player'` pattern:** Action primitives in `ai/actions.py` (`action_harvest_cell`, `action_transform_cell`, `action_place_cell`) accept `actor='player'` or any entity object. Player and NPC harvesting share the same drop/XP/sound logic — don't duplicate it.

**Memory lane:** Each entity has a list of recent cell positions. The movement code skips recently-visited cells to prevent oscillation. This is why a stuck NPC eventually unsticks — it burns through its blacklist.

**`screen_entities` is the source of truth:** If you move an entity between zones, you must update BOTH `entity.screen_x/screen_y` AND remove/add the entity in `screen_entities`. Updating only one causes the zone desync bug.

**State machine vs. legacy:** `update_entity_ai_state` (the state machine) decides what an entity wants. The outer dispatch in `update_entity_ai` executes it. When adding new NPC behavior, wire it through the state machine — don't add another priority dispatch branch.

---

## Where to Start

| If you want to... | Start here |
|---|---|
| Add a new cell type | `data/cells.py` + `constants.py` (dual-import) |
| Add a new item or recipe | `data/items.py` + `constants.py` |
| Add a new NPC type | `data/entities.py` + `constants.py` + sprite |
| Add a new NPC behavior | `data/entities.py` NPC_BEHAVIORS + `ai/actions.py` |
| Change how NPCs move or pathfind | `ai/movement.py` |
| Change the state machine | `npc_ai.py:update_entity_ai_state` |
| Add a new player action | `systems/crafting.py` (interact/place) or `game_core.py` (input) |
| Change world generation | `world/generation.py` |
| Change biome/cell spread rules | `world/cells.py` |
| Add a new spell | `data/spells.py` + `systems/enchantment.py` |
| Change faction behavior | `systems/factions.py` |
| Add UI panels | `ui/inventory.py` or `ui/hud.py` |

For detailed explanations of each major file, see the `docs/` directory — every major source file has a plain-language guide.
