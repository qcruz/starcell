from constants import *

class SpriteManager:
    """Manages loading and accessing game sprites from sprite sheets"""
    
    def __init__(self, sprite_sheet_path=None):
        """Initialize the sprite manager"""
        self.sprites = {}
        self.sprite_sheet = None
        self.cell_size = 40  # Standard cell size for Starcell
        
        if sprite_sheet_path and os.path.exists(sprite_sheet_path):
            self.load_sprite_sheet(sprite_sheet_path)
    
    def load_sprite_sheet(self, path):
        """Load the sprite sheet image"""
        try:
            self.sprite_sheet = pygame.image.load(path).convert_alpha()
            print(f"✓ Loaded sprite sheet: {path}")
            print(f"  Sprite sheet size: {self.sprite_sheet.get_size()}")
            return True
        except Exception as e:
            print(f"✗ Failed to load sprite sheet: {e}")
            return False
    
    def extract_sprite(self, x, y, width, height, scale_to=None):
        """Extract a single sprite from the sprite sheet"""
        if not self.sprite_sheet:
            # Return a placeholder surface if no sprite sheet loaded
            surface = pygame.Surface((width, height))
            surface.fill((255, 0, 255))  # Magenta placeholder
            return surface
        
        # Extract the sprite
        sprite = pygame.Surface((width, height), pygame.SRCALPHA)
        sprite.blit(self.sprite_sheet, (0, 0), (x, y, width, height))
        
        # Scale if requested
        if scale_to:
            sprite = pygame.transform.scale(sprite, scale_to)
        
        return sprite
    
    def load_terrain_sprites_grid(self, rows=2, cols=3, sprite_width=None, sprite_height=None):
        """Load terrain sprites from a grid layout sprite sheet"""
        if not self.sprite_sheet:
            print("✗ No sprite sheet loaded")
            return
        
        sheet_width, sheet_height = self.sprite_sheet.get_size()
        
        # Auto-detect sprite dimensions if not provided
        if sprite_width is None:
            sprite_width = sheet_width // cols
        if sprite_height is None:
            sprite_height = sheet_height // rows
        
        print(f"Extracting {rows}x{cols} grid, each sprite: {sprite_width}x{sprite_height}")
        
        # Define terrain types based on grid position
        terrain_map = [
            ['GRASS', 'DIRT', 'SAND'],
            ['STONE', 'WATER', 'DEEP_WATER']
        ]
        
        # Extract each sprite
        for row in range(rows):
            for col in range(cols):
                x = col * sprite_width
                y = row * sprite_height
                
                terrain_type = terrain_map[row][col]
                
                # Extract and scale to game cell size
                sprite = self.extract_sprite(
                    x, y, 
                    sprite_width, sprite_height,
                    scale_to=(self.cell_size, self.cell_size)
                )
                
                self.sprites[terrain_type] = sprite
                print(f"  ✓ Loaded {terrain_type} sprite from ({x}, {y})")
        
        # Only generate tree/flower variants if they don't exist AND grass sprite exists
        # (Don't auto-generate unless explicitly needed)
        
        # Note: Tree and flower variants are commented out to prevent filters on grass
        # If you want trees/flowers to use grass-based textures, uncomment below:
        
        # if 'GRASS' in self.sprites and 'TREE1' not in self.sprites:
        #     base_grass = self.sprites['GRASS'].copy()
        #     tree1 = base_grass.copy()
        #     overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
        #     overlay.fill((34, 139, 34, 100))
        #     tree1.blit(overlay, (0, 0))
        #     self.sprites['TREE1'] = tree1
        
        # if 'GRASS' in self.sprites and 'FLOWER' not in self.sprites:
        #     flower = self.sprites['GRASS'].copy()
        #     overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
        #     overlay.fill((255, 192, 203, 120))
        #     flower.blit(overlay, (0, 0))
        #     self.sprites['FLOWER'] = flower
        
        # Generate crop variants from DIRT only if dirt exists and crops don't
        # Commented out to prevent filters on dirt - uncomment if you want carrot variants
        # if 'DIRT' in self.sprites:
        #     for i in range(1, 4):
        #         if f'CARROT{i}' not in self.sprites:
        #             crop = self.sprites['DIRT'].copy()
        #             overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
        #             green_intensity = 50 * i
        #             overlay.fill((255, 140, 0, green_intensity))
        #             crop.blit(overlay, (0, 0))
        #             self.sprites[f'CARROT{i}'] = crop
    
    def get_sprite(self, cell_type):
        """Get a sprite for a given cell type"""
        if cell_type in self.sprites:
            return self.sprites[cell_type]
        
        # Return None if sprite not found (caller should handle fallback)
        return None
    
    def create_structure_sprites(self):
        """Create sprites for game structures and all other cell types"""
        
        # Use base terrain sprites to create variants
        base_grass = self.sprites.get('GRASS')
        base_dirt = self.sprites.get('DIRT')
        base_sand = self.sprites.get('SAND')
        base_stone = self.sprites.get('STONE')
        base_water = self.sprites.get('WATER')
        
        # CAMP - Brown/tan color
        camp = pygame.Surface((self.cell_size, self.cell_size))
        camp.fill((139, 90, 43))
        self.sprites['CAMP'] = camp
        
        # HOUSE - Gray stone color (darker stone)
        if base_stone:
            house = base_stone.copy()
            overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
            overlay.fill((100, 69, 19, 150))
            house.blit(overlay, (0, 0))
            self.sprites['HOUSE'] = house
        else:
            house = pygame.Surface((self.cell_size, self.cell_size))
            house.fill((128, 128, 128))
            self.sprites['HOUSE'] = house
        
        # WOOD - Light brown
        wood = pygame.Surface((self.cell_size, self.cell_size))
        wood.fill((160, 120, 80))
        self.sprites['WOOD'] = wood
        
        # PLANKS - Lighter wood
        planks = pygame.Surface((self.cell_size, self.cell_size))
        planks.fill((205, 133, 63))
        self.sprites['PLANKS'] = planks
        
        # WALL - Dark gray/black
        wall = pygame.Surface((self.cell_size, self.cell_size))
        wall.fill((31, 41, 55))
        self.sprites['WALL'] = wall
        
        # CAVE - Very dark
        cave = pygame.Surface((self.cell_size, self.cell_size))
        cave.fill((17, 24, 39))
        self.sprites['CAVE'] = cave
        
        # SOIL - Dark brown (tilled dirt)
        if base_dirt:
            soil = base_dirt.copy()
            overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
            overlay.fill((50, 30, 20, 100))
            soil.blit(overlay, (0, 0))
            self.sprites['SOIL'] = soil
        else:
            soil = pygame.Surface((self.cell_size, self.cell_size))
            soil.fill((101, 67, 33))
            self.sprites['SOIL'] = soil
        
        # MEAT - Red/brown
        meat = pygame.Surface((self.cell_size, self.cell_size))
        meat.fill((180, 50, 50))
        self.sprites['MEAT'] = meat
        
        # FUR - Gray
        fur = pygame.Surface((self.cell_size, self.cell_size))
        fur.fill((100, 100, 100))
        self.sprites['FUR'] = fur
        
        # BONES - Off-white
        bones = pygame.Surface((self.cell_size, self.cell_size))
        bones.fill((220, 220, 200))
        self.sprites['BONES'] = bones
        
        # Interior cell types
        # FLOOR_WOOD - Brown floor
        floor_wood = pygame.Surface((self.cell_size, self.cell_size))
        floor_wood.fill((101, 67, 33))
        self.sprites['FLOOR_WOOD'] = floor_wood
        
        # CAVE_FLOOR - Dark gray
        cave_floor = pygame.Surface((self.cell_size, self.cell_size))
        cave_floor.fill((50, 50, 50))
        self.sprites['CAVE_FLOOR'] = cave_floor
        
        # CAVE_WALL - Very dark gray
        cave_wall = pygame.Surface((self.cell_size, self.cell_size))
        cave_wall.fill((30, 30, 30))
        self.sprites['CAVE_WALL'] = cave_wall
        
        # CHEST - Brown
        chest = pygame.Surface((self.cell_size, self.cell_size))
        chest.fill((139, 69, 19))
        self.sprites['CHEST'] = chest
        
        # STAIRS_DOWN - Dark brown
        stairs_down = pygame.Surface((self.cell_size, self.cell_size))
        stairs_down.fill((100, 80, 60))
        self.sprites['STAIRS_DOWN'] = stairs_down
        
        # STAIRS_UP - Light brown
        stairs_up = pygame.Surface((self.cell_size, self.cell_size))
        stairs_up.fill((120, 100, 80))
        self.sprites['STAIRS_UP'] = stairs_up
        
        # TREE2 - If not already created, make it darker than TREE1
        if 'TREE2' not in self.sprites:
            if base_grass:
                tree2 = base_grass.copy()
                overlay = pygame.Surface((self.cell_size, self.cell_size), pygame.SRCALPHA)
                overlay.fill((35, 70, 18, 200))
                tree2.blit(overlay, (0, 0))
                self.sprites['TREE2'] = tree2
        
        # TREE3 - Darkest tree (if not already created)
        if 'TREE3' not in self.sprites:
            tree3 = pygame.Surface((self.cell_size, self.cell_size))
            tree3.fill((25, 50, 15))
            self.sprites['TREE3'] = tree3
        
        print("  ✓ Generated all structure and special cell sprites")
    
    def get_all_sprite_names(self):
        """Return list of all loaded sprite names"""
        return list(self.sprites.keys())

