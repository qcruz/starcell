# npc_ai.py — Plain Language Guide

**What this file is:**
All entity behavior in the game lives here. Every NPC — farmers, wolves, goblins, wizards, bats — runs through this code every tick. It decides what an entity wants, where it moves, when it fights, and how it interacts with the world.

**Why it's a mixin:**
`NpcAiMixin` is mixed into the main `Game` class via Python's multiple inheritance (MRO). This lets the AI methods call `self.player`, `self.entities`, `self.screens`, etc. without passing the game state around. The trade-off is that you need to understand the MRO chain to know where those attributes come from — they're on the `Game` object, not defined here.

---

## Section 1 — Shared Utilities (lines 13–141)

### `_same_context_as_player`
Answers the question: "Is this entity in the same zone as the player right now?" Both overworld zones and cave/house interiors use the same coordinate system (the structure gets virtual coordinates), so comparing `screen_x, screen_y` is all that's needed. This check appears everywhere combat and targeting logic needs to guard against cross-zone operations.

### `_apply_walk_cell_effects`
Every time an entity takes a step, there's a small chance the cell it stepped on changes. Skeletons bleach grass to dirt. Farmers till soil and auto-plant carrots. Warriors pave the center cross of a zone into cobblestone over time. This is structured as a per-type dispatch because each entity type has a distinct ecological role — it's intentional worldbuilding through passive side effects rather than explicit world-editing commands.

### `_try_adjacent_consume`
When a hungry or thirsty entity moves, it automatically eats or drinks from adjacent cells without needing to target them explicitly. The probability of eating is proportional to how hungry the entity is — a full entity almost never eats, a starving one almost always does. This fires on the entity's own cell first, then the 8 surrounding cells. It exists so entities don't need a dedicated "find food" targeting step for every meal; they can graze passively while doing other things.

---

## Section 2 — Main Update Entry Point (lines 143–1211)

### `update_entity_ai` — the outer update loop

This is called once per tick per entity. Think of it as the conductor: it enforces preconditions, runs the inner state machine, then dispatches the entity's current state to the right movement or action.

**Why it's split into outer and inner:**
The inner function (`update_entity_ai_state`) handles probabilistic state transitions — deciding *what* the entity wants to do next. The outer function handles *executing* that decision: actually moving, attacking, wandering. Keeping them separate means the state machine stays clean and the execution logic stays readable.

**Double-update guard (lines 146–150)**
Entities can be processed from multiple queues in the same tick. This stamp check (`last_ai_tick == self.tick`) prevents a single entity from running its full AI twice in one tick, which would make it move twice as fast.

**Energy idle gate (lines 152–158)**
Each entity has an energy bar. When energy is low, there's a probabilistic chance the entity skips its AI update and idles instead. Higher energy = more active. Flee state bypasses this so scared entities can always run. This creates natural rest cycles without explicit sleep state logic.

**Immediate flee override (lines 163–172)**
If a peaceful entity was hit in the last 5 ticks, it jumps straight to flee state before any other logic runs. This runs before the state machine so the reaction feels instant rather than waiting for the next timer cycle.

**Ambient sound timer (lines 174–183)**
Wolves growl, bats flap — creatures emit sounds periodically while alive. The timer is randomized per entity so a cave full of wolves doesn't all growl at the same tick.

**Autopilot freeze-clearing (lines 185–191)**
The autopilot (the bot that plays the game for testing) can get stuck if any entity's `idle_timer` is non-zero. This block force-clears those flags when autopilot is running. It's here because the autopilot and the NPC inspection system share the same freeze mechanism, and they conflict.

**Inspection freeze (lines 196–203)**
When the player targets a friendly NPC to inspect it, the NPC stops moving. This is implemented by returning early from `update_entity_ai` — effectively skipping the whole AI update. It only applies to non-hostile, non-follower entities.

**Farmer carrot guarantee (lines 205–208)**
Farmers always need at least 1 carrot in inventory so they can plant. Rather than building this into the carrot-planting behavior, it's patched here each tick. This is intentional — it's a simple invariant enforcement that avoids complex inventory-management logic.

**Keeper target resolution (lines 210–212)**
"Keepers" are NPCs assigned to guard or follow something (a player, a chest, a zone). This call syncs the keeper's stored target position with the live position of whatever they're keeping — needed because the target entity may have moved.

