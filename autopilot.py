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

# How often (ticks) to perform a random inventory / spell / NPC action
ACTION_INTERVAL = 300   # every 5 seconds

# Force a quest type rotation even when the current quest is still active
FORCE_QUEST_SWITCH_INTERVAL = 1800  # every 30 seconds

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
        self.autopilot_locked = False           # True when manually toggled on via Shift+A
        self.autopilot_proxy_id = None          # entity_id of the proxy NPC, or None
        self._autopilot_nudge_timer = 0
        self._autopilot_sync_timer = 0
        self._autopilot_action_timer = 0
        self._autopilot_force_switch_timer = 0
        self._autopilot_last_exit_target = None   # (exit_x, exit_y) from last travel nudge
        self._autopilot_stuck_exit_count = 0      # consecutive nudges toward same exit
        self._autopilot_wander_cooldown = 0       # ticks of forced wandering after stuck
        self._autopilot_proxy_last_pos = None     # (x, y) at last tick for stuck detection
        self._autopilot_pos_stuck_ticks = 0       # ticks at same position while targeting
        self._autopilot_harvest_timer = 0         # opportunistic harvest every ~30 ticks
        # Simulated input queue — autopilot posts real pygame events with human delays
        self._ap_input_queue = []      # [(fire_at_tick, event_or_callable, log_label)]
        self._ap_pending_suppress = 0  # mark_input() skips this many times for AP events
        # Grace period: autopilot cannot engage until this tick
        start_tick = getattr(self, 'tick', 0)
        self.last_input_tick = start_tick + AUTOPILOT_GRACE_TICKS

    def is_autopilot_idle(self):
        """True when the player has been idle long enough to trigger autopilot."""
        return self.tick - self.last_input_tick > AUTOPILOT_IDLE_TICKS

    def mark_input(self):
        """Called on any player input — always disables autopilot.
        Synthetic autopilot events increment _ap_pending_suppress so this
        method silently passes for each queued event without disengaging."""
        if getattr(self, '_ap_pending_suppress', 0) > 0:
            self._ap_pending_suppress -= 1
            return
        self.last_input_tick = self.tick
        if self.autopilot:
            self.autopilot_locked = False
            self._autopilot_disengage()

    def toggle_autopilot(self):
        """Manually toggle autopilot on/off (Shift+A)."""
        if self.autopilot_locked:
            self.autopilot_locked = False
            self._autopilot_disengage()
            print("[Autopilot] OFF")
        else:
            self.autopilot_locked = True
            self.autopilot = True
            print("[Autopilot] ON")

    # ── Main update (called every tick from move_player) ──────────────────────

    def update_autopilot(self):
        """Top-level autopilot tick.  Spawns proxy on first call, then maintains it."""
        if not self.autopilot or self.state != 'playing':
            return

        # Drain any queued synthetic button presses first
        self._ap_flush_input_queue()

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

        # ── Obstacle clearing: detect stuck position and chop/mine blocking cells ─
        cur_pos = (proxy.x, proxy.y)
        if proxy.ai_state in ('targeting', 'wandering') and cur_pos == self._autopilot_proxy_last_pos:
            self._autopilot_pos_stuck_ticks += 1
            # Try to clear obstacle every 60 ticks of being stuck (once per NPC AI cycle)
            if self._autopilot_pos_stuck_ticks % 60 == 0:
                self._autopilot_try_clear_obstacle(proxy)
        else:
            self._autopilot_proxy_last_pos = cur_pos
            self._autopilot_pos_stuck_ticks = 0

        # ── Opportunistic harvesting: attempt chop/mine every ~30 ticks while moving ─
        if proxy.ai_state in ('targeting', 'wandering'):
            self._autopilot_harvest_timer += 1
            if self._autopilot_harvest_timer >= 30:
                self._autopilot_harvest_timer = 0
                self._autopilot_opportunistic_harvest(proxy)
        # Periodically sync proxy inventory → player inventory
        self._autopilot_sync_timer += 1
        if self._autopilot_sync_timer >= INVENTORY_SYNC_INTERVAL:
            self._autopilot_sync_timer = 0
            self._sync_inventory_to_player(proxy)

        # ── Periodic HP restoration — let proxy take real combat damage
        #    but prevent it from dying and ending the session.
        #    Restores to full every 300 ticks if below 50% HP.
        if proxy.health < proxy.max_health * 0.5:
            if self.tick % 300 == 0:
                proxy.health = proxy.max_health
                print(f"[Autopilot] Proxy HP restored to {proxy.max_health:.0f}")

        # ── Quest completion check: 80% chance to switch quest type ────────
        if self.active_quest and self.active_quest in self.quests:
            quest = self.quests[self.active_quest]
            if quest.status == 'completed' or quest.status == 'cooldown':
                if random.random() < 0.80:
                    self._autopilot_switch_quest()

        # ── Forced periodic quest rotation (even when quest is still active)
        self._autopilot_force_switch_timer += 1
        if self._autopilot_force_switch_timer >= FORCE_QUEST_SWITCH_INTERVAL:
            self._autopilot_force_switch_timer = 0
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

        # ── Periodic inventory / spell / NPC action ──────────────────────
        self._autopilot_action_timer += 1
        if self._autopilot_action_timer >= ACTION_INTERVAL:
            self._autopilot_action_timer = 0
            self._autopilot_do_action(proxy)

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

        # ── Real stats so damage is visible; hunger/thirst kept high to
        #    avoid those systems limiting the session.  HP is restored
        #    periodically in update_autopilot() so the proxy doesn't die.
        proxy.max_health = self.player.get('max_health', 100)
        proxy.health     = proxy.max_health
        proxy.max_hunger = 9999;  proxy.hunger  = 9999   # no hunger concern
        proxy.max_thirst = 9999;  proxy.thirst  = 9999   # no thirst concern
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
        self.inspected_npc = None
        
        # Clear ALL idle timers/inspection freezes on ALL entities
        for eid, e in self.entities.items():
            if getattr(e, 'idle_timer', 0) > 0:
                e.idle_timer = 0
                e.is_idle = False

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
        self._autopilot_action_timer = 0
        self._autopilot_force_switch_timer = 0
        self._autopilot_last_exit_target = None
        self._autopilot_stuck_exit_count = 0
        self._autopilot_wander_cooldown = 0
        self._autopilot_proxy_last_pos = None
        self._autopilot_pos_stuck_ticks = 0
        self._autopilot_harvest_timer = 0


    # ── Position sync ─────────────────────────────────────────────────────────

    def _sync_player_from_proxy(self, proxy):
        """Sync visual state, grid position, and zone from proxy to player each frame.

        All positional fields are kept in lockstep with the proxy so that:
        • The zone priority system keeps the proxy's zone highest-priority.
        • Hostile NPCs targeting 'player' attack the proxy's real position,
          not a stale phantom.
        • current_screen stays correct if the proxy crosses a zone boundary.
        """
        # If the proxy somehow ended up inside a structure, do not sync position —
        # syncing virtual coords would break current_screen and in_structure state.
        if getattr(proxy, 'in_structure', False):
            return

        # Footstep sound when proxy moves to a new grid cell
        old_px, old_py = self.player.get('x', proxy.x), self.player.get('y', proxy.y)
        if (proxy.x != old_px or proxy.y != old_py) and self.current_screen:
            try:
                stepped_cell = self.current_screen['grid'][proxy.y][proxy.x]
                self.sound.on_footstep(stepped_cell)
            except (IndexError, KeyError):
                pass

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

        # ── Wander cooldown: after being stuck at an exit, wander freely ─
        if self._autopilot_wander_cooldown > 0:
            self._autopilot_wander_cooldown -= 1
            proxy.ai_state = 'wandering'
            proxy.current_target = None
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
        
        if not force_travel and random.random() < 0.65:
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

        exit_target = (exit_x, exit_y)

        # Track consecutive nudges toward the same exit cell.
        # If stuck for 5+ cycles (600 ticks), enter a wander cooldown so the
        # proxy uses natural movement to find a path rather than repeatedly
        # re-targeting the same unreachable cell.
        if self._autopilot_last_exit_target == exit_target:
            self._autopilot_stuck_exit_count += 1
        else:
            self._autopilot_last_exit_target = exit_target
            self._autopilot_stuck_exit_count = 1

        if self._autopilot_stuck_exit_count >= 5:
            self._autopilot_stuck_exit_count = 0
            self._autopilot_last_exit_target = None
            self._autopilot_wander_cooldown = 10  # 10 nudge cycles of free wandering
            proxy.ai_state = 'wandering'
            proxy.current_target = None
            print(f"[Autopilot] Stuck at exit {exit_target} — entering wander cooldown")
            return

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

    # ── Simulated input helpers ───────────────────────────────────────────────

    def _ap_key(self, key, mod=0):
        """Return a KEYDOWN pygame event for the given key."""
        return pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod,
                                  unicode='', scancode=0)

    def _ap_click(self, x, y):
        """Return a MOUSEBUTTONDOWN (left-click) pygame event at (x, y)."""
        return pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1,
                                  pos=(int(x), int(y)))

    def _ap_queue(self, action, delay, label=''):
        """Schedule an event or callable with a tick delay.

        action  — a pygame.event.Event (posted via pygame.event.post) or
                  a zero-argument callable (called directly at fire_at).
        delay   — ticks from now to fire.  Use random.randint(5,15) for
                  human-like reaction time.
        label   — printed to stdout when the action fires.
        """
        self._ap_input_queue.append((self.tick + delay, action, label))

    def _ap_flush_input_queue(self):
        """Drain ready actions.  Called once per tick at the top of update_autopilot."""
        remaining = []
        for fire_at, action, label in self._ap_input_queue:
            if self.tick >= fire_at:
                if label:
                    print(f"[AP] {label}")
                if callable(action):
                    action()
                else:
                    # Suppress mark_input for this synthetic event
                    self._ap_pending_suppress += 1
                    pygame.event.post(action)
            else:
                remaining.append((fire_at, action, label))
        self._ap_input_queue = remaining

    def _ap_crafting_slot_pixel(self, item_name):
        """Return the screen pixel centre (x, y) of the named crafting recipe slot.

        Mirrors the layout calculation in game_core.handle_inventory_click()
        so the synthetic mouse click lands exactly on the correct slot.
        Returns None if the slot is not currently visible.
        """
        slot_size = CELL_SIZE
        start_x = 10
        start_y = SCREEN_HEIGHT - 90
        categories = ['tools', 'items', 'magic', 'actions', 'followers', 'crafting']
        y_offset = 0
        for cat in categories:
            if cat not in self.inventory.open_menus:
                continue
            if cat == 'crafting':
                items = self.inventory.get_craftable_recipes()
            else:
                items = self.inventory.get_item_list(cat)
            if not items:
                continue
            if cat == 'crafting':
                for i, (name, _) in enumerate(items):
                    if name == item_name:
                        return (start_x + i * (slot_size + 2) + slot_size // 2,
                                start_y - y_offset + slot_size // 2)
            y_offset += slot_size + 15
        return None

    def _ap_click_crafting_slot(self, item_name):
        """Callable: compute pixel pos for item_name and post a click event."""
        pos = self._ap_crafting_slot_pixel(item_name)
        if pos:
            self._ap_pending_suppress += 1
            pygame.event.post(self._ap_click(pos[0], pos[1]))
        else:
            print(f"[AP] crafting slot '{item_name}' not visible — skipping click")

    # ── Periodic random actions ────────────────────────────────────────────────

    def _autopilot_do_action(self, proxy):
        """Randomly perform one of: craft available recipe, change selected tool,
        use a spell, drop an item, or inspect a nearby NPC."""
        # Don't start a new action while a queued input sequence is in flight
        if self._ap_input_queue:
            return
        # Prioritize crafting whenever a recipe is available
        if self._autopilot_try_craft():
            return
        action = random.choice(['change_tool', 'use_spell', 'drop_item', 'npc_interact'])
        if action == 'change_tool':
            self._autopilot_change_tool()
        elif action == 'use_spell':
            self._autopilot_use_spell()
        elif action == 'drop_item':
            self._autopilot_drop_item(proxy)
        else:
            self._autopilot_try_npc_interact(proxy)

    def _autopilot_try_craft(self):
        """Queue a crafting sequence: C → click slot → Space (with human delays).

        Returns True if a craft sequence was queued (not yet completed).
        The actual craft happens asynchronously when the queued Space key fires.
        """
        craftable = self.inventory.get_craftable_recipes()
        if not craftable:
            return False
        _priority = ['iron_sword', 'iron_ingot', 'stone_pickaxe', 'hoe', 'shovel',
                     'hilt', 'bone_sword', 'stone_axe', 'leather_armor', 'leather',
                     'planks', 'chest', 'cooked_meat', 'stew']
        craftable_names = [r for r, _ in craftable]
        chosen = None
        for preferred in _priority:
            if preferred in craftable_names:
                chosen = preferred
                break
        if chosen is None:
            chosen = craftable_names[0]

        # Simulate: open crafting menu → click recipe slot → press Space to craft
        d1 = random.randint(5, 12)   # reaction: decide to open crafting
        d2 = random.randint(8, 15)   # look at menu, find and click the slot
        d3 = random.randint(5, 10)   # confirm with Space
        self._ap_queue(self._ap_key(pygame.K_c),  d1,          f"press C  (open crafting → {chosen})")
        self._ap_queue(lambda c=chosen: self._ap_click_crafting_slot(c),
                                                  d1 + d2,     f"click slot '{chosen}'")
        self._ap_queue(self._ap_key(pygame.K_SPACE), d1+d2+d3, "press SPACE (craft)")
        return True


    def _autopilot_change_tool(self):
        """Select a random available tool from the player's tool inventory."""
        tools = list(self.inventory.tools.keys())
        if not tools:
            return
        chosen = random.choice(tools)
        self.inventory.selected['tools'] = chosen
        print(f"[Autopilot] Tool → {chosen}")

    def _autopilot_use_spell(self):
        """Select a spell and queue an L key press to cast it."""
        magic = getattr(self.inventory, 'magic', {})
        spells = list(magic.keys())
        if not spells:
            return
        chosen = random.choice(spells)
        # Direct selection is fine — no UI side-effect, just sets the active slot
        self.inventory.selected['magic'] = chosen
        d1 = random.randint(5, 12)
        self._ap_queue(self._ap_key(pygame.K_l), d1, f"press L  (cast {chosen})")

    def _autopilot_drop_item(self, proxy):
        """Drop one unit of a random surplus resource item at the proxy's position.

        Only drops items where the player holds more than 1 copy; never drops
        tools, spells, actions, or follower items.
        """
        droppable = [
            k for k, v in self.inventory.items.items()
            if v > 1
            and not ITEMS.get(k, {}).get('is_tool')
            and not ITEMS.get(k, {}).get('is_spell')
            and not ITEMS.get(k, {}).get('is_action')
            and not ITEMS.get(k, {}).get('is_follower')
        ]
        if not droppable:
            return
        item = random.choice(droppable)
        if hasattr(self, 'drop_item'):
            self.drop_item(item, int(proxy.x), int(proxy.y))
            print(f"[Autopilot] Dropped {item} at ({int(proxy.x)},{int(proxy.y)})")

    def _autopilot_try_npc_interact(self, proxy):
        """Inspect the nearest non-proxy NPC in the proxy's zone.

        Sets self.inspected_npc so the normal per-tick NPC inspection logic runs,
        exercising trade menus, dialogue, and relationship checks.
        """
        screen_key = f"{proxy.screen_x},{proxy.screen_y}"
        candidates = []
        for eid in self.screen_entities.get(screen_key, []):
            if eid == self.autopilot_proxy_id:
                continue
            e = self.entities.get(eid)
            if e is None or getattr(e, 'in_subscreen', False):
                continue
            dist = abs(e.x - proxy.x) + abs(e.y - proxy.y)
            candidates.append((dist, eid, e))
        if not candidates:
            return
        candidates.sort()
        dist, eid, e = candidates[0]
        if dist <= 4:
            self.inspected_npc = eid
            print(f"[Autopilot] Inspecting {e.type} (id={eid}) dist={dist}")

    def _autopilot_try_clear_obstacle(self, proxy):
        """When the proxy is stuck in 'targeting' state, scan adjacent cells for
        harvestable solid obstacles (trees, stone, iron ore) and clear them.

        Calls try_chop_tree / try_mine_rock directly — these functions transform
        the blocking cell regardless of whether the player has the right tool
        (drops are tool-gated; path clearing is not).  This surfaces pathfinding
        issues that would otherwise keep the proxy frozen indefinitely.
        """
        screen_key = f"{proxy.screen_x},{proxy.screen_y}"
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        grid = screen['grid']

        tree_adjacent = False
        rock_adjacent = False
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = int(proxy.x) + dx, int(proxy.y) + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            cell = grid[cy][cx]
            if cell in ('TREE1', 'TREE2'):
                tree_adjacent = True
            elif cell in ('STONE', 'IRON_ORE'):
                rock_adjacent = True

        if tree_adjacent:
            self.try_chop_tree(proxy, screen_key)
            print(f"[Autopilot] Obstacle-clear: chopping tree adjacent to proxy "
                  f"({int(proxy.x)},{int(proxy.y)}) stuck={self._autopilot_pos_stuck_ticks}t")
        elif rock_adjacent:
            self.try_mine_rock(proxy, screen_key)
            print(f"[Autopilot] Obstacle-clear: mining rock adjacent to proxy "
                  f"({int(proxy.x)},{int(proxy.y)}) stuck={self._autopilot_pos_stuck_ticks}t")

    def _autopilot_opportunistic_harvest(self, proxy):
        """Scan the 3×3 area around the proxy for harvestable cells and collect them.

        Fires every ~30 ticks regardless of movement/ai_state so the proxy
        accumulates resources while traversing the world.  Trees take priority
        over rocks (lumberjacking yields more varied drops).
        """
        screen_key = f"{proxy.screen_x},{proxy.screen_y}"
        if screen_key not in self.screens:
            return

        screen = self.screens[screen_key]
        grid = screen['grid']

        tree_found = False
        rock_found = False
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            cx, cy = int(proxy.x) + dx, int(proxy.y) + dy
            if not (0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT):
                continue
            cell = grid[cy][cx]
            if cell in ('TREE1', 'TREE2'):
                tree_found = True
            elif cell in ('STONE', 'IRON_ORE'):
                rock_found = True

        if tree_found:
            self.try_chop_tree(proxy, screen_key)
        elif rock_found:
            self.try_mine_rock(proxy, screen_key)