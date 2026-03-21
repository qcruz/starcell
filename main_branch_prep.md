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

**Required for main:** Clear this block. Player starts with empty inventory, or a minimal defined starter kit (e.g. one axe, one pickaxe). Decide with @qcruz before implementing.

```python
# REMOVE OR REPLACE THIS BLOCK:
for _item_key in ITEMS:
    self.inventory.add_item(_item_key, 1)
```

**Decision needed:** What items (if any) should the player start with?

---

## 2. Starting Follower

**Location:** `game_core.py:2869`

**Current dev behavior:** A random follower type (SHEEP, DEER, WOLF, BAT, GOBLIN, SKELETON, TERMITE) is selected on new_game and spawned after time passage.

**Required for main:** Confirm whether a starting follower is intended for main release. If yes, confirm which type. If no, remove the `_pending_follower_type` and `_time_pass_spawned` block.

**Decision needed:** Starting follower — yes/no? If yes, which type?

---

## 3. Autopilot Toggle (Shift+A)

**Location:** `game_core.py:1250–1255`, `ui/menus.py:36`, `ui/menus.py:118`

**Current dev behavior:** Shift+A toggles the autopilot. This key binding is listed in both the in-game controls help screens.

**Required for main:** Remove the autopilot toggle binding from the input handler and from the controls display text. The autopilot system itself (`autopilot.py`) can remain in the codebase but must not be player-accessible.

**Files to update:**
- `game_core.py` — remove `elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_SHIFT): self.toggle_autopilot()`
- `ui/menus.py` — remove `"Shift+A - Toggle autopilot"` from both controls screens

---

## 4. Dev Screen (Shift+I)

**Location:** `game_core.py:1184–1186`, `game_core.py:206`, `game_core.py:3021`, `ui/dev_screen.py`

**Current dev behavior:** Shift+I opens the dev info overlay showing internal state, entity counts, tick info, etc.

**Required for main:** Disable or remove the dev screen toggle. Simplest approach: remove the `elif event.key == pygame.K_i and Shift:` branch so Shift+I only opens the inventory (current else branch). The `draw_dev_screen()` call and `show_dev_screen` flag can remain but should always be False.

**Alternative:** Leave in as a hidden debug tool — low risk, low reward. Confirm with @qcruz.

---

## 5. Spell Energy Cost

**Location:** `systems/enchantment.py:64–69`

**Current dev behavior:** Star spell costs 3 energy per cast. This may be intentionally low for testing.

**Required for main:** Review and set final energy cost. CLAUDE.md mentions spell cost as a variable that differs between dev and main.

**Decision needed:** What is the intended spell energy cost for main?

---

## 6. Follower Energy Cost (Max Energy Reduction)

**Location:** `systems/enchantment.py:93`

**Current dev behavior:** Each follower added permanently reduces player max_energy by 1 (`max_energy - 1`). This may be intentionally low for testing.

**Required for main:** Confirm whether this is the final cost, or whether it should be higher (e.g. reduce by 5–10 per follower). CLAUDE.md notes follower costs differ between dev and main.

**Decision needed:** Final max_energy reduction per follower?

---

## 7. Biome Spread Rate

**Location:** `constants.py:125`

**Current dev value:** `BIOME_SPREAD_RATE = 0.004` — noted in comments as "4x increase"

**Required for main:** Confirm whether this elevated rate is intentional for release or was bumped for testing. If testing only, revert to 0.001.

**Decision needed:** Keep 0.004 or revert?

---

## 8. Biome Occurrence Rates

**Location:** `constants.py:214–217`

**Current dev values:**
```python
FOREST_BIOME_CHANCE = 0.60
PLAINS_BIOME_CHANCE = 0.20
MOUNTAINS_BIOME_CHANCE = 0.15
DESERT_BIOME_CHANCE = 0.05
```

**Required for main:** Confirm these are tuned for the intended player experience, not test convenience.

**Decision needed:** Adjust any of these for main?

---

## 9. E-Button Pickup

**Location:** `game_core.py:1226–1228`

**Current dev behavior:** E key calls `pickup_cell_or_items()` which allows picking up any cell directly into inventory (creative/admin mode) plus dropped items.

**CLAUDE.md note:** Branch table mentions "no E-button pickup" as a main branch custom constant.

**Required for main:** Clarify the intended behavior. Options:
- (a) Remove E key entirely — player never picks up raw cells; only dropped item piles via Space/interact
- (b) E key only picks up dropped item piles, not raw cells
- (c) Keep current behavior

