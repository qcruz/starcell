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