# ============================================================================
# END SPRITE MANAGER CLASS
# ============================================================================

class Entity:
    # Name lists for random generation
    FIRST_NAMES = [
        'Aldric', 'Brynn', 'Cedric', 'Dara', 'Elara', 'Finn', 'Greta', 'Holt', 'Isla', 'Jasper',
        'Kael', 'Luna', 'Magnus', 'Nora', 'Orin', 'Petra', 'Quinn', 'Rowan', 'Seren', 'Thane',
        'Una', 'Vale', 'Wren', 'Xander', 'Yara', 'Zephyr', 'Ash', 'Bram', 'Cara', 'Drake',
        'Ember', 'Frost', 'Gray', 'Haven', 'Iris', 'Jace', 'Kai', 'Lyra', 'Moss', 'Neve'
    ]
    
    LAST_NAMES = [
        'Ironwood', 'Stormcrow', 'Thornhill', 'Riverstone', 'Ashford', 'Blackwood', 'Whitehawk',
        'Goldleaf', 'Silverpine', 'Redfern', 'Greymoor', 'Brightwater', 'Darkhollow', 'Oakenshield',
        'Wolfsbane', 'Foxglove', 'Ravenwood', 'Swiftbrook', 'Stoneheart', 'Windwalker',
        'Moonwhisper', 'Sunfire', 'Frostbane', 'Wildrose', 'Deepwood', 'Highridge', 'Lowvale',
        'Clearwater', 'Shadowmere', 'Meadowbrook'
    ]
    
    def __init__(self, entity_type, x, y, screen_x, screen_y, level=1):
        self.type = entity_type
        # Handle _double types by using base type for props lookup
        base_type = entity_type.replace('_double', '')
        self.props = ENTITY_TYPES[base_type]
        self.level = level
        
        # Position - GRID coordinates (logical cell position)
        self.x = x  # Grid X (integer)
        self.y = y  # Grid Y (integer)
        self.screen_x = screen_x
        self.screen_y = screen_y
        
        # Position - WORLD coordinates (actual pixel position for smooth rendering)
        self.world_x = float(x)  # World X (float, for smooth movement)
        self.world_y = float(y)  # World Y (float, for smooth movement)
        
        # Movement state
        self.target_x = x  # Target grid cell
        self.target_y = y  # Target grid cell
        self.is_moving = False
        self.move_speed = 0.05  # Cells per tick (configurable per entity)
        
        # Subscreen state
        self.in_subscreen = False
        self.subscreen_key = None
        
        # Animation state
        self.facing = 'down'  # 'up', 'down', 'left', 'right'
        self.anim_frame = '1'  # '1', 'still', '2' for 3-frame walking animation
        self.anim_timer = 0  # Counter for animation speed
        self._next_step = '2'  # Tracks which step comes after 'still'
        self.last_x = x
        self.last_y = y
        
        # Pathfinding state
        self.stuck_counter = 0  # Tracks consecutive ticks with no valid move
        
        # Stats (scaled by level)
        self.max_health = self.props['max_health'] * level
        self.health = self.max_health
        self.max_hunger = self.props['max_hunger']
        self.hunger = self.max_hunger
        self.max_thirst = self.props['max_thirst']
        self.thirst = self.max_thirst
        self.strength = self.props['strength'] * level
        
        # AI state
        self.target = None  # (entity_id, 'entity') or (x, y, 'food') or (x, y, 'water')
        self.target_priority = None  # 'enemy', 'food', 'water', 'explore', 'wander', 'attack', 'defend'
        self.movement_pattern = random.choice(['wander', 'patrol', 'guard'])
        self.wander_timer = 0
        self.last_move_tick = 0
        
        # Combat state
        self.in_combat = False  # True when actively fighting
        self.combat_target = None  # entity_id of current combat opponent
        self.is_fleeing = False  # True when fleeing from threat
        self.wants_counterattack = False  # Track if entity wants to counterattack
        self.counterattack_target = None  # entity_id to counterattack
        self.last_home_return_check = 0  # Tick of last home zone check
        self.was_trading = False  # Track if entity was recently trading
        
        # Subscreen state
        self.in_subscreen = False  # True when entity is in a house/cave subscreen
        self.subscreen_key = None  # Key of subscreen entity is in
        
        # Unified AI Behavior State System
        # Set initial state based on entity type
        if entity_type in ['WARRIOR', 'COMMANDER', 'KING', 'GUARD']:
            self.ai_state = 'targeting'  # Combat NPCs start hunting
            self.target_type = 'hostile'  # Hunt hostile entities
        else:
            self.ai_state = 'wandering'  # Peaceful NPCs start wandering
        self.current_target = None  # Current target entity_id or (x, y) position
        self.ai_state_timer = random.randint(0, 3)  # Small random offset to desync entities
        
        # Get AI parameters from entity definition or use defaults
        ai_params = self.props.get('ai_params', {})
        self.aggressiveness = ai_params.get('aggressiveness', 0.30)  # Default: 30% chance to acquire targets
        self.passiveness = ai_params.get('passiveness', 0.20)  # Default: 20% chance to drop targets
        self.idleness = ai_params.get('idleness', 0.15)  # Default: 15% chance to go idle
        self.flee_chance = ai_params.get('flee_chance', 0.50)  # Default: 50% flee when threatened
        self.combat_chance = ai_params.get('combat_chance', 0.50)  # Default: 50% fight when threatened
        self.target_types = ai_params.get('target_types', ['water', 'food'])  # What this entity targets
        
        # Pathfinding memory - humanoids get longer memory
        humanoid_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'BANDIT', 'GOBLIN', 'KING', 'SKELETON']
        max_memory = 25 if entity_type in humanoid_types else 10
        self.memory_lane = []  # Track recent positions for pathfinding
        self.max_memory_length = max_memory
        self.no_food_in_zone = False  # Track if zone lacks resources
        self.seeking_exit = False  # Track if actively seeking zone exit
        
        # Stuck target detection
        self.target_stuck_counter = 0  # Tracks ticks at same target
        self.last_target_position = None  # Stores last target coords for comparison
        
        # Priority weights (how much this entity cares about each action)
        # Higher weight = more likely to choose this action
        default_weights = {
            'water': 0.3,
            'food': 0.3,
            'explore': 0.05,  # Base explore chance for all
            'wander': 0.2,
            'attack': 0.1,
            'defend': 0.0
        }
        
        # Custom weights by entity type
        type_weights = {
            'FARMER': {'water': 0.3, 'food': 0.3, 'explore': 0.03, 'wander': 0.3, 'attack': 0.02, 'defend': 0.03},
            'LUMBERJACK': {'water': 0.3, 'food': 0.3, 'explore': 0.03, 'wander': 0.3, 'attack': 0.02, 'defend': 0.03},
            'MINER': {'water': 0.3, 'food': 0.3, 'explore': 0.03, 'wander': 0.3, 'attack': 0.02, 'defend': 0.03},
            'TRADER': {'water': 0.15, 'food': 0.15, 'explore': 0.5, 'wander': 0.05, 'attack': 0.05, 'defend': 0.1},
            'GUARD': {'water': 0.15, 'food': 0.15, 'explore': 0.05, 'wander': 0.05, 'attack': 0.5, 'defend': 0.1},
            'GOBLIN': {'water': 0.15, 'food': 0.15, 'explore': 0.3, 'wander': 0.02, 'attack': 0.35, 'defend': 0.03},
            'BANDIT': {'water': 0.15, 'food': 0.15, 'explore': 0.25, 'wander': 0.02, 'attack': 0.4, 'defend': 0.03},
            'WOLF': {'water': 0.3, 'food': 0.4, 'explore': 0.05, 'wander': 0.1, 'attack': 0.1, 'defend': 0.0},
            'DEER': {'water': 0.4, 'food': 0.4, 'explore': 0.05, 'wander': 0.1, 'attack': 0.0, 'defend': 0.0},
            'SHEEP': {'water': 0.4, 'food': 0.4, 'explore': 0.03, 'wander': 0.15, 'attack': 0.0, 'defend': 0.0},
            'SKELETON': {'water': 0.0, 'food': 0.0, 'explore': 0.05, 'wander': 0.1, 'attack': 0.8, 'defend': 0.0}
        }
        
        self.priority_weights = type_weights.get(entity_type, default_weights)
        
        # Scale explore weight by level - higher level = more wanderlust
        # Each level adds 2% to explore weight
        level_explore_bonus = (level - 1) * 0.02
        self.priority_weights['explore'] = min(0.5, self.priority_weights['explore'] + level_explore_bonus)
        
        # Random idle state (for staggered movement)
        self.is_idle = False
        self.idle_timer = 0
        self.idle_duration = 0
        
        # Trader-specific state
        if entity_type == 'TRADER':
            self.target_exit = None  # Which exit trader is heading toward
            self.movement_pattern = 'travel'  # Traders always travel
        
        # Guard-specific state
        if entity_type == 'GUARD':
            self.patrol_target = None  # Patrol waypoint
            self.movement_pattern = 'patrol'  # Guards patrol center lanes
        
        # Warrior-specific state (home zone defender)
        if entity_type == 'WARRIOR':
            self.patrol_target = None  # Patrol waypoint
            self.movement_pattern = 'patrol'  # Warriors patrol like guards
            self.home_zone = None  # Set when promoted, format: "x,y"
        
        # Wizard-specific state
        if entity_type == 'WIZARD':
            self.spell = random.choice(['heal', 'fireball', 'lightning', 'ice', 'enchant'])
            self.alignment = random.choice(['hostile', 'peaceful'])
            self.spell_cooldown = 0
            self.movement_pattern = 'travel'  # Wizards travel like traders
            # Movement timing (randomized to prevent synchronization)
            base_interval = NPC_BASE_MOVE_INTERVAL
            variance = random.randint(-NPC_MOVE_VARIANCE, NPC_MOVE_VARIANCE)
            self.movement_interval = max(30, base_interval + variance)
            self.movement_timer = random.randint(0, self.movement_interval)
            self.action_animation_timer = 0  # For action animations
            self.move_frame = 0  # For movement frames
        
        # Add movement timers to all NPCs
        if not hasattr(self, 'movement_interval'):
            base_interval = NPC_BASE_MOVE_INTERVAL
            variance = random.randint(-NPC_MOVE_VARIANCE, NPC_MOVE_VARIANCE)
            self.movement_interval = max(30, base_interval + variance)
            self.movement_timer = random.randint(0, self.movement_interval)
            self.action_animation_timer = 0
            self.move_frame = 0
        
        # Inventory (for NPCs)
        self.inventory = self.props.get('inventory', {}).copy() if 'inventory' in self.props else {}
        
        # Item levels and names - track level of each item type
        self.item_levels = {}  # {item_name: level}
        self.item_names = {}   # {item_name: custom_name} for legendary items
        
        # Zone travel cooldown
        self.last_zone_change_tick = -999  # Track when last changed zones (start very negative so can travel immediately)
        
        # Name generation (for NPCs only, not animals)
        human_types = ['FARMER', 'TRADER', 'GUARD', 'LUMBERJACK', 'MINER', 'BLACKSMITH', 'BANDIT', 'GOBLIN', 'KING', 'SKELETON', 'WARRIOR', 'WIZARD']
        if entity_type in human_types:
            first_name = random.choice(Entity.FIRST_NAMES)
            last_name = random.choice(Entity.LAST_NAMES)
            self.name = f"{first_name} {last_name}"
        else:
            self.name = None  # Animals don't have names
        
        # Experience
        self.xp = 0
        self.xp_to_level = 100 * level
        
        # Age (in years) - start at random age
        if entity_type == 'SKELETON':
            self.age = 0  # Skeletons don't age
            self.max_age = 999999  # Skeletons never die of old age
        else:
            self.age = random.randint(1, 20)  # Start between 1-20 years old
            self.max_age = random.randint(65, 100)  # Random lifespan

        # Combat state
        self.combat_state = 'blocking'  # 'blocking', 'evading', 'attacking'
        self.last_state_change = 0
        self.block_reduction = 0.9  # 90% damage reduction when blocking
        
        # Faction system (used by warriors)
        self.faction = None  # Warriors join factions, None for non-warriors or unaffiliated
        
        # Quest tracking
        self.killed_by = None  # Track who killed this entity

        # ── NPC Quest Focus System ────────────────────────────────────────────
        # quest_focus:           current goal driving where this NPC navigates
        # unlocked_quest_types:  all focuses this NPC is allowed to use
        # quest_target:          specific target tuple, set by assign_npc_quest_target,
        #                        cleared when the NPC arrives and completes the action
        default_focus = NPC_QUEST_FOCUS_DEFAULT.get(base_type, 'exploring')
        self.quest_focus = default_focus
        # Hostile NPCs start with combat_all only; peaceful NPCs start with their default
        if default_focus == 'combat_all':
            self.unlocked_quest_types = ['combat_all']
        else:
            self.unlocked_quest_types = [default_focus]
        self.quest_target = None   # ('cell', x, y, cell_type) | entity_id | None
    
    def update_animation(self):
        """Update walk-cycle animation frames.
        
        Facing is set authoritatively by move_toward_position / wander_entity at
        the moment the grid position changes and must NOT be overridden here.
        Deriving facing from interpolated world coords causes wrong-direction
        flickers because world_x/y lags behind the grid target by up to ~30 ticks.
        """
        TICKS_PER_FRAME = 10

        # Is the sprite still travelling between grid cells?
        distance_to_target = abs(self.world_x - float(self.x)) + abs(self.world_y - float(self.y))
        is_moving = distance_to_target > 0.01

        # Flying entities flap even when standing still (unless inside a structure)
        is_flying_idle = (self.props.get('flying', False) and not is_moving
                          and not (hasattr(self, 'in_subscreen') and self.in_subscreen))

        if is_moving or is_flying_idle:
            self.anim_timer += 1
            if self.anim_timer >= TICKS_PER_FRAME:
                if self.anim_frame == '1':
                    self.anim_frame = 'still'
                elif self.anim_frame == 'still':
                    if not hasattr(self, '_next_step'):
                        self._next_step = '2'
                    self.anim_frame = self._next_step
                    self._next_step = '1' if self._next_step == '2' else '2'
                elif self.anim_frame == '2':
                    self.anim_frame = 'still'
                else:
                    self.anim_frame = '1'
                    self._next_step = '2'
                self.anim_timer = 0
        else:
            self.anim_frame = 'still'
            self.anim_timer = 0
            self._next_step = '1'
    
    def update_smooth_movement(self):
        """Interpolate world_x/world_y toward authoritative grid position (self.x, self.y).
        
        IMPORTANT: This function NEVER modifies self.x or self.y.
        Grid position is ONLY set by the AI/pathfinding system (move_toward_position, wander_entity).
        world_x/world_y are visual-only for smooth rendering interpolation.
        """
        # MOVEMENT SPEED CONTROL
        # Base speed synced with UPDATE_FREQUENCY (30 ticks between AI updates)
        # Visual should cross 1 cell in ~30 ticks at speed=1.0: 1/30 ≈ 0.033
        BASE_MOVEMENT_SPEED = 0.034  # cells per tick at speed=1.0
        entity_speed = self.props.get('speed', 1.0)
        movement_speed = BASE_MOVEMENT_SPEED * entity_speed
        ARRIVAL_THRESHOLD = 0.01  # Distance to consider "arrived"
        
        # Interpolate world position toward the authoritative grid position
        target_wx = float(self.x)
        target_wy = float(self.y)
        
        dx = target_wx - self.world_x
        dy = target_wy - self.world_y
        
        distance = (dx**2 + dy**2) ** 0.5
        
        if distance < ARRIVAL_THRESHOLD:
            # Snap to exact grid position
            self.world_x = target_wx
            self.world_y = target_wy
            self.is_moving = False
            return
        
        # If grid position jumped more than 2.5 cells (e.g. zone transition, safety reset),
        # snap immediately instead of slowly interpolating across the map
        if distance > 2.5:
            self.world_x = target_wx
            self.world_y = target_wy
            self.is_moving = False
            return
        
        # Move along the axis that matches entity.facing FIRST.
        # Using facing (set authoritatively at move time by move_toward_position /
        # wander_entity) instead of the larger-lag axis prevents sideways sliding
        # when the AI changes direction before world_x/y has fully caught up.
        #
        # KEY: if facing is horizontal but there is Y lag (or vice-versa), that lag
        # is residue from the PREVIOUS move — snap it to the grid immediately so it
        # never causes a perpendicular drift step.
        new_world_x = self.world_x
        new_world_y = self.world_y
        facing = getattr(self, 'facing', 'down')
        move_x_first = facing in ('left', 'right')

        if move_x_first:
            # Snap any stale Y lag immediately — we are moving horizontally now
            if abs(dy) > ARRIVAL_THRESHOLD:
                new_world_y = target_wy
            # Step along X toward target
            if abs(dx) > ARRIVAL_THRESHOLD:
                step_x = movement_speed if dx > 0 else -movement_speed
                new_world_x = self.world_x + step_x
                new_world_x = min(new_world_x, target_wx) if dx > 0 else max(new_world_x, target_wx)
        else:
            # Snap any stale X lag immediately — we are moving vertically now
            if abs(dx) > ARRIVAL_THRESHOLD:
                new_world_x = target_wx
            # Step along Y toward target
            if abs(dy) > ARRIVAL_THRESHOLD:
                step_y = movement_speed if dy > 0 else -movement_speed
                new_world_y = self.world_y + step_y
                new_world_y = min(new_world_y, target_wy) if dy > 0 else max(new_world_y, target_wy)

        self.world_x = new_world_x
        self.world_y = new_world_y
        self.is_moving = True
    
    def decay_stats(self):
        """Decay hunger and thirst over time"""
        self.hunger = max(0, self.hunger - HUNGER_DECAY_RATE)
        self.thirst = max(0, self.thirst - THIRST_DECAY_RATE)
        
        # Take damage if starving or dehydrated
        if self.hunger <= 0:
            self.health -= STARVATION_DAMAGE
        if self.thirst <= 0:
            self.health -= DEHYDRATION_DAMAGE
        
        # Take damage from old age
        if hasattr(self, 'age') and hasattr(self, 'max_age'):
            if self.age > self.max_age:
                self.health -= OLD_AGE_DAMAGE
    
    def regenerate_health(self, boost=1.0):
        """Regenerate health when well-fed and hydrated"""
        # Only heal if food and water are at max
        if self.hunger >= self.max_hunger and self.thirst >= self.max_thirst:
            base_heal = BASE_HEALING_RATE * boost
            self.heal(base_heal)
    
    def is_alive(self):
        return self.health > 0
    
    @property
    def is_dead(self):
        """Property to check if entity is dead (for quest system)"""
        return self.health <= 0
    
    def take_damage(self, damage, attacker='unknown'):
        """Take damage and track who dealt it
        
        Args:
            damage: Amount of damage to take
            attacker: Who dealt the damage ('player', 'entity_id', 'environment')
        """
        self.health = max(0, self.health - damage)
        if self.health <= 0:
            self.killed_by = attacker
        else:
            # On hit: ALWAYS counterattack (highest priority in AI)
            self.wants_counterattack = True
            self.counterattack_target = attacker
    
    def heal(self, amount):
        self.health = min(self.max_health, self.health + amount)
    
    def eat(self, food_value=30):
        """Eat food to restore hunger
        
        Args:
            food_value: Amount of hunger to restore (default 30)
                       - Grass: 20
                       - Crops (CARROT1/2/3): 40
                       - Meat (predators): 50
        """
        self.hunger = min(self.max_hunger, self.hunger + food_value)
    
    def update_facing_toward(self, target_x, target_y):
        """Update facing direction based on target position"""
        dx = target_x - self.x
        dy = target_y - self.y
        
        # Prioritize the larger distance to determine facing
        if abs(dx) > abs(dy):
            self.facing = 'right' if dx > 0 else 'left'
        elif abs(dy) > abs(dx):
            self.facing = 'down' if dy > 0 else 'up'
        else:
            # Equal distance, prioritize vertical
            if dy != 0:
                self.facing = 'down' if dy > 0 else 'up'
            else:
                self.facing = 'right' if dx > 0 else 'left'
    
    def trigger_action_animation(self):
        """Trigger brief movement animation while staying in place"""
        if hasattr(self, 'action_animation_timer'):
            self.action_animation_timer = 3  # 3 ticks
            self.move_frame = 1 - self.move_frame if hasattr(self, 'move_frame') else 1

    
    def drink(self, water_value=40):
        """Drink water to restore thirst
        
        Args:
            water_value: Amount of thirst to restore (default 40)
        """
        self.thirst = min(self.max_thirst, self.thirst + water_value)
    
    def level_up_from_activity(self, activity_type, game):
        """Chance to level up from completing activities
        
        Args:
            activity_type: 'harvest', 'chop', 'kill', 'build', 'travel'
            game: Game instance for logging
        """
        # Grant XP based on activity type
        xp_rewards = {
            'harvest': 5,
            'chop': 7,
            'mine': 6,
            'build': 10,
            'travel': 3,
            'kill': 15
        }
        
        xp_amount = xp_rewards.get(activity_type, 5)
        self.xp += xp_amount
        
        # Check if leveled up
        if self.xp >= self.xp_to_level:
            old_level = self.level
            self.level += 1
            
            # Reset XP for next level
            self.xp = 0
            self.xp_to_level = 100 * self.level
            
            # Scale stats with new level
            self.max_health = self.props['max_health'] * self.level
            self.health = self.max_health  # Full heal on level up
            self.strength = self.props['strength'] * self.level
            
            # Reduce age by 10% (minimum 20)
            age_reduction = max(1, int(self.age * 0.1))
            self.age = max(20, self.age - age_reduction)
            
            # Log level up with name if available
            name_str = self.name if self.name else self.type
            print(f"{name_str} leveled up! {old_level} -> {self.level} (max age = {self.max_age})")
            
            # Level up items in inventory (20% chance per item)
            for item_name in list(self.inventory.keys()):
                if random.random() < 0.2:  # 20% chance per item
                    current_item_level = self.item_levels.get(item_name, 1)
                    self.item_levels[item_name] = current_item_level + 1
                    
                    # Generate legendary name at level 5+
                    if current_item_level + 1 >= 5 and item_name not in self.item_names:
                        legendary_name = game.generate_legendary_item_name(item_name, self)
                        self.item_names[item_name] = legendary_name
                        print(f"  {name_str}'s {item_name} became legendary: {legendary_name}!")
                    else:
                        print(f"  {name_str}'s {item_name} leveled up to +{self.item_levels[item_name]}!")
            
            # Hostile humanoids (BANDIT, GOBLIN, SKELETON) can create factions on level up
            if self.type in ['BANDIT', 'GOBLIN', 'SKELETON'] and not self.faction:
                if random.random() < 0.1:  # 10% chance
                    screen_key = f"{self.screen_x},{self.screen_y}"
                    game.create_hostile_faction(self, screen_key)

            # ── Quest-type unlock on level up ─────────────────────────────────
            # All peaceful types + combat_hostile: 10% chance each, equal weight.
            # combat_all: 3% chance for non-hostile NPCs (higher variability risk).
            is_hostile_npc = self.props.get('hostile', False)
            for qt in NPC_QUEST_TYPES_ALL:
                if qt in self.unlocked_quest_types:
                    continue
                if qt == 'combat_all' and not is_hostile_npc:
                    chance = NPC_QUEST_UNLOCK_CHANCE_CMBT_ALL
                else:
                    chance = NPC_QUEST_UNLOCK_CHANCE
                if random.random() < chance:
                    self.unlocked_quest_types.append(qt)
                    print(f"  {name_str} unlocked quest type: {qt}!")

            # 10% chance on level-up to switch to a randomly unlocked focus
            if len(self.unlocked_quest_types) > 1 and random.random() < NPC_QUEST_FOCUS_SWITCH_CHANCE:
                old_focus = self.quest_focus
                self.quest_focus = random.choice(self.unlocked_quest_types)
                if self.quest_focus != old_focus:
                    self.quest_target = None   # force new target assignment
                    print(f"  {name_str} switched focus: {old_focus} → {self.quest_focus}")
    
    def drink(self, water_value=40):
        """Drink water to restore thirst
        
        Args:
            water_value: Amount of thirst to restore (default 40)
        """
        self.thirst = min(self.max_thirst, self.thirst + water_value)
    
    def gain_xp(self, amount):
        self.xp += amount
        if self.xp >= self.xp_to_level:
            self.level_up()
    
    def level_up(self):
        self.level += 1
        self.xp = 0
        self.xp_to_level = 100 * self.level
        
        # Guard promotion: 30% chance to become Warrior on level up
        if self.type == 'GUARD' and random.random() < 0.30:
            old_name = self.name if self.name else "Guard"
            self.type = 'WARRIOR'
            self.props = ENTITY_TYPES['WARRIOR']
            print(f"{old_name} was promoted to WARRIOR after leveling up!")
        
        # Increase stats
        self.max_health = self.props['max_health'] * self.level
        self.health = self.max_health
        self.strength = self.props['strength'] * self.level
        
        # Increase max_age by 20% (leveling extends lifespan)
        if hasattr(self, 'max_age'):
            self.max_age = int(self.max_age * 1.2)
    
    def can_merge_with(self, other):
        """Check if this entity can merge with another"""
        return (self.type == other.type and 
                abs(self.level - other.level) <= 1)
    
    def merge_with(self, other):
        """Merge with another entity, taking their stats and becoming a _double type"""
        # Change to double type
        if not self.type.endswith('_double'):
            self.type = self.type + '_double'
        
        self.level_up()
        self.health = self.max_health
        self.hunger = self.max_hunger
        self.thrist = self.max_thirst
        
        # Merge inventories if NPCs
        if self.inventory:
            for item, count in other.inventory.items():
                self.inventory[item] = self.inventory.get(item, 0) + count
    
    @property
    def screen_key(self):
        """Get the screen key for this entity's current zone.
        
        Returns string in format "x,y" representing the zone coordinates.
        This property eliminates the need for repeated string formatting.
        """
        return f"{self.screen_x},{self.screen_y}"

