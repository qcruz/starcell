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
        self.inspected_npc = None  # Entity being inspected
        self.inspected_npc_tick = 0  # When inspection started  # When to hide display

        # Debug / bug-tracking
        self.bug_catcher = BugCatcher()
        self.watchdog = Watchdog(self.bug_catcher)

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
        ]
        
        for cell_type in ['GRASS', 'DIRT', 'SAND', 'STONE', 'WATER', 'DEEP_WATER',
                          'COBBLESTONE',
                          'TREE1', 'TREE2', 'TREE3', 'FLOWER',
                          'CARROT1', 'CARROT2', 'CARROT3',
                          'CAMP', 'HOUSE', 'STONE_HOUSE', 'WOOD', 'PLANKS',
                          'WALL', 'CAVE', 'MINESHAFT', 'SOIL', 'MEAT', 'FUR', 'BONES',
                          'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'CHEST',
                          'STAIRS_DOWN', 'STAIRS_UP',
                          'CACTUS', 'BARREL', 'RUINED_SANDSTONE_COLUMN']:
            
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
                       'black bat']
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
                                    
                                    # Store with normalized name (underscores only)
                                    normalized_name = f"{entity_type}_{direction}_{frame_name}"
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
        }
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
        
        # Log death reason if not from combat
        if entity.health <= 0:
            if hasattr(entity, 'age') and hasattr(entity, 'max_age') and entity.age > entity.max_age:
                name_str = entity.name if entity.name else entity.type
                print(f"{name_str} died of old age at {entity.age} years (max: {entity.max_age})")
            elif entity.hunger <= 0:
                print(f"{entity.type} died from starvation at ({entity.x}, {entity.y})")
            elif entity.thirst <= 0:
                print(f"{entity.type} died from dehydration at ({entity.x}, {entity.y})")
        
        # Free keeper slot if this entity was a keeper
        if getattr(entity, 'keeper', False):
            for zone_key, slots in self.zone_keepers.items():
                for ktype, eid in list(slots.items()):
                    if eid == entity_id:
                        del slots[ktype]
                        break

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

        # Entity inventory drops (skip spells and wood/planks)
        for item_name, count in entity.inventory.items():
            if item_name in ITEMS and ITEMS[item_name].get('is_spell', False):
                continue
            if item_name in ('wood', 'planks'):
                continue
            all_item_drops[item_name] = all_item_drops.get(item_name, 0) + count

        if all_item_drops:
            if screen_key not in self.dropped_items:
                self.dropped_items[screen_key] = {}

            # Scatter 1-2 individual items nearby so they display as item sprites
            scatter_pool = [(k, v) for k, v in all_item_drops.items() if v >= 1]
            n_scatter = min(random.randint(1, 2), len(scatter_pool))
            scattered = random.sample(scatter_pool, n_scatter)
            for item_name, _ in scattered:
                all_item_drops[item_name] -= 1
                if all_item_drops[item_name] <= 0:
                    del all_item_drops[item_name]
                sx = max(1, min(GRID_WIDTH - 2, entity.x + random.randint(-2, 2)))
                sy = max(1, min(GRID_HEIGHT - 2, entity.y + random.randint(-2, 2)))
                cell_key = (sx, sy)
                if cell_key not in self.dropped_items[screen_key]:
                    self.dropped_items[screen_key][cell_key] = {}
                self.dropped_items[screen_key][cell_key][item_name] = \
                    self.dropped_items[screen_key][cell_key].get(item_name, 0) + 1

            # Consolidate remaining items into one pile at entity position → shows as itembag
            if all_item_drops:
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
        
        # Remove from entities dict
        del self.entities[entity_id]

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
        """Check if player is targeting any entity and Shift is held — set inspection"""
        # During autopilot, the proxy's facing direction constantly sweeps over
        # nearby NPCs.  The inspection system sets idle_timer=30 on each one and
        # the inspected_npc guard skips their entire AI update, which freezes
        # every NPC the proxy walks past.  Disable inspection while autopilot
        # is active so the proxy doesn't paralyse the zone.
        if getattr(self, 'autopilot', False):
            self.inspected_npc = None
            return

        # Inspection only triggers while Shift is held
        keys = pygame.key.get_pressed()
        if not (keys[pygame.K_LSHIFT] or keys[pygame.K_RSHIFT]):
            self.inspected_npc = None
            return

        target = self.get_target_cell()
        if not target:
            self.inspected_npc = None
            return
        
        check_x, check_y = target

        # Unified zone system: player screen coords reflect current zone (incl. structure virtual coords)
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        candidates = self.screen_entities.get(screen_key, [])

        # Find entity at target cell
        for entity_id in candidates:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.x == check_x and entity.y == check_y:
                    # Never inspect the autopilot proxy — it renders as the player
                    if entity.props.get('is_autopilot_proxy', False):
                        self.inspected_npc = None
                        return
                    if self.inspected_npc != entity_id:
                        # New NPC targeted — open all inventory panels + quest UI
                        for cat in ['items', 'tools', 'magic', 'followers']:
                            self.inventory.open_menus.add(cat)
                        self.quest_ui_open = True
                    self.inspected_npc = entity_id
                    self.inspected_npc_tick = self.tick

                    # Make peaceful entities idle briefly during inspection
                    if not entity.props.get('hostile'):
                        entity.is_idle = True
                        entity.idle_timer = 30  # 0.5 seconds
                        entity.idle_duration = 30
                    return

        # No entity at target
        self.inspected_npc = None
    
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
                    elif 'degrades_to' in cell_info and random.random() < cell_info.get('degrade_rate', 0):
                        # Special handling for cobblestone - only decay outside center lanes
                        if cell == 'COBBLESTONE':
                            center_x = GRID_WIDTH // 2
                            center_y = GRID_HEIGHT // 2
                            
                            # Check if in center lanes (±2 cells)
                            on_horizontal_center = abs(y - center_y) <= 2
                            on_vertical_center = abs(x - center_x) <= 2
                            
                            # Don't decay if on main roads
                            if on_horizontal_center or on_vertical_center:
                                continue
                            
                            # Check if touching structures (house, camp, cave)
                            has_structure_neighbor = False
                            for nx, ny in [(x-1, y), (x+1, y), (x, y-1), (x, y+1)]:
                                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                                    neighbor_cell = screen['grid'][ny][nx]
                                    if neighbor_cell in ['HOUSE', 'CAMP', 'CAVE', 'MINESHAFT']:
                                        has_structure_neighbor = True
                                        break
                            
                            # Don't decay if near structures
                            if has_structure_neighbor:
                                continue
                        
                        # Apply decay
                        self.set_grid_cell(screen, x, y, cell_info['degrades_to'])

        # Desert rock/ore formation — SAND slowly solidifies into STONE;
        # existing STONE rarely yields IRON_ORE
        if screen.get('biome') == 'DESERT':
            for y in range(1, GRID_HEIGHT - 1):
                for x in range(1, GRID_WIDTH - 1):
                    cell = screen['grid'][y][x]
                    if cell == 'SAND' and random.random() < DESERT_ROCK_FORMATION_RATE:
                        self.set_grid_cell(screen, x, y, 'STONE')
                    elif cell == 'STONE' and random.random() < DESERT_ORE_FORMATION_RATE:
                        self.set_grid_cell(screen, x, y, 'IRON_ORE')

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
                    self.handle_inventory_click(event.pos)
                    self.handle_quest_ui_click(event.pos)
            
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
                            continue
                        if 'actions' in self.inventory.open_menus:
                            selected_action = self.inventory.selected.get('actions')
                            if selected_action:
                                self.execute_action(selected_action)
                                continue
                        self.interact()
                    elif event.key == pygame.K_l:
                        selected = self.inventory.selected_magic
                        if selected == 'rain_spell':
                            self.cast_rain_spell()
                        elif selected == 'day_spell':
                            self.cast_day_spell()
                        else:
                            self.cast_star_spell()
                    elif event.key == pygame.K_k:
                        # Release all enchantments
                        self.release_enchantments()
                    elif event.key == pygame.K_j:
                        # Release selected follower
                        self.release_follower()
                    elif event.key == pygame.K_b:
                        # Toggle blocking
                        self.player['blocking'] = not self.player['blocking']
                        print(f"Blocking: {'ON' if self.player['blocking'] else 'OFF'}")
                    elif event.key == pygame.K_v:
                        # Toggle friendly fire (allow/deny damage to peaceful entities)
                        self.player['friendly_fire'] = not self.player.get('friendly_fire', False)
                        state = 'ON — can attack anyone' if self.player['friendly_fire'] else 'OFF — peaceful entities protected'
                        print(f"Friendly Fire: {state}")
                    elif event.key == pygame.K_c:
                        # Toggle crafting screen
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
                        # Attempt to craft with selected items
                        self.attempt_craft()
                    elif event.key == pygame.K_i:
                        _was_open = 'items' in self.inventory.open_menus
                        self.inventory.toggle_menu('items')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_t:
                        _was_open = 'tools' in self.inventory.open_menus
                        self.inventory.toggle_menu('tools')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_m:
                        _was_open = 'magic' in self.inventory.open_menus
                        self.inventory.toggle_menu('magic')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_r:
                        _was_open = 'actions' in self.inventory.open_menus
                        self.inventory.toggle_menu('actions')
                        if not _was_open:
                            self.sound.on_inventory_open()
                    elif event.key == pygame.K_f:
                        if pygame.key.get_mods() & pygame.KMOD_SHIFT:
                            if self.inspected_npc:
                                self.handle_npc_follow_interaction()
                        else:
                            _was_open = 'followers' in self.inventory.open_menus
                            self.inventory.toggle_menu('followers')
                            if not _was_open:
                                self.sound.on_inventory_open()
                    elif event.key == pygame.K_e:
                        # Pick up cell or items from target
                        self.pickup_cell_or_items()
                    elif event.key == pygame.K_n:
                        # NPC trade interaction
                        self.npc_trade_interaction()
                    elif event.key == pygame.K_p:
                        # Place selected item as cell
                        self.place_selected_item()
                    elif event.key == pygame.K_q:
                        mods = pygame.key.get_mods()
                        if (mods & pygame.KMOD_SHIFT) and self.inspected_npc:
                            self.handle_npc_quest_interaction()
                        else:
                            # Toggle quest UI
                            self.quest_ui_open = not self.quest_ui_open
                    elif event.key == pygame.K_d:
                        # Drop selected item
                        self.drop_selected_item()
                    elif event.key == pygame.K_LEFT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(-1)
                    elif event.key == pygame.K_RIGHT and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.cycle_inventory_slot(1)
                    elif event.key == pygame.K_a and (pygame.key.get_mods() & pygame.KMOD_SHIFT):
                        self.toggle_autopilot()
                    elif event.key == pygame.K_g:
                        # Toggle debug memory lanes visualization
                        self.debug_memory_lanes = not self.debug_memory_lanes
                        print(f"Debug Memory Lanes: {'ON' if self.debug_memory_lanes else 'OFF'}")
                    # Number keys to select inventory slots
                    elif event.key in [pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, 
                                      pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8, 
                                      pygame.K_9, pygame.K_0]:
                        slot = (event.key - pygame.K_1) if event.key != pygame.K_0 else 9
                        self.select_inventory_slot(slot)
                
                elif self.state == 'paused':
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_p:
                        self.state = 'playing'
                    elif event.key == pygame.K_s:
                        self.save_game()
                    elif event.key == pygame.K_m:
                        self.state = 'menu'
        
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
        categories = ['tools', 'items', 'magic', 'actions', 'followers', 'crafting']
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
            
            # Draw horizontally
            for i, (item_name, count) in enumerate(items):
                slot_x = start_x + i * (slot_size + 2)
                slot_y = start_y - y_offset

                # Check if click is in this slot
                if (slot_x <= pos[0] <= slot_x + slot_size and
                        slot_y <= pos[1] <= slot_y + slot_size):

                    if category == 'tools':
                        # --- Tool bar slot clicked: select and mark as pending ---
                        # Never unequip on click — unequip only happens when a
                        # different inventory item is then clicked (equip_to_slot)
                        self.inventory.selected_tool_slot_idx = i
                        self.inventory.selected['tools'] = item_name
                        self.inventory.pending_equip_slot = i
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

            y_offset += slot_size + 15  # Stack next category above
    
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
        except Exception:
            pass  # use defaults

    def _save_settings(self):
        try:
            import json as _json
            with open(_SETTINGS_PATH, 'w') as f:
                _json.dump({
                    'ambient_music': self.ambient_music_enabled,
                    'debug_prints':  self.debug_prints_enabled,
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
        if mr and mr.collidepoint(pos):
            self.ambient_music_enabled = not self.ambient_music_enabled
            self._save_settings()
            self._apply_settings()
        elif dr and dr.collidepoint(pos):
            self.debug_prints_enabled = not self.debug_prints_enabled
            self._save_settings()
            self._apply_settings()

    # -------------------------------------------------------------------------
    # Spells
    # -------------------------------------------------------------------------

    def cast_rain_spell(self):
        if self.player['energy'] < 90:
            print("[Spell] Not enough energy!")
            return
        self.player['energy'] -= 90
        if self.is_raining:
            self.is_raining = False
            self.rain_timer = 0
            print("[Spell] Rain stopped.")
        else:
            self.is_raining = True
            self.rain_timer = 0
            self.rain_duration = random.randint(RAIN_DURATION_MIN, RAIN_DURATION_MAX)
            print("[Spell] Rain started.")

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
            self.gain_xp(xp_reward)
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
                is_depth_1 = current_structure.get('depth', 1) == 1
                if is_depth_1 and new_y >= GRID_HEIGHT - 1:
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
            
            # Check if there's an entity at this position
            if screen_key in self.screen_entities:
                for entity_id in self.screen_entities[screen_key]:
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        if entity.x == check_x and entity.y == check_y:
                            # Target this entity
                            self.inspected_npc = entity_id
                            print(f"Targeting: {entity.name if entity.name else entity.type}")
                            return  # Entity targeting takes priority
        
        # Otherwise, normal interactions
        if not target:
            return
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Cannot interact with enchanted cells
        if self.is_cell_enchanted(check_x, check_y, screen_key):
            print("Cannot interact with enchanted cell!")
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
        
        # Check for chest interaction
        if cell == 'CHEST':
            self.interact_with_chest(check_x, check_y)
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
            self.gain_xp(1)
            return

        # Mine iron ore — pickaxe must be selected tool
        if cell == 'IRON_ORE' and self.inventory.selected_tool == 'pickaxe':
            self.player['energy'] = max(0, self.player.get('energy', 0) - 1)
            self.inventory.add_item('iron_ore', 1)
            self.current_screen['grid'][check_y][check_x] = self.get_biome_base_cell()
            self.show_attack_animation(check_x, check_y)
            self.gain_xp(1)
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
            self.gain_xp(1)
            return
        
        # Place bones as decoration on ground cells
        if cell in ['GRASS', 'DIRT', 'SAND', 'STONE', 'FLOOR_WOOD', 'CAVE_FLOOR', 'COBBLESTONE'] and self.inventory.has_item('bones'):
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
                existing_key = self.zone_cave_systems[parent_key]
                # Add this entrance to the cave system's entrance list
                structure = self.structures.get(existing_key)
                if structure and (cell_x, cell_y) not in structure.get('entrances', []):
                    structure.setdefault('entrances', []).append((cell_x, cell_y))

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

        # Clear structure state
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
        
        # If not found, generate new deeper level
        if not deeper_key:
            deeper_key = self.generate_structure_zone(
                parent_screen_x, parent_screen_y,
                parent_cell_x, parent_cell_y,
                'CAVE',
                depth=new_depth
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
        
        # Check if already opened
        if chest_id in self.opened_chests:
            print("This chest is empty.")
            return
        
        # Get loot table type
        if self.player['in_structure']:
            current_structure = self.structures.get(self.player['structure_key'])
            loot_table_name = current_structure['chests'].get((chest_x, chest_y), 'HOUSE_CHEST')
        else:
            loot_table_name = 'HOUSE_CHEST'  # Default
        
        # Generate loot
        loot_table = LOOT_TABLES.get(loot_table_name, [])
        items_found = []
        
        for loot_entry in loot_table:
            if random.random() < loot_entry['chance']:
                amount = random.randint(loot_entry['min'], loot_entry['max'])
                item_name = loot_entry['item']
                self.inventory.add_item(item_name, amount)
                items_found.append(f"{amount}x {ITEMS[item_name]['name']}")
        
        # Mark chest as opened
        self.opened_chests.add(chest_id)
        
        # Chest stays as CHEST (doesn't convert to floor anymore)
        # Player can see it was already looted from the "empty" message
        
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
        self.inventory.add_item('axe', 1)
        self.inventory.add_item('hoe', 1)
        self.inventory.add_item('shovel', 1)
        self.inventory.add_item('pickaxe', 1)
        self.inventory.add_item('bucket', 1)
        self.inventory.add_magic('star_spell', 1)
        self.inventory.add_item('rain_spell', 1)
        self.inventory.add_item('day_spell', 1)
        self.inventory.add_item('shove', 1)
        self.inventory.add_item('bone_sword', 1)
        self.inventory.add_item('carrot', 5)
        self.inventory.add_item('tree_sapling', 3)
        self.inventory.add_item('magic_rune', 1)  # Testing sprite overlay
        self.dropped_items = {}
        self.enchanted_cells = {}
        self.enchanted_entities = {}
        self.followers = []
        self.follower_items = {}
        self.npc_quests = []
        self.active_npc_quest_npc_id = None
        self.zone_keepers = {}
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
            print("[AutoDebug] Save written to debug/auto_debug_save.json")
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

                # AUTO_DEBUG: hard-stop when wall-clock timer expires
                if hasattr(self, '_auto_debug_end_time') and _time.time() >= self._auto_debug_end_time:
                    self._auto_debug_shutdown()
                    break

                self.tick += 1
                self.draw_game()
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
        
        pygame.quit()

if __name__ == "__main__":
    game = Game()
    game.run()