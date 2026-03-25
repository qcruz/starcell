# Autopilot ↔ NPC AI Recon

**Purpose:** Track every capability the autopilot has, whether it exists in NPC AI, and what the porting path looks like. The autopilot is the primary test bed for advanced NPC behavior — features are prototyped here, validated across observation sessions, then ported to the NPC AI layer. This document keeps the two in sync and makes the gap visible.

**The bigger goal:** The autopilot should be able to do everything a player can do. Once a capability is stable in the autopilot, it becomes a candidate for NPC AI — ideally driven by the quest/keeper system rather than explicit code, so that LoreEngine can script complex NPC behavior (build a settlement, clear a path to a resource, level up over time) by assigning ordered quest sequences rather than writing new AI routines.

---

## Capability Inventory

### Navigation & Movement

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Wander in zone | ✅ via proxy NPC AI | ✅ `wandering` state | Same underlying system |
| Target specific cell | ✅ `proxy.current_target = ('cell', x, y)` | ✅ via `behavior_config` + keeper | AP sets directly; NPC uses quest targeting |
| Cross zone boundary | ✅ `_nudge_toward_zone()` → exit cell targeting | ✅ `try_entity_screen_crossing` | AP has intent-driven cross-zone; NPCs wander across organically — no quest-driven direction |
| Navigate toward quest target zone | ✅ full — calculates exit direction, moves toward it | ❌ missing | NPCs with keepers stay in zone; no cross-zone quest pursuit |
| Stuck detection | ✅ tick counter; fires at 60 ticks stuck | ❌ missing | NPCs can freeze indefinitely against obstacles |
| Stuck recovery — wander cooldown | ✅ 10-cycle free wander after repeated failed exit nudges | ❌ missing | |
| Flee from hostiles | ✅ `flee_chance=0.95` via NPC AI | ✅ `flee` state in NPC AI | Same system; AP just sets the param higher |

### Resource Harvesting

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Chop trees | ✅ obstacle-clear + opportunistic (every 30t) | ✅ `action_harvest_cell` on TREE | NPC version is quest-driven only; no passive scan while moving |
| Mine stone / iron ore | ✅ obstacle-clear + opportunistic (every 30t) | ✅ `action_harvest_cell` on STONE/IRON_ORE | Same gap as above |
| Obstacle-clear (path unblocking) | ✅ chops/mines cells blocking movement after 60t stuck | ❌ missing | High value — NPCs that get stuck against trees just freeze |
| Opportunistic harvest (passive scan) | ✅ 4-cardinal scan every 30 ticks while moving | ❌ missing | AP accumulates resources naturally while traversing; NPCs only harvest toward quest target |
| Harvest carrots | ❌ not implemented in AP | ✅ FARMER behavior_config | |
| Build well | ❌ not implemented in AP | ✅ MINER `try_build_well` | |
| Till soil / pave cobblestone | ❌ not implemented in AP | ✅ `action_transform_cell` | |

### Crafting

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Craft from recipe list | ✅ `_autopilot_try_craft()` — prioritized list, queued UI simulation | ❌ missing | `try_craft_recipe()` port to `ai/actions.py` is on next_up |
| Priority crafting order | ✅ iron_sword > iron_ingot > pickaxe > hoe > shovel… | ❌ | Will be NPC-type-specific when ported |

### Combat

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Attack hostile entities | ❌ disabled (`combat_chance=0.0`, `aggressiveness=0.0`) | ✅ `find_and_attack_enemy` | AP intentionally non-combat; proxy flees instead |
| Target specific enemy via quest | ✅ HUNT/SLAY/COMBAT_HOSTILE — sets `proxy.current_target` to entity id | ✅ partial — keepers target nearby hostiles | NPC AI doesn't use quest target_entity_id to navigate cross-zone to a specific target |
| Block | ❌ | ✅ `combat_state='blocking'` | |

### Inventory Management

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Tool selection | ✅ randomly cycles tools every ACTION_INTERVAL | ❌ | NPCs have inventory but no tool-selection concept |
| Drop surplus items | ✅ drops any item with count > 1 at proxy position | ❌ | Goblins have ad hoc chest-looting drop; no general surplus drop |
| Sync inventory to player | ✅ every 60 ticks | n/a | AP-specific bridge |
| Pick up dropped items | ❌ not implemented in AP | ✅ GOBLIN loot pickup | |

### Spells & Actions

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Cast spell (rain, day, star) | ✅ selects magic item, queues L keypress | ❌ missing | No NPC spell casting at all yet |
| Use action (attack, block, dig) | ❌ not implemented in AP | ❌ partial — combat NPCs attack via `find_and_attack_enemy` | Action items (from actions tab) not used by either |

