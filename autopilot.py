"""
StarCell Autopilot System — NPC Possession Model
-------------------------------------------------
When the player goes idle, autopilot spawns a "proxy NPC" at the player's
position.  The proxy is a real Entity of the appropriate role type (FARMER,
WARRIOR, MINER, etc.) and is driven by the existing NPC AI with zero extra
movement code.  The wizard sprites are used instead of the NPC sprites so the
player character looks the same on screen.

Inventory changes made by the proxy (harvested items, consumed tools) are
mirrored to the real player inventory.  When the player resumes control, the
proxy is despawned and the player's grid position is snapped to the proxy's
last position.

Quest target steering: every QUEST_NUDGE_INTERVAL ticks, the proxy's
current_target and ai_state are nudged toward the quest target cell/entity so
the character spends time working toward goals rather than wandering aimlessly.
"""

import random
from constants import *
from entity import Entity


# ── Tuning constants ──────────────────────────────────────────────────────────

# How many ticks of player inactivity before autopilot engages (3 seconds)
AUTOPILOT_IDLE_TICKS = 180

# 15-second grace period on game start / load before autopilot can engage
AUTOPILOT_GRACE_TICKS = 900

# How often (ticks) to steer the proxy toward the quest target
QUEST_NUDGE_INTERVAL = 120   # every 2 seconds

# How often (ticks) to sync proxy inventory → player inventory
INVENTORY_SYNC_INTERVAL = 60  # every 1 second

# Quest type → NPC role mapping
QUEST_NPC_TYPE = {
    'FARM':           'FARMER',
    'GATHER':         'LUMBERJACK',
    'LUMBER':         'LUMBERJACK',
    'MINE':           'MINER',
    'HUNT':           'WARRIOR',
    'SLAY':           'WARRIOR',
    'EXPLORE':        'TRADER',
    'SEARCH':         'WIZARD',
    'RESCUE':         'WIZARD',
    'COMBAT_HOSTILE': 'WARRIOR',
    'COMBAT_ALL':     'WARRIOR',
}
DEFAULT_NPC_TYPE = 'FARMER'


