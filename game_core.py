"""
StarCell Game Core
Rendering, player systems, world gen, quests, save/load, zone updates.
"""
from constants import *
from entity import *


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
            'magic_pool': 10,
            'max_magic_pool': 10,
            'health': 100,
            'max_health': 100,
            'base_damage': 5,
            'blocking': False,
            'friendly_fire': False,      # OFF = cannot damage peaceful entities (press V to toggle)
            'last_attack_tick': 0,
            'in_subscreen': False,
            'subscreen_key': None,
            'subscreen_parent': None  # (parent_screen_x, parent_screen_y, parent_cell_x, parent_cell_y)
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
        
        # Subscreen system (legacy — being migrated to zone connections)
        self.subscreens = {}  # {subscreen_key: subscreen_data}
        self.opened_chests = set()  # Track which chests have been looted
        self.next_subscreen_id = 0  # For generating unique subscreen IDs
        self.zone_cave_systems = {}  # {screen_key: cave_subscreen_key} - one cave system per zone
        
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
        
        # Entities per screen: {screen_key: [entity_ids]}
        self.screen_entities = {}
        
        # Entities per subscreen: {subscreen_key: [entity_ids]}
        self.subscreen_entities = {}
        
        # Quest System
        self.quests = {}  # {quest_type: Quest object}
        self.active_quest = 'FARM'  # Default active quest
        self.quest_ui_open = False
        self.quest_ui_selected = 0
        
        # Initialize all quest types
        for quest_type in QUEST_TYPES.keys():
            self.quests[quest_type] = Quest(quest_type)
        
        # Flag for initial world generation time passage
        self.needs_initial_time_passage = True
        
        # Trading System
        self.trader_display = None  # {entity_id: {recipes: [...], position: (x,y)}}
        self.trader_display_tick = 0
        self.inspected_npc = None  # Entity being inspected
        self.inspected_npc_tick = 0  # When inspection started  # When to hide display

    def get_neighbors(self, x, y, screen_key):
        """Get all 8 neighbors of a cell"""
        if screen_key not in self.screens:
            return []
        
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                    neighbors.append(self.screens[screen_key]['grid'][ny][nx])
        return neighbors
    
    def count_cell_type(self, neighbors, cell_type):
        """Count how many neighbors match a cell type (or start with it)"""
        if not neighbors:
            return 0
        return sum(1 for n in neighbors if n == cell_type or (isinstance(n, str) and n.startswith(cell_type)))
    
    def is_at_exit(self, x, y):
        """Check if position is at a zone exit (2-tile areas)"""
        # Top exit
        if y == 0 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'top'
        # Bottom exit
        if y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'bottom'
        # Left exit
        if x == 0 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'left'
        # Right exit
        if x == GRID_WIDTH - 1 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'right'
        return False, None
    
    def get_adjacent_screen_biome(self, screen_x, screen_y, direction):
        """Get the biome of an adjacent screen"""
        adj_x, adj_y = screen_x, screen_y
        if direction == 'top':
            adj_y -= 1
        elif direction == 'bottom':
            adj_y += 1
        elif direction == 'left':
            adj_x -= 1
        elif direction == 'right':
            adj_x += 1
        
        adj_key = f"{adj_x},{adj_y}"
        if adj_key in self.screens:
            return self.screens[adj_key]['biome']
        
        # Generate biome type without creating full screen
        biome_types = list(BIOMES.keys())
        biome_index = abs(adj_x + adj_y * 3) % len(biome_types)
        return biome_types[biome_index]
    
    def get_common_cell_for_biome(self, biome_name):
        """Get a common cell type for a biome"""
        biome_cells = {
            'FOREST': ['GRASS', 'GRASS', 'DIRT'],  # Exits must be walkable
            'PLAINS': ['GRASS', 'GRASS', 'DIRT'],
            'DESERT': ['SAND', 'SAND', 'DIRT'],
            'MOUNTAINS': ['DIRT', 'DIRT', 'GRASS'],  # Exits must be walkable
        }
        cells = biome_cells.get(biome_name, ['GRASS', 'DIRT'])
        return random.choice(cells)

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
                          'CAMP', 'HOUSE', 'WOOD', 'PLANKS',
                          'WALL', 'CAVE', 'MINESHAFT', 'SOIL', 'MEAT', 'FUR', 'BONES',
                          'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'CHEST',
                          'STAIRS_DOWN', 'STAIRS_UP']:
            
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
    
    def get_neighbors(self, x, y, screen_key):
        """Get all 8 neighbors of a cell"""
        if screen_key not in self.screens:
            return []
        
        neighbors = []
        for dx in [-1, 0, 1]:
            for dy in [-1, 0, 1]:
                if dx == 0 and dy == 0:
                    continue
                nx, ny = x + dx, y + dy
                if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                    neighbors.append(self.screens[screen_key]['grid'][ny][nx])
        return neighbors
    
    def count_cell_type(self, neighbors, cell_type):
        """Count how many neighbors match a cell type (or start with it)"""
        if not neighbors:
            return 0
        return sum(1 for n in neighbors if n == cell_type or (isinstance(n, str) and n.startswith(cell_type)))
    
    def is_at_exit(self, x, y):
        """Check if position is at a zone exit (2-tile areas)"""
        # Top exit
        if y == 0 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'top'
        # Bottom exit
        if y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
            return True, 'bottom'
        # Left exit
        if x == 0 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'left'
        # Right exit
        if x == GRID_WIDTH - 1 and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
            return True, 'right'
        return False, None
    
    def get_adjacent_screen_biome(self, screen_x, screen_y, direction):
        """Get the biome of an adjacent screen"""
        adj_x, adj_y = screen_x, screen_y
        if direction == 'top':
            adj_y -= 1
        elif direction == 'bottom':
            adj_y += 1
        elif direction == 'left':
            adj_x -= 1
        elif direction == 'right':
            adj_x += 1
        
        adj_key = f"{adj_x},{adj_y}"
        if adj_key in self.screens:
            return self.screens[adj_key]['biome']
        
        # Generate biome type without creating full screen
        biome_types = list(BIOMES.keys())
        biome_index = abs(adj_x + adj_y * 3) % len(biome_types)
        return biome_types[biome_index]
    
    def get_common_cell_for_biome(self, biome_name):
        """Get a common cell type for a biome"""
        biome_cells = {
            'FOREST': ['GRASS', 'GRASS', 'DIRT'],  # Exits must be walkable
            'PLAINS': ['GRASS', 'GRASS', 'DIRT'],
            'DESERT': ['SAND', 'SAND', 'DIRT'],
            'MOUNTAINS': ['DIRT', 'DIRT', 'GRASS'],  # Exits must be walkable
        }
        cells = biome_cells.get(biome_name, ['GRASS', 'DIRT'])
        return random.choice(cells)
    
    def get_exit_positions(self, direction):
        """Get the two tile positions for a given exit direction
        Returns a list of (x, y) tuples representing the 2-tile exit"""
        if direction == 'top':
            return [(GRID_WIDTH // 2 - 1, 0), (GRID_WIDTH // 2, 0)]
        elif direction == 'bottom':
            return [(GRID_WIDTH // 2 - 1, GRID_HEIGHT - 1), (GRID_WIDTH // 2, GRID_HEIGHT - 1)]
        elif direction == 'left':
            return [(0, GRID_HEIGHT // 2 - 1), (0, GRID_HEIGHT // 2)]
        elif direction == 'right':
            return [(GRID_WIDTH - 1, GRID_HEIGHT // 2 - 1), (GRID_WIDTH - 1, GRID_HEIGHT // 2)]
        return []
    
    def get_biome_base_cell(self):
        """Return the primary walkable ground cell for the current zone's biome."""
        biome = 'FOREST'
        if self.current_screen:
            biome = self.current_screen.get('biome', 'FOREST')
        biome_map = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
            'HOUSE_INTERIOR': 'FLOOR_WOOD', 'CAVE': 'CAVE_FLOOR',
        }
        return biome_map.get(biome, 'GRASS')
    
    
    def consolidate_dropped_items(self, screen_key):
        """Merge ALL dropped items within 3-cell range into the largest nearby pile.
        Runs every zone update. Very aggressive — items should never sit adjacent."""
        
        if screen_key not in self.dropped_items:
            return
        
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        grid = screen['grid']
        items = self.dropped_items[screen_key]
        
        if len(items) <= 1:
            return
        
        # Multi-pass: keep merging until stable
        changed = True
        passes = 0
        while changed and passes < 5:
            changed = False
            passes += 1
            positions = list(items.keys())
            
            for pos in positions:
                if pos not in items:
                    continue
                
                ix, iy = pos
                my_count = sum(items[pos].values())
                
                # Find the best neighbor to merge with (within 3 cells)
                best_target = None
                best_count = -1
                best_dist = 999
                
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if dx == 0 and dy == 0:
                            continue
                        nx, ny = ix + dx, iy + dy
                        if not (0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT):
                            continue
                        neighbor_key = (nx, ny)
                        if neighbor_key not in items or neighbor_key == pos:
                            continue
                        neighbor_count = sum(items[neighbor_key].values())
                        dist = abs(dx) + abs(dy)
                        # Merge smaller into larger; if equal, merge into closer
                        if (neighbor_count > best_count or 
                            (neighbor_count == best_count and dist < best_dist)):
                            cell = grid[ny][nx]
                            if not CELL_TYPES.get(cell, {}).get('solid', False):
                                best_target = neighbor_key
                                best_count = neighbor_count
                                best_dist = dist
                
                # Merge: smaller pile goes into larger, or into closer if equal
                if best_target:
                    if my_count <= best_count:
                        # Merge pos into best_target
                        for item_name, count in items[pos].items():
                            items[best_target][item_name] = items[best_target].get(item_name, 0) + count
                        del items[pos]
                        changed = True
                    elif my_count > best_count:
                        # Merge best_target into pos
                        for item_name, count in items[best_target].items():
                            items[pos][item_name] = items[pos].get(item_name, 0) + count
                        del items[best_target]
                        changed = True
    
    def catch_up_entities(self, screen_x, screen_y, cycles):
        """Simplified entity simulation for catch-up with eating, drinking, and healing"""
        
        screen_key = f"{screen_x},{screen_y}"
        if screen_key not in self.screen_entities or screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        
        # Simplified raid simulation for high population zones during catch-up
        if cycles > 20:  # Only for significant catch-up periods
            # Count human NPCs
            human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR', 'WIZARD']
            human_count = 0
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    base_type = entity.type.replace('_double', '')
                    if base_type in human_npc_types:
                        human_count += 1
            
            # If high population and no cave exists, simulate a raid event
            if human_count >= 7:  # Higher threshold for catch-up
                # Check if cave exists
                has_cave = False
                for y in range(GRID_HEIGHT):
                    for x in range(GRID_WIDTH):
                        if screen['grid'][y][x] in ['CAVE', 'HIDDEN_CAVE', 'MINESHAFT']:
                            has_cave = True
                            break
                    if has_cave:
                        break
                
                # 20% chance to simulate raid during catch-up
                if random.random() < 0.20:
                    # Spawn 1-2 hostiles (simplified raid)
                    hostile_count = random.randint(1, 2)
                    hostile_type = random.choice(['GOBLIN', 'BANDIT', 'WOLF'])
                    
                    for _ in range(hostile_count):
                        # Spawn at random interior location
                        spawn_x = random.randint(3, GRID_WIDTH - 4)
                        spawn_y = random.randint(3, GRID_HEIGHT - 4)
                        
                        # Check if walkable
                        if not CELL_TYPES[screen['grid'][spawn_y][spawn_x]].get('solid', False):
                            entity = Entity(hostile_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
                            entity_id = self.next_entity_id
                            self.next_entity_id += 1
                            self.entities[entity_id] = entity
                            self.screen_entities[screen_key].append(entity_id)
                    
                    # Kill a low-level NPC (simulate raid casualty)
                    lowest_entity = None
                    lowest_level = 999
                    for entity_id in self.screen_entities[screen_key]:
                        if entity_id in self.entities:
                            entity = self.entities[entity_id]
                            if entity.type in human_npc_types and entity.level < lowest_level:
                                lowest_entity = entity_id
                                lowest_level = entity.level
                    
                    if lowest_entity:
                        self.remove_entity(lowest_entity)
                    
                    # Add cave if none exists
                    if not has_cave:
                        cave_x = random.randint(2, GRID_WIDTH - 3)
                        cave_y = random.randint(2, GRID_HEIGHT - 3)
                        screen['grid'][cave_y][cave_x] = 'CAVE'
                    
                    print(f"Catch-up: Raid event simulated in [{screen_key}] - {hostile_count} {hostile_type}(s) spawned")
        
        # Faction simulation for warriors during catch-up
        if cycles > 10:  # Simulate factions for moderate catch-up
            warriors_in_zone = []
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.type == 'WARRIOR':
                        warriors_in_zone.append((entity_id, entity))
            
            # Assign factions to warriors without them
            for warrior_id, warrior in warriors_in_zone:
                if not warrior.faction:
                    self.assign_warrior_faction(warrior, screen_key)
            
            # Simulate faction conflicts
            if len(warriors_in_zone) >= 2:
                # Group by faction
                faction_groups = {}
                for warrior_id, warrior in warriors_in_zone:
                    if warrior.faction:
                        if warrior.faction not in faction_groups:
                            faction_groups[warrior.faction] = []
                        faction_groups[warrior.faction].append((warrior_id, warrior))
                
                # If multiple factions, simulate conflict (10% chance)
                if len(faction_groups) >= 2 and random.random() < 0.1:
                    factions = list(faction_groups.keys())
                    faction1 = factions[0]
                    faction2 = factions[1]
                    
                    # Randomly kill one warrior from smaller faction
                    if len(faction_groups[faction1]) < len(faction_groups[faction2]):
                        casualty_id, casualty = random.choice(faction_groups[faction1])
                    else:
                        casualty_id, casualty = random.choice(faction_groups[faction2])
                    
                    entities_to_remove.append(casualty_id)
                    print(f"Catch-up: Faction war in [{screen_key}] - {casualty.name} ({casualty.faction}) killed")
        
        entities_to_remove = []
        entities_to_transition = []  # Track entities that should move to adjacent zones
        
        for entity_id in self.screen_entities[screen_key][:]:
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            
            # Peaceful human NPCs stay in their zones
            peaceful_humans = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'WIZARD']
            can_travel = entity.type not in peaceful_humans
            
            # Random chance for zone transition (animals and hostiles only)
            if can_travel and cycles > 10:  # Only for catch-up scenarios
                # Very small chance per cycle (0.5%)
                transition_chance = min(cycles * 0.005, 0.3)  # Cap at 30%
                if random.random() < transition_chance:
                    entities_to_transition.append(entity_id)
                    continue  # Skip other updates, will transition
            
            # Simulate eating and drinking based on food availability
            food_sources = entity.props.get('food_sources', [])
            water_sources = entity.props.get('water_sources', [])
            
            # Check if food is available nearby
            has_food = False
            has_water = False
            
            for y in range(GRID_HEIGHT):
                for x in range(GRID_WIDTH):
                    cell = screen['grid'][y][x]
                    
                    # Check for food
                    if cell in food_sources:
                        # Calculate distance
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist <= 5:  # Within reasonable foraging range
                            has_food = True
                    
                    # Check for water
                    if cell in water_sources:
                        dist = abs(x - entity.x) + abs(y - entity.y)
                        if dist <= 5:
                            has_water = True
            
            # Simulate eating/drinking for each cycle
            for cycle_num in range(cycles):
                # Decay stats
                entity.hunger = max(0, entity.hunger - 0.5)
                entity.thirst = max(0, entity.thirst - 0.3)
                
                # NPC-specific behaviors (simulate once per ~second of catch-up)
                if cycle_num % 2 == 0:  # Every 2 cycles (about 1 second)
                    behavior_config = entity.props.get('behavior_config')
                    if behavior_config:
                        self.execute_entity_behavior(entity, behavior_config)
                    elif entity.type in ['GOBLIN', 'BANDIT', 'TERMITE']:
                        self.hostile_structure_behavior(entity)
                    
                    # Human NPCs place camps
                    if behavior_config and behavior_config.get('can_place_camp'):
                        if random.random() < NPC_CAMP_PLACE_RATE:
                            self.npc_place_camp(entity)
                    if entity.type in ['FARMER', 'TRADER', 'BANDIT', 'GUARD', 'LUMBERJACK', 'WIZARD']:
                        if random.random() < 0.01:
                            self.npc_place_camp(entity)
                    
                    # Miners discover caves
                    if entity.type == 'MINER':
                        if random.random() < NPC_CAMP_PLACE_RATE:
                            self.miner_place_cave(entity)
                
                # Eat if hungry and food available
                if entity.hunger < 80 and has_food:
                    if random.random() < 0.6:  # 60% chance per cycle to eat (increased from 30%)
                        # Determine food value
                        food_value = 30  # Default
                        for food in food_sources:
                            if food.startswith('CARROT'):
                                food_value = 40
                                break
                            elif food == 'GRASS':
                                food_value = 20
                        entity.eat(food_value)
                
                # Drink if thirsty and water available
                if entity.thirst < 80 and has_water:
                    if random.random() < 0.6:  # 60% chance per cycle to drink (increased from 30%)
                        entity.drink(40)
                
                # Check for proximity healing bonuses
                heal_boost = 1.0
                if not entity.props.get('hostile', False):
                    # Check for camp or house within 3 cells
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
                
                # Regenerate health if well-fed and hydrated
                entity.regenerate_health(heal_boost)
                
                # Damage from starvation
                if entity.hunger <= 0:
                    entity.health -= 1
                if entity.thirst <= 0:
                    entity.health -= 2
            
            # Remove dead entities
            if entity.health <= 0:
                entities_to_remove.append(entity_id)
                continue
        
        # Process zone transitions for traveling entities
        for entity_id in entities_to_transition:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                # Pick random adjacent zone
                directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]
                dx, dy = random.choice(directions)
                
                new_screen_x = screen_x + dx
                new_screen_y = screen_y + dy
                new_screen_key = f"{new_screen_x},{new_screen_y}"
                
                # Generate target screen if needed
                if new_screen_key not in self.screens:
                    self.generate_screen(new_screen_x, new_screen_y)
                
                # Determine spawn position on appropriate edge
                if dx == -1:  # Moving left
                    new_x = GRID_WIDTH - 4
                    new_y = random.randint(2, GRID_HEIGHT - 3)
                elif dx == 1:  # Moving right
                    new_x = 3
                    new_y = random.randint(2, GRID_HEIGHT - 3)
                elif dy == -1:  # Moving up
                    new_x = random.randint(2, GRID_WIDTH - 3)
                    new_y = GRID_HEIGHT - 4
                else:  # Moving down
                    new_x = random.randint(2, GRID_WIDTH - 3)
                    new_y = 3
                
                # Check if valid position
                if new_screen_key in self.screens:
                    target_screen = self.screens[new_screen_key]
                    if not CELL_TYPES[target_screen['grid'][new_y][new_x]].get('solid', False):
                        # Remove from old screen
                        if screen_key in self.screen_entities:
                            if entity_id in self.screen_entities[screen_key]:
                                self.screen_entities[screen_key].remove(entity_id)
                        
                        # Update position
                        entity.screen_x = new_screen_x
                        entity.screen_y = new_screen_y
                        entity.x = new_x
                        entity.y = new_y
                        
                        # Add to new screen
                        if new_screen_key not in self.screen_entities:
                            self.screen_entities[new_screen_key] = []
                        self.screen_entities[new_screen_key].append(entity_id)
        
        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)
    
    def catch_up_screen(self, screen_x, screen_y, cycles_missed):
        """Apply catch-up updates efficiently"""
        
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return
        
        # Cap cycles
        cycles_missed = min(cycles_missed, MAX_CYCLES_TO_SIMULATE)
        
        # Tier 1: Recent - run normally
        if cycles_missed < 5:
            for _ in range(cycles_missed):
                self.apply_cellular_automata(screen_x, screen_y)
            self.screen_last_update[key] = self.tick
            return
        
        # Tier 2 & 3: Use bulk updates
        screen = self.screens[key]
        
        # Build neighbor cache once
        neighbor_cache = {}
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                neighbors = self.get_neighbors(x, y, key)
                neighbor_cache[(x, y)] = {
                    'water': self.count_cell_type(neighbors, 'WATER'),
                    'deep_water': self.count_cell_type(neighbors, 'DEEP_WATER'),
                    'dirt': self.count_cell_type(neighbors, 'DIRT'),
                    'grass': self.count_cell_type(neighbors, 'GRASS'),
                    'tree': self.count_cell_type(neighbors, 'TREE'),
                    'sand': self.count_cell_type(neighbors, 'SAND'),
                    'flower': self.count_cell_type(neighbors, 'FLOWER')
                }
        
        # Apply bulk changes
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]
                
                # Skip stable cells
                if cell in ['WALL', 'HOUSE', 'CAVE']:
                    continue
                
                counts = neighbor_cache.get((x, y), {})
                total_water = counts.get('water', 0) + counts.get('deep_water', 0)
                
                # Calculate accumulated probability
                change_prob = 0
                new_cell = cell
                
                # Simplified rules with accumulated probability
                if cell == 'DIRT' and total_water >= 2:
                    change_prob = min(cycles_missed * 0.03, 0.8)
                    new_cell = 'GRASS'
                
                elif cell == 'GRASS' and total_water == 0 and counts.get('dirt', 0) >= 2:
                    change_prob = min(cycles_missed * 0.02, 0.7)
                    new_cell = 'DIRT'
                
                elif cell == 'GRASS' and 1 <= counts.get('tree', 0) <= 2 and total_water >= 1:
                    change_prob = min(cycles_missed * 0.01, 0.5)
                    new_cell = 'TREE1'
                
                elif cell == 'DIRT' and total_water == 0 and counts.get('sand', 0) >= 2:
                    change_prob = min(cycles_missed * 0.02, 0.7)
                    new_cell = 'SAND'
                
                elif cell == 'WATER' and counts.get('water', 0) >= 4:
                    change_prob = min(cycles_missed * 0.05, 0.8)
                    new_cell = 'DEEP_WATER'
                
                elif cell == 'GRASS' and 1 <= counts.get('flower', 0) <= 2:
                    change_prob = min(cycles_missed * 0.01, 0.3)
                    new_cell = 'FLOWER'
                
                if random.random() < change_prob:
                    self.set_grid_cell(screen, x, y, new_cell)
        
        # Consolidate dropped items
        self.consolidate_dropped_items(key)
        
        # Simplified entity updates
        self.catch_up_entities(screen_x, screen_y, cycles_missed)
        
        self.screen_last_update[key] = self.tick
    
    def on_zone_transition(self, new_screen_x, new_screen_y):
        """When player enters new zone, catch up nearby zones"""
        
        # Catch up the zone we're entering
        new_key = f"{new_screen_x},{new_screen_y}"
        if new_key in self.screen_last_update:
            cycles = (self.tick - self.screen_last_update[new_key]) // 60
            if cycles > 0:
                self.catch_up_screen(new_screen_x, new_screen_y, cycles)
        
        # Queue adjacent zones for catch-up (lower priority)
        for dx, dy in [(-1,0), (1,0), (0,-1), (0,1)]:
            adj_x, adj_y = new_screen_x + dx, new_screen_y + dy
            adj_key = f"{adj_x},{adj_y}"
            if adj_key in self.screens and adj_key in self.screen_last_update:
                cycles = (self.tick - self.screen_last_update[adj_key]) // 60
                if cycles >= 5:  # Only queue if needs catch-up
                    distance = abs(dx) + abs(dy)
                    self.catchup_queue.append((distance, adj_x, adj_y, cycles))
    
    def process_catchup_queue(self):
        """Process catch-up queue during idle or safe moments"""
        
        if not self.catchup_queue:
            return
        
        # Sort by priority (distance)
        self.catchup_queue.sort()
        
        # Process up to budget
        processed = 0
        while self.catchup_queue and processed < MAX_CATCHUP_PER_FRAME:
            priority, sx, sy, cycles = self.catchup_queue.pop(0)
            self.catch_up_screen(sx, sy, min(cycles, MAX_CYCLES_TO_SIMULATE))
            processed += 1

    # ===================================================================
    # ZONE PRIORITY QUEUE SYSTEM
    # ===================================================================
    
    def calculate_zone_priority(self, zone_key):
        """Calculate priority score for a zone. Higher = update sooner.
        
        Components:
        - Distance to player (closer = higher priority)
        - Staleness (more ticks since last update = higher priority)
        - Connection bonus (connected to player's current zone via structures)
        - Quest bonus (has quest targets)
        - Structure bonus (has active structures)
        """
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']
        player_zone = f"{player_x},{player_y}"
        
        # If player is in a structure zone, that's their actual zone
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            player_zone = self.player['subscreen_key']
        
        # Parse zone coords
        if self.is_overworld_zone(zone_key):
            parts = zone_key.split(',')
            zone_x, zone_y = int(parts[0]), int(parts[1])
            distance = abs(zone_x - player_x) + abs(zone_y - player_y)
        else:
            # Structure zone — use parent zone distance
            if zone_key in self.structure_zones:
                parent = self.structure_zones[zone_key]['parent_zone']
                parts = parent.split(',')
                zone_x, zone_y = int(parts[0]), int(parts[1])
                distance = abs(zone_x - player_x) + abs(zone_y - player_y)
            else:
                distance = 50  # Unknown zone, low priority
        
        # === Distance score: 100 for player zone, decreasing ===
        if zone_key == player_zone:
            distance_score = 100.0
        elif distance == 0:
            distance_score = 90.0  # Same overworld zone but player in structure
        elif distance <= 1:
            distance_score = 50.0
        elif distance <= 2:
            distance_score = 25.0
        elif distance <= 3:
            distance_score = 10.0
        else:
            distance_score = max(1.0, 5.0 / distance)
        
        # === Staleness score: ticks since last update ===
        last_update = self.screen_last_update.get(zone_key, 0)
        staleness_ticks = self.tick - last_update
        # Every 60 ticks (1 sec) of staleness adds 1 priority point, capped at 30
        staleness_score = min(30.0, staleness_ticks / 60.0)
        
        # === Connection bonus: connected to player's zone via structures ===
        connection_score = 0.0
        if zone_key in self.zone_connections:
            for connected_key, conn_type, *_ in self.zone_connections[zone_key]:
                if connected_key == player_zone:
                    connection_score = 40.0  # Directly connected to player
                    break
                # Check if connected zone is adjacent to player
                if self.is_overworld_zone(connected_key):
                    cp = connected_key.split(',')
                    cd = abs(int(cp[0]) - player_x) + abs(int(cp[1]) - player_y)
                    if cd <= 1:
                        connection_score = max(connection_score, 20.0)
        
        # === Structure bonus: structure zones in zones near player get a boost ===
        structure_score = 0.0
        if zone_key in self.structure_zones:
            structure_score = 15.0  # All structure zones get a base boost
        elif zone_key in self.zone_structures:
            structure_score = 5.0  # Zones with structures get a smaller boost
        
        # === Quest bonus: zones with active quest targets ===
        quest_score = 0.0
        for quest_type, quest in self.quests.items():
            if hasattr(quest, 'target_zone') and quest.target_zone == zone_key:
                quest_score = 20.0
                break
        
        total = distance_score + staleness_score + connection_score + structure_score + quest_score
        return total
    
    def get_priority_sorted_zones(self):
        """Get all zones sorted by priority (highest first).
        Returns list of (priority, zone_key) tuples."""
        zone_priorities = []
        
        # Include all instantiated overworld zones
        for zone_key in self.instantiated_zones:
            if zone_key in self.screens:
                priority = self.calculate_zone_priority(zone_key)
                zone_priorities.append((priority, zone_key))
        
        # Include all structure zones that are in self.screens
        for struct_key in self.structure_zones:
            if struct_key in self.screens:
                priority = self.calculate_zone_priority(struct_key)
                zone_priorities.append((priority, struct_key))
        
        # Sort by priority (highest first)
        zone_priorities.sort(reverse=True)
        return zone_priorities
    
    @staticmethod
    def is_overworld_zone(zone_key):
        """Check if zone key is an overworld zone (format 'x,y') vs structure zone."""
        if ':' in zone_key or zone_key.startswith('struct_'):
            return False
        parts = zone_key.split(',')
        if len(parts) != 2:
            return False
        try:
            int(parts[0])
            int(parts[1])
            return True
        except ValueError:
            return False
    
    def add_zone_connection(self, zone_a, zone_b, connection_type, cell_x=0, cell_y=0):
        """Add a bidirectional connection between two zones."""
        if zone_a not in self.zone_connections:
            self.zone_connections[zone_a] = []
        if zone_b not in self.zone_connections:
            self.zone_connections[zone_b] = []
        
        # Avoid duplicates
        existing_a = [(c[0], c[1]) for c in self.zone_connections[zone_a]]
        if (zone_b, connection_type) not in existing_a:
            self.zone_connections[zone_a].append((zone_b, connection_type, cell_x, cell_y))
        
        existing_b = [(c[0], c[1]) for c in self.zone_connections[zone_b]]
        if (zone_a, connection_type) not in existing_b:
            self.zone_connections[zone_b].append((zone_a, connection_type, cell_x, cell_y))
    
    def remove_zone_connection(self, zone_a, zone_b):
        """Remove all connections between two zones."""
        if zone_a in self.zone_connections:
            self.zone_connections[zone_a] = [c for c in self.zone_connections[zone_a] if c[0] != zone_b]
        if zone_b in self.zone_connections:
            self.zone_connections[zone_b] = [c for c in self.zone_connections[zone_b] if c[0] != zone_a]
    
    def register_structure_as_zone(self, parent_zone_key, cell_x, cell_y, structure_type):
        """Register a structure as a proper zone with connections.
        Returns the structure's zone key."""
        # Check if structure zone already exists at this location
        for struct_key, info in self.structure_zones.items():
            if (info['parent_zone'] == parent_zone_key and 
                info['cell'] == (cell_x, cell_y)):
                return struct_key
        
        # Create new structure zone key using offset coordinates
        struct_id = self.next_structure_zone_id
        self.next_structure_zone_id += 1
        struct_zone_key = f"struct_{struct_id}"
        
        # Register in structure tracking
        self.structure_zones[struct_zone_key] = {
            'parent_zone': parent_zone_key,
            'type': structure_type,
            'cell': (cell_x, cell_y)
        }
        
        # Register in parent's structure list
        if parent_zone_key not in self.zone_structures:
            self.zone_structures[parent_zone_key] = []
        self.zone_structures[parent_zone_key].append(struct_zone_key)
        
        # Add bidirectional connection
        self.add_zone_connection(parent_zone_key, struct_zone_key, 'structure_entrance', cell_x, cell_y)
        
        return struct_zone_key
    
    def draw_sprite_or_fallback(self, sprite_name, x, y, fallback_color, fallback_symbol):
        """Draw sprite if available, otherwise draw colored square with symbol"""
        if sprite_name in self.sprites:
            self.screen.blit(self.sprites[sprite_name], (x * CELL_SIZE, y * CELL_SIZE))
        else:
            # Fallback to colored square
            pygame.draw.rect(self.screen, fallback_color,
                           (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))
            
            # Draw symbol
            text = self.tiny_font.render(fallback_symbol, True, COLORS['WHITE'])
            text_rect = text.get_rect(center=(
                x * CELL_SIZE + CELL_SIZE // 2,
                y * CELL_SIZE + CELL_SIZE // 2
            ))
            self.screen.blit(text, text_rect)
        
    def generate_screen(self, sx, sy):
        """Generate a procedural screen"""
        key = f"{sx},{sy}"
        if key in self.screens:
            return self.screens[key]
        
        # Determine biome - Forest is most common
        biome_types = list(BIOMES.keys())
        biome_roll = random.random()
        if biome_roll < 0.6:  # 60% forest
            biome_name = 'FOREST'
        elif biome_roll < 0.8:  # 20% plains
            biome_name = 'PLAINS'
        elif biome_roll < 0.95:  # 15% mountains
            biome_name = 'MOUNTAINS'
        else:  # 5% desert
            biome_name = 'DESERT'
        biome = BIOMES[biome_name]
        
        # Create exits - check neighboring screens for matching exits
        exits = {
            'top': random.random() > 0.5,
            'bottom': random.random() > 0.5,
            'left': random.random() > 0.5,
            'right': random.random() > 0.5
        }
        
        # Force exits to match neighboring screens (bidirectional)
        top_neighbor_key = f"{sx},{sy-1}"
        if top_neighbor_key in self.screens:
            # Match neighbor's bottom exit
            exits['top'] = self.screens[top_neighbor_key]['exits']['bottom']
        
        bottom_neighbor_key = f"{sx},{sy+1}"
        if bottom_neighbor_key in self.screens:
            # Match neighbor's top exit
            exits['bottom'] = self.screens[bottom_neighbor_key]['exits']['top']
        
        left_neighbor_key = f"{sx-1},{sy}"
        if left_neighbor_key in self.screens:
            # Match neighbor's right exit
            exits['left'] = self.screens[left_neighbor_key]['exits']['right']
        
        right_neighbor_key = f"{sx+1},{sy}"
        if right_neighbor_key in self.screens:
            # Match neighbor's left exit
            exits['right'] = self.screens[right_neighbor_key]['exits']['left']
        
        # Ensure at least 2-3 exits (never isolated zones)
        exit_count = sum(exits.values())
        
        if exit_count < 2:
            # Force 2 random exits
            sides = [k for k, v in exits.items() if not v]
            random.shuffle(sides)
            exits[sides[0]] = True
            if len(sides) > 1:
                exits[sides[1]] = True
        
        # 50% chance for 3rd exit if only have 2
        if sum(exits.values()) == 2 and random.random() < 0.5:
            sides = [k for k, v in exits.items() if not v]
            if sides:
                exits[random.choice(sides)] = True
        
        # UPDATE NEIGHBORS: Ensure bidirectional consistency
        # If we have an exit, neighbors must have matching entrance
        if exits['top'] and top_neighbor_key in self.screens:
            self.screens[top_neighbor_key]['exits']['bottom'] = True
            # Update neighbor's grid to have exit
            self.update_screen_exits(sx, sy-1)
        
        if exits['bottom'] and bottom_neighbor_key in self.screens:
            self.screens[bottom_neighbor_key]['exits']['top'] = True
            self.update_screen_exits(sx, sy+1)
        
        if exits['left'] and left_neighbor_key in self.screens:
            self.screens[left_neighbor_key]['exits']['right'] = True
            self.update_screen_exits(sx-1, sy)
        
        if exits['right'] and right_neighbor_key in self.screens:
            self.screens[right_neighbor_key]['exits']['left'] = True
            self.update_screen_exits(sx+1, sy)
        
        # Generate grid
        exit_cell = {'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
                     'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT'}.get(biome_name, 'GRASS')
        grid = []
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                if y == 0 or y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    if (y == 0 and exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                        row.append(exit_cell)
                    elif (y == GRID_HEIGHT - 1 and exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                        row.append(exit_cell)
                    elif (x == 0 and exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                        row.append(exit_cell)
                    elif (x == GRID_WIDTH - 1 and exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                        row.append(exit_cell)
                    else:
                        row.append('WALL')
                else:
                    rand = random.random()
                    cumulative = 0
                    cell_type = 'GRASS'
                    
                    for terrain, prob in biome.items():
                        cumulative += prob
                        if rand < cumulative:
                            cell_type = terrain
                            break
                    row.append(cell_type)
            grid.append(row)
        
        # Generate variant grid — assigns visual variants to cells
        variant_grid = []
        for y in range(GRID_HEIGHT):
            variant_row = []
            for x in range(GRID_WIDTH):
                cell = grid[y][x]
                variant = None
                variants = CELL_TYPES.get(cell, {}).get('variants')
                if variants:
                    roll = random.random()
                    cumul = 0
                    for vname, vprob in variants.items():
                        cumul += vprob
                        if roll < cumul:
                            variant = vname if vname != cell else None  # None means use base sprite
                            break
                variant_row.append(variant)
            variant_grid.append(variant_row)
        
        if random.random() > 0.7:
            struct_x = random.randint(2, GRID_WIDTH - 3)
            struct_y = random.randint(2, GRID_HEIGHT - 3)
            struct_type = random.choice(['HOUSE', 'CAVE'])
            grid[struct_y][struct_x] = struct_type
        
        screen_data = {
            'grid': grid,
            'variant_grid': variant_grid,
            'exits': exits,
            'biome': biome_name
        }
        
        self.screens[key] = screen_data
        self.instantiated_zones.add(key)  # Track this zone
        
        # Set initial last update time
        self.screen_last_update[key] = self.tick
        
        # Spawn entities in new screen
        if key not in self.screen_entities:
            self.spawn_entities_for_screen(sx, sy, biome_name)
        
        # Natural cave formation — uncommon, favors mountains
        cave_chance = NATURAL_CAVE_ZONE_CHANCE
        if biome_name == 'MOUNTAINS':
            cave_chance *= 3  # Mountains have 3x more caves
        elif biome_name == 'DESERT':
            cave_chance *= 1.5
        if random.random() < cave_chance:
            # Place a natural cave on a non-edge, non-wall cell
            valid = [(x, y) for y in range(2, GRID_HEIGHT - 2)
                     for x in range(2, GRID_WIDTH - 2)
                     if CELL_TYPES.get(grid[y][x], {}).get('solid', False)
                     and grid[y][x] != 'WALL']
            if valid:
                cx, cy = random.choice(valid)
                grid[cy][cx] = 'CAVE'
        
        # Spawn runestones (rare)
        self.spawn_runestones_for_screen(sx, sy)
        
        return screen_data

    def roll_cell_variant(self, cell_type):
        """Roll a variant for a cell type based on its variant probabilities. Returns variant name or None."""
        variants = CELL_TYPES.get(cell_type, {}).get('variants')
        if not variants:
            return None
        roll = random.random()
        cumul = 0
        for vname, vprob in variants.items():
            cumul += vprob
            if roll < cumul:
                return vname if vname != cell_type else None
        return None

    def set_grid_cell(self, screen, x, y, new_cell):
        """Set a grid cell and update its variant. Use this instead of direct grid assignment."""
        screen['grid'][y][x] = new_cell
        if 'variant_grid' in screen:
            screen['variant_grid'][y][x] = self.roll_cell_variant(new_cell)

    def update_screen_exits(self, sx, sy):
        """Update a screen's grid walls to match its current exits"""
        key = f"{sx},{sy}"
        if key not in self.screens:
            return
        
        screen = self.screens[key]
        exits = screen['exits']
        grid = screen['grid']
        biome = screen.get('biome', 'FOREST')
        current_biome_cell = self.get_common_cell_for_biome(biome)
        
        # Update top edge
        for x in range(GRID_WIDTH):
            if exits['top'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
                # Mixed biome entrance
                top_neighbor_key = f"{sx},{sy - 1}"
                if top_neighbor_key in self.screens:
                    adj_biome = self.screens[top_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    # One cell current biome, one cell adjacent biome
                    grid[0][x] = current_biome_cell if x == GRID_WIDTH // 2 - 1 else adj_cell
                else:
                    grid[0][x] = current_biome_cell
            elif not exits['top'] or not (GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                grid[0][x] = 'WALL'  # Close exit
        
        # Update bottom edge
        for x in range(GRID_WIDTH):
            if exits['bottom'] and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2:
                # Mixed biome entrance
                bottom_neighbor_key = f"{sx},{sy + 1}"
                if bottom_neighbor_key in self.screens:
                    adj_biome = self.screens[bottom_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[GRID_HEIGHT-1][x] = current_biome_cell if x == GRID_WIDTH // 2 - 1 else adj_cell
                else:
                    grid[GRID_HEIGHT-1][x] = current_biome_cell
            elif not exits['bottom'] or not (GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2):
                grid[GRID_HEIGHT-1][x] = 'WALL'
        
        # Update left edge
        for y in range(GRID_HEIGHT):
            if exits['left'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
                # Mixed biome entrance
                left_neighbor_key = f"{sx - 1},{sy}"
                if left_neighbor_key in self.screens:
                    adj_biome = self.screens[left_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[y][0] = current_biome_cell if y == GRID_HEIGHT // 2 - 1 else adj_cell
                else:
                    grid[y][0] = current_biome_cell
            elif not exits['left'] or not (GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                grid[y][0] = 'WALL'
        
        # Update right edge
        for y in range(GRID_HEIGHT):
            if exits['right'] and GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2:
                # Mixed biome entrance
                right_neighbor_key = f"{sx + 1},{sy}"
                if right_neighbor_key in self.screens:
                    adj_biome = self.screens[right_neighbor_key].get('biome', biome)
                    adj_cell = self.get_common_cell_for_biome(adj_biome)
                    grid[y][GRID_WIDTH-1] = current_biome_cell if y == GRID_HEIGHT // 2 - 1 else adj_cell
                else:
                    grid[y][GRID_WIDTH-1] = current_biome_cell
            elif not exits['right'] or not (GRID_HEIGHT // 2 - 1 <= y <= GRID_HEIGHT // 2):
                grid[y][GRID_WIDTH-1] = 'WALL'

    def generate_subscreen(self, parent_screen_x, parent_screen_y, cell_x, cell_y, structure_type, depth=1):
        """Generate interior for house/cave (caves share one system per zone at depth 1)"""
        # For CAVE at depth 1, check if zone already has a cave system
        if structure_type == 'CAVE' and depth == 1:
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            if parent_key in self.zone_cave_systems:
                # Use existing cave system
                return self.zone_cave_systems[parent_key]
        
        # Create unique subscreen key
        subscreen_id = self.next_subscreen_id
        self.next_subscreen_id += 1
        subscreen_key = f"{parent_screen_x},{parent_screen_y}:{structure_type}:{subscreen_id}"
        
        # Check if already exists
        if subscreen_key in self.subscreens:
            return subscreen_key
        
        # Initialize grid with default cells
        if structure_type == 'HOUSE_INTERIOR':
            grid = self.generate_house_interior(depth)
        elif structure_type == 'CAVE':
            grid = self.generate_cave_interior(depth)
        else:
            # Default empty interior
            grid = [['FLOOR_WOOD' for _ in range(GRID_WIDTH)] for _ in range(GRID_HEIGHT)]
        
        # Create subscreen data
        subscreen_data = {
            'type': structure_type,
            'parent_screen': (parent_screen_x, parent_screen_y),
            'parent_cell': (cell_x, cell_y),
            'grid': grid,
            'biome': structure_type,
            'depth': depth,
            'entrance': (GRID_WIDTH // 2, GRID_HEIGHT - 2),  # Bottom center
            'exit': (GRID_WIDTH // 2, GRID_HEIGHT - 2),  # Same as entrance for now
            'stairs_down': None,  # Will be set if cave has deeper levels
            'chests': {},  # Will be populated with chest locations
            'entrances': [(cell_x, cell_y)]  # Track all entrances to this cave system
        }
        
        # Store subscreen first
        self.subscreens[subscreen_key] = subscreen_data
        
        # For caves at depth 1, register as zone's cave system
        if structure_type == 'CAVE' and depth == 1:
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            self.zone_cave_systems[parent_key] = subscreen_key
        
        # Place chests and spawn entities
        if structure_type == 'HOUSE_INTERIOR':
            self.place_house_chests(subscreen_data)
            # Spawn single NPC (farmer or trader) - 50% chance
            if random.random() < 0.5:
                self.spawn_house_npc(subscreen_data)
        elif structure_type == 'CAVE':
            self.place_cave_chests(subscreen_data, depth)
        
        # Register structure as a zone in the priority system
        parent_key = f"{parent_screen_x},{parent_screen_y}"
        self.screens[subscreen_key] = subscreen_data  # Store in main screens dict
        self.screen_last_update[subscreen_key] = self.tick
        
        # Track as structure zone
        if subscreen_key not in self.structure_zones:
            self.structure_zones[subscreen_key] = {
                'parent_zone': parent_key,
                'type': structure_type,
                'cell': (cell_x, cell_y)
            }
            if parent_key not in self.zone_structures:
                self.zone_structures[parent_key] = []
            if subscreen_key not in self.zone_structures[parent_key]:
                self.zone_structures[parent_key].append(subscreen_key)
            self.add_zone_connection(parent_key, subscreen_key, 'structure_entrance', cell_x, cell_y)
        
        return subscreen_key

    def generate_house_interior(self, depth):
        """Generate a house interior layout"""
        grid = []
        
        # Create room with walls around edges
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                # Outer walls except for doorway at bottom center
                if y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    # Leave gap for doorway at bottom center
                    if y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2 + 1:
                        row.append('FLOOR_WOOD')
                    else:
                        row.append('WALL')
                # Top wall
                elif y == 0:
                    row.append('WALL')
                else:
                    # Interior floor (wood planks and logs)
                    if random.random() < 0.7:
                        row.append('FLOOR_WOOD')
                    else:
                        row.append('WOOD')
            grid.append(row)
        
        # Make sure doorway area is accessible
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2] = 'FLOOR_WOOD'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 - 1] = 'FLOOR_WOOD'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 + 1] = 'FLOOR_WOOD'
        
        return grid

    def generate_cave_interior(self, depth):
        """Generate a cave interior layout"""
        grid = []
        
        # Create cave with rocky walls
        for y in range(GRID_HEIGHT):
            row = []
            for x in range(GRID_WIDTH):
                # Outer walls with special handling for exit
                if y == GRID_HEIGHT - 1 or x == 0 or x == GRID_WIDTH - 1:
                    # First level (depth 1) has doorway exit like houses
                    if depth == 1 and y == GRID_HEIGHT - 1 and GRID_WIDTH // 2 - 1 <= x <= GRID_WIDTH // 2 + 1:
                        row.append('CAVE_FLOOR')
                    else:
                        row.append('CAVE_WALL')
                # Top wall
                elif y == 0:
                    row.append('CAVE_WALL')
                else:
                    # Interior - mostly cave floor with some rocks
                    if random.random() < 0.15:
                        row.append('STONE')
                    else:
                        row.append('CAVE_FLOOR')
            grid.append(row)
        
        # Make sure exit area is accessible
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2] = 'CAVE_FLOOR'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 - 1] = 'CAVE_FLOOR'
        grid[GRID_HEIGHT - 2][GRID_WIDTH // 2 + 1] = 'CAVE_FLOOR'
        
        # Deeper levels (depth > 1) have STAIRS_UP to go back up
        if depth > 1:
            # Place stairs up in a safe location (not too close to entrance area)
            attempts = 0
            while attempts < 20:
                stairs_x = random.randint(3, GRID_WIDTH - 4)
                stairs_y = random.randint(3, GRID_HEIGHT - 6)
                if grid[stairs_y][stairs_x] == 'CAVE_FLOOR':
                    grid[stairs_y][stairs_x] = 'STAIRS_UP'
                    # Clear area around stairs up
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            ny, nx = stairs_y + dy, stairs_x + dx
                            if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                                if grid[ny][nx] not in ['STAIRS_UP']:
                                    grid[ny][nx] = 'CAVE_FLOOR'
                    break
                attempts += 1
        
        # Add stairs down for deeper exploration (70% chance)
        if random.random() < 0.7:
            attempts = 0
            while attempts < 20:
                stairs_x = random.randint(3, GRID_WIDTH - 4)
                stairs_y = random.randint(3, GRID_HEIGHT - 4)
                # Make sure we place on cave floor
                if grid[stairs_y][stairs_x] == 'CAVE_FLOOR':
                    grid[stairs_y][stairs_x] = 'STAIRS_DOWN'
                    # Clear area around stairs down
                    for dy in [-1, 0, 1]:
                        for dx in [-1, 0, 1]:
                            ny, nx = stairs_y + dy, stairs_x + dx
                            if 0 < ny < GRID_HEIGHT - 1 and 0 < nx < GRID_WIDTH - 1:
                                if grid[ny][nx] not in ['STAIRS_DOWN', 'STAIRS_UP']:
                                    grid[ny][nx] = 'CAVE_FLOOR'
                    break
                attempts += 1
        
        return grid

    def place_house_chests(self, subscreen_data):
        """Place chests in house interior"""
        grid = subscreen_data['grid']
        
        # Place 1-2 chests in random valid locations
        num_chests = random.randint(1, 2)
        placed = 0
        attempts = 0
        
        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)
            
            # Check if spot is valid (floor and not near entrance)
            if grid[y][x] in ['FLOOR_WOOD', 'WOOD'] and y < GRID_HEIGHT - 4:
                grid[y][x] = 'CHEST'
                chest_key = f"{subscreen_data['parent_screen'][0]},{subscreen_data['parent_screen'][1]}:{subscreen_data['type']}:{x},{y}"
                subscreen_data['chests'][(x, y)] = 'HOUSE_CHEST'
                placed += 1
            
            attempts += 1

    def place_cave_chests(self, subscreen_data, depth):
        """Place chests in cave interior"""
        grid = subscreen_data['grid']
        
        # Deeper caves have more chests
        num_chests = random.randint(1, 1 + depth)
        placed = 0
        attempts = 0
        
        # Use deeper loot table for deeper caves
        loot_type = 'CAVE_DEEP_CHEST' if depth >= 3 else 'CAVE_CHEST'
        
        while placed < num_chests and attempts < 50:
            x = random.randint(2, GRID_WIDTH - 3)
            y = random.randint(2, GRID_HEIGHT - 3)
            
            # Check if spot is valid
            if grid[y][x] == 'CAVE_FLOOR':
                grid[y][x] = 'CHEST'
                chest_key = f"{subscreen_data['parent_screen'][0]},{subscreen_data['parent_screen'][1]}:{subscreen_data['type']}:{x},{y}"
                subscreen_data['chests'][(x, y)] = loot_type
                placed += 1
            
            attempts += 1

    def spawn_house_npc(self, subscreen_data):
        """Spawn a single NPC (farmer or trader) in a house"""
        grid = subscreen_data['grid']
        
        # Choose NPC type (only peaceful NPCs)
        npc_type = random.choice(['FARMER', 'TRADER'])
        
        # Find a valid spawn location (interior floor, away from entrance)
        attempts = 0
        while attempts < 50:
            x = random.randint(3, GRID_WIDTH - 4)
            y = random.randint(3, GRID_HEIGHT - 6)  # Stay away from door area
            
            # Check if valid location
            if grid[y][x] in ['FLOOR_WOOD', 'WOOD']:
                # Create entity (using 0,0 as placeholder coords for subscreens)
                entity = Entity(npc_type, x, y, 0, 0, 1)
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                self.entities[entity_id] = entity
                
                # Mark that this entity belongs to this subscreen
                if 'entities' not in subscreen_data:
                    subscreen_data['entities'] = []
                subscreen_data['entities'].append(entity_id)
                
                print(f"Spawned {npc_type} in house")
                return entity_id
            
            attempts += 1
        
        return None

    def spawn_entities_for_screen(self, screen_x, screen_y, biome_name):
        """Spawn initial entities for a newly generated screen - only at zone edges
        WARNING: This clears existing entities - use spawn_single_entity_at_entrance for runtime spawning"""
        screen_key = f"{screen_x},{screen_y}"
        self.screen_entities[screen_key] = []  # Clear for initial generation
        
        # Biome-based spawning probabilities
        spawn_tables = {
            'FOREST': [
                ('DEER', 0.5, 1, 2),
                ('WOLF', 0.3, 0, 2),
                ('SHEEP', 0.2, 0, 1),
                ('FARMER', 0.5, 0, 2),
                ('LUMBERJACK', 0.6, 1, 2),
                ('WIZARD', 0.25, 1, 2), 
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.5, 0, 1),  # 50% chance, 0-1
                ('GUARD', 1.0, 1, 2),     # Always spawn
                ('BANDIT', 0.2, 0, 1),
                ('GOBLIN', 0.3, 0, 2),
                ('TERMITE', 0.4, 0, 2)    # Termites love forests (trees)
            ],
            'PLAINS': [
                ('SHEEP', 0.6, 1, 3),
                ('DEER', 0.4, 0, 2),
                ('WOLF', 0.2, 0, 1),
                ('FARMER', 0.7, 1, 3),
                ('LUMBERJACK', 0.3, 0, 1),
                ('WIZARD', 0.25, 1, 2), 
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.5, 0, 1),  # 50% chance, 0-1
                ('GUARD', 1.0, 1, 2),     # Always spawn
                ('BANDIT', 0.2, 0, 1),
                ('GOBLIN', 0.2, 0, 1),
                ('TERMITE', 0.2, 0, 1)    # Some termites in plains
            ],
            'DESERT': [
                ('SHEEP', 0.2, 0, 1),
                ('DEER', 0.2, 0, 1),
                ('WOLF', 0.2, 0, 1),
                ('GOBLIN', 0.7, 1, 3),
                ('BANDIT', 0.5, 0, 2),
                ('WIZARD', 0.25, 1, 2), 
                ('FARMER', 0.3, 0, 1),
                ('LUMBERJACK', 0.2, 0, 1),
                ('MINER', 0.5, 0, 2),     # Added - rocky desert
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.4, 0, 1),  # 40% chance in desert
                ('GUARD', 1.0, 1, 2)      # Always spawn
            ],
            'MOUNTAINS': [
                ('WOLF', 0.6, 1, 3),
                ('DEER', 0.3, 0, 2),
                ('SHEEP', 0.2, 0, 1),
                ('GOBLIN', 0.6, 1, 3),
                ('BANDIT', 0.3, 0, 2),
                ('WIZARD', 0.25, 1, 2),
                ('FARMER', 0.2, 0, 1),
                ('LUMBERJACK', 0.4, 0, 2),
                ('MINER', 0.7, 1, 3),     # Added - primary rocky biome
                ('TRADER', 1.0, 1, 2),    # Always spawn
                ('BLACKSMITH', 0.6, 0, 1),  # 60% chance in mountains (lots of stone)
                ('GUARD', 1.0, 1, 2)      # Always spawn
            ]
        }
        
        spawn_list = spawn_tables.get(biome_name, [])
        
        # Get actual entrance positions - only spawn AT entrances
        entrance_positions = []
        screen = self.screens[screen_key]
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        
        # Top entrance (if exists)
        if screen['exits']['top']:
            for x in range(center_x - 1, center_x + 2):  # 3-cell wide entrance
                entrance_positions.append((x, 1, 'top'))
        
        # Bottom entrance (if exists)
        if screen['exits']['bottom']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, GRID_HEIGHT - 2, 'bottom'))
        
        # Left entrance (if exists)
        if screen['exits']['left']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((1, y, 'left'))
        
        # Right entrance (if exists)
        if screen['exits']['right']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((GRID_WIDTH - 2, y, 'right'))
        
        # If no entrance positions (shouldn't happen), use fallback
        if not entrance_positions:
            entrance_positions = [(center_x, center_y, 'center')]
        
        # Spawn ONE entity per zone update based on spawn chances
        # Higher spawn chances = more frequent arrivals over time
        eligible_types = []
        for entity_type, spawn_chance, min_count, max_count in spawn_list:
            # Increased spawn chances by 50% for more frequent spawns
            adjusted_chance = min(1.0, spawn_chance * 1.5)
            if random.random() < adjusted_chance:
                eligible_types.append(entity_type)
        
        # If any types eligible, pick one and spawn it
        if eligible_types:
            entity_type = random.choice(eligible_types)
            
            # Find valid spawn location AT entrance
            attempts = 0
            while attempts < 30:
                # Pick random entrance position
                x, y, entrance = random.choice(entrance_positions)
                
                cell = self.screens[screen_key]['grid'][y][x]
                if not CELL_TYPES[cell]['solid']:
                    # Check if position already occupied by another entity
                    position_occupied = False
                    for existing_id in self.screen_entities.get(screen_key, []):
                        if existing_id in self.entities:
                            existing = self.entities[existing_id]
                            if existing.x == x and existing.y == y:
                                position_occupied = True
                                break
                    
                    if not position_occupied:
                        # Spawn entity
                        entity_id = self.next_entity_id
                        self.next_entity_id += 1
                        
                        entity = Entity(entity_type, x, y, screen_x, screen_y)
                        self.entities[entity_id] = entity
                        self.screen_entities[screen_key].append(entity_id)
                        
                        # 10% chance to log arrival
                        if random.random() < 0.1:
                            print(f"{entity_type} has arrived at [{screen_key}]")
                        break
                attempts += 1
    
    def spawn_skeleton(self, near_x, near_y):
        """Spawn a hostile skeleton entity near the specified position"""
        # Find empty spot near position
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                test_x = near_x + dx
                test_y = near_y + dy
                if 0 <= test_x < GRID_WIDTH and 0 <= test_y < GRID_HEIGHT:
                    screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                    if screen_key in self.screens:
                        cell = self.screens[screen_key]['grid'][test_y][test_x]
                        if not CELL_TYPES[cell].get('solid', False):
                            # Spawn skeleton here
                            skeleton = Entity('SKELETON', test_x, test_y,
                                            self.player['screen_x'],
                                            self.player['screen_y'], 1)
                            
                            entity_id = self.next_entity_id
                            self.next_entity_id += 1
                            self.entities[entity_id] = skeleton
                            
                            if screen_key not in self.screen_entities:
                                self.screen_entities[screen_key] = []
                            self.screen_entities[screen_key].append(entity_id)
                            
                            print(f"A skeleton rises from the bones!")
                            return entity_id
        
        print("No space to spawn skeleton!")
        return None
    
    def spawn_quest_entity(self, entity_type, screen_x, screen_y, x, y):
        """Spawn an entity at a specific location for quests
        
        Returns:
            entity_id if successful, None if failed
        """
        screen_key = f"{screen_x},{screen_y}"
        
        # Make sure screen exists
        if screen_key not in self.screens:
            return None
        
        # Check if position is valid
        if not (0 <= x < GRID_WIDTH and 0 <= y < GRID_HEIGHT):
            return None
        
        cell = self.screens[screen_key]['grid'][y][x]
        if CELL_TYPES[cell].get('solid', False):
            # Try to find nearby empty spot
            for dx in range(-2, 3):
                for dy in range(-2, 3):
                    test_x = x + dx
                    test_y = y + dy
                    if 0 <= test_x < GRID_WIDTH and 0 <= test_y < GRID_HEIGHT:
                        test_cell = self.screens[screen_key]['grid'][test_y][test_x]
                        if not CELL_TYPES[test_cell].get('solid', False):
                            x, y = test_x, test_y
                            break
                else:
                    continue
                break
            else:
                # Couldn't find empty spot
                return None
        
        # Create the entity
        entity = Entity(entity_type, x, y, screen_x, screen_y, level=1)
        entity_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[entity_id] = entity
        
        # Add to screen entities
        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(entity_id)
        
        return entity_id
    
    def spawn_runestones_for_screen(self, screen_x, screen_y):
        """Spawn runestones rarely on base biome cells"""
        screen_key = f"{screen_x},{screen_y}"
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        grid = screen['grid']
        
        # Runestone types
        runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
        
        # Very low chance to spawn runestones (2% per zone)
        if random.random() < 0.25:
            # Spawn 1-2 runestones
            num_runes = random.randint(1, 2)
            
            for _ in range(num_runes):
                # Try to find a valid base biome cell
                for attempt in range(20):
                    x = random.randint(3, GRID_WIDTH - 4)
                    y = random.randint(3, GRID_HEIGHT - 4)
                    cell = grid[y][x]
                    
                    # Only spawn on base biome cells
                    if cell in ['GRASS', 'DIRT', 'SAND', 'STONE']:
                        # Random runestone type
                        rune_type = random.choice(runestone_types)
                        
                        # Add to dropped items
                        if screen_key not in self.dropped_items:
                            self.dropped_items[screen_key] = {}
                        
                        drop_key = (x, y)
                        if drop_key not in self.dropped_items[screen_key]:
                            self.dropped_items[screen_key][drop_key] = {}
                        
                        # Spawn 1-3 runes
                        amount = random.randint(1, 3)
                        self.dropped_items[screen_key][drop_key][rune_type] = \
                            self.dropped_items[screen_key][drop_key].get(rune_type, 0) + amount
                        
                        break

    def check_raid_event(self, screen_key):
        """Check if a raid event should occur in this zone"""
        # Skip if not enough time since last check
        if screen_key in self.zone_last_raid_check:
            if self.tick - self.zone_last_raid_check[screen_key] < RAID_CHECK_INTERVAL:
                return
        
        self.zone_last_raid_check[screen_key] = self.tick
        
        # Check population threshold
        if screen_key not in self.screen_entities:
            return
        
        # Count human NPCs for scaled raid chance
        human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR', 'WIZARD']
        human_count = 0
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                base_type = entity.type.replace('_double', '')
                if base_type in human_npc_types:
                    human_count += 1
        
        if human_count < RAID_POPULATION_THRESHOLD:
            return
        
        # Check if zone already has hostiles (don't stack raids)
        if self.zone_has_hostiles.get(screen_key, False):
            return
        
        # Calculate scaled raid chance: base + 5% per NPC over threshold
        npcs_over_threshold = human_count - RAID_POPULATION_THRESHOLD
        raid_chance = RAID_CHANCE_BASE + (npcs_over_threshold * 0.05)
        raid_chance = min(raid_chance, 0.80)  # Cap at 80%
        
        # Roll for raid
        if random.random() < raid_chance:
            # Trigger raid!
            self.trigger_raid(screen_key)
    
    def trigger_raid(self, screen_key):
        """Spawn a raid event in the zone"""
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        screen_x, screen_y = map(int, screen_key.split(','))
        
        # Choose raid type
        raid_types = [
            ('GOBLIN', 2),
            ('BANDIT', 2),
            ('WOLF', 3)
        ]
        raid_type, raid_count = random.choice(raid_types)
        
        # 20% chance to spawn hidden cave
        cave_pos = None
        if random.random() < HIDDEN_CAVE_SPAWN_CHANCE:
            cave_pos = self.spawn_hidden_cave(screen_key)
        
        # Spawn raiders
        self.spawn_raid_group(screen_key, raid_type, raid_count, cave_pos)
        
        # Mark zone as hostile
        self.zone_has_hostiles[screen_key] = True
        
        print(f"RAID! {raid_count} {raid_type}s attack zone [{screen_key}]!")
    
    def spawn_hidden_cave(self, screen_key):
        """Spawn a hidden cave in the zone, returns (x, y) or None"""
        if screen_key not in self.screens:
            return None
        
        screen = self.screens[screen_key]
        grid = screen['grid']
        
        # Find valid spawn locations (non-solid, non-wall cells)
        valid_positions = []
        for y in range(2, GRID_HEIGHT - 2):
            for x in range(2, GRID_WIDTH - 2):
                cell = grid[y][x]
                if not CELL_TYPES[cell].get('solid', False) and cell != 'WALL':
                    valid_positions.append((x, y))
        
        if not valid_positions:
            return None
        
        # Pick random position
        cave_x, cave_y = random.choice(valid_positions)
        grid[cave_y][cave_x] = 'HIDDEN_CAVE'
        
        print(f"A hidden cave appears at ({cave_x}, {cave_y}) in [{screen_key}]!")
        return (cave_x, cave_y)
    
    def spawn_raid_group(self, screen_key, entity_type, count, cave_pos):
        """Spawn a group of raiders around cave or random location"""
        if screen_key not in self.screens:
            return
        
        screen_x, screen_y = map(int, screen_key.split(','))
        
        # Determine spawn center
        if cave_pos:
            center_x, center_y = cave_pos
        else:
            # Random central location
            center_x = random.randint(4, GRID_WIDTH - 5)
            center_y = random.randint(4, GRID_HEIGHT - 5)
        
        # Spawn entities in 3x3 area around center
        spawned = 0
        attempts = 0
        max_attempts = count * 10
        
        while spawned < count and attempts < max_attempts:
            attempts += 1
            
            # Pick position in 3x3 area
            dx = random.randint(-1, 1)
            dy = random.randint(-1, 1)
            spawn_x = center_x + dx
            spawn_y = center_y + dy
            
            # Check bounds
            if spawn_x < 1 or spawn_x >= GRID_WIDTH - 1:
                continue
            if spawn_y < 1 or spawn_y >= GRID_HEIGHT - 1:
                continue
            
            # Check if cell is walkable
            cell = self.screens[screen_key]['grid'][spawn_y][spawn_x]
            if CELL_TYPES[cell].get('solid', False):
                continue
            
            # Check if position is occupied
            if self.is_entity_at_position(spawn_x, spawn_y, screen_key):
                continue
            
            # Spawn entity
            entity = Entity(entity_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = entity
            
            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)
            
            spawned += 1
        
        print(f"Spawned {spawned} {entity_type}s at ({center_x}, {center_y})")
    
    def check_zone_clear_hostiles(self, screen_key):
        """Check if all hostiles are dead in zone and update flag"""
        if not self.zone_has_hostiles.get(screen_key, False):
            return  # Zone wasn't marked as hostile
        
        # Check if any hostiles remain
        if screen_key not in self.screen_entities:
            return
        
        has_hostiles = False
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.props.get('hostile', False):
                    has_hostiles = True
                    break
        
        if not has_hostiles:
            # All hostiles cleared!
            self.zone_has_hostiles[screen_key] = False
            print(f"Zone [{screen_key}] cleared of hostiles!")
    
    def check_zone_threats(self, screen_key):
        """Efficiently check zone for hostiles and faction conflicts - called once per zone update"""
        if screen_key not in self.screen_entities:
            self.zone_has_hostiles[screen_key] = False
            self.zone_has_faction_conflict[screen_key] = False
            return
        
        has_hostiles = False
        factions_present = set()
        
        # Single pass through entities
        for entity_id in self.screen_entities[screen_key]:
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            
            # Check for hostiles
            if entity.props.get('hostile', False):
                has_hostiles = True
            
            # Track factions for conflict detection
            if hasattr(entity, 'faction') and entity.faction:
                if entity.type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD']:
                    factions_present.add(entity.faction)
        
        # Update zone threat flags
        self.zone_has_hostiles[screen_key] = has_hostiles
        self.zone_has_faction_conflict[screen_key] = len(factions_present) > 1
    
    def generate_faction_name(self):
        """Generate a random unique faction name"""
        max_attempts = 50
        for _ in range(max_attempts):
            color = random.choice(FACTION_COLORS)
            symbol = random.choice(FACTION_SYMBOLS)
            name = f"{color} {symbol}"
            # Ensure this faction name doesn't already exist
            if name not in self.factions:
                return name
        # Fallback: just return a random name even if it exists (shouldn't happen with 100 combinations)
        return f"{random.choice(FACTION_COLORS)} {random.choice(FACTION_SYMBOLS)}"
    
    def generate_hostile_faction_name(self):
        """Generate a random unique hostile faction name"""
        max_attempts = 50
        for _ in range(max_attempts):
            color = random.choice(HOSTILE_FACTION_COLORS)
            symbol = random.choice(HOSTILE_FACTION_SYMBOLS)
            name = f"{color} {symbol}"
            # Ensure this faction name doesn't already exist
            if name not in self.factions:
                return name
        # Fallback
        return f"{random.choice(HOSTILE_FACTION_COLORS)} {random.choice(HOSTILE_FACTION_SYMBOLS)}"
    
    def generate_legendary_item_name(self, item_name, entity):
        """Generate a legendary name for a high-level item"""
        prefixes = ['Legendary', 'Epic', 'Mythic', 'Ancient', 'Eternal', 'Divine', 'Cursed', 'Blessed']
        suffixes = ['of Power', 'of the Ancients', 'of Destiny', 'of Glory', 'of Ruin', 'of the Stars', 
                   'of Thunder', 'of Fire', 'of Ice', 'of Shadow', 'of Light']
        
        # Add magic type suffix if entity has runes
        magic_types = []
        for rune_type in ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']:
            if rune_type in entity.inventory and entity.inventory[rune_type] > 0:
                magic_name = rune_type.replace('_rune', '').capitalize()
                magic_types.append(f"of {magic_name}")
        
        # Use magic type if available, otherwise random suffix
        suffix = random.choice(magic_types) if magic_types else random.choice(suffixes)
        
        # Get base item name from ITEMS dict
        base_name = ITEMS.get(item_name, {}).get('name', item_name.capitalize())
        
        return f"{random.choice(prefixes)} {base_name} {suffix}"
    
    def create_hostile_faction(self, entity, screen_key):
        """Create new hostile faction and assign to entity"""
        new_faction = self.generate_hostile_faction_name()
        entity.faction = new_faction
        
        # Find entity_id
        entity_id = None
        for eid, ent in self.entities.items():
            if ent is entity:
                entity_id = eid
                break
        
        if entity_id:
            self.factions[new_faction] = {'warriors': [entity_id], 'zones': set(), 'hostile': True}
            print(f"{entity.name} formed the {new_faction} hostile faction!")
    
    def assign_warrior_faction(self, warrior, screen_key):
        """Assign faction to a new warrior based on zone warriors"""
        if screen_key not in self.screen_entities:
            return
        
        # Find entity_id for this warrior
        warrior_id = None
        for entity_id, entity in self.entities.items():
            if entity is warrior:
                warrior_id = entity_id
                break
        
        if not warrior_id:
            return
        
        # Find other warriors in zone with factions
        zone_factions = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.type == 'WARRIOR' and entity.faction:
                    if entity.faction not in zone_factions:
                        zone_factions[entity.faction] = 0
                    zone_factions[entity.faction] += 1
        
        # If there are warriors with factions, try to join the majority faction
        if zone_factions:
            # Join the most common faction
            majority_faction = max(zone_factions, key=zone_factions.get)
            
            # Check if faction has room
            max_size = self.get_faction_max_size(majority_faction)
            current_size = len(self.factions.get(majority_faction, {}).get('warriors', []))
            
            if current_size < max_size:
                # Has room - join
                warrior.faction = majority_faction
                
                # Add to faction tracking
                if majority_faction not in self.factions:
                    self.factions[majority_faction] = {'warriors': [], 'zones': set()}
                
                if warrior_id not in self.factions[majority_faction]['warriors']:
                    self.factions[majority_faction]['warriors'].append(warrior_id)
                
                print(f"{warrior.name} joined {majority_faction} faction!")
                return
            else:
                # Check if this warrior is higher level than lowest member
                members = self.factions[majority_faction].get('warriors', [])
                lowest_level = float('inf')
                for member_id in members:
                    if member_id in self.entities:
                        member = self.entities[member_id]
                        if member.type not in ['KING', 'COMMANDER']:
                            lowest_level = min(lowest_level, member.level)
                
                if warrior.level > lowest_level:
                    # This warrior is higher level - join and expel lowest
                    warrior.faction = majority_faction
                    if majority_faction not in self.factions:
                        self.factions[majority_faction] = {'warriors': [], 'zones': set()}
                    
                    self.factions[majority_faction]['warriors'].append(warrior_id)
                    self.enforce_faction_max_size(majority_faction)
                    print(f"{warrior.name} joined {majority_faction} faction!")
                    return
                else:
                    # Lower level than lowest - try to start own faction
                    if random.random() < 0.1:  # 10% chance
                        new_faction = self.generate_faction_name()
                        warrior.faction = new_faction
                        self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
                        print(f"{warrior.name} founded the {new_faction} faction!")
                    else:
                        # Become factionless
                        warrior.faction = None
                    return
        
        # If no factions in zone, check if any factions exist globally
        elif self.factions:
            # Try to join the largest existing faction globally
            largest_faction = max(self.factions.keys(), key=lambda f: len(self.factions[f]['warriors']))
            
            max_size = self.get_faction_max_size(largest_faction)
            current_size = len(self.factions[largest_faction].get('warriors', []))
            
            if current_size < max_size or warrior.level > 1:  # Higher level has better chance
                warrior.faction = largest_faction
                if warrior_id not in self.factions[largest_faction]['warriors']:
                    self.factions[largest_faction]['warriors'].append(warrior_id)
                    self.enforce_faction_max_size(largest_faction)
                
                print(f"{warrior.name} joined {largest_faction} faction (global recruitment)!")
            else:
                # Create new faction
                new_faction = self.generate_faction_name()
                warrior.faction = new_faction
                self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
                print(f"{warrior.name} founded the {new_faction} faction!")
        
        # If no factions exist at all, create first faction
        else:
            # Create new faction
            new_faction = self.generate_faction_name()
            warrior.faction = new_faction
            
            # Initialize faction
            self.factions[new_faction] = {'warriors': [warrior_id], 'zones': set()}
            
            print(f"{warrior.name} founded the {new_faction} faction!")
    
    def get_zone_controlling_faction(self, screen_key):
        """Get the faction that controls a zone (majority of warriors/hostiles)"""
        if screen_key not in self.screen_entities:
            return None
        
        faction_counts = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                # Count warriors, commanders, kings AND hostile faction members
                if entity.faction:
                    if entity.type in ['WARRIOR', 'COMMANDER', 'KING']:
                        if entity.faction not in faction_counts:
                            faction_counts[entity.faction] = 0
                        faction_counts[entity.faction] += 1
                    # Hostile entities with factions also count for control
                    elif entity.props.get('hostile') and entity.faction:
                        if entity.faction not in faction_counts:
                            faction_counts[entity.faction] = 0
                        faction_counts[entity.faction] += 1
        
        if not faction_counts:
            return None
        
        # Return faction with most members (simple majority)
        majority_faction = max(faction_counts, key=faction_counts.get)
        return majority_faction
    
    def get_faction_leader(self, faction_name):
        """Get the leader (KING or highest COMMANDER) of a faction"""
        if faction_name not in self.factions:
            return None, None
        
        leader = None
        leader_id = None
        best_priority = 0  # KING=3, COMMANDER=2, WARRIOR=1
        best_level = 0
        
        for entity_id in self.factions[faction_name].get('warriors', []):
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            priority = 0
            
            if entity.type == 'KING':
                priority = 3
            elif entity.type == 'COMMANDER':
                priority = 2
            elif entity.type == 'WARRIOR':
                priority = 1
            
            # Higher priority or same priority but higher level
            if priority > best_priority or (priority == best_priority and entity.level > best_level):
                leader = entity
                leader_id = entity_id
                best_priority = priority
                best_level = entity.level
        
        return leader, leader_id
    
    def get_faction_max_size(self, faction_name):
        """Calculate max faction size: 3 + leader_level"""
        leader, _ = self.get_faction_leader(faction_name)
        if not leader:
            return 3  # Default if no leader
        return 3 + leader.level
    
    def enforce_faction_max_size(self, faction_name):
        """Remove lowest level member if faction exceeds max size"""
        if faction_name not in self.factions:
            return
        
        max_size = self.get_faction_max_size(faction_name)
        current_members = self.factions[faction_name].get('warriors', [])
        
        # Remove invalid entity IDs
        current_members = [eid for eid in current_members if eid in self.entities]
        self.factions[faction_name]['warriors'] = current_members
        
        if len(current_members) <= max_size:
            return  # Within limits
        
        # Find lowest level member
        lowest_member = None
        lowest_member_id = None
        lowest_level = float('inf')
        
        for entity_id in current_members:
            entity = self.entities[entity_id]
            # Don't expel leaders
            if entity.type in ['KING', 'COMMANDER']:
                continue
            
            if entity.level < lowest_level:
                lowest_member = entity
                lowest_member_id = entity_id
                lowest_level = entity.level
        
        if lowest_member:
            # Expel from faction
            self.factions[faction_name]['warriors'].remove(lowest_member_id)
            old_faction = lowest_member.faction
            
            # Try to join nearest faction
            screen_key = f"{lowest_member.screen_x},{lowest_member.screen_y}"
            self.try_join_nearest_faction(lowest_member, lowest_member_id, screen_key, exclude_faction=old_faction)
            
            if lowest_member.faction != old_faction:
                print(f"{lowest_member.name} was expelled from {old_faction} and joined {lowest_member.faction}!")
            else:
                # Failed to join another faction
                lowest_member.faction = None
                print(f"{lowest_member.name} was expelled from {old_faction} and became factionless!")
    
    def try_join_nearest_faction(self, entity, entity_id, screen_key, exclude_faction=None):
        """Try to join nearest faction, create new faction on failure"""
        # Find nearby factions (within 2 zones)
        nearby_factions = {}
        
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                check_key = f"{entity.screen_x + dx},{entity.screen_y + dy}"
                if check_key not in self.screen_entities:
                    continue
                
                for other_id in self.screen_entities[check_key]:
                    if other_id not in self.entities or other_id == entity_id:
                        continue
                    
                    other = self.entities[other_id]
                    if other.type in ['WARRIOR', 'COMMANDER', 'KING'] and other.faction:
                        if exclude_faction and other.faction == exclude_faction:
                            continue
                        
                        if other.faction not in nearby_factions:
                            nearby_factions[other.faction] = 0
                        nearby_factions[other.faction] += 1
        
        # Try to join nearest faction
        if nearby_factions:
            best_faction = max(nearby_factions, key=nearby_factions.get)
            
            # Safety check - faction must still exist
            if best_faction not in self.factions:
                return False
            
            # Check if faction has room
            max_size = self.get_faction_max_size(best_faction)
            current_size = len(self.factions[best_faction].get('warriors', []))
            
            if current_size < max_size:
                # Join faction
                entity.faction = best_faction
                self.factions[best_faction]['warriors'].append(entity_id)
                return True
            else:
                # Check if this entity is higher level than lowest member
                members = self.factions[best_faction].get('warriors', [])
                lowest_level = float('inf')
                for member_id in members:
                    if member_id in self.entities:
                        member = self.entities[member_id]
                        if member.type not in ['KING', 'COMMANDER']:
                            lowest_level = min(lowest_level, member.level)
                
                if entity.level > lowest_level:
                    # This entity is higher level, join and expel lowest
                    entity.faction = best_faction
                    self.factions[best_faction]['warriors'].append(entity_id)
                    self.enforce_faction_max_size(best_faction)
                    return True
        
        # Failed to join nearby faction - small chance to create new faction
        if random.random() < 0.1:  # 10% chance
            new_faction = self.generate_faction_name()
            entity.faction = new_faction
            self.factions[new_faction] = {'warriors': [entity_id], 'zones': set()}
            print(f"{entity.name} founded the {new_faction} faction!")
            return True
        
        return False
    
    def calculate_magic_damage(self, inventory):
        """Calculate total magic damage and type from runestone inventory"""
        runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
        magic_damage = 0
        magic_type = None
        
        for rune_type in runestone_types:
            if rune_type in inventory:
                rune_count = inventory[rune_type]
                magic_damage += rune_count * ITEMS[rune_type].get('damage', 3)
                if not magic_type:  # Use first rune type for animation
                    magic_type = ITEMS[rune_type].get('magic_damage')
        
        return magic_damage, magic_type
    
    def calculate_weapon_bonus(self, inventory):
        """Calculate bonus damage from weapons/tools in entity inventory.
        Returns the damage of the best weapon found."""
        best_damage = 0
        for item_name, count in inventory.items():
            if count > 0 and item_name in ITEMS:
                item_data = ITEMS[item_name]
                dmg = item_data.get('damage', 0)
                if dmg > best_damage and (item_data.get('is_tool') or item_data.get('is_spell')):
                    best_damage = dmg
        return best_damage
    
    def get_faction_exploration_target(self, screen_key, faction):
        """Get target zone for faction to explore/expand into"""
        # Parse current position
        current_x, current_y = map(int, screen_key.split(','))
        
        # Check adjacent zones (4 directions)
        adjacent_zones = [
            (current_x, current_y - 1, 'top'),
            (current_x, current_y + 1, 'bottom'),
            (current_x - 1, current_y, 'left'),
            (current_x + 1, current_y, 'right')
        ]
        
        # Find zones not controlled by this faction
        expansion_targets = []
        for zone_x, zone_y, direction in adjacent_zones:
            target_key = f"{zone_x},{zone_y}"
            controlling_faction = self.get_zone_controlling_faction(target_key)
            
            # Target zones that aren't controlled by us
            if controlling_faction != faction:
                expansion_targets.append((zone_x, zone_y, direction))
        
        # If we have expansion targets, pick one consistently (use hash of faction name for determinism)
        if expansion_targets:
            # Use faction name hash to pick same target for all warriors of this faction
            faction_hash = sum(ord(c) for c in faction)
            target_index = faction_hash % len(expansion_targets)
            return expansion_targets[target_index]
        
        return None
    
    def promote_to_commander(self, screen_key):
        """Promote highest level warrior in zone to commander (requires 2+ warriors)"""
        if screen_key not in self.screen_entities:
            return
        
        # Count warriors by faction in this zone
        faction_warriors = {}
        for entity_id in self.screen_entities[screen_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.type == 'WARRIOR' and entity.faction:
                    if entity.faction not in faction_warriors:
                        faction_warriors[entity.faction] = []
                    faction_warriors[entity.faction].append((entity_id, entity))
        
        # For each faction with 2+ warriors, promote highest level
        for faction, warriors in faction_warriors.items():
            if len(warriors) >= 2:
                # Find highest level warrior
                best_warrior = None
                best_warrior_id = None
                best_level = 0
                
                for warrior_id, warrior in warriors:
                    if warrior.level > best_level:
                        best_warrior = warrior
                        best_warrior_id = warrior_id
                        best_level = warrior.level
                
                if best_warrior and random.random() < 0.5:  # 50% chance to promote
                    old_name = best_warrior.name
                    
                    # Promote to commander
                    best_warrior.type = 'COMMANDER'
                    best_warrior.props = ENTITY_TYPES['COMMANDER']
                    best_warrior.max_health = best_warrior.props['max_health'] * best_warrior.level
                    best_warrior.strength = best_warrior.props['strength'] * best_warrior.level
                    
                    # Full restore
                    best_warrior.health = best_warrior.max_health
                    best_warrior.hunger = best_warrior.max_hunger
                    best_warrior.thirst = best_warrior.max_thirst
                    
                    # Commanders stay in their zone (like guards)
                    best_warrior.home_zone = screen_key
                    
                    print(f"{old_name} promoted to COMMANDER of {faction} in [{screen_key}]!")
    
    def promote_to_king(self):
        """Promote highest level commander to king if faction controls 4+ zones"""
        for faction, faction_data in self.factions.items():
            # Count zones controlled by this faction
            controlled_zones = 0
            for zone_key in self.instantiated_zones:
                if self.get_zone_controlling_faction(zone_key) == faction:
                    controlled_zones += 1
            
            # If faction controls 4+ zones, can have a king
            if controlled_zones >= 4:
                # Find highest level commander in this faction
                best_commander = None
                best_commander_id = None
                best_level = 0
                
                for entity_id in faction_data.get('warriors', []):
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        if entity.type == 'COMMANDER' and entity.level > best_level:
                            best_commander = entity
                            best_commander_id = entity_id
                            best_level = entity.level
                
                # Check if faction already has a king
                has_king = any(
                    self.entities[eid].type == 'KING'
                    for eid in faction_data.get('warriors', [])
                    if eid in self.entities
                )
                
                if best_commander and not has_king:
                    old_name = best_commander.name
                    
                    # Promote to king
                    best_commander.type = 'KING'
                    best_commander.props = ENTITY_TYPES['KING']
                    best_commander.max_health = best_commander.props['max_health'] * best_commander.level
                    best_commander.strength = best_commander.props['strength'] * best_commander.level
                    
                    # Full restore
                    best_commander.health = best_commander.max_health
                    best_commander.hunger = best_commander.max_hunger
                    best_commander.thirst = best_commander.max_thirst
                    
                    print(f"{old_name} crowned KING of {faction}! ({controlled_zones} zones controlled)")
    
    def recruit_to_hostile_faction(self, zone_key):
        """Non-humanoid hostiles can join factions (small chance)"""
        if zone_key not in self.screen_entities:
            return
        
        # Find hostile factions in zone
        hostile_factions = {}
        for entity_id in self.screen_entities[zone_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.props.get('hostile') and entity.faction:
                    if entity.faction not in hostile_factions:
                        hostile_factions[entity.faction] = []
                    hostile_factions[entity.faction].append(entity_id)
        
        if not hostile_factions:
            return
        
        # For each factionless hostile (WOLF, etc - not humanoids)
        for entity_id in self.screen_entities[zone_key]:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if (entity.props.get('hostile') and not entity.faction and 
                    entity.type not in ['BANDIT', 'GOBLIN', 'SKELETON']):
                    if random.random() < 0.05:  # 5% chance
                        # Join largest hostile faction in zone
                        faction = max(hostile_factions, key=lambda f: len(hostile_factions[f]))
                        entity.faction = faction
                        self.factions[faction]['warriors'].append(entity_id)
                        print(f"{entity.type} joined {faction}!")
    
    def check_cave_spawn_hostile(self, screen_key):
        """Check each cave in zone for chance to spawn hostile — bats favored in empty caves"""
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        grid = screen['grid']
        
        # Find all caves in zone
        caves = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                if grid[y][x] in ['CAVE', 'HIDDEN_CAVE', 'MINESHAFT']:
                    caves.append((x, y))
        
        if not caves:
            return
        
        # Count current population in zone
        zone_population = 0
        bat_count = 0
        if screen_key in self.screen_entities:
            for eid in self.screen_entities[screen_key]:
                if eid in self.entities and self.entities[eid].health > 0:
                    zone_population += 1
                    if self.entities[eid].type == 'BAT':
                        bat_count += 1
        
        # Check each cave for spawn
        for cave_x, cave_y in caves:
            # Base spawn chance from constants
            base_chance = CAVE_HOSTILE_SPAWN_CHANCE
            
            # Boost spawn chance significantly when structure population is low
            if zone_population < 3:
                spawn_chance = 0.15  # 15% — high chance to populate empty zones
            elif zone_population < 6:
                spawn_chance = 0.05  # 5%
            elif zone_population < 10:
                spawn_chance = base_chance * 2  # Double base
            else:
                spawn_chance = base_chance  # Normal low rate
            
            # Cap bat population per zone
            if bat_count >= 4:
                spawn_chance *= 0.2  # Heavily reduce if already 4+ bats
            
            if random.random() < spawn_chance:
                self.spawn_cave_hostile(screen_key, cave_x, cave_y)
    
    def spawn_cave_hostile(self, screen_key, cave_x, cave_y):
        """Spawn a hostile entity from a cave — bats are most common"""
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        screen_x, screen_y = map(int, screen_key.split(','))
        
        # Choose hostile type (weighted — bats most common from caves)
        roll = random.random()
        if roll < 0.40:
            hostile_type = 'BAT'       # 40% — bats are the primary cave dwellers
        elif roll < 0.60:
            hostile_type = 'GOBLIN'    # 20%
        elif roll < 0.80:
            hostile_type = 'WOLF'      # 20%
        else:
            hostile_type = 'BANDIT'    # 20%
        
        # Find adjacent empty position (bats can land on solid cells since they fly)
        is_flying = ENTITY_TYPES.get(hostile_type, {}).get('flying', False)
        fly_blocked = {'WALL', 'CAVE_WALL', 'DEEP_WATER'}
        
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            spawn_x = cave_x + dx
            spawn_y = cave_y + dy
            
            if not (0 < spawn_x < GRID_WIDTH - 1 and 0 < spawn_y < GRID_HEIGHT - 1):
                continue
            
            cell = screen['grid'][spawn_y][spawn_x]
            if CELL_TYPES[cell].get('solid', False):
                if not is_flying or cell in fly_blocked:
                    continue
            
            if self.is_entity_at_position(spawn_x, spawn_y, screen_key):
                continue
            
            # Spawn hostile
            entity = Entity(hostile_type, spawn_x, spawn_y, screen_x, screen_y, level=1)
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = entity
            
            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)
            
            self.zone_has_hostiles[screen_key] = True
            return
    
    def check_night_skeleton_spawn(self, screen_key):
        """Check if skeleton should spawn at night (more likely near dropped items)"""
        if not self.is_night:
            return  # Only spawn at night
        
        if screen_key not in self.screens:
            return
        
        # Count current population in zone
        zone_population = 0
        if screen_key in self.screen_entities:
            zone_population = len([eid for eid in self.screen_entities[screen_key] 
                                  if eid in self.entities and self.entities[eid].health > 0])
        
        # Reduce spawn chance based on population
        # 0 entities: 100% chance
        # 5 entities: 75% chance
        # 10 entities: 50% chance
        # 15 entities: 25% chance
        # 20+ entities: 10% chance
        if zone_population >= 20:
            population_modifier = 0.1
        elif zone_population >= 15:
            population_modifier = 0.25
        elif zone_population >= 10:
            population_modifier = 0.5
        elif zone_population >= 5:
            population_modifier = 0.75
        else:
            population_modifier = 1.0
        
        # Base spawn chance increased if dropped items present
        spawn_chance = NIGHT_SKELETON_SPAWN_CHANCE * population_modifier
        
        # Check for dropped items (dead bodies)
        if screen_key in self.dropped_items and self.dropped_items[screen_key]:
            # Double spawn chance near dropped items
            spawn_chance *= 2.0
        
        if random.random() > spawn_chance:
            return
        
        screen = self.screens[screen_key]
        screen_x, screen_y = map(int, screen_key.split(','))
        
        # Prefer spawning near dropped items if they exist
        spawn_positions = []
        
        if screen_key in self.dropped_items and self.dropped_items[screen_key]:
            # Find positions near dropped items
            for drop_pos in self.dropped_items[screen_key].keys():
                if isinstance(drop_pos, tuple):
                    drop_x, drop_y = drop_pos
                else:
                    parts = drop_pos.split(',')
                    drop_x, drop_y = int(parts[0]), int(parts[1])
                
                # Check adjacent cells
                for dx in range(-2, 3):
                    for dy in range(-2, 3):
                        test_x = drop_x + dx
                        test_y = drop_y + dy
                        if 0 < test_x < GRID_WIDTH - 1 and 0 < test_y < GRID_HEIGHT - 1:
                            cell = screen['grid'][test_y][test_x]
                            if not CELL_TYPES[cell].get('solid', False):
                                if not self.is_entity_at_position(test_x, test_y, screen_key):
                                    spawn_positions.append((test_x, test_y))
        
        # Fallback to random spawn if no dropped items or no valid positions near them
        if not spawn_positions:
            for _ in range(10):  # Try 10 random positions
                test_x = random.randint(3, GRID_WIDTH - 4)
                test_y = random.randint(3, GRID_HEIGHT - 4)
                cell = screen['grid'][test_y][test_x]
                if not CELL_TYPES[cell].get('solid', False):
                    if not self.is_entity_at_position(test_x, test_y, screen_key):
                        spawn_positions.append((test_x, test_y))
                        break
        
        if spawn_positions:
            spawn_x, spawn_y = random.choice(spawn_positions)
            
            # Spawn hostile skeleton
            skeleton = Entity('SKELETON', spawn_x, spawn_y, screen_x, screen_y, level=1)
            # Make it hostile (override default)
            skeleton.props = ENTITY_TYPES['SKELETON'].copy()
            skeleton.props['hostile'] = True
            skeleton.props['attacks_hostile'] = False
            
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = skeleton
            
            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)
            
            # Mark zone as having hostiles
            self.zone_has_hostiles[screen_key] = True
            
            print(f"A skeleton rises from the darkness in [{screen_key}]!")
    
    def check_termite_spawn(self, screen_key):
        """Check if termite should spawn near trees (prefer FOREST/PLAINS biomes)"""
        if screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        biome = screen.get('biome', 'FOREST')
        
        # Termites spawn more in FOREST and PLAINS biomes
        biome_modifier = 1.0
        if biome == 'FOREST':
            biome_modifier = 2.0  # 2x spawn chance in forests
        elif biome == 'PLAINS':
            biome_modifier = 1.0  # Normal spawn chance in plains
        else:
            biome_modifier = 0.2  # 20% spawn chance in other biomes
        
        # Count current population in zone
        zone_population = 0
        if screen_key in self.screen_entities:
            zone_population = len([eid for eid in self.screen_entities[screen_key] 
                                  if eid in self.entities and self.entities[eid].health > 0])
        
        # Reduce spawn chance based on population (same as skeleton system)
        if zone_population >= 20:
            population_modifier = 0.1
        elif zone_population >= 15:
            population_modifier = 0.25
        elif zone_population >= 10:
            population_modifier = 0.5
        elif zone_population >= 5:
            population_modifier = 0.75
        else:
            population_modifier = 1.0
        
        spawn_chance = TERMITE_SPAWN_CHANCE * population_modifier * biome_modifier
        
        if random.random() > spawn_chance:
            return
        
        screen_x, screen_y = map(int, screen_key.split(','))
        
        # Find trees in the zone to spawn near
        tree_positions = []
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                if cell in ['TREE1', 'TREE2']:
                    tree_positions.append((x, y))
        
        # If no trees, still try to spawn but much lower chance
        if not tree_positions:
            # 10% chance to spawn anyway if no trees
            if random.random() > 0.1:
                return
        
        # Find valid spawn position near a tree
        spawn_positions = []
        
        if tree_positions:
            # Spawn near trees (within 3 cells)
            for tree_x, tree_y in tree_positions[:10]:  # Check up to 10 trees
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        test_x = tree_x + dx
                        test_y = tree_y + dy
                        
                        if 0 < test_x < GRID_WIDTH - 1 and 0 < test_y < GRID_HEIGHT - 1:
                            cell = screen['grid'][test_y][test_x]
                            if not CELL_TYPES[cell].get('solid', False):
                                if not self.is_entity_at_position(test_x, test_y, screen_key):
                                    spawn_positions.append((test_x, test_y))
        else:
            # Fallback to random spawn if no trees
            for _ in range(10):
                test_x = random.randint(3, GRID_WIDTH - 4)
                test_y = random.randint(3, GRID_HEIGHT - 4)
                cell = screen['grid'][test_y][test_x]
                if not CELL_TYPES[cell].get('solid', False):
                    if not self.is_entity_at_position(test_x, test_y, screen_key):
                        spawn_positions.append((test_x, test_y))
                        break
        
        if spawn_positions:
            spawn_x, spawn_y = random.choice(spawn_positions)
            
            # Spawn termite
            termite = Entity('TERMITE', spawn_x, spawn_y, screen_x, screen_y, level=1)
            termite.props = ENTITY_TYPES['TERMITE'].copy()
            
            entity_id = self.next_entity_id
            self.next_entity_id += 1
            self.entities[entity_id] = termite
            
            if screen_key not in self.screen_entities:
                self.screen_entities[screen_key] = []
            self.screen_entities[screen_key].append(entity_id)
            
            # Mark zone as having hostiles
            self.zone_has_hostiles[screen_key] = True
            
            print(f"A termite appears near trees in [{screen_key}]!")
    
    def evacuate_subscreen(self, subscreen_key, parent_screen_key, structure_x, structure_y):
        """Move all entities and items from subscreen back to parent zone"""
        # Get entities in this subscreen
        entities_to_evacuate = self.screen_entities.get(subscreen_key, []).copy()
        
        if not entities_to_evacuate:
            return  # No entities to evacuate
        
        # Find safe exit positions around the structure
        parent_grid = self.screens.get(parent_screen_key, {}).get('grid', [])
        if not parent_grid:
            return
        
        exit_positions = []
        
        # Check 3x3 area around structure for valid positions
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                check_x = structure_x + dx
                check_y = structure_y + dy
                
                # Skip the structure position itself
                if dx == 0 and dy == 0:
                    continue
                
                # Check if position is valid and walkable
                if (0 <= check_y < GRID_HEIGHT and 0 <= check_x < GRID_WIDTH):
                    cell = parent_grid[check_y][check_x]
                    cell_props = CELL_TYPES.get(cell, {})
                    if not cell_props.get('solid', False):
                        exit_positions.append((check_x, check_y))
        
        # If no valid positions, use structure position (they'll spawn on rubble)
        if not exit_positions:
            exit_positions = [(structure_x, structure_y)]
        
        # Evacuate each entity
        evacuated_count = 0
        for entity_id in entities_to_evacuate:
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            
            # Choose random exit position
            exit_x, exit_y = random.choice(exit_positions)
            
            # Move entity back to parent zone
            entity.x = exit_x
            entity.y = exit_y
            entity.world_x = float(exit_x)
            entity.world_y = float(exit_y)
            
            # Parse screen coordinates from parent_screen_key
            coords = parent_screen_key.split(',')
            entity.screen_x = int(coords[0]) if len(coords) > 0 else 0
            entity.screen_y = int(coords[1]) if len(coords) > 1 else 0
            
            # Clear subscreen state
            entity.in_subscreen = False
            entity.subscreen_key = None
            
            # Add to parent zone entity list
            if parent_screen_key not in self.screen_entities:
                self.screen_entities[parent_screen_key] = []
            if entity_id not in self.screen_entities[parent_screen_key]:
                self.screen_entities[parent_screen_key].append(entity_id)
            
            evacuated_count += 1
        
        # Clear subscreen from screen_entities
        if subscreen_key in self.screen_entities:
            self.screen_entities[subscreen_key] = []
        
        if evacuated_count > 0:
            print(f"  Evacuated {evacuated_count} entities from destroyed structure")
    
    def process_house_destruction(self, x, y, screen_key):
        """Handle house destruction with proper NPC/item evacuation"""
        # Build subscreen key
        subscreen_key = f"{screen_key}_{x}_{y}_HOUSE_INTERIOR"
        
        # Evacuate all NPCs from the subscreen
        if subscreen_key in self.subscreens:
            self.evacuate_subscreen(subscreen_key, screen_key, x, y)
        
        # Remove the subscreen from memory
        if subscreen_key in self.subscreens:
            del self.subscreens[subscreen_key]
        
        # Clear screen_entities for this subscreen
        if subscreen_key in self.screen_entities:
            del self.screen_entities[subscreen_key]
        
        # Drop loot on the ground
        if screen_key not in self.dropped_items:
            self.dropped_items[screen_key] = {}
        
        drop_key = (x, y)
        if drop_key not in self.dropped_items[screen_key]:
            self.dropped_items[screen_key][drop_key] = {}
        
        # Drop wood
        wood_amount = random.randint(3, 5)
        self.dropped_items[screen_key][drop_key]['wood'] = \
            self.dropped_items[screen_key][drop_key].get('wood', 0) + wood_amount
        
        # Drop stone
        stone_amount = random.randint(2, 3)
        self.dropped_items[screen_key][drop_key]['stone'] = \
            self.dropped_items[screen_key][drop_key].get('stone', 0) + stone_amount
        
        # Drop gold
        gold_amount = random.randint(1, 2)
        self.dropped_items[screen_key][drop_key]['gold'] = \
            self.dropped_items[screen_key][drop_key].get('gold', 0) + gold_amount
        
        # Convert house cell to planks (destroyed building materials)
        if screen_key in self.screens:
            grid = self.screens[screen_key]['grid']
            if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                grid[y][x] = 'PLANKS'
        
        print(f"House at ({x},{y}) in zone {screen_key} destroyed!")
    
    def update_cells(self):
        """Update cell growth and changes for all screens based on distance"""
        # Update current screen more frequently
        if self.tick % 60 == 0:
            # Current zone full update
            screen_x = self.player['screen_x']
            screen_y = self.player['screen_y']
            screen_key = f"{screen_x},{screen_y}"
            
            if screen_key in self.screens:
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


    def decay_dropped_items(self, screen_x, screen_y):
        """General function to decay dropped items based on item decay configuration"""
        screen_key = f"{screen_x},{screen_y}"
        
        if screen_key not in self.dropped_items or screen_key not in self.screens:
            return
        
        screen = self.screens[screen_key]
        cells_to_update = []
        
        # Check each position with dropped items
        for cell_pos, items in list(self.dropped_items[screen_key].items()):
            x, y = cell_pos
            current_cell = screen['grid'][y][x]
            
            # Process each item type at this position
            for item_name, item_count in list(items.items()):
                # Check if this item type has decay config
                if item_name not in ITEM_DECAY_CONFIG:
                    continue
                
                config = ITEM_DECAY_CONFIG[item_name]
                
                # Calculate decay chance (base rate * item count)
                decay_chance = config['decay_rate'] * item_count
                
                if random.random() < decay_chance:
                    # Decay one item
                    items[item_name] -= 1
                    if items[item_name] <= 0:
                        del items[item_name]
                    
                    # Remove empty items dict
                    if not items:
                        del self.dropped_items[screen_key][cell_pos]
                    
                    # Determine decay result based on current cell type
                    decay_results = config['decay_results']
                    
                    # Get results for this cell type, or default
                    results = decay_results.get(current_cell, decay_results.get('default', [(None, 1.0)]))
                    
                    # Weighted random selection of result
                    roll = random.random()
                    cumulative = 0.0
                    for result_cell, weight in results:
                        cumulative += weight
                        if roll < cumulative:
                            if result_cell is not None:
                                cells_to_update.append((x, y, result_cell))
                            break
        
        # Apply cell updates
        for x, y, new_cell in cells_to_update:
            self.set_grid_cell(screen, x, y, new_cell)

    def update_entities(self):
        """Update all entities - AI, movement, stats"""
        if self.tick % 30 != 0:  # Update entities every 0.5 seconds
            return
        
        # Check for spawning new entities in nearby zones (every 0.5 seconds)
        self.check_zone_spawning()
        
        entities_to_remove = []
        
        # Get current player screen
        player_screen_x = self.player['screen_x']
        player_screen_y = self.player['screen_y']
        
        for entity_id, entity in list(self.entities.items()):
            # Calculate distance from player's screen
            screen_distance = abs(entity.screen_x - player_screen_x) + abs(entity.screen_y - player_screen_y)
            
            # Remove dead entities FIRST (regardless of distance)
            if not entity.is_alive():
                entities_to_remove.append(entity_id)
                continue
            
            # Only update entities within 2 screens of player
            if screen_distance > 2:
                continue
            
            # Decay stats
            entity.decay_stats()
            
            # Regenerate health if well-fed and hydrated
            heal_boost = 1.0
            
            # Peaceful NPCs get healing boost near camps and houses
            if not entity.props.get('hostile', False):
                screen_key = f"{entity.screen_x},{entity.screen_y}"
                if screen_key in self.screens:
                    screen = self.screens[screen_key]
                    
                    # Check for camp or house within 3 cells
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            check_x = entity.x + dx
                            check_y = entity.y + dy
                            
                            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                cell = screen['grid'][check_y][check_x]
                                if cell == 'CAMP':
                                    heal_boost = 2.0  # 2x healing near camp
                                    break
                                elif cell == 'HOUSE':
                                    heal_boost = 3.0  # 3x healing near house
                                    break
                        if heal_boost > 1.0:
                            break
            
            # Apply healing regeneration
            entity.regenerate_health(heal_boost)
            
            # Update AI and movement - more frequently for closer screens
            if screen_distance == 0:
                # Current screen - update every tick
                self.update_entity_ai(entity_id, entity)
                self.update_subscreen_npc_behavior(entity_id, entity)
            elif screen_distance == 1:
                # Adjacent screens - update every other tick
                if self.tick % 60 == 0:
                    self.update_entity_ai(entity_id, entity)
                    self.update_subscreen_npc_behavior(entity_id, entity)
            else:
                # Distance 2 - update every 3 ticks
                if self.tick % 90 == 0:
                    self.update_entity_ai(entity_id, entity)
                    self.update_subscreen_npc_behavior(entity_id, entity)
        
        # Remove dead entities
        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)
    
    def check_zone_spawning(self):
        """Check each nearby zone and spawn entities based on population and missing types"""
        player_screen_x = self.player['screen_x']
        player_screen_y = self.player['screen_y']
        player_zone_key = f"{player_screen_x},{player_screen_y}"
        
        # Check player zone specifically
        if player_zone_key in self.screens:
            entity_count = 0
            types_in_zone = set()
            for eid in self.screen_entities.get(player_zone_key, []):
                if eid in self.entities:
                    entity_count += 1
                    types_in_zone.add(self.entities[eid].type)
        
        spawns_this_cycle = 0
        max_spawns = 3  # Allow up to 3 spawns per cycle
        
        # Check zones within 2 screens of player
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if spawns_this_cycle >= max_spawns:
                    return
                
                zone_x = player_screen_x + dx
                zone_y = player_screen_y + dy
                screen_key = f"{zone_x},{zone_y}"
                
                # Skip if zone doesn't exist
                if screen_key not in self.screens:
                    continue
                
                # Get biome for this zone
                biome = self.screens[screen_key].get('biome', 'FOREST')
                
                # Count entities in this zone and track which types exist
                entity_count = 0
                types_in_zone = set()
                for eid in self.screen_entities.get(screen_key, []):
                    if eid in self.entities:
                        entity_count += 1
                        types_in_zone.add(self.entities[eid].type)
                
                # Calculate spawn chance based on population
                if entity_count == 0:
                    spawn_chance = 1.0
                elif entity_count < 5:
                    spawn_chance = 1.0 - (entity_count * 0.16)
                else:
                    spawn_chance = 0.10
                
                roll = random.random()
                
                # Try to spawn if chance succeeds
                if roll < spawn_chance:
                    spawn_tables = {
                        'FOREST': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('LUMBERJACK', 0.20), ('FARMER', 0.18),
                            ('DEER', 0.15), ('WOLF', 0.10),
                            ('SHEEP', 0.08), ('GOBLIN', 0.06), ('BANDIT', 0.03)
                        ],
                        'PLAINS': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('FARMER', 0.25), ('SHEEP', 0.18),
                            ('DEER', 0.12), ('LUMBERJACK', 0.08),
                            ('WOLF', 0.08), ('GOBLIN', 0.06), ('BANDIT', 0.03)
                        ],
                        'DESERT': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('GOBLIN', 0.20), ('BANDIT', 0.15),
                            ('MINER', 0.18), ('FARMER', 0.10),
                            ('WOLF', 0.08), ('DEER', 0.06), ('SHEEP', 0.03)
                        ],
                        'MOUNTAINS': [
                            ('TRADER', 0.10), ('GUARD', 0.10),
                            ('MINER', 0.22), ('GOBLIN', 0.18),
                            ('WOLF', 0.15), ('LUMBERJACK', 0.10),
                            ('BANDIT', 0.08), ('DEER', 0.04), ('SHEEP', 0.03)
                        ]
                    }
                    
                    spawn_list = spawn_tables.get(biome, spawn_tables['FOREST'])
                    
                    # PRIORITY 1: Spawn missing essential types (TRADER, GUARD)
                    essential_types = ['TRADER', 'GUARD']
                    for essential_type in essential_types:
                        if essential_type not in types_in_zone:
                            success = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type=essential_type)
                            
                            if success:
                                spawns_this_cycle += 1
                                return
                    
                    # PRIORITY 2: Pick weighted random type to spawn
                    types = [t[0] for t in spawn_list]
                    weights = [t[1] for t in spawn_list]
                    entity_type = random.choices(types, weights=weights)[0]
                    
                    success = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type=entity_type)
                    
                    if success:
                        spawns_this_cycle += 1
    
    def spawn_single_entity_at_entrance(self, screen_x, screen_y, biome_name, force_type=None):
        """Spawn a single entity at a zone entrance
        
        Args:
            force_type: If provided, spawn this specific entity type instead of choosing randomly
        """
        screen_key = f"{screen_x},{screen_y}"
        
        # Biome-based spawning probabilities (all NPCs in all biomes)
        spawn_tables = {
            'FOREST': [
                ('DEER', 0.18),
                ('WOLF', 0.10),
                ('SHEEP', 0.05),
                ('FARMER', 0.12),
                ('LUMBERJACK', 0.15),
                ('TRADER', 0.15),
                ('GUARD', 0.15),
                ('BANDIT', 0.05),
                ('GOBLIN', 0.05)
            ],
            'PLAINS': [
                ('SHEEP', 0.20),
                ('DEER', 0.12),
                ('WOLF', 0.05),
                ('FARMER', 0.18),
                ('LUMBERJACK', 0.05),
                ('TRADER', 0.15),
                ('GUARD', 0.15),
                ('BANDIT', 0.05),
                ('GOBLIN', 0.05)
            ],
            'DESERT': [
                ('GOBLIN', 0.20),
                ('BANDIT', 0.14),
                ('MINER', 0.10),      # Added
                ('SHEEP', 0.05),
                ('DEER', 0.05),
                ('WOLF', 0.05),
                ('FARMER', 0.07),
                ('LUMBERJACK', 0.04),
                ('TRADER', 0.18),
                ('GUARD', 0.12)
            ],
            'MOUNTAINS': [
                ('WOLF', 0.18),
                ('GOBLIN', 0.16),
                ('MINER', 0.14),      # Added
                ('BANDIT', 0.09),
                ('DEER', 0.07),
                ('SHEEP', 0.04),
                ('FARMER', 0.03),
                ('LUMBERJACK', 0.09),
                ('TRADER', 0.12),
                ('GUARD', 0.08)
            ]
        }
        
        spawn_list = spawn_tables.get(biome_name, spawn_tables['FOREST'])
        
        # Pick entity type - use forced type if provided, otherwise random
        if force_type:
            entity_type = force_type
        else:
            # Pick one entity type based on weights
            types = [t[0] for t in spawn_list]
            weights = [t[1] for t in spawn_list]
            entity_type = random.choices(types, weights=weights)[0]
        
        # Get entrance positions
        entrance_positions = []
        screen = self.screens[screen_key]
        center_x = GRID_WIDTH // 2
        center_y = GRID_HEIGHT // 2
        
        # Top entrance (if exists)
        if screen['exits']['top']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, 1))
        
        # Bottom entrance (if exists)
        if screen['exits']['bottom']:
            for x in range(center_x - 1, center_x + 2):
                entrance_positions.append((x, GRID_HEIGHT - 2))
        
        # Left entrance (if exists)
        if screen['exits']['left']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((1, y))
        
        # Right entrance (if exists)
        if screen['exits']['right']:
            for y in range(center_y - 1, center_y + 2):
                entrance_positions.append((GRID_WIDTH - 2, y))
        
        # Fallback if no entrances
        if not entrance_positions:
            entrance_positions = [(center_x, center_y)]
        
        # Try to spawn at entrance
        for attempt in range(10):
            x, y = random.choice(entrance_positions)
            cell = screen['grid'][y][x]
            
            if not CELL_TYPES[cell]['solid']:
                # Spawn entity
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                
                entity = Entity(entity_type, x, y, screen_x, screen_y)
                self.entities[entity_id] = entity
                
                if screen_key not in self.screen_entities:
                    self.screen_entities[screen_key] = []
                self.screen_entities[screen_key].append(entity_id)
                
                # Small chance to log arrival
                if random.random() < 0.05:
                    print(f"{entity_type} arrived at [{screen_key}]")
                return True  # Successfully spawned
        
        return False  # Failed to spawn
    
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
        
        # Remove from followers if it was a follower
        if entity_id in self.followers:
            self.followers.remove(entity_id)
            # Remove from follower inventory
            follower_name = f"{entity.type.lower()}_{entity_id}"
            if self.inventory.has_item(follower_name):
                self.inventory.remove_item(follower_name, 1)
            print(f"{entity.type} follower has died!")
        
        # Drop items if entity has drops (with probability)
        if 'drops' in entity.props:
            for drop in entity.props['drops']:
                if random.random() < drop['chance']:
                    if 'cell' in drop:
                        # Cell placement drop — change the grid cell at entity position
                        if screen_key in self.screens:
                            cx = max(1, min(GRID_WIDTH - 2, entity.x))
                            cy = max(1, min(GRID_HEIGHT - 2, entity.y))
                            self.screens[screen_key]['grid'][cy][cx] = drop['cell']
                    elif 'item' in drop:
                        for _ in range(drop['amount']):
                            # Add some randomness to drop position
                            drop_x = entity.x + random.randint(-1, 1)
                            drop_y = entity.y + random.randint(-1, 1)
                            
                            # Clamp to valid positions
                            drop_x = max(1, min(GRID_WIDTH - 2, drop_x))
                            drop_y = max(1, min(GRID_HEIGHT - 2, drop_y))
                            
                            # Create the drop
                            if screen_key not in self.dropped_items:
                                self.dropped_items[screen_key] = {}
                            
                            cell_key = (drop_x, drop_y)
                            if cell_key not in self.dropped_items[screen_key]:
                                self.dropped_items[screen_key][cell_key] = {}
                            
                            item_name = drop['item']
                            self.dropped_items[screen_key][cell_key][item_name] = \
                                self.dropped_items[screen_key][cell_key].get(item_name, 0) + 1
        
        # All entities have a chance to drop a magic_rune on death
        if random.random() < 0.15:
            drop_x = max(1, min(GRID_WIDTH - 2, entity.x))
            drop_y = max(1, min(GRID_HEIGHT - 2, entity.y))
            if screen_key not in self.dropped_items:
                self.dropped_items[screen_key] = {}
            cell_key = (drop_x, drop_y)
            if cell_key not in self.dropped_items[screen_key]:
                self.dropped_items[screen_key][cell_key] = {}
            self.dropped_items[screen_key][cell_key]['magic_rune'] = \
                self.dropped_items[screen_key][cell_key].get('magic_rune', 0) + 1
        
        # Drop all items from inventory (excluding magic and wood/planks)
        for item_name, count in entity.inventory.items():
            # Skip dropping magic items (spells are permanent)
            if item_name in ITEMS and ITEMS[item_name].get('is_spell', False):
                continue
            # Skip wood and planks — they clutter the map as overlays
            if item_name in ('wood', 'planks'):
                continue
            
            for _ in range(count):
                # Add some randomness to drop position
                drop_x = entity.x + random.randint(-1, 1)
                drop_y = entity.y + random.randint(-1, 1)
                
                # Clamp to valid positions
                drop_x = max(1, min(GRID_WIDTH - 2, drop_x))
                drop_y = max(1, min(GRID_HEIGHT - 2, drop_y))
                
                # Create the drop
                if screen_key not in self.dropped_items:
                    self.dropped_items[screen_key] = {}
                
                cell_key = (drop_x, drop_y)
                if cell_key not in self.dropped_items[screen_key]:
                    self.dropped_items[screen_key][cell_key] = {}
                
                self.dropped_items[screen_key][cell_key][item_name] = \
                    self.dropped_items[screen_key][cell_key].get(item_name, 0) + 1
        
        # Remove from screen entities list
        if screen_key in self.screen_entities:
            if entity_id in self.screen_entities[screen_key]:
                self.screen_entities[screen_key].remove(entity_id)
        
        # Check if this was a hostile entity and zone is now clear
        if entity.props.get('hostile', False):
            self.check_zone_clear_hostiles(screen_key)
        
        # Remove from entities dict
        del self.entities[entity_id]
    
    def cleanup_screen_entities(self):
        """Remove None and invalid entity_ids from screen_entities"""
        for screen_key in list(self.screen_entities.keys()):
            if screen_key in self.screen_entities:
                # Filter out None and invalid IDs
                self.screen_entities[screen_key] = [
                    eid for eid in self.screen_entities[screen_key]
                    if eid is not None and eid in self.entities
                ]
                # Remove empty lists
                if not self.screen_entities[screen_key]:
                    del self.screen_entities[screen_key]

    def check_npc_inspection(self):
        """Check if player is targeting any entity and set inspection"""
        # During autopilot, the proxy's facing direction constantly sweeps over
        # nearby NPCs.  The inspection system sets idle_timer=30 on each one and
        # the inspected_npc guard skips their entire AI update, which freezes
        # every NPC the proxy walks past.  Disable inspection while autopilot
        # is active so the proxy doesn't paralyse the zone.
        if getattr(self, 'autopilot', False):
            self.inspected_npc = None
            return

        target = self.get_target_cell()
        if not target:
            self.inspected_npc = None
            return
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Find entity at target
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.x == check_x and entity.y == check_y:
                        # Never inspect the autopilot proxy — it renders as the player
                        if entity.props.get('is_autopilot_proxy', False):
                            self.inspected_npc = None
                            return
                        # Inspect ANY entity (peaceful or hostile)
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
    
    def try_travel_behavior(self, entity, screen_key):
        """Trader travel behavior - move toward zone exits"""
        # Move toward target exit
        if not hasattr(entity, 'target_exit') or entity.target_exit is None:
            # Get available exits from current screen
            if screen_key in self.screens:
                screen_exits = self.screens[screen_key]['exits']
                available_exits = [direction for direction, has_exit in screen_exits.items() if has_exit]
                if available_exits:
                    entity.target_exit = random.choice(available_exits)
                else:
                    # Fallback if no exits defined (shouldn't happen)
                    entity.target_exit = random.choice(['top', 'bottom', 'left', 'right'])
            else:
                entity.target_exit = random.choice(['top', 'bottom', 'left', 'right'])
        
        # Get target position - choose one of the 2 exit tiles randomly
        # This ensures we target an actual GRASS exit cell, not a WALL
        exit_positions = self.get_exit_positions(entity.target_exit)
        if exit_positions:
            target_x, target_y = random.choice(exit_positions)
        else:
            # Fallback (shouldn't happen)
            target_x, target_y = GRID_WIDTH // 2, GRID_HEIGHT // 2
        
        # Move toward target
        self.move_entity_towards(entity, target_x, target_y)
        
        # Check if at exit — attempt zone transition, then pick a new exit
        at_exit, _ = self.is_at_exit(entity.x, entity.y)
        if at_exit:
            # Find entity_id for zone transition
            entity_id = None
            for eid, e in self.entities.items():
                if e is entity:
                    entity_id = eid
                    break
            if entity_id is not None:
                self.try_entity_zone_transition(entity_id, entity)
            entity.target_exit = None
    

    """Second half of game logic - combat, save/load, game loop"""
    
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
    
    def teleport_follower_to_player(self, entity_id, entity):
        """Teleport a follower to the player's current screen"""
        # Remove from old screen
        old_screen_key = entity.screen_key
        if old_screen_key in self.screen_entities and entity_id in self.screen_entities[old_screen_key]:
            self.screen_entities[old_screen_key].remove(entity_id)
        
        # Move to player's screen
        new_screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Add to new screen entities list
        if new_screen_key not in self.screen_entities:
            self.screen_entities[new_screen_key] = []
        self.screen_entities[new_screen_key].append(entity_id)
        
        # Update entity position - place near player but not on top
        entity.screen_x = self.player['screen_x']
        entity.screen_y = self.player['screen_y']
        
        # Find a nearby empty position
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx == 0 and dy == 0:
                    continue
                test_x = self.player['x'] + dx
                test_y = self.player['y'] + dy
                
                # Check bounds
                if 0 <= test_x < GRID_WIDTH and 0 <= test_y < GRID_HEIGHT:
                    # Check if position is walkable
                    if new_screen_key in self.screens:
                        cell = self.screens[new_screen_key]['grid'][test_y][test_x]
                        if not CELL_TYPES[cell].get('solid', False):
                            entity.x = test_x
                            entity.y = test_y
                            return
        
        # If no empty spot found, just place near player
        entity.x = self.player['x']
        entity.y = self.player['y']
    
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
                        screen['grid'][y][x] = cell_info['grows_to']
                    
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
                        screen['grid'][y][x] = cell_info['degrades_to']
        
        # Track last update
        self.screen_last_update[key] = self.tick
    
    def apply_rain(self, screen_x, screen_y):
        """Apply rain effects - convert some cells to water and dirt to grass (biome-specific)"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return
        
        # Track last rain time for this zone
        self.zone_last_rain[key] = self.tick
        
        screen = self.screens[key]
        biome = screen.get('biome', 'FOREST')
        
        # Biome-specific rain multipliers
        rain_multiplier = 1.0
        if biome == 'DESERT':
            rain_multiplier = 0.1  # Very rare rain in desert
        elif biome == 'MOUNTAINS':
            rain_multiplier = 0.3  # Reduced rain in mountains
        elif biome == 'PLAINS':
            rain_multiplier = 1.2  # Slightly more rain in plains
        # FOREST uses default 1.0
        
        # More water creation during rain (biome adjusted)
        water_spawns = int(RAIN_WATER_SPAWNS * rain_multiplier)
        for _ in range(water_spawns):
            x = random.randint(1, GRID_WIDTH - 2)
            y = random.randint(1, GRID_HEIGHT - 2)
            
            cell = screen['grid'][y][x]
            if cell in ['DIRT', 'SAND'] and not self.is_cell_enchanted(x, y, key):
                if random.random() < 0.3:
                    screen['grid'][y][x] = 'WATER'
        
        # Convert dirt to grass during rain (biome adjusted)
        grass_spawns = int(RAIN_GRASS_SPAWNS * rain_multiplier)
        for _ in range(grass_spawns):
            x = random.randint(1, GRID_WIDTH - 2)
            y = random.randint(1, GRID_HEIGHT - 2)
            
            cell = screen['grid'][y][x]
            if cell == 'DIRT' and not self.is_cell_enchanted(x, y, key):
                if random.random() < 0.4:
                    screen['grid'][y][x] = 'GRASS'
    
    
    def is_cell_enchanted(self, x, y, screen_key):
        """Check if a cell is enchanted (frozen by wizard spell)"""
        if not self.is_overworld_zone(screen_key):
            return False
        sx, sy = map(int, screen_key.split(','))
        return (sx, sy, x, y) in self.enchanted_cells
    
    def apply_cellular_automata(self, screen_x, screen_y):
        """Apply cellular automata rules to a screen"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return
        
        screen = self.screens[key]
        new_grid = [row[:] for row in screen['grid']]  # Deep copy
        
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = screen['grid'][y][x]
                
                # Skip walls and structures
                if cell in ['WALL', 'HOUSE', 'CAVE']:
                    continue
                
                # Skip enchanted cells - they are frozen in place
                if self.is_cell_enchanted(x, y, key):
                    continue
                
                # Check if at exit for cross-zone spread
                at_exit, direction = self.is_at_exit(x, y)
                if at_exit:
                    adj_biome = self.get_adjacent_screen_biome(screen_x, screen_y, direction)
                    if adj_biome != screen['biome'] and random.random() < 0.01:
                        # Spread adjacent biome cell
                        new_grid[y][x] = self.get_common_cell_for_biome(adj_biome)
                        continue
                
                # Skip edges (except exits)
                if x == 0 or x == GRID_WIDTH - 1 or y == 0 or y == GRID_HEIGHT - 1:
                    continue
                
                neighbors = self.get_neighbors(x, y, key)
                if not neighbors:
                    continue
                
                # Count neighbor types
                water_count = self.count_cell_type(neighbors, 'WATER')
                deep_water_count = self.count_cell_type(neighbors, 'DEEP_WATER')
                dirt_count = self.count_cell_type(neighbors, 'DIRT')
                grass_count = self.count_cell_type(neighbors, 'GRASS')
                tree_count = self.count_cell_type(neighbors, 'TREE')
                sand_count = self.count_cell_type(neighbors, 'SAND')
                flower_count = self.count_cell_type(neighbors, 'FLOWER')
                
                total_water = water_count + deep_water_count
                
                # Dirt → Grass (needs water)
                if cell == 'DIRT' and total_water >= 2:
                    if random.random() < DIRT_TO_GRASS_RATE:
                        new_grid[y][x] = 'GRASS'
                
                # Grass → Dirt (lack of water)
                elif cell == 'GRASS' and total_water == 0:
                    if random.random() < GRASS_TO_DIRT_RATE:
                        new_grid[y][x] = 'DIRT'
                
                # Dirt → Sand (severe drought)
                elif cell == 'DIRT' and total_water == 0 and (sand_count >= 2 or grass_count == 0):
                    if random.random() < DIRT_TO_SAND_RATE:
                        new_grid[y][x] = 'SAND'
                
                # Tree spread (needs grass and water)
                elif cell == 'GRASS' and 1 <= tree_count <= 2 and total_water >= 1:
                    if random.random() < TREE_GROWTH_RATE:
                        new_grid[y][x] = 'TREE1'
                
                # Sand reclamation (water converts sand back to dirt)
                elif cell == 'SAND' and total_water >= 2:
                    if random.random() < SAND_RECLAIM_RATE:
                        new_grid[y][x] = 'DIRT'
                
                # Deep water formation (lakes)
                elif cell == 'WATER' and water_count >= 4:
                    if random.random() < DEEP_WATER_FORM_RATE:
                        new_grid[y][x] = 'DEEP_WATER'
                
                # Deep water evaporation
                elif cell == 'DEEP_WATER' and (water_count + deep_water_count) < 2:
                    if random.random() < DEEP_WATER_EVAPORATE_RATE:
                        new_grid[y][x] = 'WATER'
                
                # Water evaporation (slow decay to dirt without water neighbors)
                elif cell == 'WATER' and total_water <= 1:
                    if random.random() < WATER_TO_DIRT_RATE:
                        new_grid[y][x] = 'DIRT'
                
                # Flooding (water spreads to dirt when abundant)
                elif cell == 'DIRT' and total_water >= 3:
                    if random.random() < FLOODING_RATE:
                        new_grid[y][x] = 'WATER'
                
                # Flower spread
                elif cell == 'GRASS' and flower_count >= 1 and flower_count <= 2 and total_water >= 1:
                    if random.random() < FLOWER_SPREAD_RATE:
                        new_grid[y][x] = 'FLOWER'
                
                # Flower death (overcrowding or drought)
                elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
                    if random.random() < FLOWER_DECAY_RATE:
                        new_grid[y][x] = 'GRASS'

                # Tree overcrowding death
                elif cell.startswith('TREE') and tree_count >= 4:
                    if random.random() < TREE_DECAY_RATE:
                        new_grid[y][x] = 'GRASS'
                
                # Base biome cell spreading (very slow cross-biome expansion)
                # GRASS spreads to DIRT/SAND slowly
                elif cell == 'GRASS' and (dirt_count >= 2 or sand_count >= 1):
                    if random.random() < 0.001:  # 0.1% chance
                        # Can spread to dirt or sand neighbors
                        pass  # Grass already here, just noting the spread potential
                
                # SAND spreads to DIRT/GRASS slowly
                elif cell == 'SAND' and sand_count >= 2:
                    if random.random() < 0.001:  # 0.1% chance
                        # Sand can spread to adjacent dirt
                        pass
                
                # DIRT can receive spreading from either
                elif cell == 'DIRT':
                    if grass_count >= 3 and random.random() < 0.001:
                        new_grid[y][x] = 'GRASS'  # Grass invades
                    elif sand_count >= 3 and random.random() < 0.001:
                        new_grid[y][x] = 'SAND'  # Desert expands
                
                # Wood decay to dirt (high rate outside structures)
                elif cell == 'WOOD' and not self.is_near_structure(x, y, key):
                    if random.random() < 0.05:  # 5% decay rate
                        new_grid[y][x] = 'DIRT'
                
                # Planks decay to dirt (outside structures)
                elif cell == 'PLANKS' and not self.is_near_structure(x, y, key):
                    if random.random() < 0.03:  # 3% decay rate
                        new_grid[y][x] = 'DIRT'
                
                # Crop decay without rain (drought) - moderate rates
                elif cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                    # Check if zone has had rain recently
                    last_rain = self.zone_last_rain.get(key, 0)
                    ticks_since_rain = self.tick - last_rain
                    
                    # Check if zone has a farmer
                    has_farmer = False
                    if key in self.screen_entities:
                        for eid in self.screen_entities[key]:
                            if eid in self.entities and self.entities[eid].type == 'FARMER':
                                has_farmer = True
                                break
                    
                    # Moderate decay rates - balanced
                    decay_rate = 0.0001  # 0.01% with farmer
                    
                    # No rain in 1200 ticks (20 seconds) - light decay
                    if ticks_since_rain > 1200:
                        decay_rate = 0.001  # 0.1% decay rate
                    
                    # No rain in 3600 ticks (60 seconds) - moderate decay
                    if ticks_since_rain > 3600:
                        decay_rate = 0.01  # 1% decay rate
                    
                    # No farmer doubles decay
                    if not has_farmer:
                        decay_rate *= 2.0
                    
                    if random.random() < decay_rate:
                        new_grid[y][x] = 'DIRT'
        
        screen['grid'] = new_grid
        
        # Check if zone biome should update based on cell composition
        self.check_zone_biome_shift(screen_x, screen_y)
    
    def check_zone_biome_shift(self, screen_x, screen_y):
        """Check if zone biome should change based on dominant cell types"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return
        
        screen = self.screens[key]
        grid = screen['grid']
        current_biome = screen.get('biome', 'FOREST')
        
        # Count biome-indicative cells
        cell_counts = {
            'GRASS': 0,
            'SAND': 0,
            'STONE': 0,
            'DIRT': 0,
            'WATER': 0,
            'TREE': 0
        }
        
        total_cells = 0
        for y in range(GRID_HEIGHT):
            for x in range(GRID_WIDTH):
                cell = grid[y][x]
                total_cells += 1
                
                if cell == 'GRASS':
                    cell_counts['GRASS'] += 1
                elif cell == 'SAND':
                    cell_counts['SAND'] += 1
                elif cell == 'STONE':
                    cell_counts['STONE'] += 1
                elif cell == 'DIRT':
                    cell_counts['DIRT'] += 1
                elif cell in ['WATER', 'DEEP_WATER']:
                    cell_counts['WATER'] += 1
                elif cell.startswith('TREE'):
                    cell_counts['TREE'] += 1
        
        # Determine dominant characteristics
        grass_pct = cell_counts['GRASS'] / total_cells
        sand_pct = cell_counts['SAND'] / total_cells
        stone_pct = cell_counts['STONE'] / total_cells
        tree_pct = cell_counts['TREE'] / total_cells
        
        # Biome shift thresholds (need significant dominance)
        new_biome = current_biome
        
        if sand_pct > 0.4:  # 40%+ sand
            new_biome = 'DESERT'
        elif stone_pct > 0.3:  # 30%+ stone
            new_biome = 'MOUNTAINS'
        elif grass_pct > 0.5 and tree_pct < 0.1:  # 50%+ grass, few trees
            new_biome = 'PLAINS'
        elif grass_pct > 0.3 and tree_pct > 0.15:  # 30%+ grass, 15%+ trees
            new_biome = 'FOREST'
        
        # Only update if changed and print notification
        if new_biome != current_biome:
            screen['biome'] = new_biome
            print(f"Zone [{screen_x},{screen_y}] biome shifted: {current_biome} → {new_biome}")
    
    def is_near_structure(self, x, y, screen_key):
        """Check if cell is near HOUSE/CAMP (within 2 cells)"""
        if screen_key not in self.screens:
            return False
        
        grid = self.screens[screen_key]['grid']
        for dy in range(-2, 3):
            for dx in range(-2, 3):
                check_x = x + dx
                check_y = y + dy
                if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                    if grid[check_y][check_x] in ['HOUSE', 'CAMP']:
                        return True
        return False

    def handle_drops(self, cell_type, x, y):
        """Handle cell drops based on probabilities"""
        if cell_type not in CELL_TYPES:
            return
        
        cell_info = CELL_TYPES[cell_type]
        if 'drops' not in cell_info:
            return
        
        rand = random.random()
        cumulative = 0
        
        for drop in cell_info['drops']:
            cumulative += drop.get('chance', 0)
            if rand < cumulative:
                if 'item' in drop:
                    self.inventory.add_item(drop['item'], drop.get('amount', 1))
                if 'cell' in drop:
                    self.current_screen['grid'][y][x] = drop['cell']
                break
    
    def pickup_items(self, x, y):
        """Pick up dropped items from cell"""
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if screen_key not in self.dropped_items:
            return
        
        cell_key = (x, y)
        if cell_key in self.dropped_items[screen_key]:
            items_at_pos = self.dropped_items[screen_key][cell_key]
            runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
            
            total_rune_damage = 0
            runes_to_destroy = {}
            
            for rune_type in runestone_types:
                if rune_type in items_at_pos:
                    rune_count = items_at_pos[rune_type]
                    # Damage = number of runes of this type
                    total_rune_damage += rune_count
                    # 50% of runes destroyed on pickup
                    destroyed = max(1, int(rune_count * 0.5))
                    runes_to_destroy[rune_type] = destroyed
            
            # Apply runestone damage to player
            if total_rune_damage > 0:
                self.player_take_damage(total_rune_damage)
                print(f"Player takes {total_rune_damage} damage from runestones!")
            
            # Pick up items
            for item_name, count in items_at_pos.items():
                # Destroy some runestones on pickup
                if item_name in runes_to_destroy:
                    destroyed = runes_to_destroy[item_name]
                    remaining = count - destroyed
                    if remaining > 0:
                        self.inventory.add_item(item_name, remaining)
                else:
                    self.inventory.add_item(item_name, count)
            
            del self.dropped_items[screen_key][cell_key]
    
    def drop_item(self, item_name, x, y):
        """Drop item onto cell (works in both overworld and subscreens)"""
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            screen_key = self.player['subscreen_key']
        if screen_key not in self.dropped_items:
            self.dropped_items[screen_key] = {}
        
        cell_key = (x, y)
        if cell_key not in self.dropped_items[screen_key]:
            self.dropped_items[screen_key][cell_key] = {}
        
        self.dropped_items[screen_key][cell_key][item_name] = \
            self.dropped_items[screen_key][cell_key].get(item_name, 0) + 1
    
    def handle_input(self):
        """Handle keyboard and mouse input"""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
            
            # Mark input for idle detection
            if event.type in [pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN]:
                self.mark_input()
            
            if event.type == pygame.MOUSEBUTTONDOWN and self.state == 'playing':
                if event.button == 1:  # Left click
                    self.handle_inventory_click(event.pos)
                    self.handle_quest_ui_click(event.pos)
            
            if event.type == pygame.KEYDOWN:
                if self.state == 'menu':
                    if event.key == pygame.K_1:
                        self.new_game()
                    elif event.key == pygame.K_2:
                        self.load_game()
                    elif event.key == pygame.K_q:
                        self.running = False
                
                elif self.state == 'playing':
                    if event.key == pygame.K_ESCAPE:
                        self.state = 'paused'
                    elif event.key == pygame.K_SPACE:
                        self.interact()
                    elif event.key == pygame.K_l:
                        # Cast star spell
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
                        self.inventory.toggle_menu('crafting')
                    elif event.key == pygame.K_x:
                        # Attempt to craft with selected items
                        self.attempt_craft()
                    elif event.key == pygame.K_i:
                        self.inventory.toggle_menu('items')
                    elif event.key == pygame.K_t:
                        self.inventory.toggle_menu('tools')
                    elif event.key == pygame.K_m:
                        self.inventory.toggle_menu('magic')
                    elif event.key == pygame.K_f:
                        self.inventory.toggle_menu('followers')
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
                        # Toggle quest UI
                        self.quest_ui_open = not self.quest_ui_open
                    elif event.key == pygame.K_d:
                        # Drop selected item
                        self.drop_selected_item()
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
            
            # Close inventory when moving
            if moved and len(self.inventory.open_menus) > 0:
                self.inventory.close_all_menus()
    
    def handle_inventory_click(self, pos):
        """Handle clicking on inventory items"""
        if not self.inventory.open_menus:
            return
        
        # Calculate inventory position (bottom left)
        slot_size = CELL_SIZE
        start_x = 10
        start_y = SCREEN_HEIGHT - 70  # Above UI bar
        
        # Stack categories vertically from bottom
        categories = ['tools', 'items', 'magic', 'followers', 'crafting']
        y_offset = 0
        
        for category in categories:
            if category not in self.inventory.open_menus:
                continue
            
            # Special handling for crafting screen
            if category == 'crafting':
                items = self.inventory.get_all_craftable_items()
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
                    self.inventory.selected[category] = item_name
                    return
            
            y_offset += slot_size + 15  # Stack next category above
    
    def handle_quest_ui_click(self, pos):
        """Handle clicking on quest UI to select active quest"""
        if not self.quest_ui_open:
            return
        
        slot_size = CELL_SIZE
        start_x = 10
        
        # Calculate starting y position (above inventory panels)
        base_y = SCREEN_HEIGHT - 70
        y_offset = 0
        if self.inventory.open_menus:
            categories = ['tools', 'items', 'magic', 'followers', 'crafting']
            for category in categories:
                if category in self.inventory.open_menus:
                    items = self.inventory.get_all_craftable_items() if category == 'crafting' else self.inventory.get_item_list(category)
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
                print(f"Active quest: {QUEST_TYPES[quest_type]['name']}")
                return

    def pickup_cell_or_items(self):
        """Pick up cell EXACTLY as it is (creative/admin mode) or dropped items.
        Inside structures: cannot pick up base floor cells (except in mines).
        Picking up placed items inside structures restores the structure floor."""
        target = self.get_target_cell()
        if not target:
            return
        
        target_x, target_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        in_subscreen = self.player.get('in_subscreen', False)
        subscreen_key = self.player.get('subscreen_key')
        
        # Determine the correct screen key for subscreens
        if in_subscreen and subscreen_key:
            screen_key = subscreen_key
        
        # Check if cell is enchanted - cannot pick up enchanted cells
        if self.is_cell_enchanted(target_x, target_y, screen_key):
            cell_type = self.current_screen['grid'][target_y][target_x]
            if cell_type == 'WATER':
                print("Drank from enchanted water!")
                return
            print("Cannot pick up enchanted cell!")
            return
        
        # First try to pick up dropped items from ground
        if screen_key in self.dropped_items:
            cell_key = (target_x, target_y)
            if cell_key in self.dropped_items[screen_key]:
                for item_name, count in self.dropped_items[screen_key][cell_key].items():
                    self.inventory.add_item(item_name, count)
                del self.dropped_items[screen_key][cell_key]
                return
        
        # Pick up the cell EXACTLY as it is
        cell_type = self.current_screen['grid'][target_y][target_x]
        
        # Determine structure floor type (what to restore when picking up)
        structure_floor = None
        is_mine = False
        if in_subscreen and subscreen_key:
            subscreen = self.subscreens.get(subscreen_key)
            if subscreen:
                stype = subscreen.get('type', '')
                if stype == 'HOUSE_INTERIOR':
                    structure_floor = 'FLOOR_WOOD'
                elif stype == 'CAVE':
                    structure_floor = 'CAVE_FLOOR'
                    is_mine = True  # Caves/mines allow base cell pickup
        
        # Inside structures (non-mine): block pickup of base floor/wall cells
        if structure_floor and not is_mine:
            blocked_cells = {'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'WALL',
                             'STAIRS_UP', 'STAIRS_DOWN'}
            if cell_type in blocked_cells:
                print("Cannot pick up structural elements!")
                return
        
        # Create direct cell-to-item mapping for exact pickup
        exact_pickup_map = {
            'GRASS': 'grass', 'DIRT': 'dirt', 'SOIL': 'soil', 'SAND': 'sand',
            'WATER': 'water_bucket', 'DEEP_WATER': 'deep_water_bucket',
            'STONE': 'stone', 'TREE1': 'tree1', 'TREE2': 'tree2',
            'WALL': 'wall', 'HOUSE': 'house', 'CAVE': 'cave',
            'MINESHAFT': 'mineshaft', 'CAMP': 'camp', 'CHEST': 'chest',
            'CARROT1': 'carrot1', 'CARROT2': 'carrot2', 'CARROT3': 'carrot3',
            'FLOWER': 'flower', 'WOOD': 'wood', 'PLANKS': 'planks',
            'MEAT': 'meat', 'FUR': 'fur', 'BONES': 'bones'
        }
        
        if cell_type in exact_pickup_map:
            item_name = exact_pickup_map[cell_type]
            self.inventory.add_item(item_name, 1)
            
            # Replace cell: inside structures → restore structure floor, else biome base
            base = self.get_biome_base_cell()
            if structure_floor:
                self.current_screen['grid'][target_y][target_x] = structure_floor
            elif cell_type in ['CARROT1', 'CARROT2', 'CARROT3']:
                self.current_screen['grid'][target_y][target_x] = 'SOIL'
            else:
                self.current_screen['grid'][target_y][target_x] = base
    
    def place_selected_item(self):
        """Place selected item as a cell in the world, or as an overlay if no cell mapping.
        Inside structures, non-structural items are always placed as overlays
        to preserve the structure floor."""
        target = self.get_target_cell()
        if not target:
            return
        
        target_x, target_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        in_subscreen = self.player.get('in_subscreen', False)
        
        # Cannot place on enchanted cells
        if self.is_cell_enchanted(target_x, target_y, screen_key):
            print("Cannot place on enchanted cell!")
            return
        
        # Structural items that replace grid cells even inside structures
        structural_items = {'wall', 'house', 'cave', 'mineshaft', 'chest'}
        
        # Find which category has an item selected
        for category in ['items', 'tools', 'magic', 'followers']:
            selected = self.inventory.get_selected_item(category)
            if selected:
                if not self.inventory.has_item(selected):
                    continue
                
                # Inside structures: non-structural items always go as overlays
                if in_subscreen and selected not in structural_items and selected in ITEM_TO_CELL:
                    self.inventory.remove_item(selected, 1)
                    if in_subscreen and self.player.get('subscreen_key'):
                        sk = self.player['subscreen_key']
                    else:
                        sk = screen_key
                    if sk not in self.dropped_items:
                        self.dropped_items[sk] = {}
                    cell_key = (target_x, target_y)
                    if cell_key not in self.dropped_items[sk]:
                        self.dropped_items[sk][cell_key] = {}
                    self.dropped_items[sk][cell_key][selected] = \
                        self.dropped_items[sk][cell_key].get(selected, 0) + 1
                    return
                elif selected in ITEM_TO_CELL:
                    # Overworld: place as a grid cell (replaces the cell)
                    cell_type = ITEM_TO_CELL[selected]
                    self.current_screen['grid'][target_y][target_x] = cell_type
                    self.inventory.remove_item(selected, 1)
                    return
                else:
                    # No cell mapping — place as overlay
                    self.inventory.remove_item(selected, 1)
                    self.drop_item(selected, target_x, target_y)
                    return
    
    def drop_selected_item(self):
        """Drop currently selected item"""
        target = self.get_target_cell()
        if not target:
            return
        
        # Find which category has an item selected
        for category in ['items', 'tools', 'magic', 'followers']:
            selected = self.inventory.get_selected_item(category)
            if selected:
                if self.inventory.remove_item(selected, 1):
                    self.drop_item(selected, target[0], target[1])
                break
    
    def select_inventory_slot(self, slot_index):
        """Select an inventory slot by number (0-9)"""
        # Find first open menu and select that slot
        for category in ['tools', 'items', 'magic', 'followers']:
            if category in self.inventory.open_menus:
                items = self.inventory.get_item_list(category)
                if slot_index < len(items):
                    self.inventory.selected[category] = items[slot_index][0]
                break
    
    def try_craft(self, item1, item2):
        """Try to craft two items together"""
        recipe_key = tuple(sorted([item1, item2]))
        
        if recipe_key in RECIPES:
            recipe = RECIPES[recipe_key]
            
            # Check if we have required items
            can_craft = True
            for item, amount in recipe['consumes'].items():
                if not self.inventory.has_item(item, amount):
                    can_craft = False
                    break
            
            if can_craft:
                # Consume items
                for item, amount in recipe['consumes'].items():
                    self.inventory.remove_item(item, amount)
                
                # Produce result
                self.inventory.add_item(recipe['result'], recipe['produces'])
    
    def move_player(self):
        """Handle player movement"""
        if self.state != 'playing' or self.inventory.open_menus:
            return
        
        keys = pygame.key.get_pressed()
        
        # Check for autopilot every tick (has its own cooldown)
        any_movement_key = (keys[pygame.K_UP] or keys[pygame.K_w] or
                           keys[pygame.K_DOWN] or keys[pygame.K_s] or
                           keys[pygame.K_LEFT] or keys[pygame.K_a] or
                           keys[pygame.K_RIGHT] or keys[pygame.K_d])
        
        if not any_movement_key:
            if self.is_autopilot_idle():
                # If in a subscreen, navigate toward the exit instead of autopiloting
                if self.player.get('in_subscreen'):
                    subscreen = self.subscreens.get(self.player.get('subscreen_key'))
                    if subscreen:
                        exit_pos = subscreen.get('exit', subscreen.get('entrance'))
                        if exit_pos:
                            px, py = self.player['x'], self.player['y']
                            ex, ey = exit_pos
                            # If at exit, leave
                            if px == ex and py == ey:
                                self.exit_subscreen()
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
                if not self.autopilot:
                    self.autopilot = True
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
        
        # Check if in subscreen and trying to exit through doorway
        if self.player.get('in_subscreen'):
            current_subscreen = self.subscreens.get(self.player['subscreen_key'])
            # Exit when walking out the bottom (doorway area)
            # Only for houses or cave depth 1 (deeper caves use STAIRS_UP)
            if current_subscreen:
                is_depth_1 = current_subscreen.get('depth', 1) == 1
                if is_depth_1 and new_y >= GRID_HEIGHT - 1:
                    self.exit_subscreen()
                    return
        
        # Normal screen transitions for overworld
        # Exits are only open at the center corridor (±1 of center edge).
        # Require player to be inside that corridor before allowing transition,
        # matching the NPC zone transition requirement in try_entity_zone_transition.
        if not self.player.get('in_subscreen'):
            center_x = GRID_WIDTH // 2
            center_y = GRID_HEIGHT // 2
            if new_y < 0 and self.current_screen['exits']['top'] and abs(new_x - center_x) <= 1:
                new_screen_y -= 1
                new_y = GRID_HEIGHT - 2
                screen_changed = True
            elif new_y >= GRID_HEIGHT and self.current_screen['exits']['bottom'] and abs(new_x - center_x) <= 1:
                new_screen_y += 1
                new_y = 1
                screen_changed = True
            elif new_x < 0 and self.current_screen['exits']['left'] and abs(new_y - center_y) <= 1:
                new_screen_x -= 1
                new_x = GRID_WIDTH - 2
                screen_changed = True
            elif new_x >= GRID_WIDTH and self.current_screen['exits']['right'] and abs(new_y - center_y) <= 1:
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
                self.player['x'] = new_x
                self.player['y'] = new_y
                self.player['screen_x'] = new_screen_x
                self.player['screen_y'] = new_screen_y
                self.player['is_moving'] = True

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

    def player_attack(self):
        """Player attacks with equipped weapon (SPACE when weapon selected)"""
        # Check if weapon selected in tools
        weapon = self.inventory.selected_tool
        if not weapon or 'damage' not in ITEMS.get(weapon, {}):
            return False  # No weapon equipped
        
        # Attack cooldown (1 second)
        if self.tick - self.player.get('last_attack_tick', 0) < 60:
            return False
        
        self.player['last_attack_tick'] = self.tick
        
        # Get target cell
        target = self.get_target_cell()
        if not target:
            return False
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Get correct entity list based on subscreen state
        if self.player.get('in_subscreen'):
            subscreen_key = self.player.get('subscreen_key')
            entities_list = self.subscreen_entities.get(subscreen_key, []) if subscreen_key else []
        else:
            entities_list = self.screen_entities.get(screen_key, [])
        
        # Check for entity at target
        for entity_id in entities_list:
            if entity_id in self.entities:
                entity = self.entities[entity_id]
                if entity.x == check_x and entity.y == check_y:
                        # Friendly-fire guard: peaceful entities are protected when FF is OFF
                        if not self.player.get('friendly_fire', False):
                            if not entity.props.get('hostile', False):
                                print(f"[FF blocked] {entity.type} is peaceful — press V to enable friendly fire")
                                return False
                        # Calculate damage
                        weapon_damage = ITEMS[weapon].get('damage', 0)
                        total_damage = self.player['base_damage'] + weapon_damage
                        
                        # Add magic damage from runestones
                        runestone_types = ['lightning_rune', 'fire_rune', 'ice_rune', 'poison_rune', 'shadow_rune']
                        magic_damage = 0
                        magic_type = None
                        for rune_type in runestone_types:
                            if rune_type in self.inventory.items:
                                rune_count = self.inventory.items[rune_type]
                                magic_damage += rune_count * ITEMS[rune_type].get('damage', 3)
                                if not magic_type:  # Use first rune type for animation color
                                    magic_type = ITEMS[rune_type].get('magic_damage')
                        
                        total_damage += magic_damage
                        
                        # Apply blocking reduction
                        if entity.combat_state == 'blocking':
                            total_damage *= (1 - entity.block_reduction)
                        
                        entity.take_damage(total_damage, 'player')
                        
                        # Show attack animation (with magic color if applicable)
                        self.show_attack_animation(check_x, check_y, target_entity=entity, magic_type=magic_type)
                        
                        if magic_damage > 0:
                            print(f"Hit {entity.type} for {int(total_damage)} damage ({int(magic_damage)} magic)! HP: {int(entity.health)}/{entity.max_health}")
                        else:
                            print(f"Hit {entity.type} for {int(total_damage)} damage! HP: {int(entity.health)}/{entity.max_health}")
                        return True
        
        return False

    def player_take_damage(self, damage):
        """Player takes damage with blocking reduction"""
        # Don't take damage if already dead
        if self.state == 'death':
            return
        
        if self.player['blocking']:
            damage *= 0.1  # 90% reduction when blocking
        
        self.player['health'] -= damage
        print(f"Player took {int(damage)} damage! Health: {int(self.player['health'])}/{self.player['max_health']}")
        
        if self.player['health'] <= 0 and self.state != 'death':
            self.player_death()
    
    def gain_xp(self, amount):
        """Award XP to player and handle leveling up"""
        self.player['xp'] += amount
        
        # Check for level up
        while self.player['xp'] >= self.player['xp_to_level']:
            self.player['xp'] -= self.player['xp_to_level']
            self.player['level'] += 1
            
            # Increase stats on level up
            self.player['max_health'] += 10
            self.player['health'] = self.player['max_health']  # Full heal
            self.player['base_damage'] += 2
            self.player['max_magic_pool'] += 2
            self.player['magic_pool'] = self.player['max_magic_pool']  # Full restore
            
            # Increase XP required for next level
            self.player['xp_to_level'] = int(self.player['xp_to_level'] * 1.5)
            
            print(f"LEVEL UP! Now level {self.player['level']}")

    def player_death(self):
        """Handle player death - time passage and respawn"""
        print("You died!")
        self.state = 'death'
        
        # Random years to pass (100-200, reduced from 100-1000)
        years_passed = random.randint(100, 200)
        self.death_years = years_passed
        self.death_start_tick = self.tick
        self.death_ticks_simulated = 0
        
        # Drop all items at death location
        death_screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        death_pos = (self.player['x'], self.player['y'])
        
        if death_screen_key not in self.dropped_items:
            self.dropped_items[death_screen_key] = {}
        if death_pos not in self.dropped_items[death_screen_key]:
            self.dropped_items[death_screen_key][death_pos] = {}
        
        # Drop all inventory items (except magic - spells are permanent)
        for category in ['items', 'tools']:
            inv = getattr(self.inventory, category)
            for item_name, count in list(inv.items()):
                self.dropped_items[death_screen_key][death_pos][item_name] = \
                    self.dropped_items[death_screen_key][death_pos].get(item_name, 0) + count
            inv.clear()
        
        # Clear inventory selections (but keep magic)
        for cat in ['items', 'tools']:
            if cat in self.inventory.selected:
                self.inventory.selected[cat] = None

    def update_death_screen(self):
        """Update during death - accelerated time passage"""
        ticks_to_simulate = self.death_years * 10  # 10 ticks per "year"
        cycles_per_frame = 5  # Reduced from 10
        
        if self.death_ticks_simulated < ticks_to_simulate:
            # Minimal updates for performance
            for _ in range(cycles_per_frame):
                # Age all entities (10 ticks = 1 year)
                if self.death_ticks_simulated % 10 == 0:  # Every simulated year
                    current_year = self.death_ticks_simulated // 10
                    
                    entities_to_remove = []
                    for entity_id, entity in list(self.entities.items()):
                        # Age entity (no longer manually apply old age damage here - handled by decay_stats)
                        if entity.type != 'SKELETON':
                            entity.age += 1
                        
                        # Don't manually decay hunger/thirst - let catch_up and entity AI handle it
                        # Entities will eat/drink naturally through behavior updates below
                    
                    # Remove dead entities
                    for entity_id in entities_to_remove:
                        self.remove_entity(entity_id)
                    
                    # Spawn new NPCs more frequently (every 10 years instead of 30)
                    if current_year > 0 and current_year % 10 == 0:
                        # Spawn in more zones (5 instead of 3)
                        zones_to_spawn = random.sample(list(self.instantiated_zones), 
                                                      min(5, len(self.instantiated_zones)))
                        
                        for zone_key in zones_to_spawn:
                            parts = zone_key.split(',')
                            zone_x = int(parts[0])
                            zone_y = int(parts[1])
                            
                            # Spawn entities for this zone
                            if zone_key in self.screens:
                                biome = self.screens[zone_key].get('biome', 'FOREST')
                                self.spawn_entities_for_screen(zone_x, zone_y, biome)
                        
                        print(f"Year {current_year}: New NPCs spawned in {len(zones_to_spawn)} zones")
                
                # Update zones per cycle with entity AI actions
                # During initial generation, update MORE zones and MORE frequently for world building
                if hasattr(self, 'is_initial_generation') and self.is_initial_generation:
                    zones_to_update = random.sample(list(self.instantiated_zones), 
                                                   min(8, len(self.instantiated_zones)))  # 8 zones
                    update_chance = 0.5  # 100% chance to update
                    catchup_cycles = 5  # More cycles for building
                    behavior_chance = 0.5  # 80% behavior chance - NPCs actively build/farm/mine
                else:
                    zones_to_update = random.sample(list(self.instantiated_zones), 
                                                   min(8, len(self.instantiated_zones)))  # 8 zones
                    update_chance = 0.8  # 80% chance
                    catchup_cycles = 5  # More cycles
                    behavior_chance = 0.3  # 30% behavior chance
                
                for zone_key in zones_to_update:
                    parts = zone_key.split(',')
                    zone_x = int(parts[0])
                    zone_y = int(parts[1])
                    
                    if random.random() < update_chance:
                        # Use catch_up with configured cycles for cell updates
                        self.catch_up_screen(zone_x, zone_y, catchup_cycles)
                        
                        # CRITICAL: Also run full zone update for farming, building, spawning
                        # This is what creates the world structures
                        self.update_zone_with_coverage(zone_x, zone_y, 1.0, 1.0)
                        
                        # Additionally update entity behaviors in this zone
                        if zone_key in self.screen_entities:
                            for entity_id in list(self.screen_entities[zone_key]):
                                if entity_id in self.entities:
                                    entity = self.entities[entity_id]
                                    
                                    # Run special behaviors during time passage
                                    behavior_config = entity.props.get('behavior_config')
                                    if behavior_config and random.random() < behavior_chance:
                                        self.execute_entity_behavior(entity, behavior_config)
                
                self.tick += 1
                self.death_ticks_simulated += 1
                
                if self.death_ticks_simulated >= ticks_to_simulate:
                    break
        else:
            # Respawn player
            self.respawn_player()

    def respawn_player(self):
        """Respawn player in same zone at a random safe location"""
        # Clear initial generation flag if it exists
        if hasattr(self, 'is_initial_generation'):
            self.is_initial_generation = False
        
        # Stay in same zone, find a safe spawn point
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Try to find a safe spawn location in current zone
        found_safe_spot = False
        for attempt in range(100):  # Try 100 random positions
            test_x = random.randint(1, GRID_WIDTH - 2)
            test_y = random.randint(1, GRID_HEIGHT - 2)
            
            if screen_key in self.screens:
                cell = self.screens[screen_key]['grid'][test_y][test_x]
                # Check if cell is walkable (not solid, not water)
                if not CELL_TYPES[cell].get('solid', False) and cell not in ['WATER', 'DEEP_WATER']:
                    self.player['x'] = test_x
                    self.player['y'] = test_y
                    found_safe_spot = True
                    break
        
        # If no safe spot found, just spawn in center
        if not found_safe_spot:
            self.player['x'] = GRID_WIDTH // 2
            self.player['y'] = GRID_HEIGHT // 2
        
        # Reset player stats
        self.player['health'] = self.player['max_health']
        self.player['blocking'] = False
        
        # Reset all quests - clear old targets and cooldowns
        for quest in self.quests.values():
            quest.clear_target()
            quest.status = 'inactive'
            quest.cooldown_remaining = 0
        
        # Regenerate current screen to reflect time passage
        self.current_screen = self.generate_screen(self.player['screen_x'], self.player['screen_y'])
        
        # Respawn skeleton follower for testing
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        skeleton = Entity('SKELETON', self.player['x'] + 1, self.player['y'], 
                         self.player['screen_x'], self.player['screen_y'], level=1)
        skeleton_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[skeleton_id] = skeleton
        
        # Add to screen entities
        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(skeleton_id)
        
        # Add to followers
        self.followers.append(skeleton_id)
        
        # Add to inventory as follower item (use existing skeleton_bones item)
        self.inventory.add_follower('skeleton_bones', 1)
        
        print(f"Skeleton follower respawned (ID: {skeleton_id})")
        
        self.state = 'playing'
        # Autopilot grace period: don't engage for 15 seconds after entering game
        self.last_input_tick = self.tick + 900
        
        # Force immediate quest update to find new targets
        print("Quests reset - seeking new targets...")
        for quest_type, quest in self.quests.items():
            if quest.status == 'inactive':
                success = self.loreEngine(quest)
                if success:
                    print(f"  {quest_type}: Target assigned")
                else:
                    print(f"  {quest_type}: No target found yet")
        
        print(f"{self.death_years} years have passed...")
        print("You awaken where you fell. Your items are scattered nearby.")

    def draw_death_screen(self):
        """Draw death screen with years passing"""
        self.screen.fill(COLORS['BLACK'])
        
        years_passed = self.death_ticks_simulated // 10
        years_text = f"{years_passed} / {self.death_years} YEARS PASSING..."
        text = self.font.render(years_text, True, (100, 100, 100))
        text_rect = text.get_rect(center=(SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2))
        self.screen.blit(text, text_rect)

    def show_attack_animation(self, x, y, entity=None, target_entity=None, magic_type=None):
        """Show attack animation at target location (colored for magic)
        
        Args:
            x, y: Grid coordinates (fallback)
            entity: Attacking entity (for location tracking)
            target_entity: Target entity (for accurate world position)
            magic_type: Type of magic damage for color
        """
        # Use target_entity's world position if available for accurate placement
        if target_entity and hasattr(target_entity, 'world_x'):
            display_x = target_entity.world_x
            display_y = target_entity.world_y
        else:
            # Fallback to grid coordinates
            display_x = float(x)
            display_y = float(y)
        
        # Track which screen/subscreen this animation belongs to
        if entity:
            location_key = entity.screen_key
        elif self.player.get('in_subscreen'):
            location_key = self.player.get('subscreen_key')
        else:
            location_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        self.attack_animations.append({
            'x': display_x,  # Now using world coordinates
            'y': display_y,
            'start_tick': self.tick,
            'duration': 10,
            'location_key': location_key,
            'magic_type': magic_type
        })
    
    def draw_attack_animations(self):
        """Draw active attack animations only for current location"""
        # Determine current location
        if self.player.get('in_subscreen'):
            current_location = self.player.get('subscreen_key')
        else:
            current_location = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Magic type color mapping
        magic_colors = {
            'lightning': (100, 149, 237),  # Cornflower blue
            'fire': (255, 69, 0),          # Red-orange
            'ice': (173, 216, 230),        # Light blue
            'poison': (50, 205, 50),       # Lime green
            'shadow': (75, 0, 130)         # Indigo
        }
        
        for anim in self.attack_animations[:]:
            if self.tick - anim['start_tick'] > anim['duration']:
                self.attack_animations.remove(anim)
                continue
            
            # Only draw animations for current location
            if anim.get('location_key') != current_location:
                continue
            
            # Determine color (white for physical, colored for magic)
            if anim.get('magic_type') and anim['magic_type'] in magic_colors:
                color = magic_colors[anim['magic_type']]
            else:
                color = COLORS['WHITE']
            
            # Draw swipe lines
            x_pos = anim['x'] * CELL_SIZE
            y_pos = anim['y'] * CELL_SIZE
            
            # Draw diagonal swipe lines
            pygame.draw.line(self.screen, color, 
                            (x_pos + 5, y_pos + 10), (x_pos + 35, y_pos + 30), 3)
            pygame.draw.line(self.screen, color,
                            (x_pos + 10, y_pos + 5), (x_pos + 30, y_pos + 35), 3)

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
        
        # Check for subscreen exit (STAIRS_UP)
        if cell == 'STAIRS_UP':
            # Check if in a deep cave level
            if self.player.get('in_subscreen'):
                current_subscreen = self.subscreens.get(self.player['subscreen_key'])
                if current_subscreen and current_subscreen['type'] == 'CAVE' and current_subscreen['depth'] > 1:
                    # Ascend to previous cave level
                    self.ascend_cave()
                    return
            # Otherwise, exit subscreen completely
            self.exit_subscreen()
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
            self.enter_subscreen(check_x, check_y)
            return
        
        # Chop tree - drops wood
        if cell.startswith('TREE') and self.inventory.has_item('axe'):
            self.handle_drops(cell, check_x, check_y)
            return
        
        # Mine stone - drops stone items
        if cell == 'STONE' and self.inventory.has_item('pickaxe'):
            self.inventory.add_item('stone', 1)
            self.current_screen['grid'][check_y][check_x] = 'DIRT'
            self.show_attack_animation(check_x, check_y)
            return
        
        # Dig mineshaft — pickaxe on soft ground cells (overworld or inside caves)
        # This creates a mineshaft entrance leading to a cave system
        minable_ground = {'DIRT', 'SAND', 'GRASS', 'CAVE_FLOOR'}
        if cell in minable_ground and self.inventory.has_item('pickaxe'):
            depth = 1
            in_cave = False
            if self.player.get('in_subscreen'):
                subscreen = self.subscreens.get(self.player.get('subscreen_key'))
                if subscreen and subscreen.get('type') == 'CAVE':
                    depth = subscreen.get('depth', 1)
                    in_cave = True
            
            mineshaft_chance = PLAYER_MINESHAFT_BASE_CHANCE / (MINESHAFT_DEPTH_DIVISOR ** (depth - 1))
            self.show_attack_animation(check_x, check_y)
            
            if random.random() < mineshaft_chance:
                self.current_screen['grid'][check_y][check_x] = 'MINESHAFT'
                
                # Pre-generate the deeper level so it's ready when entered
                if in_cave:
                    print(f"You dug a mineshaft to depth {depth + 1}!")
                else:
                    print(f"You discovered an underground passage!")
            return
        
        # Till dirt with hoe
        if cell == 'DIRT' and self.inventory.has_item('hoe'):
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
        
        # Place bones as decoration on ground cells
        if cell in ['GRASS', 'DIRT', 'SAND', 'STONE', 'FLOOR_WOOD', 'CAVE_FLOOR', 'COBBLESTONE'] and self.inventory.has_item('bones'):
            self.inventory.remove_item('bones', 1)
            
            # Add bones to dropped items (as overlay decoration)
            screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
            if self.player.get('in_subscreen'):
                screen_key = self.player.get('subscreen_key', screen_key)
            
            if screen_key not in self.dropped_items:
                self.dropped_items[screen_key] = {}
            
            cell_key = (check_x, check_y)
            if cell_key not in self.dropped_items[screen_key]:
                self.dropped_items[screen_key][cell_key] = {}
            
            self.dropped_items[screen_key][cell_key]['bones'] = \
                self.dropped_items[screen_key][cell_key].get('bones', 0) + 1
            return
    
    def enter_subscreen(self, cell_x, cell_y):
        """Player enters a house, cave, or mineshaft"""
        cell = self.current_screen['grid'][cell_y][cell_x]
        structure_type = CELL_TYPES[cell].get('subscreen_type')
        
        if not structure_type:
            return
        
        # If entering a MINESHAFT from inside a cave — descend deeper
        if cell == 'MINESHAFT' and self.player.get('in_subscreen'):
            current_subscreen = self.subscreens.get(self.player.get('subscreen_key'))
            if current_subscreen and current_subscreen.get('type') == 'CAVE':
                self.descend_cave()
                return
        
        # Check if subscreen already exists for this location
        parent_screen_x = self.player['screen_x']
        parent_screen_y = self.player['screen_y']
        
        # Look for existing subscreen at this location
        existing_key = None
        for key, subscreen in self.subscreens.items():
            if (subscreen['parent_screen'] == (parent_screen_x, parent_screen_y) and
                subscreen['parent_cell'] == (cell_x, cell_y)):
                existing_key = key
                break
        
        # For CAVE/MINESHAFT, also check zone cave system
        if not existing_key and structure_type == 'CAVE':
            parent_key = f"{parent_screen_x},{parent_screen_y}"
            if parent_key in self.zone_cave_systems:
                existing_key = self.zone_cave_systems[parent_key]
                # Add this entrance to the cave system's entrance list
                subscreen = self.subscreens.get(existing_key)
                if subscreen and (cell_x, cell_y) not in subscreen.get('entrances', []):
                    subscreen.setdefault('entrances', []).append((cell_x, cell_y))
        
        # Generate or retrieve subscreen
        if existing_key:
            subscreen_key = existing_key
        else:
            subscreen_key = self.generate_subscreen(
                parent_screen_x, parent_screen_y, 
                cell_x, cell_y, 
                structure_type, 
                depth=1
            )
        
        # Save player's parent location
        self.player['in_subscreen'] = True
        self.player['subscreen_key'] = subscreen_key
        self.player['subscreen_parent'] = (parent_screen_x, parent_screen_y, cell_x, cell_y)
        
        # Switch to subscreen
        subscreen = self.subscreens[subscreen_key]
        self.current_screen = subscreen
        
        # Position player at entrance
        entrance = subscreen['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        
        print(f"Entered {structure_type}!")
    
    def exit_subscreen(self):
        """Player exits back to parent screen"""
        if not self.player['in_subscreen']:
            return
        
        # Get parent location
        parent_info = self.player['subscreen_parent']
        if not parent_info:
            return
        
        parent_screen_x, parent_screen_y, parent_cell_x, parent_cell_y = parent_info
        
        # Switch back to parent screen
        parent_key = f"{parent_screen_x},{parent_screen_y}"
        if parent_key in self.screens:
            self.current_screen = self.screens[parent_key]
        else:
            self.current_screen = self.generate_screen(parent_screen_x, parent_screen_y)
        
        # Position player outside the structure
        self.player['x'] = parent_cell_x
        self.player['y'] = parent_cell_y
        self.player['screen_x'] = parent_screen_x
        self.player['screen_y'] = parent_screen_y
        
        # Clear subscreen state
        self.player['in_subscreen'] = False
        self.player['subscreen_key'] = None
        self.player['subscreen_parent'] = None
        
        print("Exited to outside!")
    
    def descend_cave(self):
        """Go deeper into a cave"""
        if not self.player['in_subscreen']:
            return
        
        current_subscreen = self.subscreens.get(self.player['subscreen_key'])
        if not current_subscreen or current_subscreen['type'] != 'CAVE':
            return
        
        # Get parent info
        parent_screen_x, parent_screen_y = current_subscreen['parent_screen']
        parent_cell_x, parent_cell_y = current_subscreen['parent_cell']
        new_depth = current_subscreen['depth'] + 1
        
        # Look for existing deeper level first
        deeper_key = None
        for key, subscreen in self.subscreens.items():
            if (subscreen['parent_screen'] == (parent_screen_x, parent_screen_y) and
                subscreen['parent_cell'] == (parent_cell_x, parent_cell_y) and
                subscreen['type'] == 'CAVE' and
                subscreen['depth'] == new_depth):
                deeper_key = key
                break
        
        # If not found, generate new deeper level
        if not deeper_key:
            deeper_key = self.generate_subscreen(
                parent_screen_x, parent_screen_y,
                parent_cell_x, parent_cell_y,
                'CAVE',
                depth=new_depth
            )
        
        # Update player state
        self.player['subscreen_key'] = deeper_key
        deeper_subscreen = self.subscreens[deeper_key]
        self.current_screen = deeper_subscreen
        
        # Position player at entrance
        entrance = deeper_subscreen['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        
        print(f"Descended to cave level {new_depth}!")
        
        # Spawn enemies for this depth
        self.spawn_cave_entities(deeper_key, new_depth)
    
    def ascend_cave(self):
        """Go up one level in a cave"""
        if not self.player['in_subscreen']:
            return
        
        current_subscreen = self.subscreens.get(self.player['subscreen_key'])
        if not current_subscreen or current_subscreen['type'] != 'CAVE':
            return
        
        current_depth = current_subscreen['depth']
        if current_depth <= 1:
            # At level 1, just exit
            self.exit_subscreen()
            return
        
        # Get parent info for generating/finding the level above
        parent_screen_x, parent_screen_y = current_subscreen['parent_screen']
        parent_cell_x, parent_cell_y = current_subscreen['parent_cell']
        target_depth = current_depth - 1
        
        # Find or generate the level above
        # Look for existing subscreen at this depth
        upper_level_key = None
        for key, subscreen in self.subscreens.items():
            if (subscreen['parent_screen'] == (parent_screen_x, parent_screen_y) and
                subscreen['parent_cell'] == (parent_cell_x, parent_cell_y) and
                subscreen['type'] == 'CAVE' and
                subscreen['depth'] == target_depth):
                upper_level_key = key
                break
        
        # If not found, generate it (shouldn't normally happen, but just in case)
        if not upper_level_key:
            upper_level_key = self.generate_subscreen(
                parent_screen_x, parent_screen_y,
                parent_cell_x, parent_cell_y,
                'CAVE',
                depth=target_depth
            )
        
        # Update player state
        self.player['subscreen_key'] = upper_level_key
        upper_subscreen = self.subscreens[upper_level_key]
        self.current_screen = upper_subscreen
        
        # Position player at entrance
        entrance = upper_subscreen['entrance']
        self.player['x'] = entrance[0]
        self.player['y'] = entrance[1]
        
        print(f"Ascended to cave level {target_depth}!")
    
    def spawn_cave_entities(self, subscreen_key, depth):
        """Spawn enemies in cave based on depth"""
        subscreen = self.subscreens[subscreen_key]
        grid = subscreen['grid']
        
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
                
                # Create entity (note: using 0,0 for subscreen coords)
                entity = Entity(enemy_type, x, y, 0, 0, level)
                entity_id = self.next_entity_id
                self.next_entity_id += 1
                self.entities[entity_id] = entity
                
                # Track in subscreen (we'll need special handling for subscreen entities)
                # For now, just add to entities dict
                
                spawned += 1
            
            attempts += 1
    
    def interact_with_chest(self, chest_x, chest_y):
        """Open chest and give loot to player"""
        # Create unique chest identifier
        if self.player['in_subscreen']:
            chest_id = f"{self.player['subscreen_key']}:{chest_x},{chest_y}"
        else:
            screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
            chest_id = f"{screen_key}:{chest_x},{chest_y}"
        
        # Check if already opened
        if chest_id in self.opened_chests:
            print("This chest is empty.")
            return
        
        # Get loot table type
        if self.player['in_subscreen']:
            current_subscreen = self.subscreens.get(self.player['subscreen_key'])
            loot_table_name = current_subscreen['chests'].get((chest_x, chest_y), 'HOUSE_CHEST')
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
    
    def cast_star_spell(self):
        """Cast star spell on target cell or entity (L key)"""
        # Check if player has spell selected
        if not self.inventory.selected_magic or self.inventory.selected_magic != 'star_spell':
            print("Star spell not selected!")
            return
        
        # Check if player has magic available
        if self.player['magic_pool'] <= 0:
            print("No magic available!")
            return
        
        target = self.get_target_cell()
        if not target:
            return
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Check if there's an entity at target
        entity_at_target = None
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.x == check_x and entity.y == check_y:
                        entity_at_target = (entity_id, entity)
                        break
        
        # If entity at target, enchant entity and make it a follower
        if entity_at_target:
            entity_id, entity = entity_at_target
            current_enchant = self.enchanted_entities.get(entity_id, 0)
            self.enchanted_entities[entity_id] = current_enchant + 1
            self.player['magic_pool'] -= 1
            
            # Add to followers list if not already a follower
            if entity_id not in self.followers:
                self.followers.append(entity_id)
                # Add follower item to ITEMS dict dynamically
                follower_name = f"{entity.type.lower()}_{entity_id}"
                if follower_name not in ITEMS:
                    ITEMS[follower_name] = {
                        'color': entity.props['color'],
                        'name': f"{entity.type} Follower",
                        'is_follower': True,
                        'entity_id': entity_id
                    }
                # Add to follower inventory
                self.inventory.add_follower(follower_name, 1)
                print(f"Enchanted {entity.type} - now following you! (enchant level {self.enchanted_entities[entity_id]})")
            else:
                print(f"Increased {entity.type} enchant to level {self.enchanted_entities[entity_id]}")
            return
        
        # Otherwise, enchant cell
        cell = self.current_screen['grid'][check_y][check_x]
        
        # Initialize enchanted_cells for this screen if needed
        if screen_key not in self.enchanted_cells:
            self.enchanted_cells[screen_key] = {}
        
        # Increase enchant level
        current_enchant = self.enchanted_cells[screen_key].get((check_x, check_y), 0)
        self.enchanted_cells[screen_key][(check_x, check_y)] = current_enchant + 1
        
        # Decrease magic pool permanently
        self.player['magic_pool'] -= 1
        
        print(f"Enchanted {cell} at ({check_x}, {check_y}) to level {self.enchanted_cells[screen_key][(check_x, check_y)]}")
    
    def release_enchantments(self):
        """Release enchantment from target cell/entity (K key) - decreases by 1 level"""
        target = self.get_target_cell()
        if not target:
            return
        
        check_x, check_y = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        
        # Check if there's an entity at target
        entity_at_target = None
        if screen_key in self.screen_entities:
            for entity_id in self.screen_entities[screen_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.x == check_x and entity.y == check_y:
                        entity_at_target = entity_id
                        break
        
        # Release entity enchantment if entity is targeted
        if entity_at_target and entity_at_target in self.enchanted_entities:
            enchant_level = self.enchanted_entities[entity_at_target]
            self.enchanted_entities[entity_at_target] -= 1
            
            # Remove from dict if enchant level reaches 0
            if self.enchanted_entities[entity_at_target] <= 0:
                del self.enchanted_entities[entity_at_target]
                print(f"Fully released enchantment from entity {entity_at_target}")
            else:
                print(f"Decreased entity {entity_at_target} enchant to level {self.enchanted_entities[entity_at_target]}")
            
            # Restore 1 magic
            self.player['magic_pool'] = min(
                self.player['magic_pool'] + 1,
                self.player['max_magic_pool']
            )
            return
        
        # Otherwise release cell enchantment
        if screen_key in self.enchanted_cells:
            cell_key = (check_x, check_y)
            if cell_key in self.enchanted_cells[screen_key]:
                enchant_level = self.enchanted_cells[screen_key][cell_key]
                self.enchanted_cells[screen_key][cell_key] -= 1
                
                # Remove from dict if enchant level reaches 0
                if self.enchanted_cells[screen_key][cell_key] <= 0:
                    del self.enchanted_cells[screen_key][cell_key]
                    print(f"Fully released enchantment from cell at ({check_x}, {check_y})")
                else:
                    print(f"Decreased cell ({check_x}, {check_y}) enchant to level {self.enchanted_cells[screen_key][cell_key]}")
                
                # Restore 1 magic
                self.player['magic_pool'] = min(
                    self.player['magic_pool'] + 1,
                    self.player['max_magic_pool']
                )
                return
        
        print("Target is not enchanted!")
    
    def release_follower(self):
        """Release selected follower (J key)"""
        # Check if a follower is selected
        selected_follower = self.inventory.selected_follower
        if not selected_follower:
            print("No follower selected!")
            return
        
        # Extract entity_id from follower name (format: "type_id")
        try:
            entity_id = int(selected_follower.split('_')[-1])
        except (ValueError, IndexError):
            print("Invalid follower selection!")
            return
        
        # Check if entity exists and is a follower
        if entity_id not in self.followers:
            print("Entity is not a follower!")
            return
        
        if entity_id not in self.entities:
            print("Entity no longer exists!")
            return
        
        entity = self.entities[entity_id]
        
        # Remove from followers list
        self.followers.remove(entity_id)
        
        # Remove from follower inventory
        self.inventory.remove_item(selected_follower, 1)
        
        # Remove enchantment
        if entity_id in self.enchanted_entities:
            magic_restored = self.enchanted_entities[entity_id]
            del self.enchanted_entities[entity_id]
            
            # Restore magic
            self.player['magic_pool'] = min(
                self.player['magic_pool'] + magic_restored,
                self.player['max_magic_pool']
            )
            
            print(f"Released {entity.type} follower! Restored {magic_restored} magic.")
        else:
            print(f"Released {entity.type} follower!")
    
    def attempt_craft(self):
        """Attempt to craft items using selections from any menu + crafting screen (X key)"""
        # Need something selected in crafting screen
        crafting_item = self.inventory.selected_crafting
        if not crafting_item:
            print("Select an item in crafting screen (C) first!")
            return
        
        # Find what's selected in other menus (items, tools, or magic)
        other_item = None
        other_category = None
        for category in ['items', 'tools', 'magic']:
            selected = self.inventory.selected.get(category)
            if selected:
                other_item = selected
                other_category = category
                break
        
        if not other_item:
            print("Select an item from Items (I), Tools (T), or Magic (M) menu!")
            return
        
        # Check both orderings of the recipe
        recipe1 = (crafting_item, other_item)
        recipe2 = (other_item, crafting_item)
        
        result = None
        if recipe1 in RECIPES:
            result = RECIPES[recipe1]
        elif recipe2 in RECIPES:
            result = RECIPES[recipe2]
        
        if not result:
            print(f"No recipe for {crafting_item} + {other_item}")
            return
        
        # Check if we have both items
        if not self.inventory.has_item(crafting_item):
            print(f"Don't have {crafting_item}!")
            return
        if not self.inventory.has_item(other_item):
            print(f"Don't have {other_item}!")
            return
        
        # Craft the item!
        # Remove ingredients
        self.inventory.remove_item(crafting_item, 1)
        self.inventory.remove_item(other_item, 1)
        
        # Special case: skeleton_bones spawns a skeleton follower immediately
        if result == 'skeleton_bones':
            skeleton_id = self.spawn_skeleton(self.player['x'], self.player['y'])
            if skeleton_id:
                # Add to followers list
                self.followers.append(skeleton_id)
                # Enchant it (level 1)
                self.enchanted_entities[skeleton_id] = 1
                # Add to follower inventory
                follower_name = f"skeleton_{skeleton_id}"
                skeleton = self.entities[skeleton_id]
                if follower_name not in ITEMS:
                    ITEMS[follower_name] = {
                        'color': skeleton.props['color'],
                        'name': 'Skeleton Follower',
                        'is_follower': True,
                        'entity_id': skeleton_id
                    }
                self.inventory.add_follower(follower_name, 1)
                print(f"Skeleton summoned and bound to your will!")
        else:
            # Normal crafting - add result to appropriate inventory
            self.inventory.add_item(result, 1)
            print(f"Crafted {ITEMS[result]['name']}!")
        
        # Update selections after crafting
        # If crafting_item was depleted, select the newly crafted item in crafting screen
        if not self.inventory.has_item(crafting_item):
            # Crafting item is gone, select the result in crafting screen
            self.inventory.selected['crafting'] = result
        # If crafting_item still exists (had multiple), keep it selected
        
        # Update the other category selection
        if not self.inventory.has_item(other_item):
            # Other item is gone, try to select the result if it's in that category
            # Otherwise select the next available item in that category
            category_inv = getattr(self.inventory, other_category)
            if result in category_inv:
                self.inventory.selected[other_category] = result
            else:
                # Select first available item in that category
                if category_inv:
                    self.inventory.selected[other_category] = list(category_inv.keys())[0]
                else:
                    self.inventory.selected[other_category] = None
        # If other_item still exists, keep it selected
    
    def is_cell_enchanted(self, x, y, screen_key):
        """Check if a cell is enchanted"""
        if screen_key not in self.enchanted_cells:
            return False
        return (x, y) in self.enchanted_cells[screen_key]
    
    def is_entity_enchanted(self, entity_id):
        """Check if an entity is enchanted"""
        return entity_id in self.enchanted_entities
    
    def new_game(self):
        """Start a new game"""
        self.player = {
            'x': 12, 'y': 9, 
            'screen_x': 0, 'screen_y': 0,
            'level': 1,
            'xp': 0,
            'xp_to_level': 100,
            'magic_pool': 10,
            'max_magic_pool': 10,
            'health': 100,
            'max_health': 100,
            'base_damage': 10,
            'blocking': False,
            'friendly_fire': False,      # OFF = cannot damage peaceful entities
            'last_attack_tick': 0,
            'in_subscreen': False,
            'subscreen_key': None,
            'subscreen_parent': None,
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
        self.inventory.add_item('bone_sword', 1)
        self.inventory.add_item('carrot', 5)
        self.inventory.add_item('tree_sapling', 3)
        self.inventory.add_item('magic_rune', 1)  # Testing sprite overlay
        self.dropped_items = {}
        self.enchanted_cells = {}
        self.enchanted_entities = {}
        self.followers = []
        self.subscreens = {}
        self.opened_chests = set()
        self.next_subscreen_id = 0
        self.entities = {}
        self.next_entity_id = 0
        self.screen_entities = {}
        self.attack_animations = []
        self.current_screen = self.generate_screen(0, 0)
        
        # Spawn skeleton follower for testing
        skeleton = Entity('SKELETON', self.player['x'] + 1, self.player['y'], 0, 0, level=1)
        skeleton_id = self.next_entity_id
        self.next_entity_id += 1
        self.entities[skeleton_id] = skeleton
        
        # Add to screen entities
        screen_key = "0,0"
        if screen_key not in self.screen_entities:
            self.screen_entities[screen_key] = []
        self.screen_entities[screen_key].append(skeleton_id)
        
        # Add to followers
        self.followers.append(skeleton_id)
        
        # Add to inventory as follower item (use existing skeleton_bones item)
        self.inventory.add_follower('skeleton_bones', 1)
        
        print(f"Skeleton follower spawned for testing (ID: {skeleton_id})")
        
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
    
    def draw_menu(self):
        """Draw main menu"""
        self.screen.fill(COLORS['BLACK'])
        
        title = self.font.render("PROCEDURAL ADVENTURE", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 100))
        
        options = [
            "1 - New Game",
            "2 - Continue",
            "Q - Quit",
            "",
            "Controls:",
            "WASD/Arrows - Move",
            "Space - Interact (chop/till/harvest/plant)",
            "E - Pick up items",
            "Q - Drop selected item",
            "I - Items inventory",
            "T - Tools inventory",
            "Click items to select/craft",
            "ESC - Pause"
        ]
        
        y = 180
        for option in options:
            text = self.small_font.render(option, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 25
    
    def draw_inventory_panels(self):
        """Draw inventory panels at bottom left"""
        if not self.inventory.open_menus:
            return
        
        slot_size = CELL_SIZE
        start_x = 10
        start_y = SCREEN_HEIGHT - 70  # Above UI bar
        
        # Stack categories vertically from bottom
        categories = ['tools', 'items', 'magic', 'followers', 'crafting']
        category_colors = {
            'tools': (100, 100, 120),
            'items': (80, 120, 80),
            'magic': (120, 80, 120),
            'followers': (120, 100, 80),
            'crafting': (180, 140, 60)  # Gold color for crafting
        }
        
        y_offset = 0
        
        for category in categories:
            if category not in self.inventory.open_menus:
                continue
            
            # Special handling for crafting screen - shows all items+tools+magic
            if category == 'crafting':
                items = self.inventory.get_all_craftable_items()
            else:
                items = self.inventory.get_item_list(category)
            
            if not items:
                # Show empty category label
                label_text = self.small_font.render(f"{category.upper()} (empty)", True, COLORS['GRAY'])
                self.screen.blit(label_text, (start_x, start_y - y_offset - 15))
                y_offset += 25
                continue
            
            # Category label
            label_text = self.small_font.render(category.upper(), True, category_colors[category])
            self.screen.blit(label_text, (start_x, start_y - y_offset - 15))
            
            # Draw items horizontally
            for i, (item_name, count) in enumerate(items):
                slot_x = start_x + i * (slot_size + 2)
                slot_y = start_y - y_offset
                
                # Background
                pygame.draw.rect(self.screen, COLORS['BLACK'],
                               (slot_x, slot_y, slot_size, slot_size))
                
                # Selected highlight
                if self.inventory.selected[category] == item_name:
                    pygame.draw.rect(self.screen, COLORS['INV_SELECT'],
                                   (slot_x, slot_y, slot_size, slot_size), 3)
                else:
                    pygame.draw.rect(self.screen, COLORS['INV_BORDER'],
                                   (slot_x, slot_y, slot_size, slot_size), 1)
                
                # Item sprite or color
                has_sprite = (self.use_sprites and 
                             hasattr(self, 'sprite_manager') and 
                             item_name in self.sprite_manager.sprites)
                
                # Also try uppercase version for sprites (TREE1 vs tree1)
                if not has_sprite and self.use_sprites and hasattr(self, 'sprite_manager'):
                    has_sprite = item_name.upper() in self.sprite_manager.sprites
                    if has_sprite:
                        item_name_for_sprite = item_name.upper()
                    else:
                        item_name_for_sprite = item_name
                else:
                    item_name_for_sprite = item_name
                
                if has_sprite:
                    # Use sprite for item
                    sprite = self.sprite_manager.get_sprite(item_name_for_sprite)
                    self.screen.blit(sprite, (slot_x, slot_y))
                elif item_name in ITEMS:
                    # Fallback to colored rectangle for items
                    item_color = ITEMS[item_name]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))
                elif item_name.upper() in CELL_TYPES:
                    # Fallback for structures (tree1 -> TREE1, house -> HOUSE, etc.)
                    item_color = CELL_TYPES[item_name.upper()]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))
                elif item_name.lower() in CELL_TYPES:
                    # Try lowercase too
                    item_color = CELL_TYPES[item_name.lower()]['color']
                    pygame.draw.rect(self.screen, item_color,
                                   (slot_x + 4, slot_y + 4, slot_size - 8, slot_size - 8))
                
                # Item count
                if count > 1:
                    count_text = self.tiny_font.render(str(count), True, COLORS['WHITE'])
                    count_bg = pygame.Surface((count_text.get_width() + 2, count_text.get_height()))
                    count_bg.fill(COLORS['BLACK'])
                    count_bg.set_alpha(180)
                    self.screen.blit(count_bg, (slot_x + slot_size - count_text.get_width() - 2, 
                                                 slot_y + slot_size - count_text.get_height()))
                    self.screen.blit(count_text, (slot_x + slot_size - count_text.get_width() - 1, 
                                                   slot_y + slot_size - count_text.get_height()))
                
                # Slot number (for number key selection)
                num_text = self.tiny_font.render(str((i + 1) % 10), True, COLORS['GRAY'])
                self.screen.blit(num_text, (slot_x + 2, slot_y + 2))
            
            y_offset += slot_size + 15
    
    def draw_game(self):
            """Draw game screen"""
            self.screen.fill(COLORS['BLACK'])
            
            # Draw grid
            if self.current_screen:
                # Determine correct screen key for dropped items
                # If in subscreen, use subscreen_key; otherwise use overworld coordinates
                if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
                    screen_key = self.player['subscreen_key']
                else:
                    screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                
                # Ensure variant_grid exists (backfill for screens generated before variant system)
                if 'variant_grid' not in self.current_screen:
                    vg = []
                    for vy in range(len(self.current_screen['grid'])):
                        vrow = []
                        for vx in range(len(self.current_screen['grid'][vy])):
                            c = self.current_screen['grid'][vy][vx]
                            vrow.append(self.roll_cell_variant(c) if hasattr(self, 'roll_cell_variant') else None)
                        vg.append(vrow)
                    self.current_screen['variant_grid'] = vg
                
                for y, row in enumerate(self.current_screen['grid']):
                    for x, cell in enumerate(row):
                        # Check if this cell should use layered rendering
                        # ONLY use layering if we have BOTH base terrain AND object sprites
                        use_layered = False
                        base_terrain = None
                        object_sprite = None
                        
                        if cell in ['TREE1', 'TREE2', 'TREE3', 'FLOWER']:
                            # Trees/flowers layer on biome-appropriate walkable ground
                            if (self.use_sprites and hasattr(self, 'sprite_manager') and 
                                cell in self.sprite_manager.sprites):
                                biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                if biome == 'DESERT':
                                    base_terrain = 'SAND'
                                elif biome == 'MOUNTAINS':
                                    base_terrain = 'DIRT'
                                else:  # FOREST, PLAINS, or unknown
                                    base_terrain = 'GRASS'
                                if base_terrain in self.sprite_manager.sprites:
                                    object_sprite = cell
                                    use_layered = True
                        elif cell in ['CAMP', 'HOUSE', 'CAVE']:
                            # Camp and house layer on biome-appropriate walkable ground
                            if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                                # Determine base terrain by biome — always use walkable
                                # ground, never collision cells like STONE
                                biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                if biome == 'DESERT':
                                    base_terrain = 'SAND'
                                elif biome == 'MOUNTAINS':
                                    base_terrain = 'DIRT'
                                else:  # FOREST, PLAINS, or unknown
                                    base_terrain = 'GRASS'
                                
                                # Only use layered if base terrain sprite exists
                                if base_terrain in self.sprite_manager.sprites:
                                    object_sprite = cell
                                    use_layered = True
                        elif cell == 'CHEST':
                            # Chest uses stored background cell (what it replaced)
                            if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                                # Check if we have a stored background for this chest
                                chest_key = f"{screen_key}:{x},{y}"
                                if hasattr(self, 'chest_backgrounds') and chest_key in self.chest_backgrounds:
                                    base_terrain = self.chest_backgrounds[chest_key]
                                else:
                                    # No stored background - determine from context
                                    # Check if in subscreen (house/cave)
                                    if self.current_screen and 'parent_screen' in self.current_screen:
                                        # In subscreen - use floor type
                                        subscreen_type = self.current_screen.get('type', 'HOUSE_INTERIOR')
                                        if 'CAVE' in subscreen_type:
                                            base_terrain = 'CAVE_FLOOR'
                                        else:
                                            base_terrain = 'FLOOR_WOOD'
                                    else:
                                        # Fallback to biome-appropriate base terrain
                                        biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                        if biome == 'DESERT':
                                            base_terrain = 'SAND'
                                        elif biome == 'MOUNTAINS':
                                            base_terrain = 'STONE'
                                        elif biome == 'PLAINS':
                                            base_terrain = 'GRASS'
                                        else:  # FOREST
                                            base_terrain = 'GRASS'
                                
                                # Only use layered if base terrain sprite exists
                                if base_terrain in self.sprite_manager.sprites:
                                    object_sprite = cell
                                    use_layered = True
                        elif cell in ['CARROT1', 'CARROT2', 'CARROT3']:
                            # Check if both DIRT and crop sprites exist
                            if (self.use_sprites and hasattr(self, 'sprite_manager') and 
                                'DIRT' in self.sprite_manager.sprites and 
                                cell in self.sprite_manager.sprites):
                                base_terrain = 'DIRT'
                                object_sprite = cell
                                use_layered = True
                        elif cell == 'STONE':
                            # Stone should layer on appropriate base terrain
                            if self.use_sprites and hasattr(self, 'sprite_manager') and cell in self.sprite_manager.sprites:
                                # Check if in subscreen (house/cave)
                                if self.current_screen and 'parent_screen' in self.current_screen:
                                    # In subscreen - use floor type
                                    subscreen_type = self.current_screen.get('type', 'HOUSE_INTERIOR')
                                    if 'CAVE' in subscreen_type:
                                        base_terrain = 'CAVE_FLOOR'
                                    else:
                                        base_terrain = 'FLOOR_WOOD'
                                else:
                                    # In overworld - determine base terrain by biome
                                    biome = self.current_screen.get('biome', 'FOREST') if self.current_screen else 'FOREST'
                                    if biome == 'DESERT':
                                        base_terrain = 'SAND'
                                    elif biome == 'MOUNTAINS':
                                        base_terrain = 'DIRT'
                                    else:
                                        base_terrain = 'GRASS'
                                
                                # Only use layered if base terrain sprite exists
                                if base_terrain in self.sprite_manager.sprites:
                                    object_sprite = cell
                                    use_layered = True
                        
                        # Layered rendering (when we have both sprites)
                        if use_layered:
                            # Check if base terrain has a valid variant
                            actual_base = base_terrain
                            if self.current_screen and 'variant_grid' in self.current_screen:
                                v = self.current_screen['variant_grid'][y][x]
                                if v and base_terrain in CELL_TYPES:
                                    base_variants = CELL_TYPES[base_terrain].get('variants', {})
                                    if v in base_variants and v in self.sprite_manager.sprites:
                                        actual_base = v
                                    elif v not in base_variants:
                                        # Stale variant — re-roll for base terrain
                                        new_v = self.roll_cell_variant(base_terrain) if hasattr(self, 'roll_cell_variant') else None
                                        self.current_screen['variant_grid'][y][x] = new_v
                                        if new_v and new_v in self.sprite_manager.sprites:
                                            actual_base = new_v
                            
                            # Draw base terrain (or its variant)
                            base_sprite = self.sprite_manager.get_sprite(actual_base)
                            self.screen.blit(base_sprite, (x * CELL_SIZE, y * CELL_SIZE))
                            # Draw object on top
                            obj_sprite = self.sprite_manager.get_sprite(object_sprite)
                            self.screen.blit(obj_sprite, (x * CELL_SIZE, y * CELL_SIZE))
                        
                        # Direct rendering (no layering) - just render the cell itself
                        else:
                            # Check for cell variant sprite
                            sprite_name = cell
                            variant = None
                            if self.current_screen and 'variant_grid' in self.current_screen:
                                v = self.current_screen['variant_grid'][y][x]
                                if v and cell in CELL_TYPES:
                                    cell_variants = CELL_TYPES[cell].get('variants', {})
                                    if v in cell_variants:
                                        variant = v
                                    else:
                                        # Stale variant — cell type changed. Re-roll for new cell.
                                        new_variant = self.roll_cell_variant(cell) if hasattr(self, 'roll_cell_variant') else None
                                        self.current_screen['variant_grid'][y][x] = new_variant
                                        if new_variant:
                                            variant = new_variant
                                elif v is None and cell in CELL_TYPES and CELL_TYPES[cell].get('variants'):
                                    # Cell has variants but no variant assigned — roll one
                                    new_variant = self.roll_cell_variant(cell) if hasattr(self, 'roll_cell_variant') else None
                                    self.current_screen['variant_grid'][y][x] = new_variant
                                    if new_variant:
                                        variant = new_variant
                            
                            if cell == 'WALL' and self.current_screen:
                                biome = self.current_screen.get('biome', 'FOREST')
                                sprite_name = f"wall_{biome.lower()}"
                            elif variant:
                                sprite_name = variant
                            
                            has_sprite = (self.use_sprites and 
                                         hasattr(self, 'sprite_manager') and 
                                         sprite_name in self.sprite_manager.sprites)
                            
                            if has_sprite:
                                # Use sprite directly - NO LABEL
                                sprite = self.sprite_manager.get_sprite(sprite_name)
                                self.screen.blit(sprite, (x * CELL_SIZE, y * CELL_SIZE))
                            else:
                                # Fallback to colored rectangle with border AND label
                                color = CELL_TYPES[cell]['color']
                                pygame.draw.rect(self.screen, color,
                                               (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE))
                                # Draw border for non-sprite cells
                                pygame.draw.rect(self.screen, COLORS['BLACK'],
                                               (x * CELL_SIZE, y * CELL_SIZE, CELL_SIZE, CELL_SIZE), 1)
                                
                                # Draw label ONLY when no sprite
                                label = CELL_TYPES[cell]['label']
                                text = self.tiny_font.render(label, True, COLORS['WHITE'])
                                text_rect = text.get_rect(center=(
                                    x * CELL_SIZE + CELL_SIZE // 2,
                                    y * CELL_SIZE + CELL_SIZE // 2
                                ))
                                self.screen.blit(text, text_rect)
                        
                        # Draw enchantment indicator if cell is enchanted
                        if self.is_cell_enchanted(x, y, screen_key):
                            enchant_level = self.enchanted_cells[screen_key].get((x, y), 0)
                            # Draw golden star in corner
                            star_text = self.tiny_font.render('★', True, COLORS['YELLOW'])
                            self.screen.blit(star_text, (x * CELL_SIZE + 2, y * CELL_SIZE + 2))
                            # Draw enchant level number
                            if enchant_level > 1:
                                level_text = self.tiny_font.render(str(enchant_level), True, COLORS['YELLOW'])
                                self.screen.blit(level_text, (x * CELL_SIZE + 12, y * CELL_SIZE + 2))
                        
                        # Draw dropped items (layered over base cell)
                        if screen_key in self.dropped_items:
                            cell_key = (x, y)
                            if cell_key in self.dropped_items[screen_key]:
                                items = self.dropped_items[screen_key][cell_key]
                                item_count = len(items)
                                total_count = sum(items.values())
                                
                                # Empty cells allow full overlay
                                empty_cells = ['GRASS', 'DIRT', 'SAND', 'STONE', 'FLOOR_WOOD', 'CAVE_FLOOR', 
                                             'PLANKS', 'WOOD', 'SOIL', 'COBBLESTONE']
                                is_empty_cell = cell in empty_cells
                                
                                if item_count == 1 and total_count == 1 and is_empty_cell:
                                    # Single item, single count — show item sprite
                                    item_name = list(items.keys())[0]
                                    sprite_key = None
                                    if self.use_sprites and hasattr(self, 'sprite_manager'):
                                        if item_name in self.sprite_manager.sprites:
                                            sprite_key = item_name
                                        elif item_name in ITEMS and 'sprite_name' in ITEMS[item_name]:
                                            sn = ITEMS[item_name]['sprite_name']
                                            if sn in self.sprite_manager.sprites:
                                                sprite_key = sn
                                        if not sprite_key and item_name.upper() in self.sprite_manager.sprites:
                                            sprite_key = item_name.upper()
                                    
                                    if sprite_key:
                                        sprite = self.sprite_manager.get_sprite(sprite_key)
                                        self.screen.blit(sprite, (x * CELL_SIZE, y * CELL_SIZE))
                                    elif item_name in ITEMS:
                                        item_color = ITEMS[item_name]['color']
                                        overlay_surface = pygame.Surface((CELL_SIZE, CELL_SIZE), pygame.SRCALPHA)
                                        overlay_surface.fill((*item_color, 180))
                                        self.screen.blit(overlay_surface, (x * CELL_SIZE, y * CELL_SIZE))
                                        item_label = ITEMS[item_name].get('name', item_name)[:3].upper()
                                        text = self.tiny_font.render(item_label, True, COLORS['WHITE'])
                                        text_rect = text.get_rect(center=(
                                            x * CELL_SIZE + CELL_SIZE // 2,
                                            y * CELL_SIZE + CELL_SIZE // 2))
                                        self.screen.blit(text, text_rect)
                                else:
                                    # Multiple items or stacks — show itembag sprite
                                    has_bag = (self.use_sprites and hasattr(self, 'sprite_manager') and
                                               'itembag' in self.sprite_manager.sprites)
                                    if has_bag:
                                        bag_sprite = self.sprite_manager.get_sprite('itembag')
                                        self.screen.blit(bag_sprite, (x * CELL_SIZE, y * CELL_SIZE))
                                    else:
                                        # Fallback: brown bag circle
                                        bag_color = (139, 90, 43)
                                        pygame.draw.circle(self.screen, bag_color,
                                                         (x * CELL_SIZE + CELL_SIZE // 2,
                                                          y * CELL_SIZE + CELL_SIZE // 2),
                                                         CELL_SIZE // 3)
            
            # ... rest of draw_game continues (target highlight, entities, player, etc)
            
            # Draw target highlight
            target = self.get_target_cell()
            if target:
                highlight_x, highlight_y = target
                # Draw semi-transparent yellow overlay
                highlight_surface = pygame.Surface((CELL_SIZE, CELL_SIZE))
                highlight_surface.set_alpha(100)
                highlight_surface.fill(COLORS['YELLOW'])
                self.screen.blit(highlight_surface, 
                               (highlight_x * CELL_SIZE, highlight_y * CELL_SIZE))
                # Draw border
                pygame.draw.rect(self.screen, COLORS['YELLOW'],
                               (highlight_x * CELL_SIZE, highlight_y * CELL_SIZE, 
                                CELL_SIZE, CELL_SIZE), 3)
            
            # Draw entities on current screen or subscreen
            entities_to_draw = []
            
            if self.player.get('in_subscreen'):
                # In subscreen - draw entities that belong to this subscreen
                current_subscreen_key = self.player.get('subscreen_key')
                if current_subscreen_key and current_subscreen_key in self.subscreen_entities:
                    entities_to_draw = self.subscreen_entities[current_subscreen_key]
            else:
                # In overworld - draw entities from current screen
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                if screen_key in self.screen_entities:
                    entities_to_draw = self.screen_entities[screen_key]
            
            # Draw the entities
            for entity_id in entities_to_draw:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    
                    # Proxy NPC is drawn as the player sprite below.
                    # Still run smooth movement + animation so anim_frame advances
                    # correctly — the player sprite reads these values directly.
                    if self.autopilot and entity_id == getattr(self, 'autopilot_proxy_id', None):
                        entity.update_smooth_movement()
                        entity.update_animation()
                        continue

                    # Update smooth movement
                    entity.update_smooth_movement()
                    
                    # DISABLED: Terrain collision in rendering loop - AI safety check in update_entity_ai handles this.
                    # This rendering-phase code was fighting with the AI movement system, causing position jumps.
                    # The AI (game_logic.py lines 4997-5033) already validates positions after every AI update.
                    
                    # DISABLED: Collision pushback system - conflicts with movement reservation system in game_logic.py
                    # The move_toward_position function already prevents entities from moving into occupied cells
                    # This pushback code was causing entities to jump back after valid moves
                    """
                    # Check for entity collision - if overlapping with another entity, push back
                    # Get all entities in this screen
                    if screen_key in self.screen_entities:
                        for other_id in self.screen_entities[screen_key]:
                            if other_id == entity_id or other_id not in self.entities:
                                continue
                            
                            other = self.entities[other_id]
                            # Check if entities are occupying same cell
                            if entity.x == other.x and entity.y == other.y:
                                # Collision! Push back to previous position
                                # Calculate where entity came from
                                dx = entity.target_x - entity.x
                                dy = entity.target_y - entity.y
                                
                                # Move back one cell in opposite direction
                                pushback_x = entity.x
                                pushback_y = entity.y
                                
                                if dx > 0:
                                    pushback_x = entity.x - 1
                                elif dx < 0:
                                    pushback_x = entity.x + 1
                                    
                                if dy > 0:
                                    pushback_y = entity.y - 1
                                elif dy < 0:
                                    pushback_y = entity.y + 1
                                
                                # Clamp to bounds
                                pushback_x = max(0, min(GRID_WIDTH - 1, pushback_x))
                                pushback_y = max(0, min(GRID_HEIGHT - 1, pushback_y))
                                
                                # Verify pushback cell is safe
                                if 0 <= pushback_x < GRID_WIDTH and 0 <= pushback_y < GRID_HEIGHT:
                                    pushback_cell = screen['grid'][pushback_y][pushback_x]
                                    if pushback_cell in CELL_TYPES and not CELL_TYPES[pushback_cell].get('solid', False):
                                        # Push entity back
                                        entity.world_x = float(pushback_x)
                                        entity.world_y = float(pushback_y)
                                        entity.x = pushback_x
                                        entity.y = pushback_y
                                        entity.target_x = pushback_x
                                        entity.target_y = pushback_y
                                        entity.is_moving = False
                                        
                                        # Reset wander timer
                                        if hasattr(entity, 'wander_timer'):
                                            entity.wander_timer = 5
                                        break  # Only push back once
                    """
                    
                    # Update animation
                    entity.update_animation()
                    
                    # Calculate pixel position from WORLD coordinates (not grid + offset)
                    pixel_x = entity.world_x * CELL_SIZE
                    pixel_y = entity.world_y * CELL_SIZE
                    
                    # Try to load entity sprite
                    entity_sprite = None
                    is_double = entity.type.endswith('_double')
                    base_type = entity.type.replace('_double', '') if is_double else entity.type
                    
                    if self.use_sprites and hasattr(self, 'sprite_manager'):
                        # Get sprite name (use sprite_name property if available, otherwise use type)
                        sprite_base = entity.props.get('sprite_name', base_type).lower()
                        
                        # Try 3-frame animation first
                        sprite_name = f"{sprite_base}_{entity.facing}_{entity.anim_frame}"
                        if sprite_name in self.sprite_manager.sprites:
                            entity_sprite = self.sprite_manager.get_sprite(sprite_name)
                        else:
                            # Fallback to 2-frame animation (convert still -> 1, keep 1 and 2 as is)
                            if entity.anim_frame == 'still':
                                frame_2frame = '1'
                            else:
                                frame_2frame = entity.anim_frame  # '1' or '2'
                            sprite_name_2frame = f"{sprite_base}_{entity.facing}_{frame_2frame}"
                            if sprite_name_2frame in self.sprite_manager.sprites:
                                entity_sprite = self.sprite_manager.get_sprite(sprite_name_2frame)
                    
                    # Draw entity at smooth sub-cell position
                    if entity_sprite:
                        # Use animated sprite
                        if is_double:
                            # Draw two overlapping sprites for _double entities
                            self.screen.blit(entity_sprite, (pixel_x, pixel_y))
                            self.screen.blit(entity_sprite, (pixel_x + 4, pixel_y + 2))
                        else:
                            self.screen.blit(entity_sprite, (pixel_x, pixel_y))
                    else:
                        # Fallback to circle with symbol
                        entity_color = entity.props['color']
                        if is_double:
                            # Draw two overlapping circles for _double
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2),
                                 int(pixel_y + CELL_SIZE // 2)),
                                CELL_SIZE // 3
                            )
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2 + 4),
                                 int(pixel_y + CELL_SIZE // 2 + 2)),
                                CELL_SIZE // 3
                            )
                        else:
                            pygame.draw.circle(
                                self.screen,
                                entity_color,
                                (int(pixel_x + CELL_SIZE // 2),
                                 int(pixel_y + CELL_SIZE // 2)),
                                CELL_SIZE // 3
                            )
                        
                        # Draw symbol
                        symbol_text = self.tiny_font.render(entity.props['symbol'], True, COLORS['WHITE'])
                        symbol_rect = symbol_text.get_rect(center=(
                            int(pixel_x + CELL_SIZE // 2),
                            int(pixel_y + CELL_SIZE // 2)
                        ))
                        self.screen.blit(symbol_text, symbol_rect)
                    
                    # Draw health bar (always visible) at smooth position
                    bar_width = CELL_SIZE - 4
                    bar_height = 4
                    bar_x = int(pixel_x + 2)
                    bar_y = int(pixel_y - 6)
                    
                    # Background
                    pygame.draw.rect(self.screen, COLORS['BLACK'],
                                   (bar_x, bar_y, bar_width, bar_height))
                    # Health
                    health_width = int((entity.health / entity.max_health) * bar_width)
                    pygame.draw.rect(self.screen, (0, 255, 0),
                                   (bar_x, bar_y, health_width, bar_height))
                    
                    # Draw level if > 1
                    if entity.level > 1:
                        level_text = self.tiny_font.render(f"L{entity.level}", True, COLORS['YELLOW'])
                        self.screen.blit(level_text, (int(pixel_x + 2), int(pixel_y + CELL_SIZE - 12)))
                    
                    # Debug: Draw AI state and target info
                    if self.debug_entity_ai:
                        debug_y_offset = CELL_SIZE - 12 if entity.level > 1 else CELL_SIZE - 2
                        
                        # AI State
                        if hasattr(entity, 'ai_state'):
                            state_color = COLORS['WHITE']
                            if entity.ai_state == 'combat':
                                state_color = (255, 0, 0)  # RED
                            elif entity.ai_state == 'targeting':
                                state_color = (255, 165, 0)  # ORANGE
                            elif entity.ai_state == 'wandering':
                                state_color = COLORS['GRAY']
                            elif entity.ai_state == 'idle':
                                state_color = (192, 192, 192)  # LIGHT_GRAY
                            elif entity.ai_state == 'fleeing':
                                state_color = (255, 100, 255)  # PINK
                            
                            state_text = self.tiny_font.render(f"{entity.ai_state[:3].upper()}", True, state_color)
                            self.screen.blit(state_text, (int(pixel_x + 2), int(pixel_y + debug_y_offset + 10)))
                        
                        # Target info
                        target_info = ""
                        if hasattr(entity, 'current_target') and entity.current_target:
                            if isinstance(entity.current_target, int) and entity.current_target in self.entities:
                                target_entity = self.entities[entity.current_target]
                                target_info = f"→{target_entity.type[:3]}"
                            elif entity.current_target == 'player':
                                target_info = "→PLR"
                        elif hasattr(entity, 'target_type') and entity.target_type:
                            target_info = f"?{entity.target_type[:3]}"
                        
                        if target_info:
                            target_text = self.tiny_font.render(target_info, True, COLORS['CYAN'])
                            self.screen.blit(target_text, (int(pixel_x + 24), int(pixel_y + debug_y_offset + 10)))
                    
                    # Draw faction name if entity has one (debug display)
                    if hasattr(entity, 'faction') and entity.faction:
                        # Abbreviate faction name (first letter of each word)
                        faction_abbrev = ''.join([word[0] for word in entity.faction.split()])
                        faction_text = self.tiny_font.render(faction_abbrev, True, COLORS['CYAN'])
                        self.screen.blit(faction_text, (entity.x * CELL_SIZE + 2, entity.y * CELL_SIZE + CELL_SIZE + 2))
            
            # Debug: Draw memory lanes for traders
            if self.debug_memory_lanes:
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                if screen_key in self.screen_entities:
                    for entity_id in self.screen_entities[screen_key]:
                        if entity_id in self.entities:
                            entity = self.entities[entity_id]
                            # Only show for TRADER entities
                            if entity.type == 'TRADER' or entity.type == 'TRADER_double':
                                # Draw memory lane cells in RED
                                if hasattr(entity, 'memory_lane') and entity.memory_lane:
                                    for mem_x, mem_y in entity.memory_lane:
                                        # Semi-transparent red overlay
                                        mem_surface = pygame.Surface((CELL_SIZE - 4, CELL_SIZE - 4))
                                        mem_surface.set_alpha(100)
                                        mem_surface.fill((255, 0, 0))  # RED
                                        self.screen.blit(mem_surface, (mem_x * CELL_SIZE + 2, mem_y * CELL_SIZE + 2))
                                
                                # Draw target cell in GREEN
                                if hasattr(entity, 'target_exit') and entity.target_exit:
                                    # Get the target position based on current exit target
                                    exit_positions = self.get_exit_positions(entity.target_exit)
                                    if exit_positions:
                                        # Highlight all potential exit positions in green
                                        for target_x, target_y in exit_positions:
                                            # Semi-transparent green overlay
                                            target_surface = pygame.Surface((CELL_SIZE - 4, CELL_SIZE - 4))
                                            target_surface.set_alpha(150)
                                            target_surface.fill((0, 255, 0))  # GREEN
                                            self.screen.blit(target_surface, (target_x * CELL_SIZE + 2, target_y * CELL_SIZE + 2))

            # ── Draw player character (or autopilot proxy) ─────────────────
            # During autopilot the proxy entity has already had update_smooth_movement()
            # and update_animation() called by the entity loop above.  We read its
            # state directly — world position, facing, anim_frame — and draw the
            # wizard sprite at exactly the same pixel and frame as the underlying NPC.
            # During manual play we run the original player-driven animation + lerp.

            proxy = (self.entities.get(self.autopilot_proxy_id)
                     if self.autopilot and getattr(self, 'autopilot_proxy_id', None) else None)

            player_sprite = None

            if proxy is not None:
                # ── AUTOPILOT: mirror proxy state exactly ─────────────────
                # pixel position straight from proxy world coords (already lerped)
                px = int(proxy.world_x * CELL_SIZE)
                py = int(proxy.world_y * CELL_SIZE)
                facing    = proxy.facing
                anim_frame = proxy.anim_frame
                # Consume player is_moving (keep flag clean)
                self.player['is_moving'] = False

            else:
                # ── MANUAL: player-driven animation + lerp ────────────────
                PLAYER_TICKS_PER_FRAME = 10

                is_moving = self.player.get('is_moving', False)
                keys_held = pygame.key.get_pressed()
                movement_key_held = (keys_held[pygame.K_UP] or keys_held[pygame.K_w] or
                                     keys_held[pygame.K_DOWN] or keys_held[pygame.K_s] or
                                     keys_held[pygame.K_LEFT] or keys_held[pygame.K_a] or
                                     keys_held[pygame.K_RIGHT] or keys_held[pygame.K_d])

                if is_moving:
                    self.player['_move_anim_ticks'] = 12
                else:
                    remaining = self.player.get('_move_anim_ticks', 0)
                    if remaining > 0:
                        self.player['_move_anim_ticks'] = remaining - 1

                should_animate = is_moving or movement_key_held or self.player.get('_move_anim_ticks', 0) > 0

                if should_animate:
                    self.player['anim_timer'] = self.player.get('anim_timer', 0) + 1
                    if self.player['anim_timer'] >= PLAYER_TICKS_PER_FRAME:
                        af = self.player.get('anim_frame', 'still')
                        ns = self.player.get('_next_step', '1')
                        if af == '1':
                            self.player['anim_frame'] = 'still'
                        elif af == 'still':
                            self.player['anim_frame'] = ns
                            self.player['_next_step'] = '1' if ns == '2' else '2'
                        elif af == '2':
                            self.player['anim_frame'] = 'still'
                        else:
                            self.player['anim_frame'] = '1'
                            self.player['_next_step'] = '2'
                        self.player['anim_timer'] = 0
                else:
                    self.player['anim_frame'] = 'still'
                    self.player['anim_timer'] = 0
                    self.player['_next_step'] = '1'

                self.player['is_moving'] = False

                facing     = self.player.get('facing', 'down')
                anim_frame = self.player.get('anim_frame', 'still')

                # Lerp world position toward grid position
                target_wx = float(self.player['x'])
                target_wy = float(self.player['y'])
                PLAYER_MOVE_SPEED = 0.057  # 1 cell in ~18 frames, matches move interval
                ARRIVAL_THRESH = 0.01

                if 'world_x' not in self.player:
                    self.player['world_x'] = target_wx
                    self.player['world_y'] = target_wy

                dx_w = target_wx - self.player['world_x']
                dy_w = target_wy - self.player['world_y']
                dist_w = (dx_w ** 2 + dy_w ** 2) ** 0.5

                if dist_w < ARRIVAL_THRESH or dist_w > 2.5:
                    self.player['world_x'] = target_wx
                    self.player['world_y'] = target_wy
                else:
                    step = min(PLAYER_MOVE_SPEED, dist_w)
                    ratio = step / dist_w
                    self.player['world_x'] += dx_w * ratio
                    self.player['world_y'] += dy_w * ratio

                px = int(self.player['world_x'] * CELL_SIZE)
                py = int(self.player['world_y'] * CELL_SIZE)

            # Sprite lookup (same logic as entity draw loop)
            if self.use_sprites and hasattr(self, 'sprite_manager'):
                sprite_name = f"wizard_{facing}_{anim_frame}"
                if sprite_name in self.sprite_manager.sprites:
                    player_sprite = self.sprite_manager.get_sprite(sprite_name)
                else:
                    sprite_name_fallback = f"wizard_{facing}_still"
                    if sprite_name_fallback in self.sprite_manager.sprites:
                        player_sprite = self.sprite_manager.get_sprite(sprite_name_fallback)

            if player_sprite:
                self.screen.blit(player_sprite, (px, py))
            else:
                # Fallback to yellow @ symbol
                pygame.draw.rect(self.screen, COLORS['YELLOW'], (px, py, CELL_SIZE, CELL_SIZE))
                player_text = self.font.render('@', True, COLORS['BLACK'])
                player_rect = player_text.get_rect(center=(px + CELL_SIZE // 2, py + CELL_SIZE // 2))
                self.screen.blit(player_text, player_rect)
            
            # Draw autopilot indicator
            if self.autopilot:
                auto_text = self.tiny_font.render("AUTO", True, (100, 255, 100))
                self.screen.blit(auto_text, (px - 2, py - 10))
            
            # Draw attack animations
            self.draw_attack_animations()

            # Draw UI bar at bottom
            ui_y = GRID_HEIGHT * CELL_SIZE
            pygame.draw.rect(self.screen, COLORS['UI_BG'], (0, ui_y, SCREEN_WIDTH, 60))
            
            info_text = f"HP: {int(self.player['health'])}/{self.player['max_health']} | "
            info_text += f"Magic: {self.player['magic_pool']}/{self.player['max_magic_pool']} | "
            
            # Show location info
            if self.player.get('in_subscreen'):
                subscreen = self.subscreens.get(self.player['subscreen_key'])
                if subscreen:
                    depth_info = f" (Depth {subscreen['depth']})" if subscreen['type'] == 'CAVE' else ""
                    info_text += f"Location: {subscreen['type']}{depth_info}"
            else:
                info_text += f"Screen: ({self.player['screen_x']}, {self.player['screen_y']}) | "
                info_text += f"Biome: {self.current_screen['biome'] if self.current_screen else 'Unknown'}"
                
                # Show zone control by faction (majority only)
                screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
                controlling_faction = self.get_zone_controlling_faction(screen_key)
                if controlling_faction:
                    info_text += f" | Controlled by: {controlling_faction}"
            
            if self.player['blocking']:
                info_text += " | [BLOCKING]"
            if self.player.get('friendly_fire', False):
                info_text += " | [FF ON]"
            text = self.small_font.render(info_text, True, COLORS['WHITE'])
            self.screen.blit(text, (10, ui_y + 5))
            
            # Draw quest target info on second line
            quest_display = ""
            if self.active_quest and self.active_quest in self.quests:
                quest = self.quests[self.active_quest]
                quest_info = QUEST_TYPES.get(self.active_quest, {})
                quest_name = quest_info.get('name', self.active_quest)
                if quest.status == 'active' and quest.target_info:
                    quest_display = f"Quest [{quest_name}]: {quest.target_info}"
                elif quest.status == 'active':
                    quest_display = f"Quest [{quest_name}]: Tracking..."
                elif quest.status == 'inactive':
                    quest_display = f"Quest [{quest_name}]: Press Q to activate"
            
            if quest_display:
                quest_color = QUEST_TYPES.get(self.active_quest, {}).get('color', (200, 200, 200))
                quest_text = self.tiny_font.render(quest_display, True, quest_color)
                self.screen.blit(quest_text, (10, ui_y + 22))
            
            # Show interaction hint based on target cell
            target = self.get_target_cell()
            hint_text = "SPACE: Attack"
            if target and self.current_screen:
                check_x, check_y = target
                cell = self.current_screen['grid'][check_y][check_x]
                
                if cell == 'STAIRS_UP':
                    hint_text = "SPACE: Exit"
                elif cell == 'STAIRS_DOWN':
                    hint_text = "SPACE: Descend"
                elif cell == 'CHEST':
                    hint_text = "SPACE: Open Chest"
                elif CELL_TYPES.get(cell, {}).get('enterable'):
                    hint_text = "SPACE: Enter"
            
            controls = f"{hint_text} | B: Block | C: Craft | X: Combine | L: Cast | E: Pickup"
            text = self.tiny_font.render(controls, True, COLORS['WHITE'])
            self.screen.blit(text, (10, ui_y + 42))
            
            # ── Key reference on right side of bottom bar ──────────────
            key_ref_x = SCREEN_WIDTH - 340
            key_lines = [
                "WASD/Arrows: Move  SPACE: Interact  ESC: Pause",
                "I/T/M/F: Items/Tools/Magic/Follow  Q: Quests  N: Trade",
                "E: Pickup  P: Place  D: Drop  B: Block  V: FF  C/X: Craft",
            ]
            for i, line in enumerate(key_lines):
                ref_text = self.tiny_font.render(line, True, (160, 160, 170))
                self.screen.blit(ref_text, (key_ref_x, ui_y + 4 + i * 14))
            
            # Draw rain effect if raining (minimal, just visual indicator)
            if self.is_raining:
                # Draw subtle blue tint overlay
                rain_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 60))
                rain_overlay.set_alpha(60)  # Increased from 20 to be more visible
                rain_overlay.fill((100, 150, 200))  # Light blue
                self.screen.blit(rain_overlay, (0, 0))
                
                # Draw "RAIN" indicator in corner
                rain_text = self.small_font.render("🌧 RAIN", True, (150, 200, 255))
                self.screen.blit(rain_text, (SCREEN_WIDTH - 100, 10))
            
            # Draw night overlay (subtle gray darkness)
            if self.is_night:
                night_overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT - 60))
                night_overlay.set_alpha(NIGHT_OVERLAY_ALPHA)  # Very subtle
                night_overlay.fill((40, 40, 50))  # Dark gray-blue
                self.screen.blit(night_overlay, (0, 0))
                
                # Draw "NIGHT" indicator in corner
                night_text = self.small_font.render("🌙 NIGHT", True, (180, 180, 200))
                self.screen.blit(night_text, (SCREEN_WIDTH - 100, 30))
            
            # Draw inventory panels (replace the old inventory drawing code)
            self.draw_inventory_panels()
            
            # Draw quest UI if open
            if self.quest_ui_open:
                self.draw_quest_ui()
            
            # Draw quest arrow if quest is active
            if self.active_quest and self.quests[self.active_quest].status == 'active':
                self.draw_quest_arrow()
            
            # Draw trader UI if active
            if self.trader_display:
                self.draw_trader_ui()
            
            # Draw NPC inspection if targeting peaceful NPC
            self.draw_inspected_npc()
            
            # Draw item list when targeting a cell with dropped items or a chest
            self.draw_targeted_items()

        
    def draw_trader_ui(self):
        """Draw trader recipe UI above the trader NPC"""
        if not self.trader_display:
            return
        
        # Close UI if player moved (not adjacent to trader anymore)
        entity_id = self.trader_display['entity_id']
        if entity_id not in self.entities:
            self.trader_display = None
            return
        
        trader = self.entities[entity_id]
        player_adjacent = (
            trader.screen_x == self.player['screen_x'] and 
            trader.screen_y == self.player['screen_y'] and
            abs(trader.x - self.player['x']) + abs(trader.y - self.player['y']) <= 1
        )
        
        if not player_adjacent:
            self.trader_display = None
            return
        
        # Check if trader has enough gold + items for any recipe
        recipes = self.trader_display['recipes']
        trader_x, trader_y = self.trader_display['position']
        
        # Draw above trader
        ui_x = trader_x * CELL_SIZE
        ui_y = trader_y * CELL_SIZE - 100
        
        slot_size = CELL_SIZE
        padding = 4
        
        recipes_shown = 0
        for i, recipe in enumerate(recipes):
            # Check if trader has ingredients (just for visual feedback)
            can_craft = True
            for item_name, count in recipe['inputs']:
                if trader.inventory.get(item_name, 0) < count:
                    can_craft = False
                    break
            
            # Show ALL recipes, not just available ones
            # Draw recipe: inputs + arrow + output
            recipe_y = ui_y - (recipes_shown * (slot_size + padding))
            current_x = ui_x
            recipes_shown += 1
            
            # Draw input items
            for item_name, count in recipe['inputs']:
                # Draw slot background
                pygame.draw.rect(self.screen, COLORS['BLACK'], 
                               (current_x, recipe_y, slot_size, slot_size))
                pygame.draw.rect(self.screen, (100, 100, 100), 
                               (current_x, recipe_y, slot_size, slot_size), 2)
                
                # Draw item icon/letter
                if item_name in self.sprite_manager.sprites:
                    sprite = self.sprite_manager.sprites[item_name]
                    self.screen.blit(sprite, (current_x, recipe_y))
                else:
                    item_letter = item_name[0].upper()
                    text = self.tiny_font.render(item_letter, True, COLORS['WHITE'])
                    text_rect = text.get_rect(center=(current_x + slot_size // 2, 
                                                       recipe_y + slot_size // 2))
                    self.screen.blit(text, text_rect)
                
                # Draw count
                count_text = self.tiny_font.render(str(count), True, COLORS['WHITE'])
                self.screen.blit(count_text, (current_x + slot_size - 12, recipe_y + slot_size - 12))
                
                current_x += slot_size + padding
            
            # Draw arrow
            arrow_text = self.font.render("→", True, COLORS['WHITE'])
            self.screen.blit(arrow_text, (current_x, recipe_y + slot_size // 4))
            current_x += slot_size
            
            # Draw output item
            output_name, output_count = recipe['output']
            pygame.draw.rect(self.screen, COLORS['BLACK'], 
                           (current_x, recipe_y, slot_size, slot_size))
            pygame.draw.rect(self.screen, (0, 255, 0), 
                           (current_x, recipe_y, slot_size, slot_size), 2)
            
            if output_name in self.sprite_manager.sprites:
                sprite = self.sprite_manager.sprites[output_name]
                self.screen.blit(sprite, (current_x, recipe_y))
            else:
                output_letter = output_name[0].upper()
                text = self.tiny_font.render(output_letter, True, COLORS['WHITE'])
                text_rect = text.get_rect(center=(current_x + slot_size // 2, 
                                                   recipe_y + slot_size // 2))
                self.screen.blit(text, text_rect)
            
            # Draw output count
            if output_count > 1:
                count_text = self.tiny_font.render(str(output_count), True, COLORS['WHITE'])
                self.screen.blit(count_text, (current_x + slot_size - 12, recipe_y + slot_size - 12))
            
            # Execute trade if player presses SPACE near this recipe
            # (This will be handled in input handling)
    
    def draw_quest_ui(self):
        """Draw quest selection UI on left side matching inventory format"""
        if not self.quest_ui_open:
            return
        
        slot_size = CELL_SIZE
        start_x = 10
        # Position above inventory panels - calculate based on how many are open
        base_y = SCREEN_HEIGHT - 70  # Base inventory position
        
        # Calculate y_offset from open inventory panels
        y_offset = 0
        if self.inventory.open_menus:
            categories = ['tools', 'items', 'magic', 'followers', 'crafting']
            for category in categories:
                if category in self.inventory.open_menus:
                    items = self.inventory.get_all_craftable_items() if category == 'crafting' else self.inventory.get_item_list(category)
                    y_offset += slot_size + 15
        
        start_y = base_y - y_offset
        
        # Quest category label
        quest_color = (200, 150, 100)  # Tan/brown color for quests
        label_text = self.small_font.render("QUESTS", True, quest_color)
        self.screen.blit(label_text, (start_x, start_y - 15))
        
        # Draw quest slots horizontally
        quest_types = list(QUEST_TYPES.keys())
        for i, quest_type in enumerate(quest_types):
            quest = self.quests[quest_type]
            quest_info = QUEST_TYPES[quest_type]
            
            slot_x = start_x + i * (slot_size + 2)
            slot_y = start_y
            
            # Background
            pygame.draw.rect(self.screen, COLORS['BLACK'],
                           (slot_x, slot_y, slot_size, slot_size))
            
            # Background color based on status
            if quest.status == 'completed':
                bg_color = (50, 100, 50)  # Dark green
            elif quest.cooldown_remaining > 0:
                bg_color = (60, 60, 60)  # Dark gray
            else:
                bg_color = COLORS['BLACK']
            
            if bg_color != COLORS['BLACK']:
                pygame.draw.rect(self.screen, bg_color,
                               (slot_x + 1, slot_y + 1, slot_size - 2, slot_size - 2))
            
            # Selected highlight (active quest)
            if quest_type == self.active_quest:
                pygame.draw.rect(self.screen, COLORS['INV_SELECT'],
                               (slot_x, slot_y, slot_size, slot_size), 3)
            else:
                pygame.draw.rect(self.screen, COLORS['INV_BORDER'],
                               (slot_x, slot_y, slot_size, slot_size), 1)
            
            # Draw quest symbol
            symbol_text = self.font.render(quest_info['symbol'], True, quest_info['color'])
            symbol_rect = symbol_text.get_rect(center=(slot_x + slot_size//2, slot_y + slot_size//2))
            self.screen.blit(symbol_text, symbol_rect)
            
            # Draw completion count in bottom right
            if quest.completed_count > 0:
                count_text = self.tiny_font.render(str(quest.completed_count), True, COLORS['WHITE'])
                count_bg = pygame.Surface((count_text.get_width() + 2, count_text.get_height()))
                count_bg.fill(COLORS['BLACK'])
                count_bg.set_alpha(180)
                self.screen.blit(count_bg, (slot_x + slot_size - count_text.get_width() - 2,
                                           slot_y + slot_size - count_text.get_height()))
                self.screen.blit(count_text, (slot_x + slot_size - count_text.get_width() - 1,
                                             slot_y + slot_size - count_text.get_height()))
            
            # Draw cooldown timer in top left
            if quest.cooldown_remaining > 0:
                cooldown_sec = quest.cooldown_remaining // FPS
                cooldown_text = self.tiny_font.render(f"{cooldown_sec}s", True, COLORS['WHITE'])
                self.screen.blit(cooldown_text, (slot_x + 2, slot_y + 2))
            
            # Slot number (for future number key selection)
            num_text = self.tiny_font.render(str((i + 1) % 10), True, COLORS['GRAY'])
            self.screen.blit(num_text, (slot_x + 2, slot_y + slot_size - 12))
    
    def draw_inspected_npc(self):
        """Draw inspection info to the right of targeted NPC"""
        if not self.inspected_npc or self.inspected_npc not in self.entities:
            return
        
        entity = self.entities[self.inspected_npc]
        
        # Check if still on same screen
        if (entity.screen_x != self.player['screen_x'] or 
            entity.screen_y != self.player['screen_y']):
            self.inspected_npc = None
            return
        
        # Check subscreen context - only show if in same subscreen context
        if self.player['in_subscreen']:
            # Player in subscreen - only show entities in SAME subscreen
            if not entity.in_subscreen or entity.subscreen_key != self.player['subscreen_key']:
                self.inspected_npc = None
                return
        else:
            # Player in main zone - don't show entities in subscreens
            if entity.in_subscreen:
                self.inspected_npc = None
                return
        
        # Position info to the right of the NPC
        npc_screen_x = entity.x * CELL_SIZE
        npc_screen_y = entity.y * CELL_SIZE
        
        info_x = npc_screen_x + CELL_SIZE + 10  # 10 pixels to the right
        info_y = npc_screen_y
        line_height = 16
        
        # White text for info
        info_lines = []
        
        # Name
        name = entity.name if entity.name else entity.type
        info_lines.append(f"{name}")
        
        # Type/Profession
        info_lines.append(f"{entity.type}")
        
        # Level
        info_lines.append(f"Lv.{entity.level}")
        
        # XP (show current XP / XP needed for next level)
        if hasattr(entity, 'xp') and hasattr(entity, 'xp_to_level'):
            info_lines.append(f"XP:{entity.xp}/{entity.xp_to_level}")
        
        # Health
        health_pct = int((entity.health / entity.max_health) * 100)
        info_lines.append(f"HP:{health_pct}%")
        
        # Hunger
        hunger_pct = int((entity.hunger / entity.max_hunger) * 100)
        info_lines.append(f"Food:{hunger_pct}%")
        
        # Thirst
        thirst_pct = int((entity.thirst / entity.max_thirst) * 100)
        info_lines.append(f"Water:{thirst_pct}%")
        
        # Age (if entity has age)
        if hasattr(entity, 'age'):
            info_lines.append(f"Age:{int(entity.age)}y")
        
        # Faction (if entity has faction)
        if hasattr(entity, 'faction') and entity.faction:
            info_lines.append(f"{entity.faction}")
        
        # Wizard info (if wizard)
        if entity.type == 'WIZARD':
            if hasattr(entity, 'spell'):
                info_lines.append(f"Spell:{entity.spell}")
            if hasattr(entity, 'alignment'):
                info_lines.append(f"({entity.alignment})")
        
        # Draw each line (no background box)
        for i, line in enumerate(info_lines):
            text = self.tiny_font.render(line, True, (255, 255, 255))
            self.screen.blit(text, (info_x, info_y + i * line_height))
    
    def draw_targeted_items(self):
        """Show item list when player targets a cell with dropped items or a chest."""
        target = self.get_target_cell()
        if not target:
            return
        
        tx, ty = target
        screen_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            screen_key = self.player['subscreen_key']
        
        info_lines = []
        
        # Check for dropped items
        if screen_key in self.dropped_items:
            cell_key = (tx, ty)
            if cell_key in self.dropped_items[screen_key]:
                items = self.dropped_items[screen_key][cell_key]
                for item_name, count in items.items():
                    name = ITEMS.get(item_name, {}).get('name', item_name)
                    if count > 1:
                        info_lines.append(f"{name} x{count}")
                    else:
                        info_lines.append(name)
        
        # Check for chest contents
        if self.current_screen and self.current_screen['grid'][ty][tx] == 'CHEST':
            chest_key = f"{screen_key}:{tx},{ty}"
            if chest_key in self.chest_contents and self.chest_contents[chest_key]:
                info_lines.append("-- Chest --")
                for item_name, count in self.chest_contents[chest_key].items():
                    name = ITEMS.get(item_name, {}).get('name', item_name)
                    if count > 1:
                        info_lines.append(f"{name} x{count}")
                    else:
                        info_lines.append(name)
        
        if not info_lines:
            return
        
        # Limit display to 8 items
        if len(info_lines) > 8:
            info_lines = info_lines[:7] + [f"...+{len(info_lines) - 7} more"]
        
        # Draw to the right of target cell
        info_x = tx * CELL_SIZE + CELL_SIZE + 8
        info_y = ty * CELL_SIZE
        line_height = 14
        
        # Keep on screen
        if info_x + 120 > SCREEN_WIDTH:
            info_x = tx * CELL_SIZE - 128
        
        for i, line in enumerate(info_lines):
            text = self.tiny_font.render(line, True, (255, 255, 255))
            # Small shadow for readability
            shadow = self.tiny_font.render(line, True, (0, 0, 0))
            self.screen.blit(shadow, (info_x + 1, info_y + i * line_height + 1))
            self.screen.blit(text, (info_x, info_y + i * line_height))
    
    def draw_quest_arrow(self):
        """Draw directional arrow to quest target"""
        quest = self.quests[self.active_quest]
        
        # If player is in a subscreen, always point to the exit
        if self.player.get('in_subscreen'):
            subscreen = self.subscreens.get(self.player.get('subscreen_key'))
            if subscreen:
                exit_pos = subscreen.get('exit', subscreen.get('entrance'))
                if exit_pos:
                    ex, ey = exit_pos
                    px, py = self.player['x'], self.player['y']
                    if px != ex or py != ey:
                        arrow_x = ex * CELL_SIZE + CELL_SIZE // 2
                        arrow_y = (ey - 1) * CELL_SIZE + CELL_SIZE // 2
                        quest_color = QUEST_TYPES.get(self.active_quest, {}).get('color', (200, 200, 200))
                        arrow_text = self.font.render("EXIT ↓", True, quest_color)
                        arrow_rect = arrow_text.get_rect(center=(arrow_x, arrow_y))
                        self.screen.blit(arrow_text, arrow_rect)
                    return
        
        # Determine target position
        target_screen_x, target_screen_y = None, None
        target_x, target_y = None, None
        
        if quest.target_entity_id:
            # Find entity
            if quest.target_entity_id in self.entities:
                entity = self.entities[quest.target_entity_id]
                target_screen_x, target_screen_y = entity.screen_x, entity.screen_y
                target_x, target_y = entity.x, entity.y
        elif quest.target_location:
            target_screen_x, target_screen_y = quest.target_location
            target_x, target_y = GRID_WIDTH // 2, GRID_HEIGHT // 2  # Center of zone
        elif quest.target_cell:
            target_screen_x, target_screen_y, target_x, target_y = quest.target_cell
        
        if target_screen_x is None:
            return
        
        # Calculate relative position
        player_sx, player_sy = self.player['screen_x'], self.player['screen_y']
        player_x, player_y = self.player['x'], self.player['y']
        
        # Calculate zone distance
        zone_dx = target_screen_x - player_sx
        zone_dy = target_screen_y - player_sy
        zone_distance = int((zone_dx**2 + zone_dy**2)**0.5)
        
        # Check if in same zone
        in_same_zone = (zone_dx == 0 and zone_dy == 0)
        
        # If in same zone, calculate cell distance
        if in_same_zone:
            cell_dx = target_x - player_x
            cell_dy = target_y - player_y
            cell_distance = int((cell_dx**2 + cell_dy**2)**0.5)
            
            # Position arrow 1 cell above target, pointing down
            arrow_x = target_x * CELL_SIZE + CELL_SIZE // 2
            arrow_y = (target_y - 1) * CELL_SIZE + CELL_SIZE // 2
            
            # Always point down at the target
            arrow_symbol = "v"
            
            distance_text = f"{cell_distance}"
        else:
            # Target is in different zone - calculate zone direction
            cell_dx = zone_dx * GRID_WIDTH
            cell_dy = zone_dy * GRID_HEIGHT
            
            # Calculate arrow position (at screen edge)
            arrow_x, arrow_y = SCREEN_WIDTH // 2, (SCREEN_HEIGHT - 60) // 2
            arrow_symbol = "○"
            
            # Determine direction
            if abs(cell_dx) > abs(cell_dy):
                if cell_dx > 0:
                    arrow_symbol = ">"
                    arrow_x = SCREEN_WIDTH - 40
                else:
                    arrow_symbol = "<"
                    arrow_x = 40
            else:
                if cell_dy > 0:
                    arrow_symbol = "v"
                    arrow_y = SCREEN_HEIGHT - 100
                else:
                    arrow_symbol = "^"
                    arrow_y = 40
            
            distance_text = f"{zone_distance}"
        
        # Use white color for arrow
        arrow_color = COLORS['WHITE']
        
        # Draw arrow - slightly larger font (32pt instead of 24pt)
        arrow_font = pygame.font.Font(None, 32)
        arrow_text = arrow_font.render(arrow_symbol, True, arrow_color)
        arrow_rect = arrow_text.get_rect(center=(arrow_x, arrow_y))
        self.screen.blit(arrow_text, arrow_rect)
        
        # Draw distance below arrow
        dist_render = self.tiny_font.render(distance_text, True, arrow_color)
        dist_rect = dist_render.get_rect(center=(arrow_x, arrow_y + 20))
        self.screen.blit(dist_render, dist_rect)
    
    def draw_paused(self):
        """Draw pause menu overlay"""
        self.draw_game()
        
        # Semi-transparent overlay
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        overlay.set_alpha(128)
        overlay.fill(COLORS['BLACK'])
        self.screen.blit(overlay, (0, 0))
        
        # Pause menu
        title = self.font.render("PAUSED", True, COLORS['YELLOW'])
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 250))
        
        options = [
            "P/ESC - Resume",
            "S - Save Game",
            "M - Main Menu"
        ]
        
        y = 330
        for option in options:
            text = self.small_font.render(option, True, COLORS['WHITE'])
            self.screen.blit(text, (SCREEN_WIDTH // 2 - text.get_width() // 2, y))
            y += 30

    def update_weather(self):
        """Update weather system - rain cycles"""
        self.weather_timer += 1
        
        # Start rain when weather cycle completes
        if self.weather_timer >= self.weather_cycle:
            self.weather_timer = 0
            self.weather_cycle = random.randint(RAIN_FREQUENCY_MIN, RAIN_FREQUENCY_MAX)
            self.is_raining = True
            self.rain_duration = random.randint(RAIN_DURATION_MIN, RAIN_DURATION_MAX)
            self.rain_timer = 0  # Reset rain timer
        
        # Increment rain timer and check if rain should end
        if self.is_raining:
            self.rain_timer += 1
            if self.rain_timer >= self.rain_duration:
                self.is_raining = False
                self.rain_timer = 0
    
    def update_day_night_cycle(self):
        """Update day/night cycle - equal day and night lengths"""
        self.day_night_timer += 1
        
        full_cycle = DAY_LENGTH + NIGHT_LENGTH
        
        # Wrap around at cycle length
        if self.day_night_timer >= full_cycle:
            self.day_night_timer = 0
        
        # Update night state (night after day completes)
        old_is_night = self.is_night
        self.is_night = self.day_night_timer >= DAY_LENGTH
        
        # Log day/night transitions
        if self.is_night and not old_is_night:
            print("Night falls...")
        elif not self.is_night and old_is_night:
            print("Dawn breaks...")
    
    def move_items_to_nearest_chest(self):
        """Gradually move dropped items to nearest chests"""
        # Only run every 10 seconds
        if self.tick % 600 != 0:
            return
        
        # Check zones near player
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']
        
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                zone_key = f"{player_x + dx},{player_y + dy}"
                
                if zone_key not in self.dropped_items or zone_key not in self.screens:
                    continue
                
                screen = self.screens[zone_key]
                dropped_in_zone = self.dropped_items[zone_key]
                
                if not dropped_in_zone:
                    continue
                
                # Find all chests in zone
                chests = []
                for y in range(GRID_HEIGHT):
                    for x in range(GRID_WIDTH):
                        if screen['grid'][y][x] == 'CHEST':
                            chests.append((x, y))
                
                if not chests:
                    continue  # No chests in zone
                
                # Move one random item toward nearest chest (5% chance per item pile)
                items_to_move = list(dropped_in_zone.keys())
                if items_to_move and random.random() < 0.05:
                    # Pick random item pile
                    pile_pos = random.choice(items_to_move)
                    items_in_pile = dropped_in_zone[pile_pos]
                    
                    if not items_in_pile:
                        continue
                    
                    # Find nearest chest
                    nearest_chest = min(chests, key=lambda c: abs(c[0] - pile_pos[0]) + abs(c[1] - pile_pos[1]))
                    
                    # Move one random item from pile
                    item_name = random.choice(list(items_in_pile.keys()))
                    
                    # Add to chest
                    chest_key = f"{zone_key}_{nearest_chest[0]}_{nearest_chest[1]}"
                    if chest_key not in self.chest_contents:
                        self.chest_contents[chest_key] = {}
                    
                    self.chest_contents[chest_key][item_name] = self.chest_contents[chest_key].get(item_name, 0) + 1
                    
                    # Remove from dropped items
                    items_in_pile[item_name] -= 1
                    if items_in_pile[item_name] <= 0:
                        del items_in_pile[item_name]
                    
                    # Clean up empty pile
                    if not items_in_pile:
                        del dropped_in_zone[pile_pos]
    
    def probabilistic_zone_updates(self):
        """Priority queue based zone updates. Zones scored by distance, staleness,
        connections, quests, and structures. Higher priority = updated first."""
        # Only update every 0.5 seconds
        if self.tick % UPDATE_FREQUENCY != 0:
            return
        
        # Update weather system every update cycle
        self.update_weather()
        
        # Update day/night cycle
        self.update_day_night_cycle()
        
        # Move dropped items to chests gradually
        self.move_items_to_nearest_chest()
        
        # Small chance to instantiate a new random zone
        if random.random() < NEW_ZONE_INSTANTIATE_CHANCE:
            range_x = random.randint(-20, 20)
            range_y = random.randint(-20, 20)
            new_zone_key = f"{range_x},{range_y}"
            if new_zone_key not in self.screens:
                self.generate_screen(range_x, range_y)
                self.instantiated_zones.add(new_zone_key)
        
        # Clean up invalid entity references every 10 seconds
        if self.tick % 600 == 0:
            self.cleanup_screen_entities()
        
        # Ensure zones around player are instantiated
        self.ensure_nearby_zones_exist()
        
        # Get priority-sorted zone list
        priority_queue = self.get_priority_sorted_zones()
        
        # Stats tracking for this update cycle
        _stats_zones = 0
        _stats_entities = 0
        _stats_cells = 0
        
        # Process zones in priority order
        zones_updated = 0
        total_entities_updated = 0
        total_cells_updated = 0
        
        # CRITICAL: Always update the player's zone first at full coverage.
        player_zone_key = f"{self.player['screen_x']},{self.player['screen_y']}"
        if self.player.get('in_subscreen') and self.player.get('subscreen_key'):
            player_zone_key = self.player['subscreen_key']
        
        # Build set of mandatory zones: player + 4 cardinal neighbors
        # These always get 100% update (cells + entities).
        psx, psy = self.player['screen_x'], self.player['screen_y']
        mandatory_zones = {player_zone_key}
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            nk = f"{psx + dx},{psy + dy}"
            if nk in self.screens:
                mandatory_zones.add(nk)
        # Also include structure zones connected to player zone
        if player_zone_key in self.zone_connections:
            for connected_key, *_ in self.zone_connections[player_zone_key]:
                if connected_key in self.screens:
                    mandatory_zones.add(connected_key)
        
        # Update all mandatory zones at 100% coverage
        for mz_key in mandatory_zones:
            if mz_key in self.structure_zones:
                self.update_structure_zone(mz_key, 1.0, 1.0)
            elif self.is_overworld_zone(mz_key):
                parts = mz_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), 1.0, 1.0)
            else:
                continue
            zones_updated += 1
            ent_count = len(self.screen_entities.get(mz_key, []))
            total_entities_updated += ent_count
            total_cells_updated += GRID_WIDTH * GRID_HEIGHT
        
        # Process remaining zones from priority queue with position-based falloff
        queue_position = 0
        for priority, zone_key in priority_queue:
            if zones_updated >= MAX_ZONES_PER_UPDATE:
                break
            
            # Skip already-updated mandatory zones
            if zone_key in mandatory_zones:
                continue
            
            queue_position += 1
            
            # Update chance = (100 - queue_position)%, minimum 5%
            update_chance = max(0.05, (100 - queue_position) / 100.0)
            if random.random() > update_chance:
                continue
            
            # Cell/entity coverage = same percentage as update chance
            coverage = update_chance
            
            if zone_key in self.structure_zones:
                self.update_structure_zone(zone_key, coverage, coverage)
            elif self.is_overworld_zone(zone_key):
                parts = zone_key.split(',')
                self.update_zone_with_coverage(int(parts[0]), int(parts[1]), coverage, coverage)
            else:
                continue
            
            zones_updated += 1
            ent_count = len(self.screen_entities.get(zone_key, []))
            total_entities_updated += int(ent_count * coverage)
            total_cells_updated += int(GRID_WIDTH * GRID_HEIGHT * coverage)
        
        # ── Update cycle stats (printed every 30 seconds) ──
        if self.tick % 1800 == 0:
            total_entities = len(self.entities)
            total_zones = len(self.screens)
            print(f"[UpdateCycle] tick={self.tick} "
                  f"zones={zones_updated}/{total_zones} "
                  f"entities={total_entities_updated}/{total_entities} "
                  f"cells={total_cells_updated} "
                  f"mandatory={len(mandatory_zones)} "
                  f"player_zone={player_zone_key}"
                  f"({len(self.screen_entities.get(player_zone_key, []))}ent) "
                  f"queue={len(priority_queue)}")
    
    def update_structure_zone(self, struct_zone_key, cell_coverage, entity_coverage):
        """Update a structure zone (cave/house interior) like a regular zone."""
        if struct_zone_key not in self.screens:
            return
        
        screen = self.screens[struct_zone_key]
        
        # Update last update time
        self.screen_last_update[struct_zone_key] = self.tick
        
        # Cell growth/decay
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]
                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['grows_to'])
                    elif 'degrades_to' in cell_info and random.random() < cell_info.get('degrade_rate', 0):
                        self.set_grid_cell(screen, x, y, cell_info['degrades_to'])
        
        # Entity updates
        entity_list = self.screen_entities.get(struct_zone_key, [])
        if not entity_list:
            # Fall back to legacy subscreen entities
            entity_list = self.subscreen_entities.get(struct_zone_key, [])
        
        # AUTOPILOT SAFETY: clear freeze flags (same as overworld zone update)
        if getattr(self, 'autopilot', False):
            for eid in list(entity_list):
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False
        
        entities_to_remove = []
        for entity_id in list(entity_list):
            if entity_id not in self.entities:
                continue
            
            entity = self.entities[entity_id]
            entity.decay_stats()
            entity.regenerate_health(1.0)
            
            if not entity.is_alive():
                entities_to_remove.append(entity_id)
                continue
            
            # AI update
            self.update_entity_ai(entity_id, entity)
        
        for entity_id in entities_to_remove:
            self.remove_entity(entity_id)
    
    def update_zone_with_coverage(self, zone_x, zone_y, cell_coverage, entity_coverage):
        """Update a zone - when a zone is selected for update, update ALL its features"""
        zone_key = f"{zone_x},{zone_y}"
        
        if zone_key not in self.screens:
            return
        
        screen = self.screens[zone_key]
        
        # Update staleness tracker for priority system
        self.screen_last_update[zone_key] = self.tick
        
        # === ZONE-LEVEL UPDATES (always run when zone is selected) ===
        
        # Check for threats in zone (hostiles and faction conflicts) - FIRST so Warriors can react
        self.check_zone_threats(zone_key)
        
        # Check for raid events
        self.check_raid_event(zone_key)
        
        # Check for cave hostile spawns
        self.check_cave_spawn_hostile(zone_key)
        
        # Check for night skeleton spawns
        self.check_night_skeleton_spawn(zone_key)
        
        # Check for termite spawns (prefer forests/plains, near trees)
        self.check_termite_spawn(zone_key)
        
        # Decay dropped items
        self.decay_dropped_items(zone_x, zone_y)
        
        # Consolidate nearby dropped items into bags
        self.consolidate_dropped_items(zone_key)
        
        # === CELL UPDATES ===
        
        # Apply rain effects if raining
        if self.is_raining:
            distance = abs(zone_x - self.player['screen_x']) + abs(zone_y - self.player['screen_y'])
            if distance <= 2:  # Rain affects nearby screens
                self.apply_rain(zone_x, zone_y)
        
        # Apply cellular automata (water spreading, etc.)
        self.apply_cellular_automata(zone_x, zone_y)
        
        # Cell growth/decay - always update all cells when zone is selected
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                if self.is_cell_enchanted(x, y, zone_key):
                    continue
                
                cell = screen['grid'][y][x]
                if cell in CELL_TYPES:
                    cell_info = CELL_TYPES[cell]
                    
                    # Growth
                    if 'grows_to' in cell_info and random.random() < cell_info.get('growth_rate', 0):
                        screen['grid'][y][x] = cell_info['grows_to']
                    # Decay
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
                            
                            # Check if touching structures
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
                        old_cell = cell
                        screen['grid'][y][x] = cell_info['degrades_to']
                        
                        # Special handling for house destruction - drop loot
                        if old_cell == 'HOUSE':
                            self.process_house_destruction(x, y, zone_key)
        
        # === BIOME REVERSION & SPREADING ===
        # Foreign cells decay toward the biome's base cell type
        # Native cells have a small chance to spread to adjacent non-native cells
        biome = screen.get('biome', 'FOREST')
        biome_base_map = {
            'FOREST': 'GRASS', 'PLAINS': 'GRASS', 'DESERT': 'SAND',
            'MOUNTAINS': 'DIRT', 'TUNDRA': 'DIRT', 'SWAMP': 'DIRT',
        }
        base_cell = biome_base_map.get(biome, 'GRASS')
        
        # Define which cells are "native" to each biome and can spread
        biome_native = {
            'FOREST': {'GRASS', 'DIRT', 'TREE1', 'TREE2', 'FLOWER'},
            'PLAINS': {'GRASS', 'DIRT', 'FLOWER'},
            'DESERT': {'SAND', 'DIRT'},
            'MOUNTAINS': {'DIRT', 'STONE', 'GRASS'},
            'TUNDRA': {'DIRT', 'STONE'},
            'SWAMP': {'DIRT', 'WATER', 'GRASS'},
        }
        native_cells = biome_native.get(biome, {'GRASS', 'DIRT'})
        
        # Cells that should NOT be overwritten by spreading (structures, placed items)
        protected_cells = {'HOUSE', 'CAVE', 'MINESHAFT', 'CAMP', 'CHEST', 'WALL',
                          'COBBLESTONE', 'WATER', 'DEEP_WATER', 'WOOD', 'PLANKS',
                          'FLOOR_WOOD', 'CAVE_FLOOR', 'CAVE_WALL', 'STAIRS_UP', 
                          'STAIRS_DOWN', 'HIDDEN_CAVE', 'SOIL', 'CARROT1', 'CARROT2', 'CARROT3'}
        
        # Foreign cells that should revert to base cell
        foreign_revert = {
            'DESERT': {'GRASS', 'TREE1', 'TREE2', 'FLOWER', 'DIRT'},
            'FOREST': {'SAND'},
            'PLAINS': {'SAND'},
            'MOUNTAINS': {'SAND'},
            'TUNDRA': {'SAND', 'GRASS'},
            'SWAMP': {'SAND'},
        }
        revert_targets = foreign_revert.get(biome, set())
        
        for y in range(1, GRID_HEIGHT - 1):
            for x in range(1, GRID_WIDTH - 1):
                cell = screen['grid'][y][x]
                
                # 1. Foreign cell reversion: 0.3% chance per update
                if cell in revert_targets and random.random() < 0.003:
                    screen['grid'][y][x] = base_cell
                    continue
                
                # 2. Native cell spreading: 0.5% chance per update
                if cell in native_cells and random.random() < 0.005:
                    # Pick a random adjacent cell
                    dx, dy = random.choice([(1,0), (-1,0), (0,1), (0,-1)])
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < GRID_WIDTH and 0 <= ny < GRID_HEIGHT:
                        neighbor = screen['grid'][ny][nx]
                        if neighbor not in protected_cells and neighbor not in native_cells:
                            screen['grid'][ny][nx] = cell
        
        # === ENTITY UPDATES (always update all entities when zone is selected) ===
        
        # AUTOPILOT SAFETY: Before updating any entities, force-clear every freeze
        # flag in the zone.
        if getattr(self, 'autopilot', False) and zone_key in self.screen_entities:
            for eid in self.screen_entities[zone_key]:
                if eid in self.entities:
                    e = self.entities[eid]
                    if getattr(e, 'idle_timer', 0) > 0:
                        e.idle_timer = 0
                        e.is_idle = False
            self.inspected_npc = None
        
        if zone_key in self.screen_entities:
            entities_to_remove = []
            
            for entity_id in list(self.screen_entities[zone_key]):
                if entity_id not in self.entities:
                    continue
                
                entity = self.entities[entity_id]
                
                # Assign factions to warriors without factions (check every 5 seconds)
                if self.tick % 300 == 0 and entity.type == 'WARRIOR' and not entity.faction:
                    self.assign_warrior_faction(entity, zone_key)
                
                # Chance for warrior/commander to defect to a different faction (0.1% per update, requires 3+ warriors)
                # Only Kings cannot defect
                if entity.type in ['WARRIOR', 'COMMANDER'] and entity.faction:
                    # Count warriors in zone
                    warrior_count = sum(1 for eid in self.screen_entities.get(zone_key, [])
                                      if eid in self.entities and self.entities[eid].type in ['WARRIOR', 'COMMANDER', 'KING'])
                    
                    if warrior_count >= 3 and random.random() < 0.001:
                        # Pick a different faction if any exist
                        available_factions = [f for f in self.factions.keys() if f != entity.faction]
                        if available_factions:
                            old_faction = entity.faction
                            new_faction = random.choice(available_factions)
                            
                            # Remove from old faction
                            if old_faction in self.factions and entity_id in self.factions[old_faction]['warriors']:
                                self.factions[old_faction]['warriors'].remove(entity_id)
                            
                            # Add to new faction
                            entity.faction = new_faction
                            if new_faction not in self.factions:
                                self.factions[new_faction] = {'warriors': [], 'zones': set()}
                            if entity_id not in self.factions[new_faction]['warriors']:
                                self.factions[new_faction]['warriors'].append(entity_id)
                            
                            print(f"{entity.name} defected from {old_faction} to {new_faction}!")
                
                # Age entities during background updates (every 600 ticks = ~1 year, slower aging)
                if self.tick % 600 == 0 and entity.type != 'SKELETON':
                    entity.age += 1
                
                # Decay stats (now includes old age damage via max_age check)
                entity.decay_stats()
                
                # Skeleton daylight damage - skeletons burn in daylight
                if entity.type == 'SKELETON' and not self.is_night:
                    entity.health -= SKELETON_DAYLIGHT_DAMAGE
                    if entity.health <= 0:
                        entity.health = 0
                        entity.killed_by = 'sunlight'
                
                # Regenerate health
                heal_boost = 1.0
                if not entity.props.get('hostile', False):
                    for dx in range(-3, 4):
                        for dy in range(-3, 4):
                            check_x = entity.x + dx
                            check_y = entity.y + dy
                            if 0 <= check_x < GRID_WIDTH and 0 <= check_y < GRID_HEIGHT:
                                cell = screen['grid'][check_y][check_x]
                                if cell == 'CAMP':
                                    heal_boost = CAMP_HEALING_MULTIPLIER
                                    break
                                elif cell == 'HOUSE':
                                    heal_boost = HOUSE_HEALING_MULTIPLIER
                                    break
                        if heal_boost > 1.0:
                            break
                
                entity.regenerate_health(heal_boost)
                
                if not entity.is_alive():
                    entities_to_remove.append(entity_id)
                    continue
                
                # Full AI update
                self.update_entity_ai(entity_id, entity)
            
            for entity_id in entities_to_remove:
                self.remove_entity(entity_id)
            
            # Entity-item interactions: pickup dropped items, chest interaction, inventory overflow
            if zone_key in self.screens and self.tick % 60 == 0:
                grid = self.screens[zone_key]['grid']
                for entity_id in list(self.screen_entities.get(zone_key, [])):
                    if entity_id not in self.entities:
                        continue
                    entity = self.entities[entity_id]
                    if not entity.is_alive():
                        continue
                    
                    ex, ey = entity.x, entity.y
                    
                    # Pick up dropped items at entity position AND adjacent cells
                    if zone_key in self.dropped_items:
                        for dx, dy in [(0,0), (1,0), (-1,0), (0,1), (0,-1)]:
                            px, py = ex + dx, ey + dy
                            cell_key = (px, py)
                            if cell_key in self.dropped_items[zone_key]:
                                for item_name, count in self.dropped_items[zone_key][cell_key].items():
                                    entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                                del self.dropped_items[zone_key][cell_key]
                    
                    # Pick up from adjacent chest
                    for dx, dy in [(0,0), (1,0), (-1,0), (0,1), (0,-1)]:
                        cx, cy = ex + dx, ey + dy
                        if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                            if grid[cy][cx] == 'CHEST':
                                chest_key = f"{zone_key}:{cx},{cy}"
                                if chest_key in self.chest_contents:
                                    contents = self.chest_contents[chest_key]
                                    for item_name, count in contents.items():
                                        entity.inventory[item_name] = entity.inventory.get(item_name, 0) + count
                                    self.chest_contents[chest_key] = {}
                                    # Empty chest degrades
                                    grid[cy][cx] = 'WOOD'
                                break
                    
                    # Inventory overflow: if >10 unique item types, place chest
                    if len(entity.inventory) > 10:
                        # Find adjacent walkable cell for chest
                        for dx, dy in [(1,0), (-1,0), (0,1), (0,-1)]:
                            cx, cy = ex + dx, ey + dy
                            if 0 <= cx < GRID_WIDTH and 0 <= cy < GRID_HEIGHT:
                                cell = grid[cy][cx]
                                if not CELL_TYPES.get(cell, {}).get('solid', False):
                                    grid[cy][cx] = 'CHEST'
                                    chest_key = f"{zone_key}:{cx},{cy}"
                                    # Move half of inventory to chest
                                    items_list = list(entity.inventory.items())
                                    half = len(items_list) // 2
                                    chest_items = {}
                                    for item_name, count in items_list[:half]:
                                        chest_items[item_name] = count
                                    self.chest_contents[chest_key] = chest_items
                                    for item_name in chest_items:
                                        del entity.inventory[item_name]
                                    break
        
        # Entity consolidation: when >2 of the same base type, merge pairs into _double
        if zone_key in self.screen_entities and self.tick % 300 == 0:
            type_counts = {}
            for eid in list(self.screen_entities.get(zone_key, [])):
                if eid not in self.entities:
                    continue
                e = self.entities[eid]
                if not e.is_alive() or e.props.get('is_autopilot_proxy'):
                    continue
                base = e.type.replace('_double', '')
                if base not in type_counts:
                    type_counts[base] = []
                type_counts[base].append(eid)
            
            for base_type, eids in type_counts.items():
                # Count singles (non-double) of this type
                singles = [eid for eid in eids 
                           if self.entities[eid].type == base_type]
                if len(singles) > 2:
                    # Merge pairs: keep the higher-level one, remove the other
                    singles.sort(key=lambda eid: self.entities[eid].level, reverse=True)
                    while len(singles) > 2:
                        if len(singles) < 2:
                            break
                        keep_id = singles.pop(0)
                        remove_id = singles.pop(0)
                        keeper = self.entities[keep_id]
                        removed = self.entities[remove_id]
                        # Merge: upgrade to _double, combine inventory, boost stats
                        keeper.type = f"{base_type}_double"
                        keeper.max_health = int(keeper.max_health * 1.5)
                        keeper.health = min(keeper.health + removed.health, keeper.max_health)
                        keeper.strength = int(keeper.strength * 1.3)
                        for item, count in removed.inventory.items():
                            keeper.inventory[item] = keeper.inventory.get(item, 0) + count
                        self.remove_entity(remove_id)
        
        # Zone-wide faction change: rare chance all warriors change to new faction (0.05% per update, requires 3+ warriors)
        if zone_key in self.screen_entities and random.random() < 0.0005:
            warriors_in_zone = []
            for entity_id in self.screen_entities[zone_key]:
                if entity_id in self.entities:
                    entity = self.entities[entity_id]
                    if entity.type == 'WARRIOR' and entity.faction:
                        warriors_in_zone.append((entity_id, entity))
            
            if len(warriors_in_zone) >= 3:  # Need at least 3 warriors for zone change
                # Create new faction
                new_faction = self.generate_faction_name()
                old_factions = set()
                
                # Convert all warriors to new faction
                for warrior_id, warrior in warriors_in_zone:
                    old_faction = warrior.faction
                    old_factions.add(old_faction)
                    
                    # Remove from old faction
                    if old_faction in self.factions and warrior_id in self.factions[old_faction]['warriors']:
                        self.factions[old_faction]['warriors'].remove(warrior_id)
                    
                    # Add to new faction
                    warrior.faction = new_faction
                    if new_faction not in self.factions:
                        self.factions[new_faction] = {'warriors': [], 'zones': set()}
                    if warrior_id not in self.factions[new_faction]['warriors']:
                        self.factions[new_faction]['warriors'].append(warrior_id)
                
                print(f"ZONE REVOLUTION in [{zone_key}]! {len(warriors_in_zone)} warriors formed {new_faction} faction!")
        
        # Faction raid: rare chance for raid on high population zones (0.1% chance per update, requires 3+ warriors exist)
        if zone_key in self.screen_entities and random.random() < 0.001:
            # Count total warriors globally
            total_warriors = sum(len(f.get('warriors', [])) for f in self.factions.values())
            
            if total_warriors >= 3:
                # Count human NPCs in this zone
                human_npc_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'WARRIOR']
                human_count = 0
                for entity_id in self.screen_entities[zone_key]:
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        base_type = entity.type.replace('_double', '')
                        if base_type in human_npc_types:
                            human_count += 1
                
                # High population zones (8+ NPCs) can be raided
                if human_count >= 8 and self.factions:
                    # Pick a random faction to send raiders
                    raiding_faction = random.choice(list(self.factions.keys()))
                    
                    # Spawn 3 warriors of that faction
                    raiders_spawned = 0
                    for _ in range(3):
                        spawn_x = random.randint(3, GRID_WIDTH - 4)
                        spawn_y = random.randint(3, GRID_HEIGHT - 4)
                        
                        if zone_key in self.screens:
                            screen = self.screens[zone_key]
                            if not CELL_TYPES[screen['grid'][spawn_y][spawn_x]].get('solid', False):
                                # Create raiding warrior
                                warrior = Entity('WARRIOR', spawn_x, spawn_y, zone_x, zone_y, level=random.randint(2, 4))
                                warrior.faction = raiding_faction
                                warrior.home_zone = None  # Raiders don't return home
                                
                                warrior_id = self.next_entity_id
                                self.next_entity_id += 1
                                self.entities[warrior_id] = warrior
                                self.screen_entities[zone_key].append(warrior_id)
                                
                                # Add to faction tracking
                                if raiding_faction not in self.factions:
                                    self.factions[raiding_faction] = {'warriors': [], 'zones': set()}
                                if warrior_id not in self.factions[raiding_faction]['warriors']:
                                    self.factions[raiding_faction]['warriors'].append(warrior_id)
                                
                                raiders_spawned += 1
                    
                    if raiders_spawned > 0:
                        print(f"FACTION RAID in [{zone_key}]! {raiders_spawned} {raiding_faction} warriors invade!")
        
        # IMPROVED SPAWNING: Check every 5 seconds, spawn based on population
        if not hasattr(self, 'zone_last_spawn_check'):
            self.zone_last_spawn_check = {}
        
        # Count NPCs and track types
        npc_count = 0
        types_in_zone = set()
        if zone_key in self.screen_entities:
            for entity_id in self.screen_entities[zone_key]:
                if entity_id in self.entities:
                    npc_count += 1
                    types_in_zone.add(self.entities[entity_id].type)
        
        # Check every 5 seconds (300 ticks)
        if zone_key not in self.zone_last_spawn_check:
            self.zone_last_spawn_check[zone_key] = 0
        
        if self.tick - self.zone_last_spawn_check[zone_key] >= 300:
            self.zone_last_spawn_check[zone_key] = self.tick
            
            # Spawn chance based on population
            if npc_count == 0:
                spawn_chance = 0.8  # 80% for empty zones
            elif npc_count < 3:
                spawn_chance = 0.4  # 40% for 1-2 entities
            elif npc_count < 5:
                spawn_chance = 0.2  # 20% for 3-4 entities
            else:
                spawn_chance = 0.05  # 5% for established zones
            
            if random.random() < spawn_chance:
                biome = screen.get('biome', 'FOREST')
                
                # Priority: TRADER/GUARD if missing
                spawned = False
                if 'TRADER' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='TRADER')
                    if spawned:
                        print(f"[SPAWN] TRADER spawned in [{zone_key}] (pop: {npc_count})")
                elif 'GUARD' not in types_in_zone:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome, force_type='GUARD')
                    if spawned:
                        print(f"[SPAWN] GUARD spawned in [{zone_key}] (pop: {npc_count})")
                
                # Otherwise spawn random entity
                if not spawned:
                    spawned = self.spawn_single_entity_at_entrance(zone_x, zone_y, biome)
                    if spawned:
                        print(f"[SPAWN] Entity spawned in [{zone_key}] (pop: {npc_count})")
            
            # NPC role conversion: Traders and Guards may settle
            # Enhanced rate (25%) if zone needs specific roles, otherwise 5%
            if zone_key in self.screen_entities:
                has_farmer = False
                has_lumberjack = False
                has_miner = False
                traders = []
                guards = []
                
                for entity_id in self.screen_entities[zone_key]:
                    if entity_id in self.entities:
                        entity = self.entities[entity_id]
                        if entity.type == 'FARMER':
                            has_farmer = True
                        elif entity.type == 'LUMBERJACK':
                            has_lumberjack = True
                        elif entity.type == 'MINER':
                            has_miner = True
                        elif entity.type == 'TRADER' or entity.type == 'TRADER_double':
                            traders.append((entity_id, entity))
                        elif entity.type == 'GUARD' or entity.type == 'GUARD_double':
                            guards.append((entity_id, entity))
                
                # Determine settlement rate based on missing roles
                missing_roles = not has_farmer or not has_lumberjack or not has_miner
                settlement_rate = ENHANCED_SETTLEMENT_RATE if missing_roles else 0.05
                
                # Only proceed if settlement roll succeeds
                if random.random() < settlement_rate:
                    # Merge traders if more than 2 in zone
                    if len(traders) > 2:
                        # Merge the first two
                        trader1_id, trader1 = traders[0]
                        trader2_id, trader2 = traders[1]
                        if trader1.can_merge_with(trader2):
                            trader1.merge_with(trader2)
                            del self.entities[trader2_id]
                            print(f"Two traders merged into {trader1.type} at [{zone_key}]")
                    
                    # Merge guards if more than 2 in zone
                    if len(guards) > 2:
                        # Merge the first two
                        guard1_id, guard1 = guards[0]
                        guard2_id, guard2 = guards[1]
                        if guard1.can_merge_with(guard2):
                            guard1.merge_with(guard2)
                            del self.entities[guard2_id]
                            print(f"Two guards merged into {guard1.type} at [{zone_key}]")
                    
                    # Convert traders to needed roles
                    if traders:
                        trader_id, trader = random.choice(traders)
                        
                        if not has_farmer and random.random() < 0.5:
                            old_name = trader.name
                            trader.type = 'FARMER'
                            trader.props = ENTITY_TYPES['FARMER']
                            print(f"{old_name} (Trader) settled as a farmer at [{zone_key}]")
                        elif not has_lumberjack and random.random() < 0.5:
                            old_name = trader.name
                            trader.type = 'LUMBERJACK'
                            trader.props = ENTITY_TYPES['LUMBERJACK']
                            print(f"{old_name} (Trader) settled as a lumberjack at [{zone_key}]")
                        elif not has_miner:
                            old_name = trader.name
                            trader.type = 'MINER'
                            trader.props = ENTITY_TYPES['MINER']
                            print(f"{old_name} (Trader) settled as a miner at [{zone_key}]")
                    
                    # Convert guards to needed roles (prefer farmer/miner)
                    if guards:
                        guard_id, guard = random.choice(guards)
                        
                        if not has_farmer and random.random() < 0.5:
                            old_name = guard.name
                            guard.type = 'FARMER'
                            guard.props = ENTITY_TYPES['FARMER']
                            print(f"{old_name} (Guard) settled as a farmer at [{zone_key}]")
                        elif not has_miner and random.random() < 0.5:
                            old_name = guard.name
                            guard.type = 'MINER'
                            guard.props = ENTITY_TYPES['MINER']
                            print(f"{old_name} (Guard) settled as a miner at [{zone_key}]")
            
            # Commander and king promotions (check every 10 seconds)
            if self.tick % 600 == 0:
                self.promote_to_commander(zone_key)
                self.promote_to_king()
                self.recruit_to_hostile_faction(zone_key)
    
    def update_single_cell(self, screen_x, screen_y, x, y):
        """Apply cellular automata rules to a single cell"""
        key = f"{screen_x},{screen_y}"
        if key not in self.screens:
            return
        
        screen = self.screens[key]
        cell = screen['grid'][y][x]
        
        if cell in ['WALL', 'HOUSE', 'CAVE']:
            return
        
        if self.is_cell_enchanted(x, y, key):
            return
        
        neighbors = self.get_neighbors(x, y, key)
        if not neighbors:
            return
        
        # Count neighbor types
        water_count = self.count_cell_type(neighbors, 'WATER')
        deep_water_count = self.count_cell_type(neighbors, 'DEEP_WATER')
        dirt_count = self.count_cell_type(neighbors, 'DIRT')
        grass_count = self.count_cell_type(neighbors, 'GRASS')
        tree_count = self.count_cell_type(neighbors, 'TREE')
        sand_count = self.count_cell_type(neighbors, 'SAND')
        flower_count = self.count_cell_type(neighbors, 'FLOWER')
        
        total_water = water_count + deep_water_count
        
        # Apply same rules as apply_cellular_automata but for single cell
        new_cell = cell
        
        if cell == 'DIRT' and total_water >= 2:
            if random.random() < DIRT_TO_GRASS_RATE:
                new_cell = 'GRASS'
        elif cell == 'GRASS' and total_water == 0:
            if random.random() < GRASS_TO_DIRT_RATE:
                new_cell = 'DIRT'
        elif cell == 'DIRT' and total_water == 0 and (sand_count >= 2 or grass_count == 0):
            if random.random() < DIRT_TO_SAND_RATE:
                new_cell = 'SAND'
        elif cell == 'GRASS' and 1 <= tree_count <= 2 and total_water >= 1:
            if random.random() < TREE_GROWTH_RATE:
                new_cell = 'TREE1'
        elif cell == 'SAND' and total_water >= 2:
            if random.random() < SAND_RECLAIM_RATE:
                new_cell = 'DIRT'
        elif cell == 'WATER' and water_count >= 4:
            if random.random() < DEEP_WATER_FORM_RATE:
                new_cell = 'DEEP_WATER'
        elif cell == 'DEEP_WATER' and (water_count + deep_water_count) < 2:
            if random.random() < DEEP_WATER_EVAPORATE_RATE:
                new_cell = 'WATER'
        elif cell == 'WATER' and total_water <= 1:
            if random.random() < WATER_TO_DIRT_RATE:
                new_cell = 'DIRT'
        elif cell == 'DIRT' and total_water >= 3:
            if random.random() < FLOODING_RATE:
                new_cell = 'WATER'
        elif cell == 'GRASS' and flower_count >= 1 and flower_count <= 2 and total_water >= 1:
            if random.random() < FLOWER_SPREAD_RATE:
                new_cell = 'FLOWER'
        elif cell == 'FLOWER' and (flower_count >= 4 or total_water == 0):
            if random.random() < FLOWER_DECAY_RATE:
                new_cell = 'GRASS'
        elif cell.startswith('TREE') and tree_count >= 4:
            if random.random() < TREE_DECAY_RATE:
                new_cell = 'GRASS'
        
        # BIOME SPREADING: Base terrain cells have a very small chance to spread
        # This allows biomes to slowly morph over time
        if new_cell == cell:  # Only if no other rule applied
            base_terrain_cells = ['GRASS', 'SAND', 'SNOW', 'DIRT']
            if cell in base_terrain_cells:
                # Very small chance (0.1%) to spread to adjacent cell
                if random.random() < 0.001:
                    # Pick a random adjacent cell
                    adjacent_coords = []
                    for dy in range(-1, 2):
                        for dx in range(-1, 2):
                            if dx == 0 and dy == 0:
                                continue
                            adj_x = x + dx
                            adj_y = y + dy
                            if 0 <= adj_x < GRID_WIDTH and 0 <= adj_y < GRID_HEIGHT:
                                adjacent_coords.append((adj_x, adj_y))
                    
                    if adjacent_coords:
                        target_x, target_y = random.choice(adjacent_coords)
                        target_cell = screen['grid'][target_y][target_x]
                        
                        # Can spread to other base terrain (not structures or special cells)
                        if target_cell in base_terrain_cells and target_cell != cell:
                            screen['grid'][target_y][target_x] = cell
        
        if new_cell != cell:
            screen['grid'][y][x] = new_cell
    
    def ensure_nearby_zones_exist(self):
        """Ensure zones around player are generated"""
        player_x = self.player['screen_x']
        player_y = self.player['screen_y']
        
        # Generate zones in 3x3 grid around player
        for dx in range(-4, 4):
            for dy in range(-4, 4):
                zone_x = player_x + dx
                zone_y = player_y + dy
                zone_key = f"{zone_x},{zone_y}"
                
                if zone_key not in self.screens:
                    self.generate_screen(zone_x, zone_y)
                
                self.instantiated_zones.add(zone_key)
    
    
    
    def loreEngine(self, quest):
        """Generate or find quest target for a quest.
        Quest targets are matched to player level (equal to +2 above)."""
        quest_type = quest.quest_type
        quest_info = QUEST_TYPES[quest_type]
        player_level = self.player.get('level', 1)
        min_level = player_level
        max_level = player_level + 2
        
        # Clear any existing target
        quest.clear_target()
        
        player_sx = self.player['screen_x']
        player_sy = self.player['screen_y']
        player_zone = f"{player_sx},{player_sy}"
        
        # For HUNT quests - find hostile NPC near player level
        if quest_type == 'HUNT':
            hostile_entities = []
            for entity_id, entity in self.entities.items():
                if entity.props.get('hostile') and not entity.is_dead:
                    if min_level <= entity.level <= max_level:
                        hostile_entities.append(entity_id)
            
            # If no level-matched hostiles, accept any hostile
            if not hostile_entities:
                for entity_id, entity in self.entities.items():
                    if entity.props.get('hostile') and not entity.is_dead:
                        hostile_entities.append(entity_id)
            
            if hostile_entities:
                # Prefer targets not in current zone
                offscreen = [eid for eid in hostile_entities 
                            if f"{self.entities[eid].screen_x},{self.entities[eid].screen_y}" != player_zone]
                target_id = random.choice(offscreen if offscreen else hostile_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.type}"
                if entity.name:
                    info = f"L{entity.level} {entity.name} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True
            else:
                # Spawn a hostile in a distant zone at player level
                distant_zones = []
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if abs(dx) + abs(dy) >= 2:
                            distant_zones.append((player_sx + dx, player_sy + dy))
                
                if distant_zones:
                    target_sx, target_sy = random.choice(distant_zones)
                    screen_key = f"{target_sx},{target_sy}"
                    if screen_key not in self.screens:
                        self.generate_screen(target_sx, target_sy)
                    hostile_types = ['GOBLIN', 'BANDIT', 'WOLF', 'BAT']
                    hostile_type = random.choice(hostile_types)
                    entity_id = self.spawn_quest_entity(hostile_type, target_sx, target_sy,
                                                        random.randint(5, GRID_WIDTH-5),
                                                        random.randint(5, GRID_HEIGHT-5))
                    if entity_id:
                        # Set level to match player
                        self.entities[entity_id].level = random.randint(min_level, max_level)
                        entity = self.entities[entity_id]
                        info = f"L{entity.level} {entity.type}"
                        quest.set_target('entity', entity_id, info)
                        quest.target_zone = screen_key
                        return True
        
        # For SLAY quests - find specific enemy type near player level
        elif quest_type == 'SLAY':
            target_types = quest_info['target_types']
            target_entity_type = random.choice(target_types)
            
            matching_entities = []
            for entity_id, entity in self.entities.items():
                if entity.type == target_entity_type and not entity.is_dead:
                    if min_level <= entity.level <= max_level:
                        matching_entities.append(entity_id)
            
            # Fallback: any level
            if not matching_entities:
                for entity_id, entity in self.entities.items():
                    if entity.type == target_entity_type and not entity.is_dead:
                        matching_entities.append(entity_id)
            
            if matching_entities:
                target_id = random.choice(matching_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.type}"
                if entity.name:
                    info = f"L{entity.level} {entity.name} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True
            else:
                distant_zones = []
                for dx in range(-3, 4):
                    for dy in range(-3, 4):
                        if abs(dx) + abs(dy) >= 2:
                            distant_zones.append((player_sx + dx, player_sy + dy))
                
                if distant_zones:
                    target_sx, target_sy = random.choice(distant_zones)
                    screen_key = f"{target_sx},{target_sy}"
                    if screen_key not in self.screens:
                        self.generate_screen(target_sx, target_sy)
                    entity_id = self.spawn_quest_entity(target_entity_type, target_sx, target_sy,
                                                        random.randint(5, GRID_WIDTH-5),
                                                        random.randint(5, GRID_HEIGHT-5))
                    if entity_id:
                        self.entities[entity_id].level = random.randint(min_level, max_level)
                        entity = self.entities[entity_id]
                        info = f"L{entity.level} {entity.type}"
                        quest.set_target('entity', entity_id, info)
                        quest.target_zone = screen_key
                        return True
        
        # For EXPLORE quests - find specific location
        elif quest_type == 'EXPLORE':
            target_types = quest_info['target_types']
            target_cell_type = random.choice(target_types)
            
            found_locations = []
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue  # Skip current zone
                sx, sy = map(int, screen_key.split(','))
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell == target_cell_type:
                            found_locations.append((sx, sy, x, y))
            
            if found_locations:
                # Pick closest
                found_locations.sort(key=lambda loc: abs(loc[0] - player_sx) + abs(loc[1] - player_sy))
                target_loc = found_locations[0]
                info = f"{target_cell_type} at zone ({target_loc[0]},{target_loc[1]})"
                quest.set_target('cell', target_loc, info)
                quest.target_zone = f"{target_loc[0]},{target_loc[1]}"
                return True
        
        # For GATHER quests - find resource location
        elif quest_type == 'GATHER':
            target_types = quest_info['target_types']
            target_cell_type = random.choice(target_types)
            
            if target_cell_type == 'TREE':
                search_types = ['TREE1', 'TREE2']
            else:
                search_types = [target_cell_type]
            
            found_resources = []
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue
                sx, sy = map(int, screen_key.split(','))
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in search_types:
                            found_resources.append((sx, sy, x, y))
            
            if found_resources:
                found_resources.sort(key=lambda loc: abs(loc[0] - player_sx) + abs(loc[1] - player_sy))
                target_loc = found_resources[0]
                info = f"{target_cell_type} at zone ({target_loc[0]},{target_loc[1]})"
                quest.set_target('cell', target_loc, info)
                quest.target_zone = f"{target_loc[0]},{target_loc[1]}"
                return True
        
        # For RESCUE quests - find friendly NPC
        elif quest_type == 'RESCUE':
            target_types = quest_info['target_types']
            target_entity_type = random.choice(target_types)
            
            matching_npcs = []
            for entity_id, entity in self.entities.items():
                if entity.type == target_entity_type and not entity.is_dead:
                    matching_npcs.append(entity_id)
            
            if matching_npcs:
                target_id = random.choice(matching_npcs)
                entity = self.entities[target_id]
                info = f"{entity.name or entity.type} at ({entity.screen_x},{entity.screen_y})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True
        
        # For SEARCH quests - find any dropped items across zones
        elif quest_type == 'SEARCH':
            # Build search target list: player's selected item, or random from all items
            selected_item = self.inventory.get_selected_item_name()
            
            # Search ALL dropped items across zones — find anything available
            found_items = []
            for screen_key, items_dict in self.dropped_items.items():
                if screen_key == player_zone:
                    continue
                if not self.is_overworld_zone(screen_key):
                    continue
                try:
                    sx, sy = map(int, screen_key.split(','))
                except (ValueError, AttributeError):
                    continue
                for (cx, cy), item_bag in items_dict.items():
                    for item_name, count in item_bag.items():
                        if count > 0:
                            dist = abs(sx - player_sx) + abs(sy - player_sy)
                            # Prioritize: selected item first, runes second, others third
                            priority = 2
                            if selected_item and item_name == selected_item:
                                priority = 0
                            elif 'rune' in item_name:
                                priority = 1
                            found_items.append((priority, dist, sx, sy, cx, cy, item_name))
            
            # Also search entity inventories
            for entity_id, entity in self.entities.items():
                if entity.is_dead:
                    continue
                zone_key = f"{entity.screen_x},{entity.screen_y}"
                if zone_key == player_zone:
                    continue
                for item_name, count in entity.inventory.items():
                    if count > 0:
                        dist = abs(entity.screen_x - player_sx) + abs(entity.screen_y - player_sy)
                        priority = 2
                        if selected_item and item_name == selected_item:
                            priority = 0
                        elif 'rune' in item_name:
                            priority = 1
                        found_items.append((priority, dist, entity.screen_x, entity.screen_y, entity.x, entity.y, item_name))
            
            # Also search chests
            for chest_key, contents in self.chest_contents.items():
                for item_name, count in contents.items():
                    if count > 0:
                        # Try to parse zone coords from chest_key
                        try:
                            zone_part = chest_key.split(':')[0]
                            csx, csy = map(int, zone_part.split(','))
                            dist = abs(csx - player_sx) + abs(csy - player_sy)
                        except (ValueError, IndexError):
                            dist = 10
                            csx, csy = player_sx, player_sy
                        priority = 2
                        if selected_item and item_name == selected_item:
                            priority = 0
                        elif 'rune' in item_name:
                            priority = 1
                        found_items.append((priority, dist, csx, csy, GRID_WIDTH // 2, GRID_HEIGHT // 2, item_name))
            
            if found_items:
                # Sort by priority first, then distance
                found_items.sort(key=lambda x: (x[0], x[1]))
                priority, dist, sx, sy, cx, cy, item_name = found_items[0]
                display_name = ITEMS.get(item_name, {}).get('name', item_name)
                info = f"Find {display_name} near ({sx},{sy})"
                quest.set_target('cell', (sx, sy, cx, cy), info)
                quest.target_zone = f"{sx},{sy}"
                return True
            else:
                # No existing items found — set target to a random nearby zone to explore
                info = "Searching for items..."
                quest.target_info = info
                # Pick a random nearby zone to explore
                explore_dx = random.randint(-3, 3)
                explore_dy = random.randint(-3, 3)
                if explore_dx == 0 and explore_dy == 0:
                    explore_dx = 1
                tsx, tsy = player_sx + explore_dx, player_sy + explore_dy
                quest.set_target('cell', (tsx, tsy, GRID_WIDTH // 2, GRID_HEIGHT // 2), info)
                quest.target_zone = f"{tsx},{tsy}"
                return True
        
        # For LUMBER quests — find trees to chop
        elif quest_type == 'LUMBER':
            search_types = ['TREE1', 'TREE2']
            pz_key = f"{player_sx},{player_sy}"

            # Check if current zone has trees (proxy can chop via behavior_config)
            has_local = False
            if pz_key in self.screens:
                for row in self.screens[pz_key]['grid']:
                    for cell in row:
                        if cell in search_types:
                            has_local = True
                            break
                    if has_local:
                        break

            # 90% of the time: stay local and let NPC behavior handle chopping
            # 10% of the time (or if no local trees): set a cross-zone target
            if has_local and random.random() < 0.90:
                # Mark quest active with current zone so proxy just wanders + chops
                quest.target_info = "Chopping trees nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            # Cross-zone: find trees in a nearby zone to travel to
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == pz_key:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in search_types:
                            info = f"Travel to chop trees at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = cell
                            quest.target_zone = screen_key
                            return True
            # Fallback: stay local if nothing found
            if has_local:
                quest.target_info = "Chopping trees nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for trees..."
            return False
        
        # For MINE quests — find stone to mine
        elif quest_type == 'MINE':
            pz_key = f"{player_sx},{player_sy}"

            # Check if current zone has stone
            has_local = False
            if pz_key in self.screens:
                for row in self.screens[pz_key]['grid']:
                    for cell in row:
                        if cell == 'STONE':
                            has_local = True
                            break
                    if has_local:
                        break

            # 90%: stay local and let NPC behavior handle mining
            if has_local and random.random() < 0.90:
                quest.target_info = "Mining stone nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            # 10% or no local stone: find stone in a nearby zone
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == pz_key:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell == 'STONE':
                            info = f"Travel to mine stone at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = 'STONE'
                            quest.target_zone = screen_key
                            return True
            if has_local:
                quest.target_info = "Mining stone nearby"
                quest.target_zone = pz_key
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for stone..."
            return False
        
        # For FARM quests - farmer behavior (harvest, till, plant, build)
        elif quest_type == 'FARM':
            player_zone = f"{player_sx},{player_sy}"
            if player_zone not in self.screens:
                return False
            screen = self.screens[player_zone]

            # Check if current zone has any farmable cells
            farm_cells = {'CARROT1', 'CARROT2', 'CARROT3', 'SOIL', 'DIRT', 'TREE1', 'TREE2'}
            has_local = False
            for row in screen['grid']:
                for cell in row:
                    if cell in farm_cells:
                        has_local = True
                        break
                if has_local:
                    break

            # 90%: stay local and let FARMER behavior_config handle the work
            # (harvest, till, plant are all in the farmer's action list)
            if has_local and random.random() < 0.90:
                quest.target_info = "Farming nearby"
                quest.target_zone = player_zone
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True

            # 10% or no local targets: find farm-able cells in a nearby zone
            for screen_key, screen_data in self.screens.items():
                if not self.is_overworld_zone(screen_key):
                    continue
                if screen_key == player_zone:
                    continue
                sx, sy = map(int, screen_key.split(','))
                if abs(sx - player_sx) + abs(sy - player_sy) > 3:
                    continue
                for y, row in enumerate(screen_data['grid']):
                    for x, cell in enumerate(row):
                        if cell in farm_cells:
                            info = f"Travel to farm at zone ({sx},{sy})"
                            quest.set_target('cell', (sx, sy, x, y), info)
                            quest._original_cell = cell
                            quest.target_zone = screen_key
                            return True
            if has_local:
                quest.target_info = "Farming nearby"
                quest.target_zone = player_zone
                quest.target_cell = (player_sx, player_sy, GRID_WIDTH // 2, GRID_HEIGHT // 2)
                quest.status = 'active'
                return True
            quest.target_info = "Looking for farm targets..."
            return False

        # For COMBAT_HOSTILE quests — target hostile entities (same as HUNT)
        elif quest_type == 'COMBAT_HOSTILE':
            hostile_entities = [eid for eid, e in self.entities.items()
                                if e.props.get('hostile') and not e.is_dead
                                and min_level <= e.level <= max_level]
            if not hostile_entities:
                hostile_entities = [eid for eid, e in self.entities.items()
                                    if e.props.get('hostile') and not e.is_dead]
            if hostile_entities:
                target_id = random.choice(hostile_entities)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.name or entity.type}"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True

        # For COMBAT_ALL quests — target any entity, hostile or peaceful
        elif quest_type == 'COMBAT_ALL':
            all_targets = [eid for eid, e in self.entities.items()
                           if not e.is_dead and eid != 'player'
                           and min_level <= e.level <= max_level]
            if not all_targets:
                all_targets = [eid for eid, e in self.entities.items()
                               if not e.is_dead and eid != 'player']
            if all_targets:
                target_id = random.choice(all_targets)
                entity = self.entities[target_id]
                info = f"L{entity.level} {entity.name or entity.type} ({entity.type})"
                quest.set_target('entity', target_id, info)
                quest.target_zone = f"{entity.screen_x},{entity.screen_y}"
                return True

        return False
    
    def check_quest_completion(self):
        """Check if active quest is completed and award XP"""
        if not self.active_quest:
            return
        
        quest = self.quests[self.active_quest]
        if quest.status != 'active':
            return
        
        # Prevent rapid re-completion — guard against same-tick completion
        if hasattr(quest, '_last_completed_tick') and quest._last_completed_tick == self.tick:
            return
        
        completed = False
        xp_reward = 0
        
        # Check entity-based quests
        if quest.target_entity_id:
            if quest.target_entity_id not in self.entities:
                # Entity gone — clear quest, no XP
                quest.clear_target()
                return
            else:
                entity = self.entities[quest.target_entity_id]
                if entity.is_dead:
                    if entity.killed_by == 'player':
                        completed = True
                        xp_reward = entity.level * QUEST_XP_MULTIPLIER
                    else:
                        # Something else killed it — just clear and reassign
                        quest.clear_target()
                        return
        
        # Check cell-based quests (explore/gather/farm/search)
        elif quest.target_cell:
            sx, sy, x, y = quest.target_cell
            player_sx, player_sy = self.player['screen_x'], self.player['screen_y']
            player_x, player_y = self.player['x'], self.player['y']
            
            if sx == player_sx and sy == player_sy:
                distance = abs(x - player_x) + abs(y - player_y)
                quest_type = self.active_quest
                
                if quest_type in ('FARM', 'GATHER'):
                    # These quests require the cell to have CHANGED (player interacted)
                    if distance <= 2 and quest._original_cell is not None:
                        screen_key = f"{sx},{sy}"
                        if screen_key in self.screens:
                            grid = self.screens[screen_key]['grid']
                            if 0 <= y < len(grid) and 0 <= x < len(grid[0]):
                                current_cell = grid[y][x]
                                if current_cell != quest._original_cell:
                                    completed = True
                                    xp_reward = 10 if quest_type == 'FARM' else 15
                elif quest_type in ('EXPLORE', 'RESCUE', 'SEARCH'):
                    # Proximity is enough
                    if distance <= 2:
                        completed = True
                        xp_reward = 20
        
        # Check location-based quests
        elif quest.target_location:
            target_sx, target_sy = quest.target_location
            player_sx, player_sy = self.player['screen_x'], self.player['screen_y']
            
            if target_sx == player_sx and target_sy == player_sy:
                completed = True
                xp_reward = 30
        
        if completed:
            quest._last_completed_tick = self.tick
            if xp_reward > 0 and not self.autopilot:
                self.gain_xp(xp_reward)
                print(f"Quest [{self.active_quest}] completed! +{xp_reward} XP")
            else:
                print(f"Quest [{self.active_quest}] completed (autopilot)")
            quest.complete()
    
    def update_quests(self):
        """Update quest system - assign targets and check completion"""
        # Update cooldowns
        for quest in self.quests.values():
            if quest.cooldown_remaining > 0:
                quest.cooldown_remaining -= 1
                if quest.cooldown_remaining == 0:
                    quest.status = 'inactive'
        
        # Check for quest completion
        self.check_quest_completion()
        
        # Assign targets to inactive quests that are off cooldown
        for quest_type, quest in self.quests.items():
            if quest.status == 'inactive' and quest.cooldown_remaining == 0:
                # Try to find a target
                self.loreEngine(quest)
    
    
    def update_enchanted_cells(self):
        """Update and remove enchanted cells with small random chance"""
        cells_to_remove = []
        for cell_key in list(self.enchanted_cells.keys()):
            # 1% chance per tick to release enchantment
            if random.random() < 0.01:
                cells_to_remove.append(cell_key)
        
        for cell_key in cells_to_remove:
            del self.enchanted_cells[cell_key]
    
    def run(self):
        """Main game loop"""
        while self.running:
            self.handle_input()
            
            if self.state == 'playing':
                self.move_player()
                
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
                
                # Update quest system
                self.update_quests()
                
                # Update enchanted cells
                self.update_enchanted_cells()
                
                # New probabilistic update system
                self.probabilistic_zone_updates()
                
                # Process catch-up during idle
                if self.is_idle() and self.catchup_queue:
                    self.process_catchup_queue()
                
                self.tick += 1
                self.draw_game()
            elif self.state == 'death':
                self.update_death_screen()
                self.draw_death_screen()
            elif self.state == 'menu':
                self.draw_menu()
            elif self.state == 'paused':
                self.draw_paused()
            
            pygame.display.flip()
            self.clock.tick(FPS)
        
        pygame.quit()


if __name__ == "__main__":
    game = Game()
    game.run()