class Inventory:
    def __init__(self):
        self.items = {}  # {item_name: count}
        self.tools = {}  # {tool_name: count}
        self.magic = {}  # {spell_name: count}
        self.followers = {}  # {follower_name: count}
        self.max_slots = 20
        
        # Track which menus are open
        self.open_menus = set()  # Can contain 'items', 'tools', 'magic', 'followers', 'crafting'
        
        # Track selected item in each menu
        self.selected = {
            'items': None,
            'tools': None,
            'magic': None,
            'followers': None,
            'crafting': None  # For crafting screen selection
        }
        
    def add_item(self, item_name, amount=1, category=None):
        """Add item to appropriate category"""
        if item_name in ITEMS:
            # Determine category
            if category is None:
                if ITEMS[item_name].get('is_tool'):
                    category = 'tools'
                elif ITEMS[item_name].get('is_spell'):
                    category = 'magic'
                elif ITEMS[item_name].get('is_follower'):
                    category = 'followers'
                else:
                    category = 'items'
            
            # Add to category
            inv = getattr(self, category)
            inv[item_name] = inv.get(item_name, 0) + amount
            
            # Auto-select first item if none selected
            if self.selected[category] is None:
                self.selected[category] = item_name
            
            return True
        return False
    
    def remove_item(self, item_name, amount=1):
        """Remove item from any category"""
        for category in ['items', 'tools', 'magic', 'followers']:
            inv = getattr(self, category)
            if item_name in inv and inv[item_name] >= amount:
                inv[item_name] -= amount
                if inv[item_name] <= 0:
                    # Select next item if we deleted the selected one
                    if self.selected[category] == item_name:
                        remaining = list(inv.keys())
                        self.selected[category] = remaining[0] if remaining else None
                    
                    # Also update crafting selection if this was selected there
                    if self.selected.get('crafting') == item_name:
                        # Try to select any remaining item from items, tools, or magic
                        found_replacement = False
                        for cat in ['items', 'tools', 'magic']:
                            cat_inv = getattr(self, cat)
                            if cat_inv:
                                self.selected['crafting'] = list(cat_inv.keys())[0]
                                found_replacement = True
                                break
                        if not found_replacement:
                            self.selected['crafting'] = None
                    
                    del inv[item_name]
                return True
        return False
    
    def has_item(self, item_name, amount=1):
        """Check if item exists in any category"""
        for category in ['items', 'tools', 'magic', 'followers']:
            inv = getattr(self, category)
            if item_name in inv and inv[item_name] >= amount:
                return True
        return False
    
    def toggle_menu(self, menu_type):
        """Toggle a menu open/closed"""
        if menu_type in self.open_menus:
            self.open_menus.remove(menu_type)
        else:
            self.open_menus.add(menu_type)
    
    def close_all_menus(self):
        """Close all inventory menus"""
        self.open_menus.clear()
    
    def get_selected_item(self, category):
        """Get the currently selected item in a category"""
        return self.selected.get(category)
    
    def get_selected_item_name(self):
        """Get name of whatever item is currently selected across all categories.
        Checks items first, then tools."""
        for category in ['items', 'tools', 'magic']:
            name = self.selected.get(category)
            if name and getattr(self, category, {}).get(name, 0) > 0:
                return name
        return None
    
    def get_item_list(self, menu_type):
        """Get list of items in a menu"""
        inv = getattr(self, menu_type)
        return list(inv.items())
    
    def add_magic(self, spell_name, amount=1):
        """Convenience method to add magic spells"""
        return self.add_item(spell_name, amount, category='magic')
    
    def add_tool(self, tool_name, amount=1):
        """Convenience method to add tools"""
        return self.add_item(tool_name, amount, category='tools')
    
    def add_follower(self, follower_name, amount=1):
        """Convenience method to add followers"""
        return self.add_item(follower_name, amount, category='followers')
    
    @property
    def selected_magic(self):
        """Get currently selected magic spell"""
        return self.selected.get('magic')
    
    @property
    def selected_tool(self):
        """Get currently selected tool"""
        return self.selected.get('tools')
    
    @property
    def selected_item(self):
        """Get currently selected item"""
        return self.selected.get('items')
    
    @property
    def selected_follower(self):
        """Get currently selected follower"""
        return self.selected.get('followers')
    
    @property
    def selected_crafting(self):
        """Get currently selected crafting item"""
        return self.selected.get('crafting')
    
    def get_all_craftable_items(self):
        """Get combined list of items, tools, and magic for crafting screen"""
        all_items = {}
        # Combine items, tools, and magic (but not followers)
        all_items.update(self.items)
        all_items.update(self.tools)
        all_items.update(self.magic)
        return list(all_items.items())