### Social / NPC Interaction

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Inspect nearby NPC | ✅ finds nearest within dist=4, sets `inspected_npc` | n/a | Player-facing feature; NPC equivalent would be "notice" nearby NPC |
| Assign quest to NPC | ✅ 30% chance on inspect → `handle_npc_quest_assign` | ❌ | NPCs don't delegate quests to each other |
| Trade with NPC | ❌ not implemented in AP | ✅ partial — TRADER logic in NPC AI | |
| Recruit follower | ❌ not implemented in AP | ❌ | `handle_npc_follow_interaction` on next_up |
| Give gift to NPC | ❌ not implemented in AP | ❌ | Favor/gift system on next_up |

### Quest & Goal System

| Capability | Autopilot | NPC AI | Notes |
|---|---|---|---|
| Quest-driven behavior | ✅ full — active_quest steers NPC type, nudge target, action priorities | ✅ partial — `quest_queue` + `quest_focus` drives behavior_config | NPC system exists but is simpler; no cross-zone pursuit, no crafting, no combat quest targeting |
| Quest rotation on completion | ✅ 80% chance to switch; forced every 1800t | ✅ LoreEngine assigns new quests | AP random; NPC version uses LoreEngine weighted assignment |
| Quest assignment to other NPCs | ✅ 30% chance per NPC inspect | ❌ | No NPC-to-NPC quest delegation |
| Quest type → NPC role mapping | ✅ `QUEST_NPC_TYPE` dict | ❌ | AP changes proxy type on quest switch; NPC AI doesn't change type based on quest |
| Abandon unreachable quest | ✅ 2% chance per nudge cycle | ❌ | NPCs can get stuck pursuing an impossible target indefinitely |

---

## LoreEngine as Quest Scripting

The LoreEngine (`lore/engine.py`) is the bridge that makes NPC behavior programmable without explicit code. Rather than writing new AI routines for each complex behavior, LoreEngine assigns ordered quest sequences to NPCs that — when executed — produce the desired world impact.

**Current LoreEngine capabilities:**
- Assigns quests to keeper NPCs based on their type and zone composition
- Fires world events (settlement, discovery, conflict) that trigger NPC state changes
- Tracks quest completion and cycles to the next quest in sequence

**What it needs to become the quest scripting layer:**

| Feature | Status | Notes |
|---|---|---|
| Ordered quest sequences per NPC | ❌ | LoreEngine assigns single quests; needs queue of ordered steps |
| Conditional quest chains | ❌ | "Complete MINE quest → assign BUILD_WELL → assign GATHER" |
| Cross-zone quest targeting | ❌ | Assign a quest whose target is in a specific zone; NPC travels there |
| NPC-to-NPC quest delegation | ❌ | LoreEngine tells NPC A to assign a task to NPC B |
| World impact triggers | ✅ partial | Settlement/discovery events exist but don't chain to follow-up quests |
| Named villain designation | ❌ | On next_up — LoreEngine marks a high-level hostile with unique properties |

---

## Porting Priority (Autopilot → NPC AI)

Ordered by impact and readiness. Items marked **ready** have stable autopilot implementations across 2+ observation sessions.

1. **Obstacle clearing** — `_autopilot_try_clear_obstacle()` → `ai/actions.py:try_clear_obstacle()`. High impact: NPCs stuck against trees is a persistent observation bug. Simple port: scan 4 cardinals for TREE/STONE, call existing `try_chop_tree`/`try_mine_rock`. **Ready.**

2. **Opportunistic harvesting** — `_autopilot_opportunistic_harvest()` → `ai/actions.py`. Toned-down version: fire every ~60 ticks (vs AP's 30t) only when `ai_state == 'wandering'`. Ensures NPCs accumulate resources naturally without overriding quest work. **Ready.**

3. **Crafting** — `_autopilot_try_craft()` → `ai/actions.py:try_craft_recipe()`. Already on next_up. MINER and BLACKSMITH use it. **On next_up.**

4. **Cross-zone quest pursuit** — NPC AI currently has no mechanism to travel toward a quest target in another zone. Port the `_nudge_toward_zone` logic to `ai/movement.py` gated by `quest_focus` and keeper type. Medium complexity.

5. **Stuck detection + recovery** — Port the stuck-tick counter and wander-cooldown to `npc_ai.py` main update loop. Low complexity, high reliability improvement.

6. **Quest abandonment** — Small probability per update to clear an unreachable quest target and let LoreEngine re-assign. Prevents indefinite frozen states.

7. **Spell casting** — Once NPC spells are designed. Wizards cast; AP already has the mechanic.

8. **Surplus item dropping** — NPCs with full inventories drop surplus near structures or drop points. Feeds into the economy (items on the ground, chest filling, etc.).

---

## Session Observations Relevant to This Doc

- **Session 22 (2026-03-14):** Obstacle-clear confirmed working in AP across 10k+ ticks. Zero freezes at trees/rocks when it fires. NPC AI still shows freeze-at-tree in observation logs.
- **Session 9 (2026-03-08):** Opportunistic harvest confirmed accumulating stone and saplings passively during wandering.
- **Session 8 (2026-03-08):** Crafting sequence (C → click → Space → close) confirmed stable. No loop issue once shovel was deprioritized.