class AutopilotMixin:
    """Mixin class for player autopilot behavior. Mixed into Game via multiple inheritance."""

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def init_autopilot(self):
        """Initialise autopilot state.  Call from __init__ and after new_game/load_game."""
        self.autopilot = False
        self.autopilot_proxy_id = None          # entity_id of the proxy NPC, or None
        self._autopilot_nudge_timer = 0
        self._autopilot_sync_timer = 0
        # Grace period: autopilot cannot engage until this tick
        start_tick = getattr(self, 'tick', 0)
        self.last_input_tick = start_tick + AUTOPILOT_GRACE_TICKS

    def is_autopilot_idle(self):
        """True when the player has been idle long enough to trigger autopilot."""
        return self.tick - self.last_input_tick > AUTOPILOT_IDLE_TICKS

    def mark_input(self):
        """Called on any player input — disables autopilot and restores player control."""
        self.last_input_tick = self.tick
        if self.autopilot:
            self._autopilot_disengage()

    # ── Main update (called every tick from move_player) ──────────────────────

    def update_autopilot(self):
        """Top-level autopilot tick.  Spawns proxy on first call, then maintains it."""
        if not self.autopilot or self.state != 'playing':
            return

        # Spawn proxy if not yet created
        if self.autopilot_proxy_id is None:
            self._autopilot_engage()
            if self.autopilot_proxy_id is None:
                return  # Spawn failed

        proxy = self.entities.get(self.autopilot_proxy_id)
        if proxy is None:
            # Proxy was externally removed — disengage
            self._autopilot_disengage()
            return

        # Keep proxy position in sync so the player's logical position tracks it
        self._sync_player_from_proxy(proxy)

        # Diagnostic: print positions every tick to track teleport glitches
        pz = f"{self.player['screen_x']},{self.player['screen_y']}"
        pp = f"({self.player['x']},{self.player['y']})"
        prz = f"{proxy.screen_x},{proxy.screen_y}"
        prp = f"({proxy.x},{proxy.y})"
        state = proxy.ai_state
        tgt = proxy.current_target
        cs_key = None
        if self.current_screen:
            for k, v in self.screens.items():
                if v is self.current_screen:
                    cs_key = k
                    break
        print(f"[AP] t={self.tick} "
              f"pZ={pz} pP={pp} "
              f"xZ={prz} xP={prp} "
              f"st={state} tgt={tgt} "
              f"cs={cs_key}")

        # Periodically sync proxy inventory → player inventory
        self._autopilot_sync_timer += 1
        if self._autopilot_sync_timer >= INVENTORY_SYNC_INTERVAL:
            self._autopilot_sync_timer = 0
            self._sync_inventory_to_player(proxy)

        # ── Quest completion check: 30% chance to switch quest type ────────
        if self.active_quest and self.active_quest in self.quests:
            quest = self.quests[self.active_quest]
            if quest.status == 'completed' or quest.status == 'cooldown':
                if random.random() < 0.30:
                    self._autopilot_switch_quest()

        # Periodically nudge proxy toward quest target
        self._autopilot_nudge_timer += 1
        if self._autopilot_nudge_timer >= QUEST_NUDGE_INTERVAL:
            self._autopilot_nudge_timer = 0
            self._autopilot_nudge_quest_target(proxy)

            # Small chance (2%) per nudge to abandon current quest if stuck
            # This prevents the autopilot from endlessly chasing an
            # unreachable target (e.g. entity that crossed zones, cell that
            # was consumed by another NPC, etc.)
            if random.random() < 0.02:
                self._autopilot_switch_quest()

    # ── Engage / disengage ────────────────────────────────────────────────────

    def _autopilot_engage(self):
        """Spawn the proxy NPC at the player's current position."""
        px = self.player['x']
        py = self.player['y']
        psx = self.player['screen_x']
        psy = self.player['screen_y']
        screen_key = f"{psx},{psy}"

        # Choose NPC type from active quest
        npc_type = QUEST_NPC_TYPE.get(self.active_quest, DEFAULT_NPC_TYPE)

        # Create the entity
        proxy = Entity(npc_type, px, py, psx, psy, level=self.player.get('level', 1))

        # ── Props: deep-enough copy so originals are never mutated ────────
        proxy.props = dict(proxy.props)
        proxy.props['sprite_name'] = 'wizard'
        proxy.props['hostile'] = False       # never a valid attack target
        proxy.props['drops'] = []            # dropping nothing on death/despawn
        proxy.props['edible'] = False        # wolves won't flag it as food
        proxy.props['is_autopilot_proxy'] = True  # invisible to inspection/idle/tree-clearing
        # Neutralise attack AI but allow fleeing from threats
        proxy.props['ai_params'] = dict(proxy.props.get('ai_params', {}))
        proxy.props['ai_params']['aggressiveness'] = 0.0
        proxy.props['ai_params']['combat_chance']  = 0.0
        proxy.props['ai_params']['flee_chance']    = 0.95  # Almost always flee from hostiles

        # ── Invulnerability — proxy cannot die ────────────────────────────
        # Set stats to effectively infinite so decay_stats / combat never kill it
        BIG = 999999
        proxy.max_health = BIG;  proxy.health  = BIG
        proxy.max_hunger = BIG;  proxy.hunger  = BIG
        proxy.max_thirst = BIG;  proxy.thirst  = BIG
        proxy.strength   = self.player.get('base_damage', 10)

        # Copy player-facing direction
        proxy.facing = self.player.get('facing', 'down')

        # ── Seed proxy inventory from player ──────────────────────────────
        proxy.inventory = {}
        for cat in ('items', 'tools'):
            src = getattr(self.inventory, cat, {})
            for item_name, count in src.items():
                proxy.inventory[item_name] = proxy.inventory.get(item_name, 0) + count

        # ── Register entity ───────────────────────────────────────────────
        entity_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[entity_id] = proxy

        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(entity_id)

        self.autopilot_proxy_id = entity_id
        self.autopilot = True

        # Initial quest nudge
        self._autopilot_nudge_quest_target(proxy)

        print(f"[Autopilot] Proxy {npc_type} spawned (id={entity_id}) at ({px},{py})")

    def _autopilot_disengage(self):
        """Despawn proxy NPC and restore player position from its last location."""
        proxy_id = self.autopilot_proxy_id
        proxy = self.entities.get(proxy_id)
        if proxy is not None:
            # Sync proxy inventory back to player one last time
            self._sync_inventory_to_player(proxy)

            # Snap player grid position to wherever the proxy ended up,
            # including zone if the proxy crossed a boundary during autopilot.
            self.player['x'] = proxy.x
            self.player['y'] = proxy.y
            self.player['screen_x'] = proxy.screen_x
            self.player['screen_y'] = proxy.screen_y
            # Also snap world coords to avoid a lerp jump on resume
            self.player['world_x'] = float(proxy.x)
            self.player['world_y'] = float(proxy.y)
            self.player['facing'] = proxy.facing
            # Sync current_screen so move_player uses the correct zone grid
            new_sk = f"{proxy.screen_x},{proxy.screen_y}"
            if new_sk in self.screens:
                self.current_screen = self.screens[new_sk]
            else:
                self.current_screen = self.generate_screen(proxy.screen_x, proxy.screen_y)

            # Clear stale combat references on every entity that was targeting
            # the proxy — otherwise they become "invisible attackers" after despawn.
            # Also clear any lingering idle_timer that check_npc_inspection may
            # have set during autopilot — otherwise NPCs stay frozen after resume.
            for eid, e in self.entities.items():
                if eid == proxy_id:
                    continue
                if getattr(e, 'current_target', None) == proxy_id:
                    e.current_target = None
                    e.ai_state = 'wandering'
                    e.in_combat = False
                if getattr(e, 'combat_target', None) == proxy_id:
                    e.combat_target = None
                    e.in_combat = False
                if getattr(e, 'counterattack_target', None) == proxy_id:
                    e.counterattack_target = None
                    e.wants_counterattack = False
                # Unfreeze any NPC that was paused by inspection during autopilot
                if getattr(e, 'idle_timer', 0) > 0:
                    e.idle_timer = 0
                    e.is_idle = False

            # Remove from entity registries
            sk = f"{proxy.screen_x},{proxy.screen_y}"
            if sk in self.screen_entities and proxy_id in self.screen_entities[sk]:
                self.screen_entities[sk].remove(proxy_id)
            if proxy_id in self.entities:
                del self.entities[proxy_id]

        self.autopilot = False
        self.autopilot_proxy_id = None
        self._autopilot_nudge_timer = 0
        self._autopilot_sync_timer = 0

        # DEBUG: Dump entity states after disengage to see if anything is still frozen
        sk = f"{self.player['screen_x']},{self.player['screen_y']}"
        print(f"[Autopilot] Disengaged — player control restored, zone={sk}")
        if sk in self.screen_entities:
            for eid in self.screen_entities[sk]:
                if eid in self.entities:
                    e = self.entities[eid]
                    print(f"  [Disengage] {e.type:12s} id={eid:4d} pos=({e.x},{e.y}) "
                          f"ai_state={getattr(e, 'ai_state', '?')} "
                          f"idle_timer={getattr(e, 'idle_timer', 0)} "
                          f"is_idle={getattr(e, 'is_idle', False)} "
                          f"in_combat={getattr(e, 'in_combat', False)} "
                          f"current_target={getattr(e, 'current_target', None)} "
                          f"last_ai_tick={getattr(e, 'last_ai_tick', -1)} "
                          f"alive={e.is_alive()}")

    # ── Position sync ─────────────────────────────────────────────────────────

    def _sync_player_from_proxy(self, proxy):
        """Sync visual state, grid position, and zone from proxy to player each frame.

        All positional fields are kept in lockstep with the proxy so that:
        • The zone priority system keeps the proxy's zone highest-priority.
        • Hostile NPCs targeting 'player' attack the proxy's real position,
          not a stale phantom.
        • current_screen stays correct if the proxy crosses a zone boundary.
        """
        self.player['facing']   = proxy.facing
        self.player['world_x']  = proxy.world_x
        self.player['world_y']  = proxy.world_y
        self.player['x']        = proxy.x
        self.player['y']        = proxy.y
        self.player['screen_x'] = proxy.screen_x
        self.player['screen_y'] = proxy.screen_y

        # Keep current_screen tracking the proxy's zone so rendering is correct
        new_sk = f"{proxy.screen_x},{proxy.screen_y}"
        if self.current_screen is not self.screens.get(new_sk):
            if new_sk in self.screens:
                self.current_screen = self.screens[new_sk]

    # ── Inventory sync ────────────────────────────────────────────────────────

    def _sync_inventory_to_player(self, proxy):
        """Copy proxy entity inventory → player Inventory object.
        Handles both plain item dicts (proxy) and the Inventory class (player).
        Only syncs items/tools; magic stays on player."""
        if not hasattr(proxy, 'inventory'):
            return

        # Build a combined flat dict from player items + tools
        player_flat = {}
        for cat in ('items', 'tools'):
            for item_name, count in getattr(self.inventory, cat, {}).items():
                player_flat[item_name] = count

        proxy_flat = dict(proxy.inventory)

        # Find differences and apply them
        all_keys = set(player_flat) | set(proxy_flat)
        for key in all_keys:
            old_count = player_flat.get(key, 0)
            new_count = proxy_flat.get(key, 0)
            delta = new_count - old_count
            if delta == 0:
                continue
            if delta > 0:
                self.inventory.add_item(key, delta)
            else:
                # Remove items (best-effort)
                item_info = ITEMS.get(key, {})
                if item_info.get('is_tool'):
                    cat_dict = self.inventory.tools
                else:
                    cat_dict = self.inventory.items
                if key in cat_dict:
                    cat_dict[key] = max(0, cat_dict[key] + delta)
                    if cat_dict[key] == 0:
                        del cat_dict[key]

        # Keep proxy in sync so next diff is relative to current state
        proxy.inventory = dict(proxy_flat)

    # ── Quest target steering ─────────────────────────────────────────────────

    def _autopilot_nudge_quest_target(self, proxy):
        """Periodically steer the autopilot proxy.

        Design: the proxy should behave like its NPC type (farmer farms,
        lumberjack chops, miner mines) 90% of the time.  Only 10% of
        nudges set a cross-zone travel target to encourage exploration.

        Never interrupts flee or combat states — the proxy should be able
        to run from threats without getting overridden.
        """
        # ── Never override reactive states (flee, combat) ──────────────
        if proxy.ai_state in ('flee', 'combat'):
            return

        if not self.active_quest or self.active_quest not in self.quests:
            return

        # COMBAT_ALL requires friendly fire to be ON.
        if self.active_quest == 'COMBAT_ALL' and not self.player.get('friendly_fire', False):
            safe_quests = [q for q in self.quests
                           if not QUEST_TYPES.get(q, {}).get('requires_friendly_fire', False)
                           and self.quests[q].status in ('active', 'inactive')]
            if safe_quests:
                self.active_quest = safe_quests[0]
                print(f"[Autopilot] COMBAT_ALL skipped (FF off) — switched to {self.active_quest}")
            else:
                return

        quest = self.quests[self.active_quest]
        if quest.status != 'active':
            self.loreEngine(quest)
        if quest.status != 'active':
            return

        screen_key = f"{proxy.screen_x},{proxy.screen_y}"

        # ── Combat quests always target entities ───────────────────────
        combat_quests = ('HUNT', 'SLAY', 'COMBAT_HOSTILE', 'COMBAT_ALL')
        if self.active_quest in combat_quests:
            if quest.target_entity_id and quest.target_entity_id in self.entities:
                target_entity = self.entities[quest.target_entity_id]
                target_sk = f"{target_entity.screen_x},{target_entity.screen_y}"
                if target_sk == screen_key:
                    proxy.current_target = quest.target_entity_id
                    proxy.target_type = 'hostile'
                    proxy.ai_state = 'targeting'
                    proxy.ai_state_timer = 3
                else:
                    self._nudge_toward_zone(proxy, target_entity.screen_x,
                                            target_entity.screen_y, screen_key)
            return

        # ── Non-combat quests (FARM, LUMBER, MINE, GATHER, EXPLORE, etc.)
        # 90% of the time: let the proxy wander and execute natural NPC
        # behavior (farming, chopping, mining).  The behavior_config from
        # the entity type handles the actual work.
        # 10% of the time: set a cross-zone travel target to encourage
        # the proxy to explore new areas.
        # Exception: SEARCH and RESCUE always travel toward target zone.
        
        travel_quests = ('SEARCH', 'RESCUE', 'EXPLORE')
        force_travel = self.active_quest in travel_quests
        
        if not force_travel and random.random() < 0.90:
            # Natural behavior mode — just make sure proxy is wandering
            # so its behavior_config fires on the next tick % 60 cycle.
            if proxy.ai_state == 'targeting':
                # Only clear targeting if it was a quest-assigned target,
                # not a reactive one (hostile, etc.)
                if proxy.target_type in ('resource', 'entity', None):
                    proxy.ai_state = 'wandering'
                    proxy.current_target = None
                    proxy.ai_state_timer = 2
            return

        # ── 10% travel nudge: pick a target from a nearby zone ─────────
        if quest.target_cell:
            tsx, tsy, tx, ty = quest.target_cell
            target_sk = f"{tsx},{tsy}"
            if target_sk == screen_key:
                # Already in the target zone — let natural behavior handle it
                proxy.ai_state = 'wandering'
                proxy.current_target = None
                proxy.ai_state_timer = 2
            else:
                self._nudge_toward_zone(proxy, tsx, tsy, screen_key)
        elif quest.target_entity_id and quest.target_entity_id in self.entities:
            target_entity = self.entities[quest.target_entity_id]
            target_sk = f"{target_entity.screen_x},{target_entity.screen_y}"
            if target_sk != screen_key:
                self._nudge_toward_zone(proxy, target_entity.screen_x,
                                        target_entity.screen_y, screen_key)
        else:
            # No target — let it wander naturally
            proxy.ai_state = 'wandering'

    def _nudge_toward_zone(self, proxy, target_sx, target_sy, screen_key):
        """Set proxy target toward the center-corridor exit that leads to (target_sx, target_sy).

        Exits are a 2-cell corridor at the exact center of each edge.  The proxy
        must reach that corridor for try_entity_zone_transition to fire, so we
        always aim at the center exit cell rather than any arbitrary edge position.
        """
        zone_dx = target_sx - proxy.screen_x
        zone_dy = target_sy - proxy.screen_y

        center_x = GRID_WIDTH // 2    # e.g. 12 for GRID_WIDTH=24
        center_y = GRID_HEIGHT // 2   # e.g. 9  for GRID_HEIGHT=18

        if abs(zone_dx) >= abs(zone_dy) and zone_dx != 0:
            # Move horizontally — aim at the actual edge cell
            exit_x = (GRID_WIDTH - 1) if zone_dx > 0 else 0
            exit_y = center_y
        else:
            # Move vertically — aim at the actual edge cell
            exit_y = (GRID_HEIGHT - 1) if zone_dy > 0 else 0
            exit_x = center_x

        proxy.current_target = ('cell', exit_x, exit_y)
        proxy.target_type = 'resource'   # 'resource' is handled by move_toward_position
        proxy.ai_state = 'targeting'
        proxy.ai_state_timer = 3

    def _autopilot_switch_quest(self):
        """Switch the autopilot to a random different quest type.

        Picks from all available quest types (excluding COMBAT_ALL unless
        friendly fire is on), skipping the current quest so it always
        actually changes.
        """
        available = []
        for qt in self.quests:
            if qt == self.active_quest:
                continue
            # Skip COMBAT_ALL when friendly fire is off
            if qt == 'COMBAT_ALL' and not self.player.get('friendly_fire', False):
                continue
            available.append(qt)

        if not available:
            return

        old = self.active_quest
        self.active_quest = random.choice(available)

        # Clear stale target from the previous quest so the next nudge
        # picks a fresh target for the new quest type.
        if old and old in self.quests:
            self.quests[old].clear_target()

        print(f"[Autopilot] Quest switch: {old} → {self.active_quest}")