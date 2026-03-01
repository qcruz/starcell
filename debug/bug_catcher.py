"""
BugCatcher — structured game debug logging system.

Each BugCatcher instance tracks one category of activity (e.g. bat animation,
cell mutations) and writes structured log lines to a single file that is
cleared at game start (new game or continue/load).

Usage
-----
    bug_catcher = BugCatcher(log_path='debug/bugcatcher.log')
    bug_catcher.clear()                         # call on every game start

    # Each AI update tick (bat entities in player zone):
    bug_catcher.log_bat_state(tick, entity_id, entity, player_zone)

    # Each cell update tick (for the player's current zone):
    bug_catcher.log_zone_cells(tick, screen_key, grid)
"""

import os
import datetime

_DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), 'bugcatcher.log')

# Stop writing once the log exceeds this size (bytes) to keep it reviewable
_MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB


class BugCatcher:
    """Debug logger for targeted bug investigation.

    Currently tracks:
        • Bat animation state, position history, and AI state transitions
          for every BAT entity in the player's current zone.
        • HOUSE / STONE_HOUSE cell presence and mutations in the player's
          current zone (to catch phantom decay).

    Extend with additional log_* methods for future categories.
    """

    def __init__(self, log_path: str = _DEFAULT_LOG_PATH):
        self.log_path = log_path
        self._suppressed = False  # True once file exceeds _MAX_LOG_BYTES
        # Per-entity state for detecting transitions
        self._prev_bat_state: dict = {}   # entity_id -> {'ai_state', 'facing', 'anim_frame'}
        # Previous cell snapshot for detecting mutations
        self._prev_zone_cells: dict = {}  # screen_key -> {(x,y): cell_type}
        # Create the log file immediately so it exists from game start
        self.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self):
        """Wipe the log file. Call at the start of every game run."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, 'w') as f:
            ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"=== BugCatcher log cleared at {ts} ===\n\n")
        self._suppressed = False
        self._prev_bat_state.clear()
        self._prev_zone_cells.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_size(self) -> bool:
        """Return True (ok to write) unless log has grown too large."""
        if self._suppressed:
            return False
        try:
            if os.path.getsize(self.log_path) >= _MAX_LOG_BYTES:
                self._suppressed = True
                with open(self.log_path, 'a') as f:
                    f.write(
                        f"\n=== LOG SUPPRESSED: file reached {_MAX_LOG_BYTES // 1024} KB "
                        f"— quit and review ===\n"
                    )
                return False
        except OSError:
            pass
        return True

    def _write(self, line: str):
        if not self._check_size():
            return
        with open(self.log_path, 'a') as f:
            f.write(line + '\n')

    # ------------------------------------------------------------------
    # Entity animation / AI state logger (bats, wolves, any suspect type)
    # ------------------------------------------------------------------

    def log_bat_state(self, tick: int, entity_id, entity, player_zone: str):
        """Log entity AI state every update for tracked entities in the player's zone.

        Logs a full state line every update and highlights transitions
        with a *** TRANSITION marker.

        Currently tracks: BAT, BAT_double, WOLF, WOLF_double.
        """
        entity_zone = f"{entity.screen_x},{entity.screen_y}"
        if entity_zone != player_zone:
            return

        ai_state   = getattr(entity, 'ai_state', '?')
        ai_timer   = getattr(entity, 'ai_state_timer', '?')
        facing     = getattr(entity, 'facing', '?')
        anim_frame = getattr(entity, 'anim_frame', '?')
        anim_timer = getattr(entity, 'anim_timer', '?')
        in_combat  = getattr(entity, 'in_combat', False)
        target     = getattr(entity, 'current_target', None)
        cooldown   = getattr(entity, 'move_cooldown', '?')
        is_moving  = getattr(entity, 'is_moving', False)

        # Detect state transitions
        prev = self._prev_bat_state.get(entity_id, {})
        transitions = []
        if prev.get('ai_state') != ai_state:
            transitions.append(f"AI_STATE {prev.get('ai_state','?')} -> {ai_state}")
        if prev.get('facing') != facing:
            transitions.append(f"FACING {prev.get('facing','?')} -> {facing}")
        if prev.get('anim_frame') != anim_frame:
            transitions.append(f"ANIM {prev.get('anim_frame','?')} -> {anim_frame}")

        self._prev_bat_state[entity_id] = {
            'ai_state': ai_state,
            'facing': facing,
            'anim_frame': anim_frame,
        }

        header = (
            f"[tick={tick:07d}] {entity.type} id={entity_id} "
            f"grid=({entity.x},{entity.y}) "
            f"world=({entity.world_x:.2f},{entity.world_y:.2f}) "
            f"zone={entity.screen_x},{entity.screen_y}"
        )
        self._write(
            f"{header} | "
            f"state={ai_state}(timer={ai_timer}) "
            f"target={target} in_combat={in_combat} cooldown={cooldown} "
            f"facing={facing} anim_frame={anim_frame}(t={anim_timer}) "
            f"moving={is_moving}"
        )
        for t in transitions:
            self._write(f"  *** TRANSITION {t}  [tick={tick}]")

    # ------------------------------------------------------------------
    # Zone cell state logger (HOUSE / STONE_HOUSE tracking)
    # ------------------------------------------------------------------

    def log_zone_cells(self, tick: int, screen_key: str, grid: list):
        """Snapshot HOUSE and STONE_HOUSE positions in the zone each update.

        Only writes a log line when a cell's type has CHANGED from the
        previous snapshot, so the log stays compact.  Logs the full
        current HOUSE/STONE_HOUSE layout on the very first call for
        each zone (baseline snapshot).
        """
        tracked = {'HOUSE', 'STONE_HOUSE'}

        # Build current snapshot of all tracked cells
        current: dict = {}
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell in tracked:
                    current[(x, y)] = cell

        prev = self._prev_zone_cells.get(screen_key)

        if prev is None:
            # First call for this zone — emit baseline
            if current:
                positions = ', '.join(
                    f"{cell}@({x},{y})" for (x, y), cell in sorted(current.items())
                )
                self._write(
                    f"[tick={tick:07d}] ZONE_CELLS baseline zone={screen_key}: {positions}"
                )
            else:
                self._write(
                    f"[tick={tick:07d}] ZONE_CELLS baseline zone={screen_key}: (no HOUSE/STONE_HOUSE)"
                )
            self._prev_zone_cells[screen_key] = current
            return

        # Detect mutations (additions, removals, type changes)
        all_pos = set(prev) | set(current)
        mutations = []
        for pos in sorted(all_pos):
            old = prev.get(pos)
            new = current.get(pos)
            if old != new:
                mutations.append(f"({pos[0]},{pos[1]}): {old} -> {new}")

        if mutations:
            self._write(
                f"[tick={tick:07d}] ZONE_CELLS MUTATION zone={screen_key}: "
                + ", ".join(mutations)
            )

        self._prev_zone_cells[screen_key] = current

    # ------------------------------------------------------------------
    # Utility: freeform message
    # ------------------------------------------------------------------

    def log(self, category: str, message: str, tick: int = 0):
        """Generic log line for one-off notes from any system."""
        self._write(f"[tick={tick:07d}] [{category}] {message}")