**Inner state machine call (line 215)**
`update_entity_ai_state` runs here. It may change `entity.ai_state`, `entity.current_target`, and `entity.target_type`. Everything below this line acts on whatever state the machine just set.

**In-structure consistency guard (lines 221–242)**
An entity's `in_structure` flag and `screen_x/screen_y` coordinates can fall out of sync — especially after loads or teleports. This block checks them against the ground truth (is the entity's zone key in `self.structures`?) and corrects both directions. It's here because it needs to run every tick before behavior dispatches.

**Outer state dispatch (lines 244–703)**
A chain of `if/elif` blocks that executes behavior based on `entity.ai_state`:

- **combat** — Entity attacks or moves toward its target. Player attacks use `attack_chance` from entity props. Entity-vs-entity combat uses `find_and_attack_enemy`. Flying entities (bats) disengage 40% of the time after landing a hit, which creates the darting bat behavior.
- **flee** — Entity moves away from its threat at 80% probability per tick. Stays in flee while recently attacked or while a hostile is within 5 cells. Returns to wandering when clear.
- **exit** — Entity moves toward a zone exit. Keepers can't exit (they're anchored), so they just return to wandering.
- **targeting** — Entity has a target and is moving toward it. Handles three target types: `'player'` (move toward player), integer entity ID (move toward another entity, with cross-zone routing), and tuple cell coordinates (move toward a specific cell, with structure-entry logic for houses/mines).
- **wandering** — Entity moves randomly. Keepers of type 1 (guards) hold their anchor position. Keepers of type 2 (patrols) wander within range. All others call `wander_entity`.
- **idle** — Entity stands still and executes its action if a target is adjacent. The idle-action dispatch covers eating food, drinking water, harvesting resources, entering structures, and the "clearing action" (destroying blocking cells). If the target is not adjacent, it returns to targeting.

**Cooldown timers (lines 705–711)**
Spell cooldowns and action animation timers are decremented after behavior runs, not before. This ensures timers don't expire mid-behavior.

**Walk cell effects and passive consume (lines 713–719)**
Only fire when the entity actually moved this tick (`moved_this_update`). Firing these on stationary ticks would cause unintended terrain mutation and overeating.

**Automatic item pickup (lines 721–739)**
Any entity walking over a dropped item picks it up. Gold near the player triggers a trade calculation. This fires for both overworld and structure entities, which is why it's placed here before the in-structure checks lower in the function.

**Opportunistic structure entry (line 742)**
`try_npc_enter_structure` is called every tick for overworld entities. It handles cases where an entity walks adjacent to a cave or house entrance outside of explicit targeting — for example, a wandering wolf approaching a cave and walking in.

**Warrior home zone return (lines 744–780)**
Warriors track which zone they spawned in. Every `WARRIOR_HOME_RETURN_INTERVAL` ticks, if they're not in their home zone, they set a target toward the nearest exit in the direction of home. This creates the behavior of war parties eventually returning to their base zone.

**Follower formation (lines 824–841)**
Skeleton followers and similar companions maintain close distance to the player. If more than 2 cells away, they close the gap immediately. If on a different screen entirely, they teleport. This is handled late in the function so followers still benefit from all the earlier logic (combat, item pickup, etc.).

