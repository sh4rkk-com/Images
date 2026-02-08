import os
import sys
from pathlib import Path
from PIL import Image
import concurrent.futures

def should_use_low_compression(filename, img_width, img_height):
    """
    Determine if an image should use lower compression (higher quality).
    Thumbnail-like images get better quality to avoid visible artifacts.
    
    Args:
        filename (str): The image filename
        img_width (int): Image width in pixels
        img_height (int): Image height in pixels
    
    Returns:
        bool: True if lower compression should be used
    """
    filename_lower = filename.lower()
    
    # Check for thumbnail indicators in filename
    thumbnail_indicators = ['thumb', 'thumbnail', 'banner', 'hero', 'large', 'cover', 'featured']
    if any(indicator in filename_lower for indicator in thumbnail_indicators):
        return True
    
    # Check image dimensions - larger images get better quality
    total_pixels = img_width * img_height
    if total_pixels > 800 * 600:  # Images larger than ~0.5MP get better quality
        return True
    
    return False

def convert_image_to_webp(input_path, output_path, default_quality=75, low_compression_quality=85):
    """
    Convert an image to WebP format with smart quality settings.
    Preserves transparency for images with alpha channels, converts others without.
    
    Args:
        input_path (Path): Path to the input image
        output_path (Path): Path for the output WebP image
        default_quality (int): Default WebP quality for regular images
        low_compression_quality (int): Higher quality for thumbnails/large images
    """
    try:
        with Image.open(input_path) as img:
            # Get image dimensions for quality decision
            width, height = img.size
            
            # Determine optimal quality setting
            if should_use_low_compression(input_path.name, width, height):
                quality = low_compression_quality
                quality_type = "high quality (thumbnail/large image)"
            else:
                quality = default_quality
                quality_type = "standard quality"
            
            # Check if image has transparency by looking at mode and info
            has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
            
            if has_alpha:
                # Preserve transparency for images with alpha channel
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                
                # Use slower but better compression method for alpha
                img.save(output_path, 'WEBP', quality=quality, method=6, lossless=False)
                
            else:
                # Convert to RGB for images without transparency
                if img.mode == 'P':
                    img = img.convert('RGB')
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
                
                # Save as WebP without transparency
                img.save(output_path, 'WEBP', quality=quality, method=6)
            
            # Get file size info
            original_size = input_path.stat().st_size
            new_size = output_path.stat().st_size
            compression_ratio = (1 - new_size / original_size) * 100
            
            transparency_status = "with transparency" if has_alpha else "without transparency"
            print(f"✓ Converted: {input_path.name}")
            print(f"  Quality: {quality} ({quality_type}), {transparency_status}")
            print(f"  Size: {original_size/1024:.1f}KB → {new_size/1024:.1f}KB ({compression_ratio:.1f}% smaller)")
            
            return True
            
    except Exception as e:
        print(f"✗ Failed to convert {input_path}: {str(e)}")
        return False

def process_directory(root_dir, output_base_dir, default_quality=75, low_compression_quality=85):
    """
    Process all images in directory and subdirectories.
    
    Args:
        root_dir (Path): Root directory to process
        output_base_dir (Path): Base output directory
        default_quality (int): Default WebP quality for regular images
        low_compression_quality (int): Higher quality for thumbnails/large images
    """
    # Supported image formats (EXCLUDING GIFs)
    supported_formats = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    
    # Find all image files
    image_files = []
    for format_ext in supported_formats:
        image_files.extend(root_dir.rglob(f'*{format_ext}'))
        image_files.extend(root_dir.rglob(f'*{format_ext.upper()}'))
    
    print(f"Found {len(image_files)} images to process (GIFs are ignored)...")
    
    # Process images with threading for better performance
    successful_conversions = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        future_to_path = {}
        
        for input_path in image_files:
            # Create corresponding output path
            relative_path = input_path.relative_to(root_dir)
            output_path = output_base_dir / relative_path.with_suffix('.webp')
            
            # Create output directory if it doesn't exist
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Skip if output already exists and is newer
            if output_path.exists() and output_path.stat().st_mtime > input_path.stat().st_mtime:
                print(f"⏭️  Skipping (already processed): {input_path.name}")
                continue
            
            # Submit conversion task
            future = executor.submit(
                convert_image_to_webp, 
                input_path, 
                output_path, 
                default_quality, 
                low_compression_quality
            )
            future_to_path[future] = input_path
        
        # Process completed tasks
        for future in concurrent.futures.as_completed(future_to_path):
            input_path = future_to_path[future]
            try:
                if future.result():
                    successful_conversions += 1
            except Exception as e:
                print(f"✗ Error processing {input_path}: {str(e)}")
    
    return successful_conversions, len(image_files)

def main():
    """Main function to orchestrate the conversion process."""
    # Get current directory
    current_dir = Path.cwd()
    output_dir = current_dir / "Processed_Images"
    
    print("🖼️  Image to WebP Converter")
    print("=" * 50)
    print(f"Input directory: {current_dir}")
    print(f"Output directory: {output_dir}")
    print("✓ GIF files are ignored")
    print("✓ Smart quality settings:")
    print("  - Standard images: 75 quality (good compression)")
    print("  - Thumbnails/large images: 85 quality (better quality)")
    print("✓ Transparency preserved for PNG/alpha images")
    print()
    
    # Check if output directory exists, create if not
    output_dir.mkdir(exist_ok=True)
    
    # Process all images with smart quality settings
    successful, total = process_directory(
        current_dir, 
        output_dir, 
        default_quality=75, 
        low_compression_quality=85
    )
    
    print()
    print("=" * 50)
    print("🎉 Conversion complete!")
    print(f"Successfully converted: {successful}/{total} images")
    print(f"Output location: {output_dir}")
    
    if successful < total:
        print("Some images failed to convert. Check the logs above for details.")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    # Verify PIL is available
    try:
        from PIL import Image
    except ImportError:
        print("Error: Pillow library is required but not installed.")
        print("Please install it using: pip install Pillow")
        sys.exit(1)
    
    main()