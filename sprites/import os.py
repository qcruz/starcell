import os
import random
from PIL import Image
import numpy as np

_BASE = os.path.dirname(os.path.abspath(__file__))
INPUT_FOLDER = os.path.join(_BASE, "input_sprites")
OUTPUT_FOLDER = os.path.join(_BASE, "output_sprites")
VARIANTS_PER_SPRITE = 12
SPRITE_SIZE = (40, 40)

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ---------- Utility Functions ----------

def load_sprite(path):
    img = Image.open(path).convert("RGBA")
    if img.size != SPRITE_SIZE:
        raise ValueError(f"{path} is not 40x40.")
    return img


def save_sprite(img, base_name, variant_id):
    name = f"{base_name}_var{variant_id}.png"
    img.save(os.path.join(OUTPUT_FOLDER, name))


def get_palette_pixels(arr):
    """Return list of unique non-transparent colors."""
    pixels = arr.reshape(-1, 4)
    colors = {tuple(p) for p in pixels if p[3] > 0}
    return list(colors)


# ---------- Mutation Functions ----------

def color_shift(arr):
    """Shift hue slightly by modifying RGB values."""
    shift = np.array([random.randint(-20, 20) for _ in range(3)] + [0])
    mask = arr[:, :, 3] > 0
    arr[mask] = np.clip(arr[mask] + shift, 0, 255)
    return arr


def swap_palette(arr):
    """Swap two random colors in the sprite."""
    palette = get_palette_pixels(arr)
    if len(palette) < 2:
        return arr

    c1, c2 = random.sample(palette, 2)

    mask1 = np.all(arr == c1, axis=-1)
    mask2 = np.all(arr == c2, axis=-1)

    arr[mask1] = c2
    arr[mask2] = c1
    return arr


def add_noise(arr, amount=0.03):
    """Add pixel noise."""
    h, w, _ = arr.shape
    for _ in range(int(h * w * amount)):
        x = random.randint(0, w - 1)
        y = random.randint(0, h - 1)
        if arr[y, x, 3] > 0:
            arr[y, x, :3] = np.clip(arr[y, x, :3] + np.random.randint(-30, 30, 3), 0, 255)
    return arr


def add_stripes(arr):
    """Overlay subtle stripe pattern."""
    for y in range(0, arr.shape[0], random.choice([3, 4, 5])):
        for x in range(arr.shape[1]):
            if arr[y, x, 3] > 0:
                arr[y, x, :3] = np.clip(arr[y, x, :3] - 15, 0, 255)
    return arr


def add_dots(arr):
    """Add small dot pattern."""
    for _ in range(20):
        x = random.randint(0, 39)
        y = random.randint(0, 39)
        if arr[y, x, 3] > 0:
            arr[y, x, :3] = np.clip(arr[y, x, :3] + 25, 0, 255)
    return arr


def partial_mirror(arr):
    """Mirror a random quadrant for subtle symmetry variation."""
    h, w, _ = arr.shape
    quadrant = random.choice(["left", "right"])
    if quadrant == "left":
        arr[:, :w//2] = arr[:, :w//2][:, ::-1]
    else:
        arr[:, w//2:] = arr[:, w//2:][:, ::-1]
    return arr


# ---------- Mutation Pipeline ----------

MUTATIONS = [
    color_shift,
    swap_palette,
    add_noise,
    add_stripes,
    add_dots,
    partial_mirror,
]


def mutate_sprite(img):
    arr = np.array(img)

    # Apply 1–3 random mutations
    for mutation in random.sample(MUTATIONS, random.randint(1, 3)):
        arr = mutation(arr)

    return Image.fromarray(arr, "RGBA")


# ---------- Main Processing ----------

def process_all():
    for file in os.listdir(INPUT_FOLDER):
        if not file.lower().endswith(".png"):
            continue

        base_name = os.path.splitext(file)[0]
        path = os.path.join(INPUT_FOLDER, file)

        sprite = load_sprite(path)

        for i in range(VARIANTS_PER_SPRITE):
            mutated = mutate_sprite(sprite)
            save_sprite(mutated, base_name, i)

    print("Done! Check output_sprites folder.")


if __name__ == "__main__":
    process_all()