**Decision needed:** Which option?

---

## 10. Controls Help Text

**Location:** `ui/menus.py:34–38`, `ui/menus.py:116–120`

**Required for main:** After resolving items 3 and 9 above, update the controls text in both help screens to reflect final key bindings. Remove any dev-only bindings.

---

## 11. Dev Doc Files — Remove from Main

These files exist in dev branches for planning, tracking, and debugging. They should not appear in the main branch.

**Files to exclude from main (do not commit to main or delete from worktree before merge):**

| File | Reason |
|---|---|
| `next_up.md` | Dev work queue |
| `roadmap.md` | Internal planning doc |
| `current_features.md` | Dev implementation notes |
| `debug/bug_report.md` | Dev session logs |
| `debug/held_back.md` | Dev backlog |
| `debug/auto_debug.cfg` | Already git-ignored; confirm it stays out |
| `debug/auto_debug_save.json` | Already git-ignored |
| `debug/auto_debug_state.json` | Already git-ignored |
| `debug/session_stdout.log` | Already git-ignored |
| `autopilot_npc_recon.md` | Dev recon doc |
| `code_cleanup_plan.md` | Dev planning doc |
| `DEVELOPMENT_STRATEGY.md` | Dev strategy doc |
| `monolith_extraction_recon.md` | Dev recon doc |
| `biome_template.md` | Dev design template |
| `npc_society_design.md` | Dev design doc |
| `economy_balance.md` | Dev design doc |
| `player_arc.md` | Dev design doc |
| `design_identity.md` | Dev design doc (review — may be worth keeping for contributors) |
| `sound_design.md` | Dev design doc |
| `art_direction.md` | Dev design doc |
| `BOUNTIES.md` | Dev design doc |
| `starcellv1-1-*.py` | Legacy monolith versions — remove from main |
| `spritechange.py`, `spritepro.py` | Dev utility scripts |
| `next_up 2.md` | Duplicate/stale |

**Files to KEEP in main:**

| File | Reason |
|---|---|
| `README.md` | Player-facing documentation |
| `CHANGELOG.md` | Release notes — keep and update |
| `CLAUDE.md` | Keep but review for main-appropriate instructions |
| `contributing.md` | Contributor guidelines |
| `commercial_use.md`, `Legal Disclosures.md` | Legal — keep |

---

## 12. Debug System Accessibility

**Location:** `debug/` directory, `debug/bug_catcher.py`, `debug/watchdog.py`, `debug/fixes.py`

**Current dev behavior:** Bug catcher, watchdog, and fixes are active at runtime. They log to `debug/bug_catcher.log` and run integrity checks every 300 ticks.

**Required for main:** The debug modules should stay in the codebase (they're harmless), but confirm:
- `debug/bug_catcher.log` is in `.gitignore` (it is — ephemeral)
- No debug output leaks to console during normal gameplay (`print()` statements in debug path)
- The Watchdog overhead is acceptable for release (currently ~every 300 ticks — likely fine)

---

## 13. Print Statements in Game Code

**Required for main:** Run a grep pass to remove or silence all `print()` statements outside of `autopilot.py` and `debug/` before merging to main. These show up in terminal but not in-game, so they're low urgency — but they're messy for release.

```bash
grep -rn "print(" --include="*.py" --exclude-dir=debug . | grep -v autopilot.py
```

Review each result: keep intentional game messages (if any use a proper log channel), remove raw debug prints.

---

## 14. `.gitignore` Check

Confirm these are git-ignored before merging to main:
- `debug/auto_debug.cfg`
- `debug/auto_debug_save*.json`
- `debug/auto_debug_state*.json`
- `debug/session_stdout.log`
- `debug/bugcatcher.log` / `debug/bug_catcher.log`
- `__pycache__/` and `*.pyc`
- Any `.DS_Store` files

---

## 15. Final Smoke Test

Before pushing to main:
1. Start a fresh new game — confirm inventory is correct, no dev items
2. Play 5 minutes manually — confirm all core systems work (movement, combat, crafting, spells, followers, zone travel)
3. Confirm no autopilot toggle appears in controls screen
4. Confirm Shift+I dev screen is disabled (or hidden)
5. Confirm no crash on death and respawn

---

## Merge Command (only after full checklist signed off)

```bash
git checkout main
git merge dev --no-ff -m "Release: merge dev → main (YYYY-MM-DD)"
# Remove dev-only files listed in section 11
git push origin main
```

**Do not run this until @qcruz gives explicit approval.**
