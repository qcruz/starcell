#!/usr/bin/env python3
"""
Starcell Sprite Processor
Automatically crops black borders and resizes sprites to 40x40 for game use
"""

from PIL import Image
import os
import sys

def process_sprite(input_path, output_path=None, target_size=40, verbose=True):
    """
    Process a sprite for Starcell game use
    
    Args:
        input_path: Path to the input sprite image
        output_path: Path for output (if None, saves as inputname_40x40.png)
        target_size: Target size in pixels (default 40)
        verbose: Print progress messages
    
    Returns:
        Path to the output file
    """
    if not os.path.exists(input_path):
        print(f"Error: File not found: {input_path}")
        return None
    
    # Load image
    img = Image.open(input_path)
    if verbose:
        print(f"Processing: {input_path}")
        print(f"  Original size: {img.size[0]}x{img.size[1]}")
    
    # Convert to RGBA if needed
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    pixels = img.load()
    width, height = img.size
    
    # Find content bounds (non-black, non-transparent pixels)
    min_x, min_y = width, height
    max_x, max_y = 0, 0
    
    for y in range(height):
        for x in range(width):
            pixel = pixels[x, y]
            # Check if pixel is not black/transparent (threshold 30)
            if len(pixel) >= 3 and sum(pixel[:3]) > 30:
                min_x = min(min_x, x)
                min_y = min(min_y, y)
                max_x = max(max_x, x)
                max_y = max(max_y, y)
    
    # Crop to content
    if max_x >= min_x and max_y >= min_y:
        cropped = img.crop((min_x, min_y, max_x + 1, max_y + 1))
        if verbose:
            print(f"  Cropped to: {cropped.size[0]}x{cropped.size[1]} (removed borders)")
    else:
        cropped = img
        if verbose:
            print(f"  No borders to remove")
    
    # Make square by centering in larger dimension
    crop_width, crop_height = cropped.size
    max_dim = max(crop_width, crop_height)
    
    # Create transparent square canvas
    square = Image.new('RGBA', (max_dim, max_dim), color=(0, 0, 0, 0))
    paste_x = (max_dim - crop_width) // 2
    paste_y = (max_dim - crop_height) // 2
    square.paste(cropped, (paste_x, paste_y))
    
    if verbose:
        print(f"  Made square: {max_dim}x{max_dim}")
    
    # Resize to target size with high quality
    final = square.resize((target_size, target_size), Image.Resampling.LANCZOS)
    
    if verbose:
        print(f"  Resized to: {target_size}x{target_size}")
    
    # Determine output path
    if output_path is None:
        base = os.path.splitext(input_path)[0]
        output_path = f"{base}_{target_size}x{target_size}.png"
    
    # Save
    final.save(output_path, 'PNG')
    
    if verbose:
        print(f"  ✓ Saved to: {output_path}\n")
    
    return output_path

def batch_process(directory=".", target_size=40):
    """Process all PNG files in a directory"""
    processed = 0
    
    for filename in os.listdir(directory):
        if filename.lower().endswith('.png') and not filename.endswith(f'_{target_size}x{target_size}.png'):
            input_path = os.path.join(directory, filename)
            output_name = filename.replace('.png', f'_{target_size}x{target_size}.png')
            output_path = os.path.join(directory, output_name)
            
            process_sprite(input_path, output_path, target_size)
            processed += 1
    
    print(f"Processed {processed} sprites")

if __name__ == "__main__":
    print("Starcell Sprite Processor")
    print("=" * 50)
    
    if len(sys.argv) < 2:
        print("\nUsage:")
        print("  Single file:  python sprite_processor.py grass.png")
        print("  Batch mode:   python sprite_processor.py --batch [directory]")
        print("  Custom size:  python sprite_processor.py grass.png --size 64")
        print("\nExamples:")
        print("  python sprite_processor.py grass.png")
        print("  python sprite_processor.py grass.png --size 32")
        print("  python sprite_processor.py --batch sprites/")
        sys.exit(1)
    
    # Parse arguments
    if sys.argv[1] == '--batch':
        directory = sys.argv[2] if len(sys.argv) > 2 else "."
        batch_process(directory)
    else:
        input_file = sys.argv[1]
        target_size = 40
        output_file = None
        
        # Check for --size flag
        if '--size' in sys.argv:
            size_index = sys.argv.index('--size')
            if len(sys.argv) > size_index + 1:
                target_size = int(sys.argv[size_index + 1])
        
        # Check for --output flag
        if '--output' in sys.argv:
            output_index = sys.argv.index('--output')
            if len(sys.argv) > output_index + 1:
                output_file = sys.argv[output_index + 1]
        
        process_sprite(input_file, output_file, target_size)