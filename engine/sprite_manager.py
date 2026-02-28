from data import *

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

        # Load individual PNG sprites for new cell/item types
        _individual_sprites = {
            'IRON_ORE':   'ironore.png',
            'WELL':       'well.png',
            'iron_sword': 'sword.png',
        }
        sprite_dir = os.path.join(os.path.dirname(__file__), '..', 'sprites')
        for sprite_key, filename in _individual_sprites.items():
            path = os.path.join(sprite_dir, filename)
            if os.path.exists(path):
                try:
                    img = pygame.image.load(path).convert_alpha()
                    self.sprites[sprite_key] = pygame.transform.scale(img, (self.cell_size, self.cell_size))
                    print(f"  ✓ Loaded {sprite_key} sprite from {filename}")
                except Exception as e:
                    print(f"  ✗ Failed to load {filename}: {e}")

    def get_all_sprite_names(self):
        """Return list of all loaded sprite names"""
        return list(self.sprites.keys())
