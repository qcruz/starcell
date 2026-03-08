"""
BugCatcher — structured game debug logging system (JSON-lines format).

Each log entry is one JSON object per line, flushed from an in-memory buffer
to disk every time flush() is called (typically every 300 ticks / ~5 s).
The log file is cleared at game start (new game or continue/load).

Rolling trim: when the file exceeds _MAX_LOG_BYTES, the oldest 25% of lines
are dropped and logging continues uninterrupted.

Usage
-----
    bug_catcher = BugCatcher()
    bug_catcher.clear()                           # called on every game start

    # Per-frame in the render loop:
    bug_catcher.log_bat_state(tick, entity_id, entity, player_zone)

    # Per-cell-update cycle (current zone):
    bug_catcher.log_zone_cells(tick, screen_key, grid)

    # Generic structured entry from any system:
    bug_catcher.log({'tick': tick, 'category': 'my_system', ...})

    # Periodically (every ~300 ticks):
    bug_catcher.flush()
"""

import os
import json
import datetime

_DEFAULT_LOG_PATH = os.path.join(os.path.dirname(__file__), 'bugcatcher.log')
_MAX_LOG_BYTES = 2 * 1024 * 1024  # 2 MB


class BugCatcher:
    """Structured JSON-lines debug logger with in-memory buffering."""

    def __init__(self, log_path: str = _DEFAULT_LOG_PATH):
        self.log_path = log_path
        self._buffer: list = []
        # Per-entity state for detecting transitions
        self._prev_bat_state: dict = {}   # entity_id -> {'ai_state', 'facing', 'anim_frame'}
        # Previous cell snapshot for detecting mutations
        self._prev_zone_cells: dict = {}  # screen_key -> {(x,y): cell_type}
        self.clear()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def clear(self):
        """Wipe the log file and in-memory buffer. Call at every game start."""
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        ts = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_path, 'w') as f:
            f.write(json.dumps({'event': 'log_cleared', 'ts': ts}) + '\n')
        self._buffer.clear()
        self._prev_bat_state.clear()
        self._prev_zone_cells.clear()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _trim_file(self):
        """Drop the oldest 25% of lines when the file exceeds _MAX_LOG_BYTES."""
        try:
            if os.path.getsize(self.log_path) < _MAX_LOG_BYTES:
                return
            with open(self.log_path, 'r') as f:
                lines = f.readlines()
            keep_from = len(lines) // 4
            with open(self.log_path, 'w') as f:
                f.write(json.dumps({'event': 'log_trimmed',
                                    'dropped_lines': keep_from}) + '\n')
                f.writelines(lines[keep_from:])
        except OSError:
            pass

    def _record(self, entry: dict):
        """Add an entry to the in-memory buffer."""
        self._buffer.append(entry)

    # ------------------------------------------------------------------
    # Flush (call periodically from game loop)
    # ------------------------------------------------------------------

    def flush(self):
        """Write buffered entries to disk and clear the buffer."""
        if not self._buffer:
            return
        self._trim_file()
        try:
            with open(self.log_path, 'a') as f:
                for entry in self._buffer:
                    f.write(json.dumps(entry) + '\n')
        except OSError:
            pass
        self._buffer.clear()

    # ------------------------------------------------------------------
    # Entity animation / AI state logger (bats, wolves, any suspect type)
    # ------------------------------------------------------------------

    def log_bat_state(self, tick: int, entity_id, entity, player_zone: str):
        """Log entity AI/animation state every frame for entities in the player's zone.

        Records transitions with a 'transitions' list on the entry.
        Tracked types: BAT, BAT_double, WOLF, WOLF_double.
        """
        entity_zone = f"{entity.screen_x},{entity.screen_y}"
        if entity_zone != player_zone:
            return

        ai_state      = getattr(entity, 'ai_state', None)
        ai_timer      = getattr(entity, 'ai_state_timer', None)
        facing        = getattr(entity, 'facing', None)
        anim_frame    = getattr(entity, 'anim_frame', None)
        anim_timer    = getattr(entity, 'anim_timer', None)
        in_combat     = getattr(entity, 'in_combat', False)
        target        = getattr(entity, 'current_target', None)
        cooldown      = getattr(entity, 'move_cooldown', None)
        is_moving     = getattr(entity, 'is_moving', False)
        in_subscreen  = getattr(entity, 'in_subscreen', False)
        subscreen_key = getattr(entity, 'subscreen_key', None)

        prev = self._prev_bat_state.get(entity_id, {})
        transitions = []
        if prev.get('ai_state') != ai_state:
            transitions.append(f"AI_STATE {prev.get('ai_state')} -> {ai_state}")
        if prev.get('facing') != facing:
            transitions.append(f"FACING {prev.get('facing')} -> {facing}")
        if prev.get('anim_frame') != anim_frame:
            transitions.append(f"ANIM {prev.get('anim_frame')} -> {anim_frame}")
        if prev.get('in_subscreen') != in_subscreen:
            transitions.append(f"SUBSCREEN {prev.get('in_subscreen')} -> {in_subscreen}")

        self._prev_bat_state[entity_id] = {
            'ai_state': ai_state,
            'facing': facing,
            'anim_frame': anim_frame,
            'in_subscreen': in_subscreen,
        }

        # Only log on actual state transitions — steady-state is noise
        if not transitions:
            return

        self._record({
            'tick': tick,
            'category': 'entity',
            'type': entity.type,
            'id': entity_id,
            'zone': entity_zone,
            'grid': [entity.x, entity.y],
            'world': [round(entity.world_x, 2), round(entity.world_y, 2)],
            'ai_state': ai_state,
            'ai_timer': ai_timer,
            'in_combat': in_combat,
            'target': target,
            'cooldown': cooldown,
            'facing': facing,
            'anim_frame': anim_frame,
            'anim_timer': anim_timer,
            'moving': is_moving,
            'in_subscreen': in_subscreen,
            'subscreen_key': subscreen_key,
            'transitions': transitions,
        })

    # ------------------------------------------------------------------
    # Zone cell state logger (HOUSE / STONE_HOUSE tracking)
    # ------------------------------------------------------------------

    def log_zone_cells(self, tick: int, screen_key: str, grid: list):
        """Snapshot HOUSE and STONE_HOUSE positions each update.

        Emits a 'baseline' entry on the first call for a zone, then
        'mutation' entries only when a cell type changes.
        """
        tracked = {'HOUSE', 'STONE_HOUSE'}

        current: dict = {}
        for y, row in enumerate(grid):
            for x, cell in enumerate(row):
                if cell in tracked:
                    current[(x, y)] = cell

        prev = self._prev_zone_cells.get(screen_key)

        if prev is None:
            self._record({
                'tick': tick,
                'category': 'zone_cells',
                'zone': screen_key,
                'event': 'baseline',
                'cells': {f"{x},{y}": cell
                          for (x, y), cell in sorted(current.items())},
            })
            self._prev_zone_cells[screen_key] = current
            return

        all_pos = set(prev) | set(current)
        changes = {}
        for pos in sorted(all_pos):
            old = prev.get(pos)
            new = current.get(pos)
            if old != new:
                changes[f"{pos[0]},{pos[1]}"] = {'from': old, 'to': new}

        if changes:
            self._record({
                'tick': tick,
                'category': 'zone_cells',
                'zone': screen_key,
                'event': 'mutation',
                'changes': changes,
            })

        self._prev_zone_cells[screen_key] = current

    # ------------------------------------------------------------------
    # Generic structured log entry
    # ------------------------------------------------------------------

    def log(self, entry: dict):
        """Record any structured dict entry from any system."""
        self._record(entry)
