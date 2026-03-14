import json
import os
import random

from entity import Entity, Quest, NpcQuestSlot
from constants import ITEMS, COLORS


class SaveLoadMixin:
    """Handles saving and loading game state to/from JSON."""

    def save_game(self, path='savegame.json'):
        """Save game to file. Pass a different path for backup saves."""
        entities_data = {}
        for entity_id, entity in self.entities.items():
            entities_data[entity_id] = {
                'type': entity.type,
                'x': entity.x,
                'y': entity.y,
                'screen_x': entity.screen_x,
                'screen_y': entity.screen_y,
                'level': entity.level,
                'health': entity.health,
                'hunger': entity.hunger,
                'thirst': entity.thirst,
                'inventory': entity.inventory,
                'xp': entity.xp,
                # New attributes for comprehensive save
                'faction': getattr(entity, 'faction', None),
                'name': getattr(entity, 'name', None),
                'age': getattr(entity, 'age', 0),
                'alignment': getattr(entity, 'alignment', None),  # Wizard peaceful/hostile
                'spell': getattr(entity, 'spell', None),  # Wizard spell type
                'home_zone': getattr(entity, 'home_zone', None),  # Warrior home zone
                'movement_pattern': getattr(entity, 'movement_pattern', None),
                'item_levels': getattr(entity, 'item_levels', {}),
                'item_names': getattr(entity, 'item_names', {}),
                'keeper': getattr(entity, 'keeper', False)
            }

        # Convert dropped_items tuple keys to strings for JSON serialization
        dropped_items_serializable = {}
        for screen_key, items_dict in self.dropped_items.items():
            dropped_items_serializable[screen_key] = {}
            for cell_tuple, items in items_dict.items():
                # Convert (x, y) tuple to "x,y" string
                cell_key_str = f"{cell_tuple[0]},{cell_tuple[1]}"
                dropped_items_serializable[screen_key][cell_key_str] = items

        # Convert enchanted_cells tuple keys to strings for JSON serialization
        enchanted_cells_serializable = {}
        for screen_key, cells_dict in self.enchanted_cells.items():
            enchanted_cells_serializable[screen_key] = {}
            for cell_tuple, enchant_level in cells_dict.items():
                # Convert (x, y) tuple to "x,y" string
                cell_key_str = f"{cell_tuple[0]},{cell_tuple[1]}"
                enchanted_cells_serializable[screen_key][cell_key_str] = enchant_level

        # Convert structures tuple keys to strings for JSON serialization
        structures_serializable = {}
        for structure_key, structure_data in self.structures.items():
            serialized_structure = {}
            for key, value in structure_data.items():
                if key == 'chests':
                    # Convert chest position tuples to strings
                    serialized_chests = {}
                    for chest_pos, loot_type in value.items():
                        chest_key_str = f"{chest_pos[0]},{chest_pos[1]}"
                        serialized_chests[chest_key_str] = loot_type
                    serialized_structure[key] = serialized_chests
                else:
                    serialized_structure[key] = value
            structures_serializable[structure_key] = serialized_structure

        # Serialize screens — structure zones may have tuple keys in 'chests'
        screens_serializable = {}
        for screen_key, screen_data in self.screens.items():
            serialized_screen = {}
            for key, value in screen_data.items():
                if key == 'chests' and isinstance(value, dict):
                    serialized_chests = {}
                    for chest_pos, loot_type in value.items():
                        if isinstance(chest_pos, tuple):
                            chest_key_str = f"{chest_pos[0]},{chest_pos[1]}"
                        else:
                            chest_key_str = str(chest_pos)
                        serialized_chests[chest_key_str] = loot_type
                    serialized_screen[key] = serialized_chests
                elif key == 'parent_screen' and isinstance(value, tuple):
                    serialized_screen[key] = list(value)
                elif key == 'parent_cell' and isinstance(value, tuple):
                    serialized_screen[key] = list(value)
                elif key == 'entrance' and isinstance(value, tuple):
                    serialized_screen[key] = list(value)
                elif key == 'exit' and isinstance(value, tuple):
                    serialized_screen[key] = list(value)
                elif key == 'entrances' and isinstance(value, list):
                    serialized_screen[key] = [list(e) if isinstance(e, tuple) else e for e in value]
                else:
                    serialized_screen[key] = value
            screens_serializable[screen_key] = serialized_screen

        # Convert structure_zones cell tuples to lists for JSON
        structure_zones_serializable = {}
        for sz_key, sz_data in self.structure_zones.items():
            sz_copy = dict(sz_data)
            if 'cell' in sz_copy and isinstance(sz_copy['cell'], tuple):
                sz_copy['cell'] = list(sz_copy['cell'])
            structure_zones_serializable[sz_key] = sz_copy

        # Convert zone_connections tuples to lists for JSON
        zone_connections_serializable = {}
        for zc_key, connections in self.zone_connections.items():
            zone_connections_serializable[zc_key] = [list(c) for c in connections]

        save_data = {
            'player': self.player,
            'screens': screens_serializable,
            'tick': self.tick,
            'inventory_items': self.inventory.items,
            'inventory_tool_slots': self.inventory.tool_slots,
            'inventory_selected_tool_slot': self.inventory.selected_tool_slot_idx,
            'inventory_magic': self.inventory.magic,
            'inventory_followers': self.inventory.followers,
            'inventory_actions': self.inventory.actions,
            'inventory_selected': self.inventory.selected,
            'dropped_items': dropped_items_serializable,
            'screen_last_update': self.screen_last_update,
            'target_direction': self.target_direction,
            'entities': entities_data,
            'screen_entities': self.screen_entities,
            'next_entity_id': self.next_entity_id,
            'enchanted_cells': enchanted_cells_serializable,
            'enchanted_entities': self.enchanted_entities,
            'followers': self.followers,
            'follower_items': {str(k): v for k, v in self.follower_items.items()},
            'structures': structures_serializable,
            'opened_chests': list(self.opened_chests),  # Convert set to list for JSON
            'chest_contents': getattr(self, 'chest_contents', {}),
            'chest_backgrounds': getattr(self, 'chest_backgrounds', {}),
            'next_structure_id': self.next_structure_id,
            # Zone priority system
            'zone_connections': zone_connections_serializable,
            'structure_zones': structure_zones_serializable,
            'zone_structures': self.zone_structures,
            'next_structure_zone_id': self.next_structure_zone_id,
            'active_quest': self.active_quest,
            'active_npc_quest_npc_id': getattr(self, 'active_npc_quest_npc_id', None),
            'zone_keepers': self.zone_keepers,
            'zone_cave_systems': getattr(self, 'zone_cave_systems', {}),
            'npc_quests': [
                {
                    'npc_id':           nq.npc_id,
                    'quest_type':       nq.quest.quest_type,
                    'status':           nq.quest.status,
                    'target_entity_id': nq.quest.target_entity_id,
                    'target_location':  list(nq.quest.target_location) if nq.quest.target_location else None,
                    'target_cell':      list(nq.quest.target_cell) if nq.quest.target_cell else None,
                    'target_info':      nq.quest.target_info,
                    'target_zone':      nq.quest.target_zone,
                    'completed_count':  nq.quest.completed_count,
                    'original_cell':    getattr(nq.quest, '_original_cell', None),
                    'progress':         getattr(nq.quest, 'progress', 0.0),
                }
                for nq in getattr(self, 'npc_quests', [])
            ],
        }
        with open(path, 'w') as f:
            json.dump(save_data, f)
        if path == 'savegame.json':
            print("Game saved!")

    def load_game(self):
        """Load game from file"""
        if os.path.exists('savegame.json'):
            with open('savegame.json', 'r') as f:
                save_data = json.load(f)
            self.player = save_data['player']
            # Ensure player has all combat fields (for backward compatibility)
            if 'health' not in self.player:
                self.player['health'] = 100
                self.player['max_health'] = 100
                self.player['base_damage'] = 10
                self.player['blocking'] = False
                self.player['last_attack_tick'] = 0
            # Migrate old save keys (subscreen → structure)
            if 'in_subscreen' in self.player and 'in_structure' not in self.player:
                self.player['in_structure'] = self.player.pop('in_subscreen')
            if 'subscreen_key' in self.player and 'structure_key' not in self.player:
                self.player['structure_key'] = self.player.pop('subscreen_key')
            if 'subscreen_parent' in self.player and 'structure_parent' not in self.player:
                self.player['structure_parent'] = self.player.pop('subscreen_parent')
            # Ensure player has structure fields
            if 'in_structure' not in self.player:
                self.player['in_structure'] = False
                self.player['structure_key'] = None
                self.player['structure_parent'] = None
            # Ensure player has energy fields (added after initial release)
            if 'energy' not in self.player:
                self.player['energy'] = self.player.get('max_energy', 100)
                self.player['max_energy'] = self.player.get('max_energy', 100)
            # Remove legacy magic_pool fields if present
            self.player.pop('magic_pool', None)
            self.player.pop('max_magic_pool', None)
            # Ensure player has animation fields
            if 'facing' not in self.player:
                self.player['facing'] = 'down'
                self.player['anim_frame'] = 'still'
                self.player['anim_timer'] = 0
                self.player['_next_step'] = '1'
                self.player['is_moving'] = False
            self.screens = save_data['screens']
            self.tick = save_data['tick']
            self.inventory.items = save_data.get('inventory_items', {})
            self.inventory.magic = save_data.get('inventory_magic', {})
            self.inventory.followers = save_data.get('inventory_followers', {})
            self.inventory.actions = save_data.get('inventory_actions', {})
            # Restore tool slots — with backward compat for old saves using tools dict
            if 'inventory_tool_slots' in save_data:
                self.inventory.tool_slots = save_data['inventory_tool_slots']
            elif 'inventory_tools' in save_data:
                # Migrate old tools dict → slots
                old_tools = save_data['inventory_tools']
                self.inventory.tool_slots = [None] * 8
                slot_idx = 0
                for iname, cnt in old_tools.items():
                    for _ in range(cnt):
                        if slot_idx < 8:
                            self.inventory.tool_slots[slot_idx] = iname
                            slot_idx += 1
            self.inventory.selected_tool_slot_idx = save_data.get('inventory_selected_tool_slot')
            # Sync selected['tools'] from active slot
            idx = self.inventory.selected_tool_slot_idx
            slot_item = self.inventory.tool_slots[idx] if idx is not None and 0 <= idx < 8 else None
            self.inventory.selected = save_data.get('inventory_selected', {
                'items': None, 'tools': None, 'magic': None, 'followers': None,
                'actions': None, 'crafting': None,
            })
            # Ensure new keys exist in loaded selected dict
            self.inventory.selected.setdefault('actions', None)
            self.inventory.selected.setdefault('crafting', None)
            self.inventory.selected['tools'] = slot_item

            # Convert dropped_items string keys back to tuples
            dropped_items_loaded = save_data.get('dropped_items', {})
            self.dropped_items = {}
            for screen_key, items_dict in dropped_items_loaded.items():
                self.dropped_items[screen_key] = {}
                for cell_key_str, items in items_dict.items():
                    # Convert "x,y" string back to (x, y) tuple
                    x, y = map(int, cell_key_str.split(','))
                    self.dropped_items[screen_key][(x, y)] = items

            self.screen_last_update = save_data.get('screen_last_update', {})
            self.target_direction = save_data.get('target_direction', 0)
            self.screen_entities = save_data.get('screen_entities', {})
            self.next_entity_id = save_data.get('next_entity_id', 0)

            # Load enchantment data - convert string keys back to tuples
            enchanted_cells_loaded = save_data.get('enchanted_cells', {})
            self.enchanted_cells = {}
            for screen_key, cells_dict in enchanted_cells_loaded.items():
                self.enchanted_cells[screen_key] = {}
                for cell_key_str, enchant_level in cells_dict.items():
                    # Convert "x,y" string back to (x, y) tuple
                    x, y = map(int, cell_key_str.split(','))
                    self.enchanted_cells[screen_key][(x, y)] = enchant_level

            self.enchanted_entities = save_data.get('enchanted_entities', {})

            # Load followers list
            self.followers = save_data.get('followers', [])

            # Load follower_items (JSON stores int keys as strings — convert back)
            raw_fi = save_data.get('follower_items', {})
            self.follower_items = {int(k): v for k, v in raw_fi.items()}

            # Reconstruct entities
            self.entities = {}
            entities_data = save_data.get('entities', {})
            for entity_id_str, entity_data in entities_data.items():
                entity_id = int(entity_id_str)
                entity = Entity(
                    entity_data['type'],
                    entity_data['x'],
                    entity_data['y'],
                    entity_data['screen_x'],
                    entity_data['screen_y'],
                    entity_data['level']
                )
                entity.health = entity_data['health']
                entity.hunger = entity_data['hunger']
                entity.thirst = entity_data['thirst']
                entity.inventory = entity_data.get('inventory', {})
                entity.xp = entity_data.get('xp', 0)

                # Restore new attributes (with backward compatibility)
                entity.faction = entity_data.get('faction', None)
                entity.name = entity_data.get('name', None)
                entity.age = entity_data.get('age', 0)
                entity.alignment = entity_data.get('alignment', None)  # Wizard
                entity.spell = entity_data.get('spell', None)  # Wizard
                entity.home_zone = entity_data.get('home_zone', None)  # Warrior
                entity.movement_pattern = entity_data.get('movement_pattern', None)
                entity.item_levels = entity_data.get('item_levels', {})
                entity.item_names = entity_data.get('item_names', {})
                entity.keeper = entity_data.get('keeper', False)

                # Ensure wizards from old saves have spell and alignment
                if entity.type == 'WIZARD':
                    if entity.spell is None:
                        entity.spell = random.choice(['heal', 'fireball', 'lightning', 'ice', 'enchant'])
                    if entity.alignment is None:
                        entity.alignment = 'peaceful' if random.random() < 0.75 else 'hostile'
                    if not hasattr(entity, 'spell_cooldown'):
                        entity.spell_cooldown = 0

                self.entities[entity_id] = entity

                # Recreate follower items in ITEMS dict for followers
                if entity_id in self.followers:
                    follower_name = f"{entity.type.lower()}_{entity_id}"
                    if follower_name not in ITEMS:
                        ITEMS[follower_name] = {
                            'color': entity.props['color'],
                            'name': f"{entity.type} Follower",
                            'is_follower': True,
                            'entity_id': entity_id
                        }
                    # Reconstruct follower_items entry if missing (old saves without this field)
                    if entity_id not in self.follower_items:
                        self.follower_items[entity_id] = follower_name

            # Load structure data and convert string keys back to tuples
            structures_loaded = save_data.get('structures', save_data.get('subscreens', {}))
            self.structures = {}
            for structure_key, structure_data in structures_loaded.items():
                deserialized_structure = {}
                for key, value in structure_data.items():
                    if key == 'chests':
                        # Convert chest position strings back to tuples
                        deserialized_chests = {}
                        for chest_key_str, loot_type in value.items():
                            x, y = map(int, chest_key_str.split(','))
                            deserialized_chests[(x, y)] = loot_type
                        deserialized_structure[key] = deserialized_chests
                    elif key in ('parent_screen', 'parent_cell', 'entrance', 'exit') and isinstance(value, list):
                        # JSON serialises tuples as lists — convert back so door-lookup
                        # comparisons (parent_cell == (x, y)) succeed on load.
                        deserialized_structure[key] = tuple(value)
                    elif key == 'entrances' and isinstance(value, list):
                        deserialized_structure[key] = [tuple(e) if isinstance(e, list) else e for e in value]
                    else:
                        deserialized_structure[key] = value
                self.structures[structure_key] = deserialized_structure

            self.opened_chests = set(save_data.get('opened_chests', []))
            self.chest_contents = save_data.get('chest_contents', {})
            self.chest_backgrounds = save_data.get('chest_backgrounds', {})
            self.next_structure_id = save_data.get('next_structure_id', save_data.get('next_subscreen_id', 0))

            # Load zone priority system data
            self.zone_connections = {}
            for zc_key, connections in save_data.get('zone_connections', {}).items():
                self.zone_connections[zc_key] = [tuple(c) for c in connections]

            self.structure_zones = {}
            for sz_key, sz_data in save_data.get('structure_zones', {}).items():
                sz_copy = dict(sz_data)
                if 'cell' in sz_copy and isinstance(sz_copy['cell'], list):
                    sz_copy['cell'] = tuple(sz_copy['cell'])
                self.structure_zones[sz_key] = sz_copy

            self.zone_structures = save_data.get('zone_structures', {})
            self.next_structure_zone_id = save_data.get('next_structure_zone_id', 0)
            self.zone_keepers = save_data.get('zone_keepers', {})
            self.zone_cave_systems = save_data.get('zone_cave_systems', {})

            # Restore tuple keys in screen data (chests, parent_screen, etc.)
            for screen_key, screen_data in self.screens.items():
                if 'chests' in screen_data and isinstance(screen_data['chests'], dict):
                    restored_chests = {}
                    for ck, loot in screen_data['chests'].items():
                        if isinstance(ck, str) and ',' in ck:
                            x, y = map(int, ck.split(','))
                            restored_chests[(x, y)] = loot
                        else:
                            restored_chests[ck] = loot
                    screen_data['chests'] = restored_chests
                for tuple_key in ['parent_screen', 'parent_cell', 'entrance', 'exit']:
                    if tuple_key in screen_data and isinstance(screen_data[tuple_key], list):
                        screen_data[tuple_key] = tuple(screen_data[tuple_key])
                if 'entrances' in screen_data and isinstance(screen_data['entrances'], list):
                    screen_data['entrances'] = [tuple(e) if isinstance(e, list) else e for e in screen_data['entrances']]

            # Ensure structure zones are also in self.screens (backward compat)
            for struct_key, struct_data in self.structure_zones.items():
                if struct_key not in self.screens and struct_key in self.structures:
                    self.screens[struct_key] = self.structures[struct_key]
                    self.screen_last_update.setdefault(struct_key, self.tick)

            # If player is in a structure, load that as current screen
            if self.player.get('in_structure') and self.player.get('structure_key'):
                structure_key = self.player['structure_key']
                if structure_key in self.structures:
                    self.current_screen = self.structures[structure_key]
                else:
                    # Structure doesn't exist — exit player to parent overworld zone.
                    # player['screen_x/y'] may be virtual coords; use structure_parent instead.
                    parent_info = self.player.get('structure_parent')
                    if parent_info and len(parent_info) >= 2:
                        parent_x, parent_y = parent_info[0], parent_info[1]
                    else:
                        parent_x, parent_y = 0, 0
                    self.player['in_structure'] = False
                    self.player['structure_key'] = None
                    self.player['structure_parent'] = None
                    self.player['screen_x'] = parent_x
                    self.player['screen_y'] = parent_y
                    self.current_screen = self.generate_screen(parent_x, parent_y)
            else:
                self.current_screen = self.generate_screen(
                    self.player['screen_x'],
                    self.player['screen_y']
                )
            self.attack_animations = []
            self.state = 'playing'
            # Restore active quest (default to FARM for older saves)
            self.active_quest = save_data.get('active_quest', 'FARM')
            # Restore NPC quests
            self.npc_quests = []
            for d in save_data.get('npc_quests', []):
                q = Quest(d['quest_type'])
                q.status           = d.get('status', 'active')
                q.target_entity_id = d.get('target_entity_id')
                q.target_location  = tuple(d['target_location']) if d.get('target_location') else None
                q.target_cell      = tuple(d['target_cell'])     if d.get('target_cell')     else None
                q.target_info      = d.get('target_info', '')
                q.target_zone      = d.get('target_zone')
                q.completed_count  = d.get('completed_count', 0)
                q._original_cell   = d.get('original_cell')
                q.progress         = d.get('progress', 0.0)
                self.npc_quests.append(NpcQuestSlot(d['npc_id'], q))
            self.active_npc_quest_npc_id = save_data.get('active_npc_quest_npc_id')
            # Autopilot grace period: don't engage for 15 seconds after loading
            self.last_input_tick = self.tick + 900
            self.bug_catcher.clear()
            print("Game loaded!")
        else:
            print("No save file found!")
