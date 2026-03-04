"""
debug/fixes.py — Library of reusable game-state correction functions.

Each function detects an anomaly, logs it via bug_catcher if one is provided,
and returns a FixResult:

    FixResult(detected, fixed, description)
        detected  — True if the anomaly was present
        fixed     — True if a correction was applied
        description — human-readable summary

Strategy
--------
Fixes default to detect-only (apply=False), honouring the log-and-detect
approach.  Once a root cause is confirmed patched at the source, set
apply=True to enable the safety-net correction that prevents recurrence.

Adding new fixes
----------------
1. Document the bug class and its root cause in the function docstring.
2. Write a pure detector that works from game state alone.
3. Register the fix in FIX_REGISTRY at the bottom of this file.
"""

from typing import NamedTuple


class FixResult(NamedTuple):
    detected: bool
    fixed: bool
    description: str


# ── Fix #1 ──────────────────────────────────────────────────────────────────
# Bug class:   Entity flag / tracking-list mismatch (state sync)
#
# Symptom:     Flying entity (bat, etc.) visible in overworld with animation
#              permanently frozen on the 'still' frame.
#
# Root cause:  npc_enter_subscreen() (ai/movement.py) sets entity.in_subscreen=True
#              and removes the entity_id from screen_entities[zone_key].  If
#              entity.screen_x/y mismatches the key used for the remove call at
#              that moment, the entity stays in screen_entities.  The render loop
#              (ui/hud.py) then draws it with in_subscreen=True, which causes
#              is_flying_idle to evaluate False → animation freezes at 'still'.
#
# Detection:   entity.in_subscreen=True AND entity_id in screen_entities[zone_key]
#
# Root-cause patch (applied separately):
#   ui/hud.py render loop — skip drawing entities where player is in overworld
#   but entity.in_subscreen=True (still run smooth-movement + animation).
#
# Safety-net (apply=True):
#   Clear entity.in_subscreen=False so animation resumes immediately.
#   The entity remains in screen_entities where it was already rendering.


def fix_entity_subscreen_flag(entity_id, entity, game, bug_catcher=None,
                               tick: int = 0, apply: bool = False) -> FixResult:
    """Detect (and optionally correct) entity with in_subscreen=True stuck in
    screen_entities.

    Parameters
    ----------
    entity_id : int
    entity    : Entity
    game      : game object with screen_entities dict
    bug_catcher : BugCatcher | None — log anomaly if provided
    tick      : current game tick (for log entry)
    apply     : if True, clear in_subscreen=False as a safety net

    Returns
    -------
    FixResult
    """
    if not getattr(entity, 'in_subscreen', False):
        return FixResult(False, False, 'no anomaly')

    zone_key = f"{entity.screen_x},{entity.screen_y}"
    screen_entities = getattr(game, 'screen_entities', {})
    in_screen = (zone_key in screen_entities
                 and entity_id in screen_entities[zone_key])

    if not in_screen:
        return FixResult(False, False, 'no anomaly')

    desc = (
        f"entity {entity_id} ({entity.type}) has in_subscreen=True "
        f"but is still in screen_entities[{zone_key}]"
        + (f" — in_subscreen cleared" if apply else " — detected only")
    )

    if bug_catcher is not None:
        bug_catcher.log({
            'tick': tick,
            'category': 'fix_entity_subscreen_flag',
            'entity_id': entity_id,
            'entity_type': entity.type,
            'zone': zone_key,
            'subscreen_key': getattr(entity, 'subscreen_key', None),
            'applied': apply,
            'description': desc,
        })

    if apply:
        # Remove from subscreen_entities before clearing the key
        old_sub_key = getattr(entity, 'subscreen_key', None)
        if old_sub_key is not None:
            sub_list = getattr(game, 'subscreen_entities', {}).get(old_sub_key, [])
            if entity_id in sub_list:
                sub_list.remove(entity_id)
        entity.in_subscreen = False
        entity.subscreen_key = None
        return FixResult(True, True, desc)

    return FixResult(True, False, desc)


# ── Fix Registry ─────────────────────────────────────────────────────────────
# Maps a short name to each fix function for use by the Watchdog or manual
# calls.  Import and call via:
#
#   from debug.fixes import FIX_REGISTRY
#   result = FIX_REGISTRY['entity_subscreen_flag'](entity_id, entity, game,
#                                                   bug_catcher, tick)

FIX_REGISTRY = {
    'entity_subscreen_flag': fix_entity_subscreen_flag,
}