**Legacy `target_priority` system (lines 936–1123)**
This large block is **disabled** (wrapped in a triple-quoted string that isn't executed). It was the original priority-based AI system before the state machine was built. It's kept for reference during the transition period. It will eventually be deleted.

**Zone transition (lines 1128–1172)**
After all movement, if the entity is standing on an exit cell, it rolls to cross into the adjacent zone. The autopilot always crosses. Wolves cross at 60% (natural explorers). Entities actively targeting something always cross. On a successful cross, the stuck counter resets because the entity is in a new environment.

**Safety position check (lines 1174–1210)**
After all AI logic runs, the entity's position is validated. Out-of-bounds coordinates get clamped. If the entity somehow ended up on a solid cell (edge case from teleports or world-edits), it's moved to the nearest walkable cell. This is a catch-all rather than a guarantee — the movement code should never place an entity on a solid cell, but this catches anything that slips through.

---

## Section 3 — Inner State Machine (lines 1212–1753)

### `update_entity_ai_state` — the probabilistic state machine

This runs before the outer dispatch. It observes the entity's surroundings and decides what state the entity should be in next.

**Why two separate functions?**
The inner machine handles "what does the entity want?" The outer function handles "how does it act on that?" The inner machine runs first so the outer dispatch always acts on fresh state.

**Skip conditions (lines 1220–1222)**
The player entity and dead entities are excluded. Dead entities should have already been removed, but this is a safety guard.

**Lazy attribute initialization (lines 1224–1234)**
Rather than requiring every possible attribute to be set on every entity in every code path, the state machine initializes missing ones on first use. This is important for save-file compatibility: old saves won't have every field, and adding a `hasattr` guard here means loaded entities get reasonable defaults automatically.

**Nocturnal bat behavior (lines 1250–1327)**
Bats are a special case: they sleep during the day and become active at night. Daytime bats seek the nearest enterable structure (cave, house) and go idle inside. Night bats follow normal hostile behavior. This is handled early in the function because it short-circuits all other logic with a `return`.

**Counterattack check (lines 1300–1358)**
If the entity was hit, it stores who hit it in `counterattack_target`. This block checks for that and immediately enters fight-or-flight: roll against flee chance (scaled by level ratio — stronger attackers are scarier), then enter either `flee` or `combat` state. This fires every tick, not just when the timer expires, so responses are immediate.

**Hostile proximity check (lines 1360–1456)**
Every tick, the entity scans all entities in its current zone for threats. It determines "is this other entity an enemy?" based on faction membership, hostile flags, and follower status. If a threat is found within `HOSTILE_DETECTION_RANGE` (8 cells), the entity either enters combat (if adjacent), targeting (if close), or flee (if non-combat entity). This reactive check runs regardless of the timer gate because proximity reactions should always be immediate.

**Timer decrement (lines 1462–1464)**
The `ai_state_timer` counts down 1 per update. It gates the section below, preventing state transitions while the entity is "committed" to its current action for a short window.

**Timer gate (lines 1665–1666)**
If the timer is still positive, the function returns here. Everything below this line is for state transitions only — deciding to switch from wandering to targeting, or from idle to wandering. The reactive checks above still ran; only the deliberate-decision logic is skipped.

**Survival urgency modifier (lines 1668–1676)**
When hunger or thirst is low, the effective aggressiveness score is boosted. Starving entities are more motivated to find targets. At night, peaceful NPCs get a further boost toward seeking shelter.

**`_resolve_current_target` inner function (lines 1678–1704)**
Given a target type string like `'food'`, `'water'`, `'shelter'`, or `'role'`, this function finds the actual concrete target (a cell position, entity ID, etc.) and returns it. It exists as an inner function because it needs access to both `entity` and `screen_key` which are local variables of the outer function. There is no handler for `'hostile'` — hostile targets are resolved later by `find_closest_target_by_type`.

**Idle state transitions (lines 1706–1725)**
When the idle timer expires, the entity rolls against `aggressiveness` to find a new target, `idleness` to stay idle longer, or defaults to wandering.

**Wandering state transitions (lines 1727–1747)**
When the wandering timer expires, same roll structure as idle: find a target (`aggressiveness`), go idle (`idleness`), or keep wandering. On entry to wandering, both `current_target` and `target_type` are cleared so stale targeting state doesn't leak into the next cycle.

**Flee state timer reset (lines 1749–1752)**
Flee state always resets its timer to 2, keeping the entity responsive to the proximity check above. The exit condition (clear of threats) is handled in the outer machine's flee block.

---

## Section 4 — Priority Evaluation (lines 1754–1987)

### `evaluate_entity_priorities`
**Status: legacy, mostly bypassed.**
This was the original scoring system before the state machine. The state machine now sets `target_priority` directly for most paths. This function only runs if nothing else set a priority. It returns a `(priority_string, target)` tuple. Will be removed once the state machine fully replaces it.

### `_try_flying_item_drop`
Flying entities occasionally drop a random inventory item onto the ground below them. This creates "delivery" behavior where birds and bats scatter items around the world passively. The drop is filtered to meaningful items (no junk) and only fires at low probability.

---

## Section 5 — Combat (lines 2024–2325)

### `find_and_attack_enemy`
Called when a hostile entity is adjacent to a valid target. It selects the best adjacent target (prioritizing the player, then nearby hostile entities based on threat level), calculates damage from strength plus weapon and magic bonuses, and applies it. XP is awarded on each successful hit. The function handles the case where the entity is a follower (followers don't attack other followers) and the case where the target is the player (triggers `player_take_damage`).

---

## Section 6 — Keeper System (lines 2341–2430)

### `resolve_keeper_target`
Keepers are NPCs tied to a specific thing: a player, a chest, a zone. This function refreshes `keeper_target_pos` to the live position of whatever the keeper is guarding. It handles three sub-types of keeper targets: entity, cell, and item. It exists because keeper targets can move (players walk around, chests can be picked up), and the position needs to be re-synced every tick.

---

## Section 7 — Quest System (lines 2431–2603)

### `_try_complete_assigned_quest` and `_assign_specific_quest_target`
When an NPC has a quest assignment, these functions manage the lifecycle: assigning a concrete target cell or entity when the quest starts, and checking completion conditions when the NPC reaches its target. Quests give NPCs a directed goal for a period, after which they return to normal wandering behavior.

---

## Section 8 — Target Type Determination (lines 2634–2969)

### `determine_target_type`
This is the scoring engine that decides what an entity should pursue. It scores available target types (food, water, shelter, hostile, quest, role, special) using a priority stack. Each tier checks whether the target type is available in the current zone and assigns a score based on urgency (how hungry, how dangerous, how close to night, etc.). The highest-scoring available target type is returned. Wolves and other purely hostile types always score high on 'hostile' because that's their only target type.

### `_evaluate_quest_tier`, `_evaluate_role_tier`, `_evaluate_special_tier`
Helper scorers for specific target categories. Quest targets only fire for entities with active quests. Role targets fire for entities with a defined `quest_focus` (e.g., a miner looks for MINESHAFT cells). Special targets (like clearing blocking terrain) only apply to humanoid entities.

---

## Section 9 — Behavior Execution (lines 3028–3373)

### `execute_entity_behavior`
Each NPC type has a `behavior_config` dict in `data/entities.py` that lists what actions it can take (mine, chop, harvest, build, etc.). This function reads that config and dispatches to the right action mixin method. It's structured as a config dispatch rather than per-type if/else so adding a new behavior to an NPC type only requires updating its config dict, not this function.

### `_check_adjacent_chest_behavior`
All humanoid NPCs passively check adjacent chests each tick. If standing next to a chest, they may deposit items (lumberjacks deposit wood, miners deposit ore) or loot it (hostile types). This fires probabilistically and requires no explicit targeting — it's "opportunistic" behavior.

---

## Section 10 — Individual NPC Behaviors (lines 3374–3692)

### `farmer_behavior`, `lumberjack_behavior`, `guard_behavior`, `trader_behavior`
These functions encode the specific activities each NPC type performs during its idle action slot. Farmers plant and harvest carrots. Lumberjacks chop trees and deposit wood. Guards patrol and attack hostiles. Traders travel between zones. These are called from `execute_entity_behavior` when the entity reaches its target and enters idle state.

---

## Section 11 — NPC Transformation (lines 3694–3795)

### `check_npc_transformation`
Entities can change type over time — a farmer who gains enough combat XP might become a guard, or a skeleton might age into a stronger variant. This function checks transformation conditions (level thresholds, XP, time) and replaces the entity's type and props in place. The entity ID stays the same; only its type, appearance, and behavior change.

---

## Section 12 — Wizard Behaviors (lines 3796–3924)

### `try_wizard_seek_rune`, `try_wizard_cast_spell`, `try_wizard_explore_cave`, `cast_wizard_spell`
Wizards have a richer behavior chain than other NPCs. They actively seek rune items to power spells, explore caves to find them, and cast spells in combat. `cast_wizard_spell` is the only function in this section that directly modifies other entities — it applies spell effects (damage, freeze, heal) to targets. The wizard spell system is intentionally kept in the AI file rather than in `systems/` because wizard spell behavior is tightly coupled to their targeting and movement decisions.
