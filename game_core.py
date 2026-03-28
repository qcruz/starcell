"""
StarCell Game Core
Rendering, player systems, world gen, quests, save/load, zone updates.
"""
import sys
import os as _os
import time as _time
import datetime as _datetime

from constants import *
from entity import *
from debug.bug_catcher import BugCatcher
from debug.watchdog import Watchdog
from systems.sound_manager import SoundManager

_SETTINGS_PATH = 'settings.json'
_REAL_STDOUT = sys.stdout  # saved before any redirect

class GameCoreMixin:
    """Core game systems. Mixed into Game via multiple inheritance."""
    """First half of game logic - world generation, spawning, AI"""
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Procedural Adventure")
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)
        self.small_font = pygame.font.Font(None, 18)
        self.tiny_font = pygame.font.Font(None, 14)
        
        # Game state
        self.state = 'menu'
        self.player = {
            'x': 12, 'y': 9, 
            'screen_x': 0, 'screen_y': 0,
            'level': 1,
            'xp': 0,
            'xp_to_level': 100,
            'health': 100,
            'max_health': 100,
            'energy': 100,
            'max_energy': 100,
            'base_damage': 5,
            'blocking': False,
            'block_locked': False,
            'last_shift_press_tick': 0,
            'friendly_fire': False,      # OFF = cannot damage peaceful entities (press V to toggle)
            'last_attack_tick': 0,
            'in_structure': False,
            'structure_key': None,
            'structure_parent': None  # (parent_screen_x, parent_screen_y, parent_cell_x, parent_cell_y)
        }
        self.screens = {}
        self.current_screen = None
        self.tick = 0
        self.running = True
        self.inventory = Inventory()
        self.target_direction = 0  # 0=up, 1=down, 2=left, 3=right
        
        # Enchantment tracking
        # Cell enchantments: {screen_key: {(x,y): enchant_level}}
        self.enchanted_cells = {}
        # Entity enchantments: {entity_id: enchant_level}
        self.enchanted_entities = {}
        
        # Dropped items on cells: {screen_key: {(x,y): {item_name: count}}}
        self.dropped_items = {}

        # Buried items (not visible; dug up by player shovel or farmed): {screen_key: {(x,y): {item: count}}}
        self.buried_items = {}
        
        # Chest contents: {chest_key: {item_name: count}}
        self.chest_contents = {}
        
        # Track last update tick for each screen
        self.screen_last_update = {}
        
        # Structure system
        self.structures = {}  # {structure_key: structure_data}
        self.opened_chests = set()  # Track which chests have been looted
        self.next_structure_id = 0  # For generating unique structure IDs
        self.zone_cave_systems = {}  # {screen_key: cave_structure_key} - one cave system per zone
        
        # Zone connection and priority system
        # Connections map: {zone_key: [(connected_zone_key, connection_type, cell_x, cell_y), ...]}
        # connection_type: 'structure_entrance', 'structure_exit', 'zone_exit'
        self.zone_connections = {}
        # Priority scores: {zone_key: float} — higher = update sooner
        self.zone_priority = {}
        # Structure zone mapping: {structure_zone_key: {'parent_zone': key, 'type': str, 'cell': (x,y)}}
        self.structure_zones = {}
        # Reverse lookup: {parent_zone_key: [structure_zone_key, ...]}
        self.zone_structures = {}
        # Gravestone inscriptions: {screen_key: {(x,y): [name, ...]}}
        self.gravestone_names = {}
        # Next structure zone ID (structure zones use coords like (10000+id, 0))
        self.next_structure_zone_id = 0
        
        # Catch-up system
        self.last_input_tick = 0
        self.catchup_queue = []  # [(priority, screen_x, screen_y, cycles), ...]
        self.init_autopilot()  # Initialize autopilot state (from AutopilotMixin)
        
        # Weather system
        self.weather_timer = 0
        self.weather_cycle = random.randint(RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX)
        self.is_raining = False
        self.rain_duration = 0  # Initialize rain duration
        self.rain_timer = 0  # Separate timer for tracking rain duration
        self.zone_last_rain = {}  # {screen_key: tick} - track last rain per zone for crop decay
        self.zone_keepers = {}   # {zone_key: {keeper_type: entity_id}} — one keeper per slot per zone
        self.domains = {}        # {domain_id: {'name': str, 'type': 'biome'|'faction', 'biome': str|None, 'faction': str|None, 'zones': set()}}
        self._domain_counter = 0 # Auto-increment domain ID
        
        # Day/Night cycle
        self.day_night_timer = 0  # Cycles from 0 to DAY_NIGHT_CYCLE_LENGTH
        self.is_night = False
        
        # Probabilistic update system
        self.updates_this_tick = 0
        self.instantiated_zones = set()  # Track zones that exist
        
        # Raid event system
        self.zone_has_hostiles = {}  # {screen_key: bool} - tracks hostile presence per zone
        self.zone_has_faction_conflict = {}  # {screen_key: bool} - tracks if zone has competing factions
        self.zone_last_raid_check = {}  # {screen_key: tick} - tracks last raid check per zone
        
        # Faction system
        self.factions = {}  # {faction_name: {'warriors': [entity_ids], 'zones': [screen_keys]}}
        self.enchanted_cells = {}  # {(sx, sy, x, y): remaining_duration} - cells frozen by wizard enchant spell

        # Debug visualization
        self.debug_memory_lanes = False  # Shows trader memory lanes and targets
        self.debug_entity_ai = True  # Shows entity AI state and target info

        # Persistent settings (loaded from settings.json)
        self.ambient_music_enabled = True
        self.debug_prints_enabled = True
        self.autosave_enabled = True
        self._load_settings()

        # Load sprites
        self.load_sprites()

        # Attack animations
        self.attack_animations = []
       
        # Give starting tools
        self.inventory.add_item('axe', 1)
        self.inventory.add_item('hoe', 1)
        self.inventory.add_item('shovel', 1)
        self.inventory.add_item('pickaxe', 1)
        self.inventory.add_item('bucket', 1)
        self.inventory.add_item('bone_sword', 1)
        
        # Give starting spell
        self.inventory.add_magic('star_spell', 1)

        # Entity tracking: {entity_id: Entity}
        self.entities = {}
        self.next_entity_id = 0
        
        # Follower tracking: [entity_ids] - list of entity IDs that are followers
        self.followers = []
        # Maps entity_id → inventory item name used to summon that follower
        self.follower_items = {}  # {entity_id: item_name}
        
        # Entities per zone (overworld and structure): {zone_key: [entity_ids]}
        self.screen_entities = {}

        # Door mapping: {(zone_key, cell_x, cell_y): (target_zone_key, target_x, target_y)}
        # Links overworld entrance cells to structure zone entrances and back.
        self.door_map = {}
        
        # Quest System
        self.quests = {}  # {quest_type: Quest object}
        self.active_quest = 'FARM'  # Default active quest
        self.quest_ui_open = False
        self.quest_ui_selected = 0
        self.npc_quests = []  # list of NpcQuestSlot, max 3
        self.active_npc_quest_npc_id = None  # npc_id of the currently tracked NPC quest
        
        # Initialize all quest types
        for quest_type in QUEST_TYPES.keys():
            self.quests[quest_type] = Quest(quest_type)
        
        # Flag for initial world generation time passage
        self.needs_initial_time_passage = True

        # Time pass acceleration
        self.time_pass_active = False   # True while death/init simulation is running
        self.time_pass_speed  = 1.0     # Rate multiplier applied to all probabilistic systems
        
        # Trading System
        self.trader_display = None  # {entity_id: {recipes: [...], position: (x,y)}}
        self.trader_display_tick = 0
        self.inspected_npc = None       # Entity being inspected
        self.inspected_npc_tick = 0     # When inspection started
        self.inspect_cell_target = None # (x, y) of cell being inspected (no NPC at target)

        # Item UID registry — tracks individually identified items (quest/keeper targets)
        self._item_uid_counter = 0
        self.item_registry = {}
        # {uid: {'name': str, 'location': 'world'|'inventory',
        #         'holder': entity_id or (sx,sy,x,y), 'pos': (x,y), 'screen': (sx,sy)}}

        # Debug / bug-tracking
        self.bug_catcher = BugCatcher()
        self.watchdog = Watchdog(self.bug_catcher)
        self.show_dev_screen = False  # Toggled by Shift+I

        # Audio
        self.sound = SoundManager()
        self._apply_settings()  # apply after SoundManager exists

        # Last git push timestamp (shown on pause screen)
        try:
            import subprocess as _sp
            _script_dir = os.path.dirname(os.path.abspath(__file__))
            _res = _sp.run(
                ['git', 'log', '-1', '--format=%ci', 'origin/main'],
                capture_output=True, text=True, cwd=_script_dir, timeout=3
            )
            _raw = _res.stdout.strip()
            if _res.returncode == 0 and _raw:
                # Format: "2026-02-28 10:37:22 -0600" → "2026-02-28 10:37"
                self.last_push_time = ' '.join(_raw.split()[:2])[:16]
            else:
                self.last_push_time = 'Unknown'
        except Exception:
            self.last_push_time = 'Unknown'

    def load_sprites(self):
        """Load sprite images from individual PNG files"""
        # Initialize the sprite manager
        self.sprite_manager = SpriteManager()
        
        # Load individual sprite files from current directory and subdirectories
        sprite_files_loaded = 0
        
        # Determine base directory (where the game script lives)
        script_dir = os.path.dirname(os.path.abspath(__file__))
        cwd = os.getcwd()
        
        search_paths = [
            "",  # Current directory
            "sprites/",
            "starcell/sprites/",
            "starcell/sprites/grass_sprites/",
            "NPCs/",
            "animal sprites/",
            "sprites/NPCs/",
            "sprites/animal sprites/",
            # Also try relative to script directory (in case cwd differs)
            os.path.join(script_dir, ""),
            os.path.join(script_dir, "sprites") + os.sep,
            os.path.join(script_dir, "starcell", "sprites") + os.sep,
            os.path.join(script_dir, "starcell", "sprites", "grass_sprites") + os.sep,
            os.path.join(script_dir, "sprites", "grass_sprites") + os.sep,
            os.path.join(script_dir, "sprites", "NPCs") + os.sep,
            os.path.join(script_dir, "sprites", "animal sprites") + os.sep,
        ]
        
        for cell_type in ['GRASS', 'DIRT', 'SAND', 'STONE', 'WATER', 'DEEP_WATER',
                          'COBBLESTONE',
                          'TREE1', 'TREE2', 'TREE3', 'FLOWER',
                          'CARROT1', 'CARROT2', 'CARROT3',
                          'CAMP', 'HOUSE', 'STONE_HOUSE', 'WOOD', 'PLANKS',
                          'WALL', 'CAVE', 'MINESHAFT', 'SOIL', 'MEAT', 'FUR', 'BONES',
                          'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL',
                          'STAIRS_DOWN', 'STAIRS_UP',
                          'CACTUS', 'BARREL', 'RUINED_SANDSTONE_COLUMN', 'BUSH', 'EMPTY_CRATE',
                          'FLOWER_PATTERN1', 'FLOWER_PATTERN2', 'FLOWER_PATTERN3']:
            
            # Skip if already loaded
            if cell_type in self.sprite_manager.sprites:
                continue
            
            # Try lowercase filename in each search path
            filename_base = f"{cell_type.lower()}.png"
            
            for search_path in search_paths:
                filename = os.path.join(search_path, filename_base) if search_path else filename_base
                
                if os.path.exists(filename):
                    try:
                        # Load image - works with both PNG and JPEG
                        sprite_img = pygame.image.load(filename)
                        
                        # Check if image has transparency (RGBA)
                        if sprite_img.get_alpha() is not None or sprite_img.get_colorkey() is not None:
                            # Has transparency - convert to RGBA (for objects like trees)
                            sprite_img = sprite_img.convert_alpha()
                        else:
                            # No transparency - convert to RGB (for base terrain)
                            sprite_img = sprite_img.convert()
                        
                        # Scale to game cell size
                        sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                        self.sprite_manager.sprites[cell_type] = sprite_img
                        sprite_files_loaded += 1
                        break  # Found it, stop searching paths for this cell type
                    except Exception as e:
                        print(f"Failed to load {filename}: {e}")
        
        # Load cell variant sprites (grass1, grass2, etc.)
        variant_search_count = 0
        variant_loaded_count = 0
        variant_missing = []
        for cell_type, props in CELL_TYPES.items():
            variants = props.get('variants', {})
            for variant_name in variants:
                if variant_name == cell_type:
                    continue  # Skip base type — already loaded above
                if variant_name in self.sprite_manager.sprites:
                    continue  # Already loaded
                
                variant_search_count += 1
                filename_base = f"{variant_name.lower()}.png"
                found = False
                for search_path in search_paths:
                    filename = os.path.join(search_path, filename_base) if search_path else filename_base
                    if os.path.exists(filename):
                        try:
                            sprite_img = pygame.image.load(filename)
                            if sprite_img.get_alpha() is not None or sprite_img.get_colorkey() is not None:
                                sprite_img = sprite_img.convert_alpha()
                            else:
                                sprite_img = sprite_img.convert()
                            sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                            self.sprite_manager.sprites[variant_name] = sprite_img
                            sprite_files_loaded += 1
                            variant_loaded_count += 1
                            found = True
                            break
                        except Exception as e:
                            variant_missing.append(f"{variant_name}: load error - {e}")
                if not found:
                    checked = [os.path.join(sp, filename_base) if sp else filename_base for sp in search_paths]
                    variant_missing.append(f"{variant_name}: not found at {checked}")
        
        # Load entity animation sprites
        # Support both 2-frame and 3-frame animations
        # 2-frame: entity_direction_1, entity_direction_2
        # 3-frame: entity_direction_1, entity_direction_still, entity_direction_2
        entity_types = ['sheep', 'wolf', 'deer', 'farmer', 'guard', 'trader',
                       'lumberjack', 'miner', 'blacksmith', 'bandit', 'goblin',
                       'king', 'skeleton', 'warrior', 'commander', 'yellow termite', 'wizard',
                       'black bat', 'red bird', 'butterfly', 'chicken', 'blackSpider']
        directions = ['up', 'down', 'left', 'right']
        
        for entity_type in entity_types:
            for direction in directions:
                # Try to load 3-frame animation: 1, still, 2
                for frame_name in ['1', 'still', '2']:
                    # Try multiple naming formats
                    naming_formats = [
                        f"{entity_type}_{direction}_{frame_name}",  # entity_direction_frame
                        f"{entity_type} {direction}_{frame_name}",  # "entity direction_frame"
                        f"{entity_type} {direction} {frame_name}",  # "entity direction frame"
                    ]
                    
                    for sprite_name_format in naming_formats:
                        filename_base = f"{sprite_name_format}.png"
                        found = False
                        
                        for search_path in search_paths:
                            filename = os.path.join(search_path, filename_base) if search_path else filename_base
                            
                            if os.path.exists(filename):
                                try:
                                    sprite_img = pygame.image.load(filename).convert_alpha()
                                    sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                                    
                                    # Store with normalized name (underscores only, lowercased to match HUD lookup)
                                    normalized_name = f"{entity_type}_{direction}_{frame_name}".lower()
                                    self.sprite_manager.sprites[normalized_name] = sprite_img
                                    sprite_files_loaded += 1
                                    found = True
                                    break
                                except Exception as e:
                                    print(f"Failed to load {filename}: {e}")
                        
                        if found:
                            break  # Found with this format, stop trying other formats
                
                # Also try old 2-frame format (backward compatibility)
                for frame in [1, 2]:
                    sprite_name = f"{entity_type}_{direction}_{frame}"
                    
                    # Only load if not already loaded by 4-frame system
                    if sprite_name in self.sprite_manager.sprites:
                        continue
                    
                    filename_base = f"{sprite_name}.png"
                    
                    for search_path in search_paths:
                        filename = os.path.join(search_path, filename_base) if search_path else filename_base
                        
                        if os.path.exists(filename):
                            try:
                                sprite_img = pygame.image.load(filename).convert_alpha()
                                sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                                self.sprite_manager.sprites[sprite_name] = sprite_img
                                sprite_files_loaded += 1
                                break
                            except Exception as e:
                                print(f"Failed to load {filename}: {e}")
        
        # Load biome-specific wall variants
        wall_variants = ['wall_forest', 'wall_desert', 'wall_plains', 
                        'wall_mountains', 'wall_tundra', 'wall_swamp']
        
        for wall_variant in wall_variants:
            filename_base = f"{wall_variant}.png"
            
            for search_path in search_paths:
                filename = os.path.join(search_path, filename_base) if search_path else filename_base
                
                if os.path.exists(filename):
                    try:
                        sprite_img = pygame.image.load(filename).convert()
                        sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                        self.sprite_manager.sprites[wall_variant] = sprite_img
                        sprite_files_loaded += 1
                        break
                    except Exception as e:
                        print(f"Failed to load {filename}: {e}")
        
        # Load item sprites (for dropped item overlays)
        # Collect unique sprite_name values from ITEMS definitions
        item_sprite_names = set()
        for item_key, item_data in ITEMS.items():
            if 'sprite_name' in item_data:
                item_sprite_names.add(item_data['sprite_name'])
            # Also try loading by item key name directly
            item_sprite_names.add(item_key)
        
        # Also load utility sprites (itembag, etc.)
        item_sprite_names.add('itembag')
        
        for sprite_name in item_sprite_names:
            if sprite_name in self.sprite_manager.sprites:
                continue  # Already loaded (e.g. same as a cell sprite)
            filename_base = f"{sprite_name}.png"
            for search_path in search_paths:
                filename = os.path.join(search_path, filename_base) if search_path else filename_base
                if os.path.exists(filename):
                    try:
                        sprite_img = pygame.image.load(filename).convert_alpha()
                        sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                        self.sprite_manager.sprites[sprite_name] = sprite_img
                        sprite_files_loaded += 1
                        break
                    except Exception as e:
                        print(f"Failed to load item sprite {filename}: {e}")
        
        # Load sprites whose filenames don't match the standard key.lower()+".png" pattern,
        # or that need guaranteed convert_alpha() regardless of alpha-detection result.
        _explicit_sprites = {
            'IRON_ORE':              'ironore.png',
            'WELL':                  'well.png',
            'iron_sword':            'sword.png',
            'RUINED_SANDSTONE_COLUMN': 'ruined_sandstone_column.png',
            'STONE_HOUSE':           'stone_house.png',
            'CACTUS':                'cactus.png',
            'BARREL':                'barrel.png',
            'BUSH':                  'bush.png',
            'EMPTY_CRATE':           'emptycrate.png',
            'FLOWER_PATTERN1':       'flowerpattern1.png',
            'FLOWER_PATTERN2':       'flowerpattern2.png',
            'FLOWER_PATTERN3':       'flowerpattern3.png',
            # Chest variants: LOCKED_CHEST = old chest, CHEST = closeable, OPEN_CHEST = looted
            'LOCKED_CHEST':          'chest.png',
            'CHEST':                 'closed_chest.png',
            'OPEN_CHEST':            'open_chest.png',
            'GRAVESTONE':            'gravestone.png',
            'BROKEN_GRAVESTONE':     'broken_gravestone.png',
            'BED_BLUE':              'bed_blue.png',
            'BED_WHITE':             'bed_white.png',
            'DESERT_WELL':           'desert_well.png',
            'CLIFF':                 'cliff_wall.png',
            'STAIRS_DOWN':           'stairs_down.png',
            'STAIRS_UP':             'stairs_up.png',
            'BOOKSHELF':             'bookshelf.png',
            'WOOD_CHAIR':            'wood_chair.png',
            'WOOD_TABLE':            'wood_table.png',
            'WATER_TROUGH':          'water_trough.png',
            'SMALL_POTTED_PLANT':    'small_potted_plant.png',
            'BLUE_MUSHROOM':         'blue_mushroom.png',
            # Item sprites
            'bottle':                'bottle.png',
            'bottles':               'bottles.png',
            'pickaxe':               'pickaxe.png',
            # UI sprites (faction banners — not items, so not found by the ITEMS loop)
            'blue_banner':           'blue_banner.png',
            'red_banner':            'red_banner.png',
            # Attack swipe animations — directional
            'swipe_down':            'down_swipe.png',
            'swipe_up':              'up_swipe.png',
            'swipe_left':            'left_swipe.png',
            'swipe_right':           'right_swipe.png',
        }

        # Weapon / armour sprites — subdir has a space so they can't be found by the
        # generic search loop above; load them explicitly with the full relative path.
        _wa_dir = os.path.join(script_dir, 'sprites', 'weapons and armour')
        _wa_sprites = {
            'iron_sword':      'sword_red_handle.png',
            'bone_sword':      'sword_red_handle.png',
            'enchanted_sword': 'sword_gold.png',
            'club':            'club_red.png',
            'bow':             'bow.png',
            'bow_metal':       'bow_metal.png',
            'staff_red':       'staff_red.png',
            'spear':           'spear_black.png',
            'warhammer':       'warhammer_red_bronze.png',
            'shield':          'shield_metal.png',
            'shield_bronze':   'shield_red_bronze.png',
            'armour_chest':    'armour_chest_metal.png',
            'armour_helm':     'armour_helm_metal.png',
            'armour_legs':     'armour_legs_metal.png',
            'armour_shoes':    'armour_shoes_metal.png',
        }
        for sprite_key, fname in _wa_sprites.items():
            if sprite_key in self.sprite_manager.sprites:
                continue
            path = os.path.join(_wa_dir, fname)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.sprite_manager.sprites[sprite_key] = pygame.transform.scale(img, (CELL_SIZE, CELL_SIZE))
                    sprite_files_loaded += 1
                except Exception as e:
                    print(f"Failed to load weapon/armour sprite {fname}: {e}")
        for sprite_key, filename_base in _explicit_sprites.items():
            if sprite_key in self.sprite_manager.sprites:
                continue
            for search_path in search_paths:
                filename = os.path.join(search_path, filename_base) if search_path else filename_base
                if os.path.exists(filename):
                    try:
                        sprite_img = pygame.image.load(filename).convert_alpha()
                        sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                        self.sprite_manager.sprites[sprite_key] = sprite_img
                        sprite_files_loaded += 1
                        break
                    except Exception as e:
                        print(f"Failed to load {filename}: {e}")

        # If individual files were loaded, use them
        if sprite_files_loaded > 0:
            print("\n" + "=" * 60)
            print("LOADING SPRITE SYSTEM...")
            print("=" * 60)
            print(f"✓ Loaded {sprite_files_loaded} individual sprite files")
            
            # Debug: Show what was loaded
            print("\nLoaded sprites:")
            for sprite_name in sorted(self.sprite_manager.sprites.keys()):
                sprite = self.sprite_manager.sprites[sprite_name]
                has_alpha = sprite.get_flags() & pygame.SRCALPHA
                print(f"  - {sprite_name}: {sprite.get_size()}, alpha={'YES' if has_alpha else 'NO'}")
            
            # Don't generate structure sprites - only use actual sprite files
            # This ensures cells without sprites show as colored rectangles with labels

            # Generate dev spell sprites (summon/transform for all NPC types)
            from data.entities import ENTITY_TYPES
            self.sprite_manager.create_dev_spell_sprites(ENTITY_TYPES)

            loaded_sprites = self.sprite_manager.get_all_sprite_names()
            print(f"✓ Total sprites available: {len(loaded_sprites)}")
            
            # Variant sprite report
            if variant_search_count > 0:
                print(f"\nCell variants: {variant_loaded_count}/{variant_search_count} loaded")
                if variant_missing:
                    for msg in variant_missing[:5]:  # Show first 5 missing
                        print(f"  ✗ {msg}")
            
            print("=" * 60 + "\n")
            self.use_sprites = True
        else:
            # No sprites found, use color fallback
            print("\n" + "=" * 60)
            print("No sprite files found - using colored rectangles")
            print("=" * 60)
            print("To use sprites, place PNG files in game directory:")
            print("  Examples: grass.png, dirt.png, sand.png, water.png, etc.")
            print("=" * 60 + "\n")
            self.use_sprites = False
        
        # Legacy: Load from starcell/sprites folder if it exists
        self.sprites = {}
        sprites_dir = 'starcell/sprites/'
        if os.path.exists(sprites_dir):
            for filename in os.listdir(sprites_dir):
                if filename.endswith('.png'):
                    sprite_name = filename[:-4].upper()
                    sprite_path_local = os.path.join(sprites_dir, filename)
                    try:
                        sprite_img = pygame.image.load(sprite_path_local)
                        sprite_img = pygame.transform.scale(sprite_img, (CELL_SIZE, CELL_SIZE))
                        self.sprites[sprite_name] = sprite_img
                    except Exception as e:
                        print(f"Failed to load sprite {filename}: {e}")
    
    def is_idle(self):
        """Check if player has been idle for catch-up window"""
        return self.tick - self.last_input_tick > 60  # 1 second idle
    
    def update_cells(self):
        """Update cell growth and changes for all screens based on distance"""
        # Update current screen more frequently
        if self.tick % 60 == 0:
            # Current zone full update
            screen_x = self.player['screen_x']
            screen_y = self.player['screen_y']
            screen_key = f"{screen_x},{screen_y}"
            
            if screen_key in self.screens:
                self.bug_catcher.log_zone_cells(self.tick, screen_key, self.screens[screen_key]['grid'])
                self.apply_cellular_automata(screen_x, screen_y)
                self.decay_dropped_items(screen_x, screen_y)
                self.decay_overworld_chests(screen_key)
                self.decay_items_to_buried(screen_key)
                self.decay_buried_items(screen_key)

        # Update nearby screens less frequently
        if self.tick % 180 == 0:  # Every 3 seconds
            # Update adjacent screens (distance 1)
            for dx in [-1, 0, 1]:
                for dy in [-1, 0, 1]:
                    if dx == 0 and dy == 0:
                        continue  # Skip current screen
                    screen_x = self.player['screen_x'] + dx
                    screen_y = self.player['screen_y'] + dy
                    screen_key = f"{screen_x},{screen_y}"

                    if screen_key in self.screens:
                        self.apply_cellular_automata(screen_x, screen_y)
                        self.decay_dropped_items(screen_x, screen_y)
                        self.decay_overworld_chests(screen_key)
                        self.decay_items_to_buried(screen_key)
                        self.decay_buried_items(screen_key)

        # Update distant screens even less frequently
        if self.tick % 600 == 0:  # Every 10 seconds
            # Update screens at distance 2
            for dx in [-2, -1, 0, 1, 2]:
                for dy in [-2, -1, 0, 1, 2]:
                    distance = abs(dx) + abs(dy)  # Manhattan distance
                    if distance <= 1 or distance > 2:
                        continue
                    screen_x = self.player['screen_x'] + dx
                    screen_y = self.player['screen_y'] + dy
                    screen_key = f"{screen_x},{screen_y}"

                    if screen_key in self.screens:
                        self.apply_cellular_automata(screen_x, screen_y)
                        self.decay_dropped_items(screen_x, screen_y)
                        self.decay_overworld_chests(screen_key)
                        self.decay_items_to_buried(screen_key)
                        self.decay_buried_items(screen_key)
            pass  # distance-2 update complete

    def update_entities(self):
        """Update all entities - AI, movement, stats.

        On-screen entities (screen_distance == 0) get AI updated every game
        tick so combat move_cooldown counts down at the correct 60-fps rate.
        Stat decay/healing and off-screen AI are still throttled every 30 ticks
        to keep performance reasonable.
        """
        do_slow_update = (self.tick % 30 == 0)

        # Spawning check every 0.5 s
        if do_slow_update:
            self.check_zone_spawning()

        entities_to_remove = []

        player_screen_x = self.player['screen_x']
        player_screen_y = self.player['screen_y']

        for entity_id, entity in list(self.entities.items()):
            screen_distance = abs(entity.screen_x - player_screen_x) + abs(entity.screen_y - player_screen_y)

            # Remove dead entities FIRST (regardless of distance)
            if not entity.is_alive():
                entities_to_remove.append(entity_id)
                continue

            # Only update entities within 2 screens of player
            if screen_distance > 2:
                continue

            # ── Slow path (every 30 ticks): stat decay, healing, split ────
            if do_slow_update:
                entity_screen_key = f"{entity.screen_x},{entity.screen_y}"
                if entity.type.endswith('_double'):
                    if self.try_split_double_entity(entity_id, entity, entity_screen_key):
                        continue  # Entity was split — re-evaluate next tick

                entity.decay_stats()

                heal_boost = 1.0
                if not entity.props.get('hostile', False):
                    screen_key = f"{entity.screen_x},{entity.screen_y}"
                    if screen_key in self.screens:
                        screen = self.screens[screen_key]
                        for dx in range(-3, 4):
                            for dy in range(-3, 4):
                                check_x = entity.x + dx
                                check_y = entity.y + dy
                                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                    cell = screen['grid'][check_y][check_x]
                                    if cell == 'CAMP':
                                        heal_boost = 2.0
                                        break
                                    elif cell == 'HOUSE':
                                        heal_boost = 3.0
                                        break
                            if heal_boost > 1.0:
                                break
                if (self.tick - getattr(entity, 'last_attacked_tick', 0)) > 120:
                    entity.regenerate_health(heal_boost)

            # ── AI update: on-screen every tick, off-screen throttled ──────
            if screen_distance == 0:
                self.update_entity_ai(entity_id, entity)
                self.update_structure_npc_behavior(entity_id, entity)
            elif screen_distance == 1:
                if self.tick % 60 == 0:
                    self.update_entity_ai(entity_id, entity)
                    self.update_structure_npc_behavior(entity_id, entity)
            else:
                if self.tick % 90 == 0:
                    self.update_entity_ai(entity_id, entity)
                    self.update_structure_npc_behavior(entity_id, entity)

        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)
    
    def remove_entity(self, entity_id):
        """Remove an entity from the game"""
        if entity_id not in self.entities:
            return
        
        entity = self.entities[entity_id]
        screen_key = f"{entity.screen_x},{entity.screen_y}"
        
        # Track and log death cause
        if entity.health <= 0:
            _dc = getattr(self, 'death_counts', {})
            if hasattr(entity, 'age') and hasattr(entity, 'max_age') and entity.age > entity.max_age:
                _dc['old_age'] = _dc.get('old_age', 0) + 1
            elif entity.hunger <= 0:
                _dc['starvation'] = _dc.get('starvation', 0) + 1
            elif entity.thirst <= 0:
                _dc['dehydration'] = _dc.get('dehydration', 0) + 1
            elif getattr(entity, 'killed_by', None) is not None:
                _dc['combat'] = _dc.get('combat', 0) + 1
            else:
                _dc['other'] = _dc.get('other', 0) + 1
            self.death_counts = _dc
        
        # Free keeper slot if this entity was a keeper
        if getattr(entity, 'keeper', False):
            for zone_key, slots in self.zone_keepers.items():
                for ktype, eid in list(slots.items()):
                    if eid == entity_id:
                        del slots[ktype]
                        break

        # Broadcast quest completion to all keeper NPCs targeting this entity
        for watcher_id, watcher in list(self.entities.items()):
            kt = getattr(watcher, 'keeper_target', None)
            if kt and kt.get('type') == 'entity' and kt.get('ref') == entity_id:
                watcher.keeper_target = None
                watcher.keeper_target_pos = None
                self._try_complete_assigned_quest(watcher)

        # Player quest targeting this entity: let check_quest_completion handle the
        # kill on the next update_quests tick — entity.is_dead (health<=0) triggers
        # proper completion with XP and sound. Don't clear_target() here or the
        # completion logic is bypassed.

        # Remove from followers if it was a follower
        if entity_id in self.followers:
            self.followers.remove(entity_id)
            item_name = self.follower_items.pop(entity_id, None)
            if item_name and self.inventory.has_item(item_name):
                self.inventory.remove_item(item_name, 1)
            print(f"{entity.type} follower has died!")

        # Collect all item drops into a single dict before placing them
        all_item_drops = {}  # {item_name: count}

        # Cell-placement drops (not items — apply immediately)
        if 'drops' in entity.props:
            for drop in entity.props['drops']:
                if random.random() < drop['chance']:
                    if 'cell' in drop:
                        if screen_key in self.screens:
                            cx = max(1, min(GRID_WIDTH - 2, entity.x))
                            cy = max(1, min(GRID_HEIGHT - 2, entity.y))
                            self.screens[screen_key]['grid'][cy][cx] = drop['cell']
                    elif 'item' in drop:
                        item_name = drop['item']
                        all_item_drops[item_name] = all_item_drops.get(item_name, 0) + drop.get('amount', 1)

        # Magic rune chance
        if random.random() < 0.15:
            all_item_drops['magic_rune'] = all_item_drops.get('magic_rune', 0) + 1

        # Entity inventory drops — unique items survive intact; common items 40% destruction per item
        _UNIQUE_FLAGS = ('is_tool', 'is_spell', 'is_follower', 'magic_damage', 'armor')
        for item_name, count in entity.inventory.items():
            item_data = ITEMS.get(item_name, {})
            if any(item_data.get(f) for f in _UNIQUE_FLAGS):
                all_item_drops[item_name] = all_item_drops.get(item_name, 0) + count
            else:
                surviving = sum(1 for _ in range(count) if random.random() > 0.40)
                if surviving > 0:
                    all_item_drops[item_name] = all_item_drops.get(item_name, 0) + surviving

        if all_item_drops:
            if screen_key not in self.dropped_items:
                self.dropped_items[screen_key] = {}

            # Drop everything at the exact cell where the entity died
            pile_x = max(1, min(GRID_WIDTH - 2, entity.x))
            pile_y = max(1, min(GRID_HEIGHT - 2, entity.y))
            pile_key = (pile_x, pile_y)
            if pile_key not in self.dropped_items[screen_key]:
                self.dropped_items[screen_key][pile_key] = {}
            for item_name, count in all_item_drops.items():
                self.dropped_items[screen_key][pile_key][item_name] = \
                    self.dropped_items[screen_key][pile_key].get(item_name, 0) + count
        
        # Remove from screen entities list
        if screen_key in self.screen_entities:
            if entity_id in self.screen_entities[screen_key]:
                self.screen_entities[screen_key].remove(entity_id)

        # Remove from any structure entities lists (catches entities that die inside structures)
        for sub_list in self.screen_entities.values():
            if entity_id in sub_list:
                sub_list.remove(entity_id)
        
        # Check if this was a hostile entity and zone is now clear
        if entity.props.get('hostile', False):
            self.check_zone_clear_hostiles(screen_key)
        else:
            # Peaceful entity died — maybe place a gravestone
            self._maybe_spawn_gravestone(entity, screen_key)

        # Remove from entities dict
        del self.entities[entity_id]

    def _maybe_spawn_gravestone(self, entity, screen_key):
        """Spawn or inscribe a gravestone when a named humanoid NPC dies."""
        # Only peaceful, named humanoids — skip animals, hostile types, and unnamed entities
        props = ENTITY_TYPES.get(entity.type, {})
        if not props.get('humanoid') or props.get('hostile') or not entity.name:
            return
        name = entity.name

        # If entity died inside a structure zone, resolve to the parent overworld zone
        overworld_key = screen_key
        if screen_key not in self.screens and screen_key in self.structures:
            parent = self.structures[screen_key].get('parent_screen')
            if parent:
                overworld_key = f"{parent[0]},{parent[1]}"

        grid = self.screens.get(overworld_key, {}).get('grid')

        # Zone must have at least one house/stone_house cell in the actual grid
        has_house = grid and any(
            grid[y][x] in ('HOUSE', 'STONE_HOUSE')
            for y in range(GRID_HEIGHT)
            for x in range(GRID_WIDTH)
        )
        if not has_house:
            return

        level = getattr(entity, 'level', 1)
        if level < 2 and random.random() >= 0.40:
            return
        if not grid:
            return

        # Count existing gravestones
        existing = [
            (x, y)
            for y in range(GRID_HEIGHT)
            for x in range(GRID_WIDTH)
            if grid[y][x] == 'GRAVESTONE'
        ]

        zone_gs = self.gravestone_names.setdefault(overworld_key, {})

        if len(existing) >= 5:
            # Add name to an existing gravestone with room (max 10 names)
            candidates = [pos for pos in existing if len(zone_gs.get(pos, [])) < 10]
            if candidates:
                chosen = random.choice(candidates)
                zone_gs.setdefault(chosen, []).append(name)
            return

        # Only place near existing gravestones — no corner fallback
        _open = {'GRASS', 'DIRT', 'SAND', 'COBBLESTONE', 'SOIL'}
        cluster_pos = self.find_cluster_position(overworld_key, 'GRAVESTONE', radius=5)
        if cluster_pos:
            cx, cy = cluster_pos
            if grid[cy][cx] in _open:
                grid[cy][cx] = 'GRAVESTONE'
                zone_gs[(cx, cy)] = [name]

    def check_follower_integrity(self):
        """Every-tick check: ensure followers are alive, non-hostile, not targeting player."""
        stale_ids = []
        for entity_id in list(self.followers):
            entity = self.entities.get(entity_id)
            if entity is None or not entity.is_alive():
                stale_ids.append(entity_id)
                continue
            # If follower is somehow targeting the player, clear it
            if getattr(entity, 'current_target', None) == 'player':
                entity.in_combat = False
                entity.current_target = None
                entity.ai_state = 'idle'
            # Ensure hostile flag stays off
            if entity.props.get('hostile', False):
                entity.props['hostile'] = False

        for entity_id in stale_ids:
            self.followers.remove(entity_id)
            item_name = self.follower_items.pop(entity_id, None)
            if item_name and self.inventory.has_item(item_name):
                self.inventory.remove_item(item_name, 1)
        # Clean up follower_items entries with no matching follower
        for entity_id in list(self.follower_items.keys()):
            if entity_id not in self.followers:
                self.follower_items.pop(entity_id, None)

    def check_npc_inspection(self):
        """Inspect whatever the player is facing when Shift is held or inspect tool is active."""
        if getattr(self, 'autopilot', False):
            self.inspected_npc = None
            self.inspect_cell_target = None
            return

        keys = pygame.key.get_pressed()
        shift_held = keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]
        _ts_idx = self.inventory.selected_tool_slot_idx
        inspect_tool_active = (
            _ts_idx is not None and
            _ts_idx < len(self.inventory.tool_slots) and
            self.inventory.tool_slots[_ts_idx] == 'inspect'
        )
        if not (shift_held or inspect_tool_active):
            self.inspected_npc = None
            self.inspect_cell_target = None
            return

        # Hostile within 2 cells suppresses inspect entirely
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        px, py = self.player['x'], self.player['y']
        for eid in self.screen_entities.get(screen_key, []):
            if eid in self.entities:
                e = self.entities[eid]
                if e.props.get('hostile', False) and abs(e.x - px) + abs(e.y - py) <= 2:
                    self.inspected_npc = None
                    self.inspect_cell_target = None
                    return

        target = self.get_target_cell()
        target = self.get_target_cell()
        if not target:
            self.inspected_npc = None
            self.inspect_cell_target = None
            return

        check_x, check_y = target
        candidates = self.screen_entities.get(screen_key, [])

        # NPC at target cell?
        for entity_id in candidates:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.x == check_x and entity.y == check_y:
                    if entity.props.get('is_autopilot_proxy', False):
                        self.inspected_npc = None
                        self.inspect_cell_target = None
                        return
                    self.inspected_npc = entity_id
                    self.inspect_cell_target = None
                    self.inspected_npc_tick = self.tick
                    if not entity.props.get('hostile'):
                        entity.is_idle = True
                        entity.idle_timer = 30
                        entity.idle_duration = 30
                    return

        # No NPC — inspect the cell/items at target
        self.inspected_npc = None
        self.inspect_cell_target = (check_x, check_y)
    
    def is_at_corner(self, x, y):
        """Check if position is near a zone corner"""
        # Define corners as 3x3 areas in each corner
        corner_size = 3
        # Top-left corner
        if x < corner_size and y < corner_size:
            return True
        # Top-right corner
        if x >= GRID_WIDTH - corner_size and y < corner_size:
            return True
        # Bottom-left corner
        if x < corner_size and y >= GRID_HEIGHT - corner_size:
            return True
        # Bottom-right corner
        if x >= GRID_WIDTH - corner_size and y >= GRID_HEIGHT - corner_size:
            return True
        return False
    
    def get_nearest_corner_target(self, x, y):
        """Get the nearest corner position for miner to target"""
        corners = [
            (2, 2),  # Top-left
            (GRID_WIDTH - 3, 2),  # Top-right
            (2, GRID_HEIGHT - 3),  # Bottom-left
            (GRID_WIDTH - 3, GRID_HEIGHT - 3)  # Bottom-right
        ]
        
        # Find closest corner
        closest = None
        closest_dist = float('inf')
        for corner_x, corner_y in corners:
            dist = abs(x - corner_x) + abs(y - corner_y)
            if dist < closest_dist:
                closest_dist = dist
                closest = (corner_x, corner_y)
        
        return closest
    
    def is_entity_at_position(self, x, y, screen_key, exclude_entity=None):
        """Check if any entity is at the given position (for collision detection)"""
        if screen_key not in self.screen_entities:
            return False
        
        for entity_id in self.screen_entities[screen_key]:
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            
            # Skip the entity we're checking for (don't collide with self)
            if exclude_entity and entity is exclude_entity:
                continue
            
            # Check if entity is at this position
            if entity.x == x and entity.y == y:
                return True
        
        return False
    
    def update_screen_cells(self, screen_x, screen_y):
        """Update cells for a specific screen coordinate"""
        key = f"{screen_x},{screen_y}"
        
        # Only update if screen exists (has been generated)
        if key not in self.screens:
            return
        
        screen = self.screens[key]
        
        # Apply rain effects to nearby screens
        if self.is_raining:
            distance = abs(screen_x - self.player['screen_x']) + abs(screen_y - self.player['screen_y'])
            if distance <= 2:  # Rain affects nearby screens
                self.apply_rain(screen_x, screen_y)
        
        # BugCatcher: snapshot HOUSE/STONE_HOUSE before cell updates (player zone only)
        player_zone = f"{self.player['screen_x']},{self.player['screen_y']}"
        if key == player_zone:
            self.bug_catcher.log_zone_cells(self.tick, key, screen['grid'])

        # Apply cellular automata rules first
        self.apply_cellular_automata(screen_x, screen_y)

        # Then apply normal growth/decay
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                # Skip enchanted cells - they don't grow or decay
                if self.is_cell_enchanted(x, y, key):
                    continue
                
                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]
                    
                    # Growth
                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['grows_to'])
                    
                    # Degradation (for crops and cobblestone)
                    elif 'degrades_to' in cell_info:
                        base_rate = cell_info.get('degrade_rate', 0)
                        decay_target = cell_info['degrades_to']

                        # Carrots decay faster on hostile terrain (cobblestone/sand)
                        if cell in ('CARROT1', 'CARROT2', 'CARROT3'):
                            _has_cob = _has_sand = False
                            for _nx, _ny in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
                                if 0 <= _nx < GRID_WIDTH and 0 <= _ny < GRID_HEIGHT:
                                    _nc = screen['grid'][_ny][_nx]
                                    if _nc == 'COBBLESTONE':
                                        _has_cob = True
                                    elif _nc == 'SAND':
                                        _has_sand = True
                            if _has_cob:
                                base_rate *= 50.0
                            elif _has_sand:
                                base_rate *= 10.0
                                if cell == 'CARROT1':
                                    decay_target = 'DIRT'

                        if random.random() < base_rate:
                            # Cobblestone: only decay outside center lanes and away from structures
                            if cell == 'COBBLESTONE':
                                center_x = GRID_WIDTH // 2
                                center_y = GRID_HEIGHT // 2
                                if abs(y - center_y) <= 2 or abs(x - center_x) <= 2:
                                    continue
                                skip = False
                                for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                                        if screen['grid'][ny][nx] in ('HOUSE', 'CAMP', 'CAVE', 'MINESHAFT'):
                                            skip = True
                                            break
                                if skip:
                                    continue
                            self.set_grid_cell(screen, x, y, decay_target)

        # Track last update
        self.screen_last_update[key] = self.tick
    
    def handle_input(self):
        """Handle keyboard and mouse input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Mark input for idle detection — skip synthetic autopilot events
            if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN]:
                if not getattr(event, '_ap_synthetic', False):
                    self.mark_input()
            
            if event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1 and self.state == 'menu':
                    self._handle_menu_click(event.pos)
                elif event.button == 1 and self.state == 'playing':
                    if self.handle_npc_trade_click(event.pos):
                        self.gain_xp(1)
                    else:
                        self.handle_inventory_click(event.pos)
                    self.handle_quest_ui_click(event.pos)

            if event.type == pygame.KEYUP:
                if event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                    if self.state == 'playing' and not self.player.get('block_locked', False):
                        self.player['blocking'] = False

            if event.type == pygame.KEYDOWN:
                if self.state == 'menu':
                    if event.key == pygame.K_1:
                        self.sound.on_menu_select()
                        self.new_game()
                    elif event.key == pygame.K_2:
                        self.sound.on_menu_select()
                        self.load_game()
                    elif event.key == pygame.K_q:
                        self.running = False
                
                elif self.state == 'playing':
                    if event.key == pygame.K_ESCAPE:
                        self.state = 'paused'
                    elif event.key == pygame.K_SPACE:
                        if 'crafting' in self.inventory.open_menus and self.inventory.selected.get('crafting'):
                            self.attempt_craft_selected()
                            self.gain_xp(1)
                            continue
                        if 'actions' in self.inventory.open_menus:
                            selected_action = self.inventory.selected.get('actions')
                            if selected_action:
                                self.execute_action(selected_action)
                                self.gain_xp(1)
                                continue
                        # Fire selected toolbar slot; do nothing if slot is empty
                        _slot_item = None
                        if self.inventory.selected_tool_slot_idx is not None:
                            _slot_item = self.inventory.tool_slots[self.inventory.selected_tool_slot_idx]
                        if _slot_item and _slot_item in self.inventory.magic:
                            _prev_magic = self.inventory.selected.get('magic')
                            self.inventory.selected['magic'] = _slot_item
                            if _slot_item == 'rain_spell':
                                self.cast_rain_spell()
                            elif _slot_item == 'day_spell':
                                self.cast_day_spell()
                            elif _slot_item == 'keeper_spell':
                                self.cast_keeper_spell()
                            elif _slot_item.startswith('summon_'):
                                self.cast_summon_spell()
                            elif _slot_item.startswith('transform_'):
                                self.cast_transform_spell()
                            else:
                                self.cast_star_spell()
                            self.inventory.selected['magic'] = _prev_magic
                            self.gain_xp(1)
                        elif _slot_item and _slot_item in self.inventory.actions:
                            self.execute_action(_slot_item)
                            self.gain_xp(1)
                        else:
                            # No tool slot item (or item is a regular item) — default interact
                            self.interact()
                            self.gain_xp(1)
                    elif event.key == pygame.K_l:
                        selected = self.inventory.selected_magic
                        if selected == 'rain_spell':
                            self.cast_rain_spell()
                        elif selected == 'day_spell':
                            self.cast_day_spell()
                        elif selected == 'keeper_spell':
                            self.cast_keeper_spell()
                        elif selected and selected.startswith('summon_'):
                            self.cast_summon_spell()
                        elif selected and selected.startswith('transform_'):
                            self.cast_transform_spell()
                        else:
                            self.cast_star_spell()
                        self.gain_xp(1)
                    elif event.key == pygame.K_k:
                        self.release_enchantments()
                        self.gain_xp(1)
                    elif event.key == pygame.K_j:
                        self.release_follower()
                        self.gain_xp(1)
                    elif event.key in (pygame.K_LSHIFT, pygame.K_RSHIFT):
                        # Shift held = start blocking; double-tap within 18 ticks = toggle block lock
                        now = self.tick
                        last = self.player.get('last_shift_press_tick', 0)
                        if now - last <= 18:
                            locked = not self.player.get('block_locked', False)
                            self.player['block_locked'] = locked
                            print(f"Block lock: {'ON' if locked else 'OFF'}")
                        self.player['last_shift_press_tick'] = now
                        self.player['blocking'] = True
                    elif event.key == pygame.K_v:
                        # Toggle friendly fire (allow/deny damage to peaceful entities)
                        self.player['friendly_fire'] = not self.player.get('friendly_fire', False)
                        state = 'ON — can attack anyone' if self.player['friendly_fire'] else 'OFF — peaceful entities protected'
                        print(f"Friendly Fire: {state}")
                        self.gain_xp(1)
                    elif event.key == pygame.K_c:
                        # Toggle crafting screen (UI open/close — no XP)
                        _was_open = 'crafting' in self.inventory.open_menus
                        self.inventory.toggle_menu('crafting')
                        if not _was_open:
                            # Auto-open ingredient panels so items are visible
                            for _panel in ('items', 'tools', 'magic'):
                                self.inventory.open_menus.add(_panel)
                            # Pre-select first craftable recipe
                            _craftable = self.inventory.get_craftable_recipes()
                            if _craftable and not self.inventory.selected.get('crafting'):
                                self.inventory.selected['crafting'] = _craftable[0][0]
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_x:
                        self.attempt_craft()
                        self.gain_xp(1)
                    elif event.key == pygame.K_i:
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            self.show_dev_screen = not self.show_dev_screen
                        else:
                            _was_open = 'items' in self.inventory.open_menus
                            self.inventory.toggle_menu('items')
                            if not _was_open:
                                self.sound.on_inventory_open()
                    elif event.key == pygame.K_t:
                        if (pygame.key.get_mods() & pygame.KMOD_SHIFT) and self.inspected_npc:
                            self.open_npc_trade_window()
                        else:
                            _was_open = 'tools' in self.inventory.open_menus
                            self.inventory.toggle_menu('tools')
                            if not _was_open:
                                self.sound.on_inventory_open()
                    elif event.key == pygame.K_m:
                        _was_open = 'magic' in self.inventory.open_menus
                        self.inventory.toggle_menu('magic')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_u:
                        _was_open = 'actions' in self.inventory.open_menus
                        self.inventory.toggle_menu('actions')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_g:
                        if (pygame.key.get_mods() & pygame.KMOD_SHIFT) and self.inspected_npc:
                            self.give_gift_to_npc(self.inspected_npc)
                        else:
                            self.debug_memory_lanes = not self.debug_memory_lanes
                            print(f"Debug Memory Lanes: {'ON' if self.debug_memory_lanes else 'OFF'}")
                    elif event.key == pygame.K_f:
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            if self.inspected_npc:
                                self.handle_npc_follow_interaction()
                                self.gain_xp(1)
                        else:
                            _was_open = 'followers' in self.inventory.open_menus
                            self.inventory.toggle_menu('followers')
                            if not _was_open:
                                self.sound.on_inventory_open()
                    elif event.key == pygame.K_e:
                        self.pickup_cell_or_items()
                        self.gain_xp(1)
                    elif event.key == pygame.K_n:
                        self.npc_trade_interaction()
                        self.gain_xp(1)
                    elif event.key == pygame.K_p:
                        self.place_selected_item()
                        self.gain_xp(1)
                    elif event.key == pygame.K_q:
                        mods = pygame.key.get_mods()
                        if (mods & pygame.KMOD_SHIFT) and self.inspected_npc:
                            self.handle_npc_quest_interaction()
                            self.gain_xp(1)
                        else:
                            # Toggle quest UI (no XP)
                            self.quest_ui_open = not self.quest_ui_open
                    elif event.key == pygame.K_d:
                        self.drop_selected_item()
                        self.gain_xp(1)
                    elif event.key == pygame.K_LEFT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(-1)
                    elif event.key == pygame.K_RIGHT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(1)
                    elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        if self.inspected_npc:
                            self.handle_npc_quest_assign()
                            self.gain_xp(1)
                        else:
                            self.toggle_autopilot()
                    # Number keys: tool slot select/use when no menus open; assign when tools open
                    elif event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                                      pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8,
                                      pygame.K_9, pygame.K_0]:
                        slot = (event.key - pygame.K_1) if event.key != pygame.K_0 else 9
                        mods = pygame.key.get_mods()
                        if 'tools' in self.inventory.open_menus:
                            if self.inventory.selected_tool_slot_idx == slot:
                                # Second press on same slot — unequip and mark pending
                                self.inventory.unequip_slot(slot)
                                self.inventory.selected['tools'] = None
                                self.inventory.pending_equip_slot = slot
                                self.inventory.pending_equip_equipment_slot = None
                            else:
                                # First press — just select the slot
                                self.inventory.selected_tool_slot_idx = slot
                                self.inventory.selected['tools'] = self.inventory.tool_slots[slot]
                                self.inventory.pending_equip_slot = None
                        elif not self.inventory.open_menus:
                            # No menus open: hotkey activates the tool slot
                            if slot < len(self.inventory.tool_slots):
                                slot_item = self.inventory.tool_slots[slot]
                                self.inventory.selected_tool_slot_idx = slot
                                self.inventory.selected['tools'] = slot_item
                                if slot_item:
                                    if mods & pygame.KMOD_SHIFT:
                                        self.place_selected_item(item_name=slot_item)
                                    elif slot_item in self.inventory.magic:
                                        _prev_magic = self.inventory.selected.get('magic')
                                        self.inventory.selected['magic'] = slot_item
                                        if slot_item == 'rain_spell': self.cast_rain_spell()
                                        elif slot_item == 'day_spell': self.cast_day_spell()
                                        elif slot_item == 'keeper_spell': self.cast_keeper_spell()
                                        elif slot_item.startswith('summon_'): self.cast_summon_spell()
                                        elif slot_item.startswith('transform_'): self.cast_transform_spell()
                                        else: self.cast_star_spell()
                                        self.inventory.selected['magic'] = _prev_magic
                                    elif slot_item in self.inventory.actions:
                                        self.execute_action(slot_item)
                                    else:
                                        self.interact()
                                    self.gain_xp(1)
                        else:
                            self.select_inventory_slot(slot)
                
                elif self.state == 'paused':
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        self.state = 'playing'
                    elif event.key == pygame.K_s:
                        self.save_game()
                    elif event.key == pygame.K_m:
                        self.state = 'menu'
                    # Inventory panels accessible while paused (crafting execution blocked)
                    elif event.key == pygame.K_i:
                        self.inventory.toggle_menu('items')
                    elif event.key == pygame.K_t:
                        self.inventory.toggle_menu('tools')
                    elif event.key == pygame.K_u:
                        self.inventory.toggle_menu('actions')
                    elif event.key == pygame.K_f:
                        self.inventory.toggle_menu('followers')
                    elif event.key == pygame.K_c:
                        self.inventory.toggle_menu('crafting')
                    elif event.key == pygame.K_q:
                        self.quest_ui_open = not self.quest_ui_open
                    elif event.key == pygame.K_LEFT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(-1)
                    elif event.key == pygame.K_RIGHT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(1)
                    elif event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                                       pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8,
                                       pygame.K_9, pygame.K_0]:
                        slot = (event.key - pygame.K_1) if event.key != pygame.K_0 else 9
                        if 'tools' in self.inventory.open_menus:
                            if self.inventory.selected_tool_slot_idx == slot:
                                self.inventory.unequip_slot(slot)
                                self.inventory.selected['tools'] = None
                                self.inventory.pending_equip_slot = slot
                                self.inventory.pending_equip_equipment_slot = None
                            else:
                                self.inventory.selected_tool_slot_idx = slot
                                self.inventory.selected['tools'] = self.inventory.tool_slots[slot]
                                self.inventory.pending_equip_slot = None
                        else:
                            self.select_inventory_slot(slot)
        
        # Handle direction changes and close inventory on movement
        if self.state == 'playing':
            keys = pygame.key.get_pressed()
            moved = False
            if keys[pygame.K_UP] or keys[pygame.K_w]:
                self.target_direction = 0
                moved = True
            elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
                self.target_direction = 1
                moved = True
            elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
                self.target_direction = 2
                moved = True
            elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
                self.target_direction = 3
                moved = True
            
            # Close inventory and quest UI when moving
            if moved and (len(self.inventory.open_menus) > 0 or self.quest_ui_open):
                self.inventory.close_all_menus()
                self.quest_ui_open = False
    
    def handle_inventory_click(self, pos):
        """Handle clicking on inventory items"""
        if not self.inventory.open_menus:
            return
        
        # Calculate inventory position (bottom left)
        slot_size = CELL_SIZE
        start_x = 10
        start_y = SCREEN_HEIGHT - 90  # Above UI bar
        
        # Stack categories vertically from bottom
        categories = ['tools', 'equipment', 'items', 'magic', 'actions', 'followers', 'crafting']
        y_offset = 0

        for category in categories:
            if category not in self.inventory.open_menus:
                continue

            # Special handling for crafting screen — use same list as the renderer
            if category == 'crafting':
                items = self.inventory.get_craftable_recipes()
            else:
                items = self.inventory.get_item_list(category)
            
            if not items:
                continue

            # Match wrap-around layout from draw_inventory_panels
            slots_per_row = max(1, (SCREEN_WIDTH - 20) // (slot_size + 2))
            total_rows = max(1, (len(items) + slots_per_row - 1) // slots_per_row)

            # Draw horizontally with row wrapping
            for i, (item_name, count) in enumerate(items):
                row = i // slots_per_row
                col = i % slots_per_row
                slot_x = start_x + col * (slot_size + 2)
                slot_y = (start_y - y_offset) - row * (slot_size + 15)

                # Check if click is in this slot
                if (slot_x <= pos[0] <= slot_x + slot_size and
                        slot_y <= pos[1] <= slot_y + slot_size):

                    if category == 'tools':
                        if self.inventory.selected_tool_slot_idx == i:
                            # Second click on same slot — unequip and mark pending for reassignment
                            self.inventory.unequip_slot(i)
                            self.inventory.selected['tools'] = None
                            self.inventory.pending_equip_slot = i
                            self.inventory.pending_equip_equipment_slot = None
                        else:
                            # First click — just select the slot, keep its item
                            self.inventory.selected_tool_slot_idx = i
                            self.inventory.selected['tools'] = self.inventory.tool_slots[i]
                            self.inventory.pending_equip_slot = None
                        self.sound.on_inventory_select()
                        return

                    elif category == 'equipment':
                        # --- Equipment slot clicked: mark as pending for item assignment ---
                        slot_name = self.inventory.EQUIPMENT_SLOT_NAMES[i]
                        if self.inventory.pending_equip_equipment_slot == slot_name:
                            # Clicking same slot again clears pending
                            self.inventory.pending_equip_equipment_slot = None
                        else:
                            self.inventory.pending_equip_equipment_slot = slot_name
                            self.inventory.pending_equip_slot = None
                        self.sound.on_inventory_select()
                        return

                    elif (self.inventory.pending_equip_equipment_slot is not None and
                          item_name is not None):
                        # --- Item clicked while equipment slot is pending ---
                        slot_name = self.inventory.pending_equip_equipment_slot
                        # Enforce slot type: item must declare the matching equipment_slot
                        item_equip_slot = ITEMS.get(item_name, {}).get('equipment_slot')
                        _target = 'ring' if slot_name in ('ring1', 'ring2') else slot_name
                        if item_equip_slot != _target and item_equip_slot != slot_name:
                            # Wrong slot type — ignore click, keep pending
                            return
                        self.inventory.equip_to_equipment_slot(slot_name, item_name, category)
                        if ITEMS.get(item_name, {}).get('damage'):
                            self.sound.on_equip_sword()
                        else:
                            self.sound.on_inventory_select()
                        return

                    elif ('tools' in self.inventory.open_menus and
                          self.inventory.pending_equip_slot is not None and
                          item_name is not None):
                        # --- Item in another tab clicked while a tool slot is pending ---
                        slot_idx = self.inventory.pending_equip_slot
                        self.inventory.equip_to_slot(slot_idx, item_name, category)
                        if ITEMS.get(item_name, {}).get('damage'):
                            self.sound.on_equip_sword()
                        else:
                            self.sound.on_inventory_select()
                        return

                    else:
                        # --- Normal selection ---
                        self.inventory.selected[category] = item_name
                        if ITEMS.get(item_name, {}).get('damage'):
                            self.sound.on_equip_sword()
                        else:
                            self.sound.on_inventory_select()
                        return

            y_offset += total_rows * (slot_size + 15)  # Stack next category above
    
    def handle_quest_ui_click(self, pos):
        """Handle clicking on quest UI to select active quest"""
        if not self.quest_ui_open:
            return
        
        slot_size = CELL_SIZE
        start_x = 10
        
        # Calculate starting y position (above inventory panels)
        base_y = SCREEN_HEIGHT - 90
        y_offset = 0
        if self.inventory.open_menus:
            categories = ['tools', 'items', 'magic', 'actions', 'followers', 'crafting']
            for category in categories:
                if category in self.inventory.open_menus:
                    items = self.inventory.get_craftable_recipes() if category == 'crafting' else self.inventory.get_item_list(category)
                    y_offset += slot_size + 15

        start_y = base_y - y_offset

        quest_types = list(QUEST_TYPES.keys())
        for i, quest_type in enumerate(quest_types):
            slot_x = start_x + i * (slot_size + 2)
            slot_y = start_y

            # Check if click is in this quest slot
            if (slot_x <= pos[0] <= slot_x + slot_size and
                slot_y <= pos[1] <= slot_y + slot_size):
                self.active_quest = quest_type
                self.active_npc_quest_npc_id = None  # deselect NPC quest when picking standard
                print(f"Active quest: {QUEST_TYPES[quest_type]['name']}")
                return

        # Check NPC quest slots (offset by 1 gap after standard slots)
        npc_slots = getattr(self, 'npc_quests', [])
        for j, nq in enumerate(npc_slots):
            slot_x = start_x + (len(quest_types) + 1 + j) * (slot_size + 2)
            slot_y = start_y
            if (slot_x <= pos[0] <= slot_x + slot_size and
                    slot_y <= pos[1] <= slot_y + slot_size):
                self.active_npc_quest_npc_id = nq.npc_id
                giver = self.entities.get(nq.npc_id)
                npc_name = (giver.name or giver.type) if giver else "NPC"
                q_name = QUEST_TYPES.get(nq.quest.quest_type, {}).get('name', nq.quest.quest_type)
                print(f"Tracking NPC quest [{q_name}] from {npc_name}")
                return

    # -------------------------------------------------------------------------
    # Settings helpers
    # -------------------------------------------------------------------------

    def _load_settings(self):
        try:
            import json as _json
            with open(_SETTINGS_PATH, 'r') as f:
                data = _json.load(f)
            self.ambient_music_enabled = bool(data.get('ambient_music', True))
            self.debug_prints_enabled  = bool(data.get('debug_prints',  True))
            self.autosave_enabled      = bool(data.get('autosave',      True))
        except Exception:
            pass  # use defaults

    def _save_settings(self):
        try:
            import json as _json
            with open(_SETTINGS_PATH, 'w') as f:
                _json.dump({
                    'ambient_music': self.ambient_music_enabled,
                    'debug_prints':  self.debug_prints_enabled,
                    'autosave':      self.autosave_enabled,
                }, f)
        except Exception:
            pass

    def _apply_settings(self):
        # Music
        if hasattr(self, 'sound'):
            self.sound.set_music_enabled(self.ambient_music_enabled)
        # Debug prints: redirect stdout to devnull when disabled
        if self.debug_prints_enabled:
            sys.stdout = _REAL_STDOUT
        else:
            if sys.stdout is not _REAL_STDOUT:
                return  # already redirected
            try:
                sys.stdout = open(_os.devnull, 'w')
            except Exception:
                pass

    # checkbox rects used by both draw_menu and _handle_menu_click
    MENU_CB_MUSIC_RECT  = pygame.Rect(0, 0, 140, 18)  # positioned in draw_menu
    MENU_CB_DEBUG_RECT  = pygame.Rect(0, 0, 140, 18)

    def _handle_menu_click(self, pos):
        """Handle left-click on main menu (checkbox toggles)."""
        mr = getattr(self, '_menu_cb_music_rect', None)
        dr = getattr(self, '_menu_cb_debug_rect', None)
        ar = getattr(self, '_menu_cb_autosave_rect', None)
        if mr and mr.collidepoint(pos):
            self.ambient_music_enabled = not self.ambient_music_enabled
            self._save_settings()
            self._apply_settings()
        elif dr and dr.collidepoint(pos):
            self.debug_prints_enabled = not self.debug_prints_enabled
            self._save_settings()
            self._apply_settings()
        elif ar and ar.collidepoint(pos):
            self.autosave_enabled = not self.autosave_enabled
            self._save_settings()

    # -------------------------------------------------------------------------
    # Spells
    # -------------------------------------------------------------------------

    def cast_rain_spell(self):
        if self.player['energy'] < 90:
            return
        if self.is_raining:
            return
        self.player['energy'] -= 90
        # Set rain on the player's current zone through the zone_rain system
        # (global self.is_raining is synced from zone_rain each update cycle)
        _pzk = f"{self.player['screen_x']},{self.player['screen_y']}"
        if not hasattr(self, 'zone_rain'):
            self.zone_rain = {}
        if _pzk not in self.zone_rain:
            self.zone_rain[_pzk] = {
                'is_raining': False,
                'weather_timer': 0,
                'weather_cycle': RAIN_FREQUENCY_MAX,
                'rain_timer': 0,
                'rain_duration': 0,
            }
        zr = self.zone_rain[_pzk]
        zr['is_raining'] = True
        zr['rain_timer'] = 0
        zr['rain_duration'] = RAIN_DURATION_MIN
        # Also reset weather_timer so the zone doesn't immediately trigger another cycle
        zr['weather_timer'] = 0
        self.is_raining = True

    def cast_day_spell(self):
        if self.player['energy'] < 90:
            print("[Spell] Not enough energy!")
            return
        self.player['energy'] -= 90
        self.is_night = not self.is_night
        if self.is_night:
            self.day_night_timer = DAY_LENGTH + 1
        else:
            self.day_night_timer = 0
        print(f"[Spell] Now {'night' if self.is_night else 'day'}.")

    def execute_action(self, action_name):
        if action_name == 'shove':
            self.do_shove()
        elif action_name == 'attack':
            self.interact()
        elif action_name == 'block':
            self.player['blocking'] = True
        elif action_name == 'inspect':
            pass  # Handled by check_npc_inspection via tool slot or Shift key
        elif action_name in ('sneak', 'dig', 'talk'):
            pass  # Placeholder — implementation in future sessions

    def give_gift_to_npc(self, npc_id):
        """Shift+G: offer selected item to inspected NPC to gain favor."""
        if npc_id not in self.entities:
            return
        entity = self.entities[npc_id]
        # Find best item to gift (selected item first, then first available)
        item_name = (self.inventory.selected.get('items') or
                     next(iter(self.inventory.items), None))
        if not item_name or self.inventory.items.get(item_name, 0) <= 0:
            print("[Gift] No item to give.")
            return
        item_data = ITEMS.get(item_name, {})
        # Favor gain: base 10, +5 per damage value (weapons are better gifts)
        favor_gain = 10 + item_data.get('damage', 0) // 2
        favor_gain = min(favor_gain, 30)
        self.inventory.remove_item(item_name, 1)
        entity.favor = max(-100, min(100, entity.favor + favor_gain))
        item_display = item_data.get('name', item_name)
        npc_name = entity.name or entity.type
        print(f"[Gift] Gave {item_display} to {npc_name}. Favor: {entity.favor:+d}")

    def do_shove(self):
        px, py = self.player['x'], self.player['y']
        facing = self.player.get('facing', 'down')
        dx, dy = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}[facing]
        tx, ty = px + dx, py + dy
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        for eid in list(self.screen_entities.get(screen_key, [])):
            e = self.entities.get(eid)
            if e and int(e.x) == tx and int(e.y) == ty and not getattr(e, 'in_subscreen', False):
                nx, ny = tx + dx, ty + dy
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                    target_cell = self.current_screen['grid'][ny][nx]
                    if not CELL_TYPES.get(target_cell, {}).get('solid', True):
                        e.x, e.y = nx, ny
                        print(f"[Shove] Pushed {e.type}!")
                break

    def handle_npc_follow_interaction(self):
        npc_id = self.inspected_npc
        if npc_id not in self.entities:
            return
        entity = self.entities[npc_id]
        npc_name = entity.name if entity.name else entity.type

        if npc_id in self.followers:
            print(f"{npc_name} is already following you.")
            return

        if random.random() < 0.5:
            self.followers.append(npc_id)
            follower_name = f"{entity.type.lower()}_{npc_id}"
            entry = {
                'color': entity.props.get('color', (180, 180, 180)),
                'name': npc_name,
                'is_follower': True,
                'entity_id': npc_id,
            }
            ITEMS[follower_name] = entry
            from data.items import ITEMS as DATA_ITEMS
            DATA_ITEMS[follower_name] = entry
            self.inventory.add_item(follower_name, 1)
            if hasattr(self, 'follower_items'):
                self.follower_items[npc_id] = follower_name
            # Clear pathfinding state so follower moves cleanly from the start
            entity.memory_lane = []
            entity.last_move_tick = 0
            entity.target_stuck_counter = 0
            entity.last_target_position = None
            # Clear combat state — stop attacking player immediately
            entity.in_combat = False
            entity.current_target = None
            entity.ai_state = 'idle'
            entity.idle_timer = 0
            entity.props['hostile'] = False
            print(f"{npc_name} has decided to follow you!")
        else:
            print(f"{npc_name} declined to follow.")

    def handle_npc_quest_interaction(self):
        """Handle Shift+Q while inspecting an NPC: give, progress, or turn in quest."""
        npc_id = self.inspected_npc
        if npc_id not in self.entities:
            return

        entity = self.entities[npc_id]
        npc_name = entity.name if entity.name else entity.type

        # Find existing slot for this NPC
        existing = next((nq for nq in self.npc_quests if nq.npc_id == npc_id), None)

        if existing and existing.quest.status == 'completed':
            # TURN IN — player and NPC both gain XP
            xp_reward = 1
            entity.gain_xp(100)
            leveled = entity.xp == 0  # gain_xp resets xp to 0 on level-up
            self.npc_quests.remove(existing)
            if self.active_npc_quest_npc_id == npc_id:
                self.active_npc_quest_npc_id = None
            level_msg = f" ({npc_name} leveled up to {entity.level}!)" if leveled else ""
            print(f"Quest turned in! +{xp_reward} XP. {npc_name} +100 XP.{level_msg}")
            return

        if existing and existing.quest.status == 'active':
            print(f"Quest from {npc_name} still in progress.")
            return

        if len(self.npc_quests) >= 3:
            print("Quest log full (max 3 NPC quests).")
            return

        # RECEIVE: pick random quest type, generate target via loreEngine
        quest_type = random.choice(list(QUEST_TYPES.keys()))
        quest = Quest(quest_type)
        success = self.loreEngine(quest)
        if success:
            self.npc_quests.append(NpcQuestSlot(npc_id, quest))
            self.active_npc_quest_npc_id = npc_id  # auto-select as active NPC quest
            self.sound.on_quest_received()
            q_name = QUEST_TYPES[quest_type]['name']
            print(f"Received quest [{q_name}] from {npc_name}!")
        else:
            print(f"No quest available from {npc_name} right now.")

    def handle_npc_quest_assign(self):
        """Shift+A while inspecting an NPC: assign the player's selected quest to the NPC.

        For NPCs with a base quest (FARMER etc.) the queue system is used — assigned quests
        insert at the front of their queue (max NPC_QUEST_QUEUE_MAX) and become the primary
        target until completed.  Special (transferred) quests are removed from the player's
        npc_quests list.  For other NPC types the existing single quest_focus path is used.
        """
        npc_id = self.inspected_npc
        if npc_id not in self.entities:
            return

        entity = self.entities[npc_id]
        npc_name = entity.name if entity.name else entity.type

        # Check if a special NPC quest is currently active/selected
        active_special = None
        if self.active_npc_quest_npc_id is not None:
            active_special = next(
                (nq for nq in self.npc_quests if nq.npc_id == self.active_npc_quest_npc_id),
                None,
            )

        qt = active_special.quest.quest_type if active_special else self.active_quest
        if not qt:
            print("No quest selected to assign.")
            return
        q_name = QUEST_TYPES.get(qt, {}).get('name', qt)

        # Queue-based assignment for NPCs with a base quest (FARMER etc.)
        if entity.type in NPC_BASE_QUEST:
            # Ensure queue is initialized with base quest
            if not hasattr(entity, 'quest_queue') or not entity.quest_queue:
                base_qt = NPC_BASE_QUEST[entity.type]
                entity.quest_queue = [{'type': base_qt, 'base': True, 'slot': None}]

            # Reject if already at max capacity
            if len(entity.quest_queue) >= NPC_QUEST_QUEUE_MAX:
                print(f"Quest queue full for {npc_name} (max {NPC_QUEST_QUEUE_MAX}).")
                return

            # Reject duplicate quest types already in queue
            if any(e['type'] == qt for e in entity.quest_queue):
                print(f"{npc_name} already has a [{q_name}] quest queued.")
                return

            slot = active_special  # None for standing quests
            entity.quest_queue.insert(0, {'type': qt, 'base': False, 'slot': slot})
            entity.quest_focus = qt
            entity.quest_target = None
            entity._quest_update_counter = 10  # trigger immediate retry on next AI cycle

            # Pre-seed quest_target if the special quest has a known target
            if slot:
                q = slot.quest
                if q.target_entity_id is not None:
                    entity.quest_target = q.target_entity_id
                elif q.target_cell is not None:
                    entity.quest_target = ('cell', q.target_cell[2], q.target_cell[3])
                entity.assigned_quest = slot

            # Seed target directly from the player's quest object if it has one
            # (e.g. player's HUNT quest already tracking a named entity)
            if entity.quest_target is None:
                player_quest = self.quests.get(qt)
                if player_quest and getattr(player_quest, 'target_entity_id', None):
                    eid = player_quest.target_entity_id
                    if eid in self.entities and self.entities[eid].is_alive():
                        entity.quest_target = eid

            # Fall back to AI search if player quest had no specific target yet
            if entity.quest_target is None:
                screen_key = f"{entity.screen_x},{entity.screen_y}"
                self._assign_specific_quest_target(entity, screen_key)

            # Quest becomes the keeper target — anchor NPC to the quest target.
            # keeper_target tracks entity/cell/item by reference; pos updated each tick.
            entity.keeper = True
            qt = entity.quest_target
            if isinstance(qt, int) and qt in self.entities:
                self._set_keeper_target_entity(entity, qt)
            elif isinstance(qt, tuple) and len(qt) >= 3 and qt[0] == 'cell':
                self._set_keeper_target_cell(entity, qt[1], qt[2])
            else:
                # No target found yet — roam freely (keeper_type 2) until AI finds one
                entity.keeper_type = 2
                entity.keeper_target = None
                entity.keeper_target_pos = None

            if active_special:
                self.npc_quests.remove(active_special)
                self.active_npc_quest_npc_id = None
                print(f"Assigned special quest [{q_name}] to {npc_name}. Quest transferred.")
            else:
                print(f"Assigned quest [{q_name}] to {npc_name}.")
            self.sound.on_quest_received()
            return

        # Fallback for NPC types without a base quest — single quest_focus (existing behavior)
        if active_special:
            entity.quest_focus = qt
            entity.assigned_quest = active_special
            entity.quest_target = None
            entity._quest_update_counter = 0
            self.npc_quests.remove(active_special)
            self.active_npc_quest_npc_id = None
            self.sound.on_quest_received()
            print(f"Assigned special quest [{q_name}] to {npc_name}. Quest transferred.")
        else:
            entity.quest_focus = qt
            entity.quest_target = None
            entity._quest_update_counter = 0
            self.sound.on_quest_received()
            print(f"Assigned quest [{q_name}] to {npc_name}.")

    def _next_item_uid(self):
        """Return a new unique item ID for individually tracked items."""
        self._item_uid_counter += 1
        return self._item_uid_counter

    def register_item_target(self, item_name, entity_id=None, cell=None, screen=None):
        """Register a specific item instance for quest/keeper tracking.

        Pass entity_id if the item is in an entity's inventory, or cell=(x,y) if it
        is a world drop.  Returns the assigned UID.
        """
        uid = self._next_item_uid()
        if entity_id is not None and entity_id in self.entities:
            e = self.entities[entity_id]
            pos = (e.x, e.y)
            scr = (e.screen_x, e.screen_y)
            self.item_registry[uid] = {
                'name': item_name, 'location': 'inventory',
                'holder': entity_id, 'pos': pos, 'screen': scr,
            }
        elif cell is not None:
            pos = cell
            scr = screen or (self.player['screen_x'], self.player['screen_y'])
            self.item_registry[uid] = {
                'name': item_name, 'location': 'world',
                'holder': cell, 'pos': pos, 'screen': scr,
            }
        return uid

    def open_npc_trade_window(self):
        """Shift+T on inspected NPC: open an inventory trade window.

        Builds trader_display from the NPC's current inventory with random per-item
        gold prices (5–10 gold each, generated fresh each open).
        """
        npc_id = self.inspected_npc
        if npc_id not in self.entities:
            return
        entity = self.entities[npc_id]

        # Build item list: only items with count > 0
        items = [(item, count) for item, count in entity.inventory.items() if count > 0]

        trade_items = []
        for item_name, count in items:
            price = random.randint(5, 10)
            trade_items.append({'item': item_name, 'count': count, 'price': price})

        self.trader_display = {
            'mode': 'inventory',
            'entity_id': npc_id,
            'position': (entity.x, entity.y),
            'items': trade_items,
        }
        self.trader_display_tick = self.tick

    def handle_npc_trade_click(self, pos):
        """Handle mouse click on the NPC inventory trade window.

        Each item slot is 32px wide with 4px padding.  Clicking an item slot
        transfers gold from the player and moves the item to player inventory.
        """
        if not self.trader_display or self.trader_display.get('mode') != 'inventory':
            return False

        npc_id = self.trader_display['entity_id']
        if npc_id not in self.entities:
            self.trader_display = None
            return False

        entity = self.entities[npc_id]
        items = self.trader_display['items']

        slot_size = CELL_SIZE
        padding = 4
        # UI anchored above the NPC — same layout as draw_npc_inventory_trade_ui
        tx, ty = self.trader_display['position']
        ui_x = tx * slot_size
        ui_y = ty * slot_size - (len(items) + 1) * (slot_size + padding) - 10

        for i, entry in enumerate(items):
            # Each row: [gold slot][padding][arrow(20px)][item slot]
            row_y = ui_y + i * (slot_size + padding)
            item_slot_x = ui_x + slot_size + padding + 20  # matches draw_npc_inventory_trade_ui
            if (item_slot_x <= pos[0] <= item_slot_x + slot_size and
                    row_y <= pos[1] <= row_y + slot_size):
                # Player clicked this item
                player_gold = self.inventory.items.get('gold', 0)
                price = entry['price']
                if player_gold < price:
                    print(f"Not enough gold. Need {price}, have {player_gold}.")
                    return True
                # Transfer gold
                self.inventory.remove_item('gold', price)
                entity.inventory['gold'] = entity.inventory.get('gold', 0) + price
                # Transfer item
                item_name = entry['item']
                self.inventory.add_item(item_name, 1)
                entity.inventory[item_name] = max(0, entity.inventory.get(item_name, 0) - 1)
                print(f"Bought {item_name} for {price} gold.")
                # Refresh display or close if empty
                items[:] = [e for e in items if entity.inventory.get(e['item'], 0) > 0]
                if not items:
                    self.trader_display = None
                return True
        return False

    def select_inventory_slot(self, slot_index):
        """Select an inventory slot by number (0-9)"""
        # Find first open menu and select that slot
        for category in ['tools', 'items', 'magic', 'actions', 'followers']:
            if category in self.inventory.open_menus:
                items = self.inventory.get_item_list(category)
                if slot_index < len(items):
                    self.inventory.selected[category] = items[slot_index][0]
                break

    def cycle_inventory_slot(self, direction):
        """Cycle selected slot in the first open inventory menu by direction (+1 or -1)."""
        for category in ['tools', 'items', 'magic', 'actions', 'followers']:
            if category in self.inventory.open_menus:
                items = self.inventory.get_item_list(category)
                if not items:
                    break
                names = [item[0] for item in items]
                current = self.inventory.selected.get(category)
                if current in names:
                    idx = (names.index(current) + direction) % len(names)
                else:
                    idx = 0 if direction > 0 else len(names) - 1
                self.inventory.selected[category] = names[idx]
                if ITEMS.get(names[idx], {}).get('damage'):
                    self.sound.on_equip_sword()
                else:
                    self.sound.on_inventory_select()
                break
    
    def move_player(self):
        """Handle player movement"""
        # Drain autopilot input queue before menu guard so synthetic events
        # fire even while inventory/crafting menus are open.
        if getattr(self, 'autopilot', False):
            self._ap_flush_input_queue()
            # Force-close all UI panels when the queue is idle.
            # MUST run before the open_menus early-return below — update_autopilot()
            # (where the close logic also lives) is never reached when open_menus
            # is non-empty, so this is the only reliable close site.
            if not self._ap_input_queue:
                _any_ui = (self.inventory.open_menus or self.quest_ui_open
                           or self.trader_display or self.inspected_npc)
                if _any_ui:
                    self.inventory.close_all_menus()
                    self.quest_ui_open = False
                    self.trader_display = None
                    self.inspected_npc = None
                    self.inspect_cell_target = None
        if self.state != 'playing' or self.inventory.open_menus:
            return
        
        keys = pygame.key.get_pressed()
        
        # Check for autopilot every tick (has its own cooldown)
        any_movement_key = (keys[pygame.K_UP] or keys[pygame.K_w] or
                           keys[pygame.K_DOWN] or keys[pygame.K_s] or
                           keys[pygame.K_LEFT] or keys[pygame.K_a] or
                           keys[pygame.K_RIGHT] or keys[pygame.K_d])
        
        if not any_movement_key:
            if getattr(self, 'autopilot_locked', False):
                # If in a structure, navigate toward the exit instead of autopiloting
                if self.player.get('in_structure'):
                    structure = self.structures.get(self.player.get('structure_key'))
                    if structure:
                        exit_pos = structure.get('exit', structure.get('entrance'))
                        if exit_pos:
                            px, py = self.player['x'], self.player['y']
                            ex, ey = exit_pos
                            # If at exit, leave
                            if px == ex and py == ey:
                                self.exit_structure()
                                return
                            # Move toward exit
                            if self.tick % 18 == 0:
                                dx = 1 if ex > px else (-1 if ex < px else 0)
                                dy = 1 if ey > py else (-1 if ey < py else 0)
                                # Prefer one axis at a time
                                if dx != 0 and dy != 0:
                                    if random.random() < 0.5:
                                        dx = 0
                                    else:
                                        dy = 0
                                new_x, new_y = px + dx, py + dy
                                cell = self.current_screen['grid'][new_y][new_x]
                                if not CELL_TYPES.get(cell, {}).get('solid', False):
                                    self.player['x'] = new_x
                                    self.player['y'] = new_y
                                    facing_map = {(0,-1): 'up', (0,1): 'down', (-1,0): 'left', (1,0): 'right'}
                                    self.player['facing'] = facing_map.get((dx, dy), self.player['facing'])
                    return
                self.update_autopilot()
            return
        
        # Manual movement — only on tick intervals
        if self.tick % 18 != 0:
            return
        
        new_x = self.player['x']
        new_y = self.player['y']
        new_screen_x = self.player['screen_x']
        new_screen_y = self.player['screen_y']
        
        if keys[pygame.K_UP] or keys[pygame.K_w]:
            new_y -= 1
            self.target_direction = 0
            self.player['facing'] = 'up'
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            new_y += 1
            self.target_direction = 1
            self.player['facing'] = 'down'
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            new_x -= 1
            self.target_direction = 2
            self.player['facing'] = 'left'
        elif keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            new_x += 1
            self.target_direction = 3
            self.player['facing'] = 'right'
        
        self.mark_input()  # Player is actively moving
        
        # Screen transitions - check BEFORE updating position
        screen_changed = False
        
        # Check if in structure and trying to exit through doorway
        if self.player.get('in_structure'):
            current_structure = self.structures.get(self.player['structure_key'])
            # Exit when walking out the bottom (doorway area)
            # Only for houses or cave depth 1 (deeper caves use STAIRS_UP)
            if current_structure:
                # Caves now have solid CAVE_WALL borders — exit only via STAIRS_UP.
                # House interiors still use the bottom-edge walkout.
                is_house = current_structure.get('type') != 'CAVE'
                if is_house and new_y >= GRID_HEIGHT - 1:
                    self.exit_structure()
                    return
        
        # Normal screen transitions for overworld
        # Exits are only open at the center corridor (±1 of center edge).
        # Require player to be inside that corridor before allowing transition,
        # matching the NPC zone transition requirement in try_entity_zone_transition.
        _exits = self.current_screen.get('exits') if self.current_screen else None
        if not self.player.get('in_structure') and _exits:
            center_x = GRID_WIDTH // 2
            center_y = GRID_HEIGHT // 2
            if new_y < 0 and _exits.get('top') and abs(new_x - center_x) <= 1:
                new_screen_y -= 1
                new_y = GRID_HEIGHT - 2
                screen_changed = True
            elif new_y >= GRID_HEIGHT and _exits.get('bottom') and abs(new_x - center_x) <= 1:
                new_screen_y += 1
                new_y = 1
                screen_changed = True
            elif new_x < 0 and _exits.get('left') and abs(new_y - center_y) <= 1:
                new_screen_x -= 1
                new_x = GRID_WIDTH - 2
                screen_changed = True
            elif new_x >= GRID_WIDTH and _exits.get('right') and abs(new_y - center_y) <= 1:
                new_screen_x += 1
                new_x = 1
                screen_changed = True
        
        # Handle screen change
        if screen_changed:
            # Load screen immediately
            self.current_screen = self.generate_screen(new_screen_x, new_screen_y)
            # Update player position immediately
            self.player['x'] = new_x
            self.player['y'] = new_y
            self.player['screen_x'] = new_screen_x
            self.player['screen_y'] = new_screen_y
            self.player['is_moving'] = True
            # Snap world coords so interpolation doesn't slide across screens
            self.player['world_x'] = float(new_x)
            self.player['world_y'] = float(new_y)
            # Trigger catch-up for new zone
            self.on_zone_transition(new_screen_x, new_screen_y)
            return
        
        # Normal movement - bounds and collision check
        if 0 <= new_x < GRID_WIDTH and 0 <= new_y < GRID_HEIGHT:
            target_cell = self.current_screen['grid'][new_y][new_x]
            if not CELL_TYPES[target_cell]['solid']:
                # Entity collision — block movement if an NPC occupies the target cell
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                proxy_id = getattr(self, 'autopilot_proxy_id', None)
                entity_blocked = False
                check_list = self.screen_entities.get(screen_key, [])
                for eid in check_list:
                    if eid == proxy_id:
                        continue  # autopilot proxy is not a physical obstacle
                    if eid in self.entities:
                        e = self.entities[eid]
                        if e.x == new_x and e.y == new_y:
                            entity_blocked = True
                            break
                if entity_blocked:
                    return
                self.player['x'] = new_x
                self.player['y'] = new_y
                self.player['screen_x'] = new_screen_x
                self.player['screen_y'] = new_screen_y
                self.player['is_moving'] = True
                # Footstep sound on successful grid move
                _stepped_cell = self.current_screen['grid'][new_y][new_x]
                self.sound.on_footstep(_stepped_cell)

    def get_target_cell(self):
        """Get the cell coordinates the player is targeting.
        During autopilot, returns the proxy NPC's current action target cell
        so the reticle tracks what the proxy is actually doing."""
        # ── Autopilot: derive target from proxy's current_target ──────────
        if self.autopilot and getattr(self, 'autopilot_proxy_id', None):
            proxy = self.entities.get(self.autopilot_proxy_id)
            if proxy is not None:
                ct = proxy.current_target
                if isinstance(ct, tuple):
                    # ('cell', x, y, ...) or plain (x, y)
                    if len(ct) >= 3 and ct[0] in ('cell', 'entity', 'structure'):
                        tx, ty = int(ct[1]), int(ct[2])
                    elif len(ct) >= 2 and isinstance(ct[0], (int, float)):
                        tx, ty = int(ct[0]), int(ct[1])
                    else:
                        tx, ty = None, None
                    if tx is not None and 0 <= tx < GRID_WIDTH and 0 <= ty < GRID_HEIGHT:
                        return tx, ty
                elif isinstance(ct, int) and ct in self.entities:
                    # Entity target — point at that entity's cell
                    te = self.entities[ct]
                    return te.x, te.y
                # Fall through: proxy has no current target — aim at cell in front of proxy
                facing_dirs = {'up': (0, -1), 'down': (0, 1), 'left': (-1, 0), 'right': (1, 0)}
                fdx, fdy = facing_dirs.get(proxy.facing, (0, 1))
                tx, ty = proxy.x + fdx, proxy.y + fdy
                if 0 <= tx < GRID_WIDTH and 0 <= ty < GRID_HEIGHT:
                    return tx, ty
                return None

        # ── Manual play: use target_direction as before ───────────────────
        directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]
        dx, dy = directions[self.target_direction]
        target_x = self.player['x'] + dx
        target_y = self.player['y'] + dy
        
        if 0 <= target_x < GRID_WIDTH and 0 <= target_y < GRID_HEIGHT:
            return target_x, target_y
        return None

    def interact(self):
        """Handle space bar interactions - attack if weapon equipped, otherwise normal gameplay"""
        # Snap player facing to match target direction
        facing_map = {0: 'up', 1: 'down', 2: 'left', 3: 'right'}
        self.player['facing'] = facing_map.get(self.target_direction, self.player['facing'])
        
        # Try to attack first if weapon selected
        if self.player_attack():
            return  # Attack was performed
        
        # Check for entity at target location FIRST (before cell interactions)
        target = self.get_target_cell()
        if target:
            check_x, check_y = target
            screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
            
        # Otherwise, normal interactions
        if not target:
            return
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Cannot interact with enchanted cells
        if self.is_cell_enchanted(check_x, check_y, screen_key):
            cell_type = self.current_screen['grid'][check_y][check_x]
            if cell_type == 'WATER':
                print("Drank from enchanted water!")
                return
            print("Cannot interact with enchanted cell!")
            return

        # Pick up any dropped items on this cell first
        if screen_key in self.dropped_items:
            cell_key = (check_x, check_y)
            if cell_key in self.dropped_items[screen_key]:
                for item_name, count in self.dropped_items[screen_key][cell_key].items():
                    self.inventory.add_item(item_name, count)
                del self.dropped_items[screen_key][cell_key]
                self.sound.on_pickup()
                return

        cell = self.current_screen['grid'][check_y][check_x]

        # Check for structure exit (STAIRS_UP)
        if cell == 'STAIRS_UP':
            # Check if in a deep cave level
            if self.player.get('in_structure'):
                current_structure = self.structures.get(self.player['structure_key'])
                if current_structure and current_structure['type'] == 'CAVE' and current_structure['depth'] > 1:
                    # Ascend to previous cave level
                    self.ascend_cave()
                    return
            # Otherwise, exit structure completely
            self.exit_structure()
            return
        
        # Check for deeper cave level (STAIRS_DOWN)
        if cell == 'STAIRS_DOWN':
            self.descend_cave()
            return
        
        # Check for chest/container interaction
        if cell in ('CHEST', 'OPEN_CHEST', 'EMPTY_CRATE', 'BARREL'):
            self.interact_with_chest(check_x, check_y)
            return

        # LOCKED_CHEST — requires destruction to open
        if cell == 'LOCKED_CHEST':
            print("This chest is locked. Destroy it to get the contents.")
            return

        # WELL / DESERT_WELL / WATER_TROUGH — restore energy
        if cell in ('WELL', 'DESERT_WELL', 'WATER_TROUGH'):
            restore = min(40, self.player['max_energy'] - self.player.get('energy', 0))
            self.player['energy'] = self.player.get('energy', 0) + restore
            label = "desert well" if cell == 'DESERT_WELL' else "well"
            print(f"You drink from the {label}. (+{restore} energy)")
            return
        
        # Check for enterable structure (HOUSE, CAVE)
        if CELL_TYPES.get(cell, {}).get('enterable'):
            self.enter_structure(check_x, check_y)
            return
        
        # Weapon check — swords only attack and enter/exit; no world tool interactions
        selected_tool = self.inventory.selected_tool
        if selected_tool and ITEMS.get(selected_tool, {}).get('is_weapon', False):
            return

        # Chop tree — axe must be selected tool
        if cell.startswith('TREE') and self.inventory.selected_tool == 'axe':
            self.player['energy'] = max(0, self.player.get('energy', 0) - 1)
            self.handle_drops(cell, check_x, check_y)
            self.show_attack_animation(check_x, check_y)
            return

        # Mine iron ore — pickaxe must be selected tool
        if cell == 'IRON_ORE' and self.inventory.selected_tool == 'pickaxe':
            self.player['energy'] = max(0, self.player.get('energy', 0) - 1)
            self.inventory.add_item('iron_ore', 1)
            self.current_screen['grid'][check_y][check_x] = self.get_biome_base_cell()
            self.show_attack_animation(check_x, check_y)
            return

        # Mine stone — pickaxe must be selected tool
        if cell == 'STONE' and self.inventory.selected_tool == 'pickaxe':
            self.player['energy'] = max(0, self.player.get('energy', 0) - 1)
            self.inventory.add_item('stone', 1)
            self.current_screen['grid'][check_y][check_x] = 'DIRT'
            self.show_attack_animation(check_x, check_y)
            return

        # Dig mineshaft — pickaxe must be selected tool
        minable_ground = {'DIRT', 'SAND', 'GRASS', 'CAVE_FLOOR'}
        if cell in minable_ground and self.inventory.selected_tool == 'pickaxe':
            self.player['energy'] = max(0, self.player.get('energy', 0) - 1)
            depth = 1
            in_cave = False
            if self.player.get('in_structure'):
                structure = self.structures.get(self.player.get('structure_key'))
                if structure and structure.get('type') == 'CAVE':
                    depth = structure.get('depth', 1)
                    in_cave = True

            mineshaft_chance = PLAYER_MINESHAFT_BASE_CHANCE / (MINESHAFT_DEPTH_DIVISOR ** (depth - 1))

            # In overland: divide chance by count of existing caves/mineshafts in this zone
            if not in_cave:
                grid = self.current_screen['grid']
                cave_count = sum(1 for row in grid for c in row if c in ('CAVE', 'MINESHAFT', 'HIDDEN_CAVE'))
                if cave_count > 0:
                    mineshaft_chance /= cave_count

            self.show_attack_animation(check_x, check_y)

            if random.random() < mineshaft_chance:
                self.current_screen['grid'][check_y][check_x] = 'MINESHAFT'
                if in_cave:
                    print(f"You dug a mineshaft to depth {depth + 1}!")
                else:
                    print(f"You discovered an underground passage!")
            return

        # Till dirt — hoe must be selected tool
        if cell == 'DIRT' and self.inventory.selected_tool == 'hoe':
            self.current_screen['grid'][check_y][check_x] = 'SOIL'
            return
        
        # Harvest crops - get food items
        if cell.startswith('CARROT') and 'harvest' in CELL_TYPES[cell]:
            harvest = CELL_TYPES[cell]['harvest']
            self.inventory.add_item(harvest['item'], harvest['amount'])
            self.current_screen['grid'][check_y][check_x] = 'SOIL'
            return
        
        # Plant carrot on soil
        if cell == 'SOIL' and self.inventory.has_item('carrot'):
            self.inventory.remove_item('carrot', 1)
            self.current_screen['grid'][check_y][check_x] = 'CARROT1'
            return
        
        # Place bones as decoration on ground cells (only when bones is the selected item)
        if cell in ['GRASS', 'DIRT', 'SAND', 'STONE', 'FLOOR_WOOD', 'CAVE_FLOOR', 'COBBLESTONE'] \
                and self.inventory.selected.get('items') == 'bones' \
                and self.inventory.has_item('bones'):
            self.inventory.remove_item('bones', 1)
            
            # Add bones to dropped items (as overlay decoration)
            screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
            if self.player.get('in_structure'):
                screen_key = self.player.get('structure_key', screen_key)
            
            if screen_key not in self.dropped_items:
                self.dropped_items[screen_key] = {}
            
            cell_key = (check_x, check_y)
            if cell_key not in self.dropped_items[screen_key]:
                self.dropped_items[screen_key][cell_key] = {}
            
            self.dropped_items[screen_key][cell_key]['bones'] = \
                self.dropped_items[screen_key][cell_key].get('bones', 0) + 1
            return
    
    def enter_structure(self, cell_x, cell_y):
        """Player enters a house, cave, or mineshaft"""
        cell = self.current_screen['grid'][cell_y][cell_x]
        structure_type = CELL_TYPES[cell].get('interior_type')

        if not structure_type:
            return
        self.sound.on_enter_structure()
        
        # If entering a MINESHAFT from inside a cave — descend deeper
        if cell == 'MINESHAFT' and self.player.get('in_structure'):
            current_structure = self.structures.get(self.player.get('structure_key'))
            if current_structure and current_structure.get('type') == 'CAVE':
                self.descend_cave()
                return

        # Check if structure already exists for this location
        parent_screen_x = self.player['screen_x']
        parent_screen_y = self.player['screen_y']

        # If entering a CAVE/MINESHAFT from inside a house, record which structure
        # we came from so ascend_cave() can return the player to the right place.
        came_from_structure = None
        came_from_pos = None
        if structure_type == 'CAVE' and self.player.get('in_structure'):
            origin_sub = self.structures.get(self.player.get('structure_key'))
            if origin_sub and origin_sub.get('type') == 'HOUSE_INTERIOR':
                came_from_structure = self.player['structure_key']
                came_from_pos = (cell_x, cell_y)

        # Look for existing structure at this location
        existing_key = None
        for key, structure in self.structures.items():
            if (structure['parent_screen'] == (parent_screen_x, parent_screen_y) and
                structure['parent_cell'] == (cell_x, cell_y)):
                existing_key = key
                break

        # For CAVE/MINESHAFT, also check zone cave system
        if not existing_key and structure_type == 'CAVE':
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            if parent_key in self.zone_cave_systems:
                candidate = self.zone_cave_systems[parent_key]
                if candidate in self.structures:
                    existing_key = candidate
                    # Add this entrance to the cave system's entrance list
                    structure = self.structures[existing_key]
                    if (cell_x, cell_y) not in structure.get('entrances', []):
                        structure.setdefault('entrances', []).append((cell_x, cell_y))
                else:
                    # Stale reference — purge so a fresh interior gets generated
                    del self.zone_cave_systems[parent_key]

        # Generate or retrieve structure
        if existing_key:
            structure_key = existing_key
        else:
            structure_key = self.generate_structure_zone(
                parent_screen_x, parent_screen_y,
                cell_x, cell_y,
                structure_type,
                depth=1
            )

        # Save player's parent location for exit routing
        self.player['in_structure'] = True
        self.player['structure_key'] = structure_key
        self.player['structure_parent'] = (parent_screen_x, parent_screen_y, cell_x, cell_y)
        # Secret-entrance context so ascend_cave knows how to exit
        self.player['cave_via_structure'] = came_from_structure
        self.player['cave_via_pos'] = came_from_pos

        # Update player zone coords to the structure's virtual coordinates
        vx, vy = map(int, structure_key.split(','))
        self.player['screen_x'] = vx
        self.player['screen_y'] = vy

        # Switch to structure grid
        structure = self.structures[structure_key]
        self.current_screen = structure

        # Position player at entrance — snap world coords to prevent interpolation slide
        entrance = structure['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        self.player['world_x'] = float(entrance[0])
        self.player['world_y'] = float(entrance[1])

        print(f"Entered {structure_type}!")
        self._teleport_followers_with_player()

    def _teleport_followers_with_player(self):
        """Teleport all followers to wherever the player currently is (overworld or structure)."""
        in_sub = self.player.get('in_structure', False)
        sub_key = self.player.get('structure_key')
        player_screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"

        for fid in list(self.followers):
            if fid not in self.entities:
                continue
            f = self.entities[fid]

            # Remove from old location (unified registry — search all zone entity lists)
            old_sk = f"{f.screen_x},{f.screen_y}"
            for sk, lst in self.screen_entities.items():
                if fid in lst:
                    lst.remove(fid)

            # Place in new location (screen_entities is the unified registry)
            if in_sub and sub_key:
                if sub_key not in self.screen_entities:
                    self.screen_entities[sub_key] = []
                if fid not in self.screen_entities[sub_key]:
                    self.screen_entities[sub_key].append(fid)
                f.in_structure = True
                f.structure_key = sub_key
            else:
                if player_screen_key not in self.screen_entities:
                    self.screen_entities[player_screen_key] = []
                if fid not in self.screen_entities[player_screen_key]:
                    self.screen_entities[player_screen_key].append(fid)
                f.in_structure = False
                f.structure_key = None

            # Snap to player's current zone coords (virtual when in structure)
            f.screen_x = self.player['screen_x']
            f.screen_y = self.player['screen_y']
            f.x = max(1, self.player['x'] - 1)
            f.y = self.player['y']
            f.world_x = float(f.x)
            f.world_y = float(f.y)

    def exit_structure(self):
        """Player exits back to parent screen"""
        if not self.player['in_structure']:
            return
        
        # Get parent location
        parent_info = self.player['structure_parent']
        if not parent_info:
            return
        
        parent_screen_x, parent_screen_y, parent_cell_x, parent_cell_y = parent_info
        
        # Switch back to parent screen
        parent_key = f"{parent_screen_x},{parent_screen_y}"
        if parent_key in self.screens:
            self.current_screen = self.screens[parent_key]
        else:
            self.current_screen = self.generate_screen(parent_screen_x, parent_screen_y)
        
        # Restore player to parent overworld zone — snap world coords to prevent interpolation slide
        self.player['x'] = parent_cell_x
        self.player['y'] = parent_cell_y
        self.player['screen_x'] = parent_screen_x
        self.player['screen_y'] = parent_screen_y
        self.player['world_x'] = float(parent_cell_x)
        self.player['world_y'] = float(parent_cell_y)

        # If returning to another structure (e.g., house after exiting a cave inside it)
        parent_key = f"{parent_screen_x},{parent_screen_y}"
        if parent_key in self.structures:
            parent_struct = self.structures[parent_key]
            grand_parent = parent_struct.get('parent_screen')
            grand_cell = parent_struct.get('parent_cell')
            self.player['in_structure'] = True
            self.player['structure_key'] = parent_key
            self.player['structure_parent'] = (
                grand_parent[0], grand_parent[1], grand_cell[0], grand_cell[1]
            ) if grand_parent and grand_cell else None
        else:
            self.player['in_structure'] = False
            self.player['structure_key'] = None
            self.player['structure_parent'] = None

        print("Exited to outside!")
        self._teleport_followers_with_player()

    def descend_cave(self):
        """Go deeper into a cave"""
        if not self.player['in_structure']:
            return
        
        current_structure = self.structures.get(self.player['structure_key'])
        if not current_structure or current_structure['type'] != 'CAVE':
            return
        
        # Get parent info
        parent_screen_x, parent_screen_y = current_structure['parent_screen']
        parent_cell_x, parent_cell_y = current_structure['parent_cell']
        new_depth = current_structure['depth'] + 1
        
        # Look for existing deeper level first
        deeper_key = None
        for key, structure in self.structures.items():
            if (structure['parent_screen'] == (parent_screen_x, parent_screen_y) and
                structure['parent_cell'] == (parent_cell_x, parent_cell_y) and
                structure['type'] == 'CAVE' and
                structure['depth'] == new_depth):
                deeper_key = key
                break
        
        # If not found, generate new deeper level aligned with current STAIRS_DOWN position
        if not deeper_key:
            stairs_down = current_structure.get('stairs_down')
            align_kwargs = {'align_x': stairs_down[0], 'align_y': stairs_down[1]} if stairs_down else {}
            deeper_key = self.generate_structure_zone(
                parent_screen_x, parent_screen_y,
                parent_cell_x, parent_cell_y,
                'CAVE',
                depth=new_depth,
                **align_kwargs
            )
        
        # Update player to new structure zone
        vx, vy = map(int, deeper_key.split(','))
        self.player['structure_key'] = deeper_key
        self.player['screen_x'] = vx
        self.player['screen_y'] = vy
        deeper_structure = self.structures[deeper_key]
        self.current_screen = deeper_structure

        # Position player at entrance — snap world coords to prevent interpolation slide
        entrance = deeper_structure['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        self.player['world_x'] = float(entrance[0])
        self.player['world_y'] = float(entrance[1])

        print(f"Descended to cave level {new_depth}!")
        self._teleport_followers_with_player()

        # Spawn enemies for this depth
        self.spawn_cave_entities(deeper_key, new_depth)
    
    def ascend_cave(self):
        """Go up one level in a cave"""
        if not self.player['in_structure']:
            return
        
        current_structure = self.structures.get(self.player['structure_key'])
        if not current_structure or current_structure['type'] != 'CAVE':
            return
        
        current_depth = current_structure['depth']
        if current_depth <= 1:
            via_key = self.player.get('cave_via_structure')
            if via_key:
                self._exit_secret_cave_entrance()
            else:
                self.exit_structure()
            return
        
        # Get parent info for generating/finding the level above
        parent_screen_x, parent_screen_y = current_structure['parent_screen']
        parent_cell_x, parent_cell_y = current_structure['parent_cell']
        target_depth = current_depth - 1
        
        # Find or generate the level above
        # Look for existing structure at this depth
        upper_level_key = None
        for key, structure in self.structures.items():
            if (structure['parent_screen'] == (parent_screen_x, parent_screen_y) and
                structure['parent_cell'] == (parent_cell_x, parent_cell_y) and
                structure['type'] == 'CAVE' and
                structure['depth'] == target_depth):
                upper_level_key = key
                break
        
        # If not found, generate it (shouldn't normally happen, but just in case)
        if not upper_level_key:
            upper_level_key = self.generate_structure_zone(
                parent_screen_x, parent_screen_y,
                parent_cell_x, parent_cell_y,
                'CAVE',
                depth=target_depth
            )
        
        # Update player to upper structure zone
        vx, vy = map(int, upper_level_key.split(','))
        self.player['structure_key'] = upper_level_key
        self.player['screen_x'] = vx
        self.player['screen_y'] = vy
        upper_structure = self.structures[upper_level_key]
        self.current_screen = upper_structure

        # Position player at entrance — snap world coords to prevent interpolation slide
        entrance = upper_structure['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        self.player['world_x'] = float(entrance[0])
        self.player['world_y'] = float(entrance[1])

        print(f"Ascended to cave level {target_depth}!")
        self._teleport_followers_with_player()

    def _exit_secret_cave_entrance(self):
        """Exit a cave that was entered via a secret MINESHAFT inside a house.

        Priority:
          1. Overworld CAVE/MINESHAFT entrance for this zone (teleports player there).
          2. Back inside the house interior at the MINESHAFT tile.
        """
        parent_info = self.player['structure_parent']
        psx, psy = parent_info[0], parent_info[1]
        zone_key = f"{psx},{psy}"
        via_key = self.player.get('cave_via_structure')
        via_pos = self.player.get('cave_via_pos')

        # Clear secret-entrance tracking
        self.player['cave_via_structure'] = None
        self.player['cave_via_pos'] = None

        # ── Option 1: find a real overworld cave entrance ─────────────────────
        zone_grid = self.screens.get(zone_key, {}).get('grid', [])
        overworld_entrance = None
        cave_system_key = self.zone_cave_systems.get(zone_key)
        if cave_system_key and cave_system_key in self.structures:
            cx, cy = self.structures[cave_system_key].get('parent_cell', (None, None))
            if (cx is not None and
                    0 <= cy < len(zone_grid) and 0 <= cx < len(zone_grid[cy]) and
                    zone_grid[cy][cx] in ('CAVE', 'MINESHAFT')):
                overworld_entrance = (cx, cy)

        if overworld_entrance:
            ox, oy = overworld_entrance
            self.current_screen = (self.screens[zone_key] if zone_key in self.screens
                                   else self.generate_screen(psx, psy))
            self.player['x'] = ox
            self.player['y'] = oy
            self.player['world_x'] = float(ox)
            self.player['world_y'] = float(oy)
            self.player['screen_x'] = psx
            self.player['screen_y'] = psy
            self.player['in_structure'] = False
            self.player['structure_key'] = None
            self.player['structure_parent'] = None
            print("Exited secret cave — arrived at overworld cave entrance.")
            return

        # ── Option 2: return to house interior at the MINESHAFT tile ─────────
        house_sub = self.structures.get(via_key)
        if house_sub:
            self.current_screen = house_sub
            px = via_pos[0] if via_pos else house_sub['entrance'][0]
            py = via_pos[1] if via_pos else house_sub['entrance'][1]
            self.player['x'] = px
            self.player['y'] = py
            self.player['world_x'] = float(px)
            self.player['world_y'] = float(py)
            self.player['in_structure'] = True
            self.player['structure_key'] = via_key
            vx, vy = map(int, via_key.split(','))
            self.player['screen_x'] = vx
            self.player['screen_y'] = vy
            hp = house_sub.get('parent_screen', (psx, psy))
            hc = house_sub.get('parent_cell', (0, 0))
            self.player['structure_parent'] = (hp[0], hp[1], hc[0], hc[1])
            print("Exited secret cave — returned to house interior.")
            return

        # Fallback: normal exit to overworld
        self.exit_structure()

    def spawn_cave_entities(self, structure_key, depth):
        """Spawn enemies in cave based on depth"""
        structure = self.structures[structure_key]
        grid = structure['grid']
        
        # Number of enemies scales with depth (1-3 + depth)
        num_enemies = random.randint(1 + depth, 3 + depth)
        enemy_types = ['GOBLIN', 'SKELETON', 'WOLF']
        
        spawned = 0
        attempts = 0
        
        while spawned < num_enemies and attempts < 100:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)
            
            # Check if valid spawn location (cave floor, not near entrance)
            if grid[y][x] == 'CAVE_FLOOR' and abs(y - GRID_HEIGHT + 2) > 3:
                enemy_type = random.choice(enemy_types)
                # Level scales with depth
                level = random.randint(depth, depth + 1)
                
                vx, vy = map(int, structure_key.split(','))
                entity = Entity(enemy_type, x, y, vx, vy, level)
                entity.in_structure = True
                entity.structure_key = structure_key
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                self.entities[entity_id] = entity
                self.entities_spawned_total = getattr(self, 'entities_spawned_total', 0) + 1

                if structure_key not in self.screen_entities:
                    self.screen_entities[structure_key] = []
                self.screen_entities[structure_key].append(entity_id)

                spawned += 1
            
            attempts += 1
    
    def interact_with_chest(self, chest_x, chest_y):
        """Open chest and give loot to player"""
        # Create unique chest identifier
        if self.player['in_structure']:
            chest_id = f"{self.player['structure_key']}:{chest_x},{chest_y}"
        else:
            screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
            chest_id = f"{screen_key}:{chest_x},{chest_y}"
        
        # OPEN_CHEST cell is already looted — visual state only
        current_cell = self.current_screen['grid'][chest_y][chest_x]
        if current_cell == 'OPEN_CHEST':
            print("This chest is empty.")
            return

        # Check if already opened (fallback for older opened_chests set)
        if chest_id in self.opened_chests:
            print("This chest is empty.")
            return

        items_found = []

        # NPC-stashed chests: contents stored directly in chest_contents
        chest_contents = getattr(self, 'chest_contents', {})
        if chest_id in chest_contents:
            contents = chest_contents.pop(chest_id)
            for item_name, count in contents.items():
                if count > 0:
                    self.inventory.add_item(item_name, count)
                    item_label = ITEMS.get(item_name, {}).get('name', item_name)
                    items_found.append(f"{count}x {item_label}")
            # Flip NPC-placed CHEST to OPEN_CHEST after looting
            if not self.player['in_structure']:
                self.current_screen['grid'][chest_y][chest_x] = 'OPEN_CHEST'
            self.opened_chests.add(chest_id)
            if items_found:
                print(f"Found: {', '.join(items_found)}")
            else:
                print("The chest was empty...")
            self.sound.on_pickup()
            return

        # Structure/loot-table chests
        if self.player['in_structure']:
            current_structure = self.structures.get(self.player['structure_key'])
            loot_table_name = current_structure['chests'].get((chest_x, chest_y), 'HOUSE_CHEST')
        else:
            loot_table_name = 'HOUSE_CHEST'

        # Generate loot
        loot_table = LOOT_TABLES.get(loot_table_name, [])

        
        for loot_entry in loot_table:
            if random.random() < loot_entry['chance']:
                amount = random.randint(loot_entry['min'], loot_entry['max'])
                item_name = loot_entry['item']
                self.inventory.add_item(item_name, amount)
                items_found.append(f"{amount}x {ITEMS[item_name]['name']}")
        
        # Mark chest as opened; NPC-placed overworld CHEST flips to OPEN_CHEST
        self.opened_chests.add(chest_id)
        if not self.player['in_structure'] and self.current_screen['grid'][chest_y][chest_x] == 'CHEST':
            self.current_screen['grid'][chest_y][chest_x] = 'OPEN_CHEST'

        if items_found:
            print(f"Found: {', '.join(items_found)}")
        else:
            print("The chest was empty...")
    
    def new_game(self):
        """Start a new game"""
        self.bug_catcher.clear()
        self.player = {
            'x': 12, 'y': 9, 
            'screen_x': 0, 'screen_y': 0,
            'level': 1,
            'xp': 0,
            'xp_to_level': 100,
            'health': 100,
            'max_health': 100,
            'energy': 100,
            'max_energy': 100,
            'base_damage': 10,
            'blocking': False,
            'block_locked': False,
            'last_shift_press_tick': 0,
            'friendly_fire': False,      # OFF = cannot damage peaceful entities
            'last_attack_tick': 0,
            'in_structure': False,
            'structure_key': None,
            'structure_parent': None,
            'facing': 'down',
            'anim_frame': 'still',
            'anim_timer': 0,
            '_next_step': '1',
            'is_moving': False,
        }
        self.init_autopilot()
        self.screens = {}
        self.tick = 0
        self.inventory = Inventory()
        # Purge stale dynamic follower entries injected into ITEMS by previous sessions
        for _stale in [k for k, v in list(ITEMS.items()) if v.get('is_follower')]:
            del ITEMS[_stale]
        # Add every static item — skip is_follower (spawned later via _pending_follower_type)
        for _item_key in ITEMS:
            if not ITEMS[_item_key].get('is_follower'):
                self.inventory.add_item(_item_key, 1)
        self.dropped_items = {}
        self.buried_items = {}
        self.enchanted_cells = {}
        self.enchanted_entities = {}
        self.followers = []
        self.follower_items = {}
        self.npc_quests = []
        self.active_npc_quest_npc_id = None
        self.zone_keepers = {}
        self.domains = {}
        self._domain_counter = 0
        self.structures = {}
        self.opened_chests = set()
        self.next_structure_id = 0
        self.door_map = {}
        self.entities = {}
        self.next_entity_id = 0
        self.screen_entities = {}
        self.attack_animations = []
        self.current_screen = self.generate_screen(0, 0)

        # Choose follower type now but defer actual spawning until after time pass.
        # Spawning immediately puts the entity in screen_entities where hostile NPCs
        # can kill it during the 150-250 year simulation before the player even loads.
        self._pending_follower_type = random.choice(['SHEEP', 'DEER', 'WOLF', 'BAT', 'GOBLIN', 'SKELETON', 'TERMITE'])
        self._time_pass_spawned = False

        # Trigger initial time passage for world generation
        if self.needs_initial_time_passage:
            self.needs_initial_time_passage = False
            
            # Instantiate nearby zones so they all get equal development
            for dx in range(-3, 4):
                for dy in range(-3, 4):
                    zone_x = self.player['screen_x'] + dx
                    zone_y = self.player['screen_y'] + dy
                    screen_key = f"{zone_x},{zone_y}"
                    if screen_key not in self.screens:
                        self.generate_screen(zone_x, zone_y)
            
            # Run minimal initialization to spawn entities
            print("Initializing world...")
            for _ in range(3):  # Just 3 quick cycles to ensure spawns
                self.probabilistic_zone_updates()
            
            self.state = 'death'  # Trigger death sequence
            self.death_years = random.randint(150, 250)  # More years for better history
            self.death_start_tick = self.tick
            self.death_ticks_simulated = 0
            self.is_initial_generation = True  # Flag for time passage
            print(f"World is generating... {self.death_years} years passing...")
        else:
            self.state = 'playing'
            # Autopilot grace period: don't engage for 15 seconds after starting
            self.last_input_tick = self.tick + 900
    
    def update_enchanted_cells(self):
        """Update and remove enchanted cells with small random chance"""
        cells_to_remove = []
        for cell_key in list(self.enchanted_cells.keys()):
            # 1% chance per tick to release enchantment
            if random.random() < 0.01:
                cells_to_remove.append(cell_key)
        
        for cell_key in cells_to_remove:
            del self.enchanted_cells[cell_key]
    
    def _auto_debug_shutdown(self):
        """Save, flush logs, and quit cleanly at end of AUTO_DEBUG session."""
        ts = _datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[AutoDebug] Timer expired at tick {self.tick} ({ts}) — saving and quitting")
        self.bug_catcher.log({
            'tick': self.tick,
            'category': 'auto_debug_shutdown',
            'ts': ts,
            'total_ticks': self.tick,
            'is_night': getattr(self, 'is_night', False),
            'entity_count': len(getattr(self, 'entities', {})),
            'zone_count': len(getattr(self, 'screens', {})),
            'structure_count': len(getattr(self, 'structures', {})),
            'follower_count': len(getattr(self, 'followers', [])),
            'player_zone': f"{self.player.get('screen_x',0)},{self.player.get('screen_y',0)}",
            'player_health': self.player.get('health'),
            'player_level': self.player.get('level'),
        })
        self.bug_catcher.flush()
        try:
            self.save_game(path='debug/auto_debug_save.json')
            self.save_game(path='savegame.json')
            print("[AutoDebug] Save written to debug/auto_debug_save.json and savegame.json")
        except Exception as exc:
            print(f"[AutoDebug] Save failed: {exc}")
        try:
            import json as _json
            _run = getattr(self, '_auto_debug_run_num', 0)
            _sf  = getattr(self, '_auto_debug_state_file', 'debug/auto_debug_state.json')
            with open(_sf, 'w') as _f:
                _json.dump({'run': _run + 1}, _f)
        except Exception as exc:
            print(f"[AutoDebug] State file write failed: {exc}")
        import pygame
        pygame.quit()
        self.running = False

    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_input()
            
            if self.state == 'playing':
                self.move_player()
                self.check_follower_integrity()

                # Sound: update music context + ambient each tick
                _in_struct = bool(self.player.get('in_structure', False))
                _cell_at_player = self.current_screen['grid'][self.player['y']][self.player['x']] if self.current_screen else None
                self.sound.update(self.tick, 'playing', self.is_night, _in_struct, _cell_at_player)

                # Check if targeting peaceful NPC for inspection
                self.check_npc_inspection()
                
                # Periodic ghost-entity reconciliation (every ~10 seconds)
                if self.tick % 600 == 1:
                    self.reconcile_screen_entities()

                # Freeze detector — log if any entity in the player's zone has idle_timer
                if self.tick % 300 == 0:
                    _pk = f"{self.player['screen_x']},{self.player['screen_y']}"
                    _frozen = []
                    for _eid in self.screen_entities.get(_pk, []):
                        if _eid in self.entities:
                            _e = self.entities[_eid]
                            if getattr(_e, 'idle_timer', 0) > 0:
                                _frozen.append(f"{_e.type}(id={_eid},timer={_e.idle_timer})")
                    if _frozen:
                        print(f"[FREEZE-DETECT] tick={self.tick} autopilot={getattr(self, 'autopilot', False)} "
                              f"inspected_npc={self.inspected_npc} frozen={_frozen}")
                
                # Very slow player health and energy regen (once per second)
                if self.tick % 60 == 0:
                    if self.player['health'] < self.player['max_health']:
                        self.player['health'] = min(
                            self.player['health'] + 0.3,
                            self.player['max_health']
                        )
                    max_e = self.player.get('max_energy', 100)
                    cur_e = self.player.get('energy', max_e)
                    if cur_e < max_e:
                        self.player['energy'] = min(cur_e + 1, max_e)

                # Update quest system
                self.update_quests()
                
                # Update enchanted cells
                self.update_enchanted_cells()
                
                # New probabilistic update system
                self.probabilistic_zone_updates()
                
                # Process catch-up during idle
                if self.is_idle() and self.catchup_queue:
                    self.process_catchup_queue()

                # Watchdog: periodic sample + integrity checks + flush
                self.watchdog.update(self.tick, self)

                # Autosave every 30 seconds
                if self.autosave_enabled and self.tick > 0 and self.tick % (30 * FPS) == 0:
                    self.save_game()

                # AUTO_DEBUG: hard-stop when wall-clock timer expires
                if hasattr(self, '_auto_debug_end_time') and _time.time() >= self._auto_debug_end_time:
                    self._auto_debug_shutdown()
                    break

                self.tick += 1
                self.draw_game()
                self.draw_dev_screen()
            elif self.state == 'death':
                self.update_death_screen()
                self.draw_death_screen()
            elif self.state == 'menu':
                self.sound.update(self.tick, 'menu', False, False, None)
                self.draw_menu()
            elif self.state == 'paused':
                self.draw_paused()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        self.bug_catcher.flush()
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()