class Quest:
    """Quest tracking system"""
    def __init__(self, quest_type):
        self.quest_type = quest_type
        self.target_entity_id = None  # For NPC targets
        self.target_location = None   # (screen_x, screen_y) for location targets
        self.target_cell = None        # (screen_x, screen_y, x, y) for cell targets
        self.target_info = ''          # Human-readable target description for HUD
        self.target_zone = None        # Zone key where target is located
        self.status = 'inactive'       # 'inactive', 'active', 'completed'
        self.cooldown_remaining = 0
        self.completed_count = 0
    
    def set_target(self, target_type, target_data, info=''):
        """Set quest target"""
        if target_type == 'entity':
            self.target_entity_id = target_data
            self.target_location = None
            self.target_cell = None
        elif target_type == 'location':
            self.target_entity_id = None
            self.target_location = target_data
            self.target_cell = None
        elif target_type == 'cell':
            self.target_entity_id = None
            self.target_location = None
            self.target_cell = target_data
        self.target_info = info
        self._original_cell = None  # Set by game logic after target is assigned
        self.status = 'active'
    
    def clear_target(self):
        """Clear quest target"""
        self.target_entity_id = None
        self.target_location = None
        self.target_cell = None
        self._original_cell = None
        self.status = 'inactive'
    
    def complete(self):
        """Mark quest as completed"""
        self.status = 'completed'
        self.completed_count += 1
        # FARM quests chain quickly, others use standard cooldown
        if self.quest_type == 'FARM':
            self.cooldown_remaining = 30  # 0.5 second between farm actions
        else:
            self.cooldown_remaining = QUEST_COOLDOWN
        self.clear_target()