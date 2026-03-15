import pygame
from constants import COLORS, SCREEN_WIDTH, SCREEN_HEIGHT


class DevScreenMixin:
    """Toggleable developer info overlay. Shift+I to open/close during gameplay."""

    # ── Data collection ────────────────────────────────────────────────────────

    def _collect_dev_stats(self):
        """Gather a snapshot of all game-world stats for the dev overlay."""

        # Biomes
        biome_counts = {}
        for screen in self.screens.values():
            b = screen.get('biome', 'UNKNOWN')
            biome_counts[b] = biome_counts.get(b, 0) + 1

        # Entities
        type_counts  = {}
        level_counts = {}
        alive_count  = 0
        total_npc_items = 0
        for entity in self.entities.values():
            if entity.health <= 0:
                continue
            alive_count += 1
            type_counts[entity.type] = type_counts.get(entity.type, 0) + 1
            lv = getattr(entity, 'level', 1)
            level_counts[lv] = level_counts.get(lv, 0) + 1
            inv = getattr(entity, 'inventory', {})
            if isinstance(inv, dict):
                total_npc_items += sum(inv.values())

        # Structures — scan every cell grid
        tracked = ('HOUSE', 'STONE_HOUSE', 'CAVE', 'MINESHAFT',
                   'FORGE', 'CAMP', 'WELL', 'CHEST', 'BARREL')
        struct_counts = {c: 0 for c in tracked}
        for screen in self.screens.values():
            for row in screen.get('grid', []):
                for cell in row:
                    if cell in struct_counts:
                        struct_counts[cell] += 1

        # Keepers — alive only
        keeper_counts = {}
        for slots in self.zone_keepers.values():
            for slot, eid in slots.items():
                if eid in self.entities and self.entities[eid].health > 0:
                    keeper_counts[slot] = keeper_counts.get(slot, 0) + 1

        # NPC non-base quests
        npc_quest_counts = {}
        for entity in self.entities.values():
            if entity.health <= 0:
                continue
            for q in getattr(entity, 'quest_queue', []):
                if not q.get('base', False):
                    qt = q.get('type', '?')
                    npc_quest_counts[qt] = npc_quest_counts.get(qt, 0) + 1

        # Dropped items
        total_dropped   = 0
        zones_with_drops = 0
        for cell_dict in self.dropped_items.values():
            if cell_dict:
                zones_with_drops += 1
            for items in cell_dict.values():
                if isinstance(items, dict):
                    total_dropped += sum(items.values())

        # Chest contents
        total_chest_items = 0
        for contents in self.chest_contents.values():
            if isinstance(contents, dict):
                total_chest_items += sum(contents.values())

        # screen_entities registrations (total refs, including dead)
        total_se_refs = sum(len(v) for v in self.screen_entities.values())

        return {
            'biome_counts':      dict(sorted(biome_counts.items())),
            'type_counts':       dict(sorted(type_counts.items(), key=lambda x: -x[1])),
            'level_counts':      dict(sorted(level_counts.items())),
            'alive_count':       alive_count,
            'total_entities':    len(self.entities),
            'total_npc_items':   total_npc_items,
            'struct_counts':     struct_counts,
            'keeper_counts':     dict(sorted(keeper_counts.items())),
            'npc_quest_counts':  dict(sorted(npc_quest_counts.items(), key=lambda x: -x[1])),
            'total_dropped':     total_dropped,
            'zones_with_drops':  zones_with_drops,
            'total_chest_items': total_chest_items,
            'total_se_refs':     total_se_refs,
            'priority_queue':    self.get_priority_sorted_zones(),
            'total_zones':       len(self.screens),
            'overworld_zones':   sum(1 for zk in self.screens if self.is_overworld_zone(zk)),
            'struct_zones':      len(self.structure_zones),
        }

    # ── Renderer ───────────────────────────────────────────────────────────────

    def draw_dev_screen(self):
        """Render the dev info overlay on top of the current game view."""
        if not getattr(self, 'show_dev_screen', False):
            return

        stats = self._collect_dev_stats()

        # Semi-transparent backdrop
        backdrop = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        backdrop.fill((0, 0, 0, 215))
        self.screen.blit(backdrop, (0, 0))

        sf = self.small_font   # 18 pt
        tf = self.tiny_font    # 14 pt

        # Colour palette
        HDR = (220, 225, 255)   # section header
        DAT = (180, 180, 180)   # normal data
        YEL = (255, 220, 80)    # player zone / title
        RED = (255, 100, 100)   # bloat alert
        GRN = (120, 220, 120)   # ok

        def _t(text, x, y, color=DAT, font=tf):
            """Blit text, return next y."""
            s = font.render(str(text), True, color)
            self.screen.blit(s, (x, y))
            return y + font.get_height() + 2

        def _h(text, x, y):
            """Blit a section header with underline, return next y."""
            s = sf.render(text, True, HDR)
            self.screen.blit(s, (x, y))
            ny = y + sf.get_height() + 2
            pygame.draw.line(self.screen, (70, 70, 110), (x, ny - 1), (x + 210, ny - 1))
            return ny + 2

        # ── Title bar ──────────────────────────────────────────────────────────
        title = sf.render(
            f"DEV INFO  —  tick {self.tick}  —  Shift+I to close",
            True, YEL
        )
        self.screen.blit(title, (10, 5))

        TOP = 28

        # ══════════════════════════════════════════════════════════════════════
        # Column 1 — World & Structures                                x=10
        # ══════════════════════════════════════════════════════════════════════
        cx, cy = 10, TOP

        cy = _h("WORLD", cx, cy)
        cy = _t(f"Total zones:      {stats['total_zones']}", cx, cy)
        cy = _t(f"Overworld:        {stats['overworld_zones']}", cx, cy)
        cy = _t(f"Structure zones:  {stats['struct_zones']}", cx, cy)
        cy = _t(f"Instantiated:     {len(self.instantiated_zones)}", cx, cy)
        cy += 4
        for biome, count in stats['biome_counts'].items():
            cy = _t(f"  {biome:<12} {count}", cx, cy)

        cy += 8
        cy = _h("STRUCTURES  (cells on grid)", cx, cy)
        for cell, count in stats['struct_counts'].items():
            alert = RED if (cell == 'CHEST' and count > 300) else DAT
            cy = _t(f"  {cell:<14} {count}", cx, cy, alert)

        cy += 8
        cy = _h("KEEPERS  (alive)", cx, cy)
        if stats['keeper_counts']:
            for slot, count in stats['keeper_counts'].items():
                cy = _t(f"  {slot:<16} {count}", cx, cy)
        else:
            cy = _t("  (none)", cx, cy)

        # ══════════════════════════════════════════════════════════════════════
        # Column 2 — Entities                                          x=245
        # ══════════════════════════════════════════════════════════════════════
        cx, cy = 245, TOP

        cy = _h(f"ENTITIES  alive {stats['alive_count']} / total {stats['total_entities']}", cx, cy)
        for etype, count in stats['type_counts'].items():
            cy = _t(f"  {etype:<18} {count}", cx, cy)

        cy += 8
        cy = _h("BY LEVEL", cx, cy)
        for lv, count in stats['level_counts'].items():
            bar = '█' * min(count, 18)
            cy = _t(f"  L{lv:<3} {count:>4}  {bar}", cx, cy)

        # ══════════════════════════════════════════════════════════════════════
        # Column 3 — Quests & Bloat watch                              x=490
        # ══════════════════════════════════════════════════════════════════════
        cx, cy = 490, TOP

        cy = _h("NPC NON-BASE QUESTS", cx, cy)
        if stats['npc_quest_counts']:
            for qt, count in stats['npc_quest_counts'].items():
                cy = _t(f"  {qt:<22} {count}", cx, cy)
        else:
            cy = _t("  (none)", cx, cy)

        cy += 8
        cy = _h("BLOAT WATCH", cx, cy)

        def _bloat_color(val, warn, crit):
            return RED if val >= crit else (YEL if val >= warn else GRN)

        npc_col = _bloat_color(stats['total_npc_items'],   2000, 5000)
        che_col = _bloat_color(stats['total_chest_items'],  500, 1000)
        drp_col = _bloat_color(stats['total_dropped'],      200,  500)
        ser_col = _bloat_color(stats['total_se_refs'],      500,  800)
        ent_col = _bloat_color(stats['total_entities'],     600,  900)
        och_col = _bloat_color(len(self.opened_chests),     200,  500)

        cy = _t(f"  NPC inventory items   {stats['total_npc_items']:>6}", cx, cy, npc_col)
        cy = _t(f"  Chest contents items  {stats['total_chest_items']:>6}", cx, cy, che_col)
        cy = _t(f"  Dropped items         {stats['total_dropped']:>6}", cx, cy, drp_col)
        cy = _t(f"    zones w/ drops      {stats['zones_with_drops']:>6}", cx, cy)
        cy = _t(f"  screen_entity refs    {stats['total_se_refs']:>6}", cx, cy, ser_col)
        cy = _t(f"  total entities dict   {stats['total_entities']:>6}", cx, cy, ent_col)
        cy = _t(f"  opened_chests set     {len(self.opened_chests):>6}", cx, cy, och_col)
        cy = _t(f"  chest_contents keys   {len(self.chest_contents):>6}", cx, cy)
        cy = _t(f"  enchanted cells       {len(self.enchanted_cells):>6}", cx, cy)
        cy = _t(f"  enchanted entities    {len(self.enchanted_entities):>6}", cx, cy)
        cy = _t(f"  followers             {len(self.followers):>6}", cx, cy)
        cy = _t(f"  zone_keepers zones    {len(self.zone_keepers):>6}", cx, cy)
        cy = _t(f"  active quests (NPC)   {sum(stats['npc_quest_counts'].values()):>6}", cx, cy)

        # ══════════════════════════════════════════════════════════════════════
        # Column 4 — Zone priority queue                               x=706
        # ══════════════════════════════════════════════════════════════════════
        pygame.draw.line(self.screen, (60, 60, 100), (702, TOP), (702, SCREEN_HEIGHT - 6))
        cx, cy = 706, TOP

        cy = _h(f"ZONE QUEUE  ({len(stats['priority_queue'])} total)", cx, cy)

        # Header row — compact to fit ~250 px
        col_fmt = f"{'ZONE':<12}{'BIOME':<9}{'N':>2}  {'STALE':>5}  {'PRI':>5}"
        cy = _t(col_fmt, cx, cy, HDR)

        player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
        max_rows = (SCREEN_HEIGHT - cy - 8) // (tf.get_height() + 2)
        shown = 0
        for priority, zone_key in stats['priority_queue']:
            if shown >= max_rows:
                remaining = len(stats['priority_queue']) - shown
                _t(f"  +{remaining} more", cx, cy, DAT)
                break

            screen_data = self.screens.get(zone_key)
            if not screen_data:
                continue

            biome     = screen_data.get('biome', '?')[:8]
            npc_count = len([
                e for e in self.screen_entities.get(zone_key, [])
                if e in self.entities and self.entities[e].health > 0
            ])
            stale     = self.tick - self.screen_last_update.get(zone_key, 0)
            zk_disp   = zone_key if len(zone_key) <= 11 else zone_key[:9] + '..'
            is_player = (zone_key == player_zone)
            row_col   = YEL if is_player else DAT

            line = (f"{zk_disp:<12}{biome:<9}{npc_count:>2}  "
                    f"{stale:>5}t  {priority:>5.0f}")
            cy = _t(line, cx, cy, row_col)
            shown += 1
