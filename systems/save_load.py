import json
import os
import random

from entity import Entity
from constants import ITEMS, COLORS


class SaveLoadMixin:
    """Handles saving and loading game state to/from JSON."""

    def save_game(self):
        """Save game to file"""
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
                'item_names': getattr(entity, 'item_names', {})
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

        # Convert subscreens tuple keys to strings for JSON serialization
        subscreens_serializable = {}
        for subscreen_key, subscreen_data in self.subscreens.items():
            serialized_subscreen = {}
            for key, value in subscreen_data.items():
                if key == 'chests':
                    # Convert chest position tuples to strings
                    serialized_chests = {}
                    for chest_pos, loot_type in value.items():
                        chest_key_str = f"{chest_pos[0]},{chest_pos[1]}"
                        serialized_chests[chest_key_str] = loot_type
                    serialized_subscreen[key] = serialized_chests
                else:
                    serialized_subscreen[key] = value
            subscreens_serializable[subscreen_key] = serialized_subscreen

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
            'inventory_tools': self.inventory.tools,
            'inventory_magic': self.inventory.magic,
            'inventory_followers': self.inventory.followers,
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
            'subscreens': subscreens_serializable,
            'opened_chests': list(self.opened_chests),  # Convert set to list for JSON
            'next_subscreen_id': self.next_subscreen_id,
            # Zone priority system
            'zone_connections': zone_connections_serializable,
            'structure_zones': structure_zones_serializable,
            'zone_structures': self.zone_structures,
            'next_structure_zone_id': self.next_structure_zone_id,
            'active_quest': self.active_quest,
        }
        with open('savegame.json', 'w') as f:
            json.dump(save_data, f)
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
            # Ensure player has subscreen fields
            if 'in_subscreen' not in self.player:
                self.player['in_subscreen'] = False
                self.player['subscreen_key'] = None
                self.player['subscreen_parent'] = None
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
            self.inventory.tools = save_data.get('inventory_tools', {})
            self.inventory.magic = save_data.get('inventory_magic', {})
            self.inventory.followers = save_data.get('inventory_followers', {})
            self.inventory.selected = save_data.get('inventory_selected', {
                'items': None, 'tools': None, 'magic': None, 'followers': None
            })

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

            # Load subscreen data and convert string keys back to tuples
            subscreens_loaded = save_data.get('subscreens', {})
            self.subscreens = {}
            for subscreen_key, subscreen_data in subscreens_loaded.items():
                deserialized_subscreen = {}
                for key, value in subscreen_data.items():
                    if key == 'chests':
                        # Convert chest position strings back to tuples
                        deserialized_chests = {}
                        for chest_key_str, loot_type in value.items():
                            x, y = map(int, chest_key_str.split(','))
                            deserialized_chests[(x, y)] = loot_type
                        deserialized_subscreen[key] = deserialized_chests
                    else:
                        deserialized_subscreen[key] = value
                self.subscreens[subscreen_key] = deserialized_subscreen

            self.opened_chests = set(save_data.get('opened_chests', []))
            self.next_subscreen_id = save_data.get('next_subscreen_id', 0)

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
                if struct_key not in self.screens and struct_key in self.subscreens:
                    self.screens[struct_key] = self.subscreens[struct_key]
                    self.screen_last_update.setdefault(struct_key, self.tick)

            # If player is in a subscreen, load that as current screen
            if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
                subscreen_key = self.player['subscreen_key']
                if subscreen_key in self.subscreens:
                    self.current_screen = self.subscreens[subscreen_key]
                else:
                    # Subscreen doesn't exist, exit player to parent
                    self.player['in_subscreen'] = False
                    self.player['subscreen_key'] = None
                    self.player['subscreen_parent'] = None
                    self.current_screen = self.generate_screen(
                        self.player['screen_x'],
                        self.player['screen_y']
                    )
            else:
                self.current_screen = self.generate_screen(
                    self.player['screen_x'],
                    self.player['screen_y']
                )
            self.attack_animations = []
            self.state = 'playing'
            # Restore active quest (default to FARM for older saves)
            self.active_quest = save_data.get('active_quest', 'FARM')
            # Autopilot grace period: don't engage for 15 seconds after loading
            self.last_input_tick = self.tick + 900
            print("Game loaded!")
        else:
            print("No save file found!")
