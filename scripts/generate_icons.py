from PIL import Image, ImageDraw
import os

def create_icon(size, output_path):
    """Generate a simple OpsBrief icon: dark blue background with a white radar symbol."""
    # Dark blue background (#0f172a)
    img = Image.new('RGB', (size, size), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)
    
    # Calculate center and radius
    cx, cy = size // 2, size // 2
    radius = int(size * 0.35)
    
    # Draw concentric circles (radar rings)
    ring_color = (59, 130, 246)  # #3b82f6 blue
    for r in [radius, int(radius * 0.65), int(radius * 0.35)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=ring_color, width=max(2, size // 100))
    
    # Draw radar sweep line (45 degrees)
    line_width = max(3, size // 60)
    draw.line([cx, cy, cx + int(radius * 0.9), cy - int(radius * 0.9)], fill=ring_color, width=line_width)
    
    # Draw a dot at the end of the sweep line
    dot_r = max(4, size // 40)
    dot_x = cx + int(radius * 0.9)
    dot_y = cy - int(radius * 0.9)
    draw.ellipse([dot_x - dot_r, dot_y - dot_r, dot_x + dot_r, dot_y + dot_r], fill=(96, 165, 250))  # lighter blue
    
    # Center dot
    center_r = max(3, size // 50)
    draw.ellipse([cx - center_r, cy - center_r, cx + center_r, cy + center_r], fill=(255, 255, 255))
    
    img.save(output_path, 'PNG')
    print(f"Created {output_path} ({size}x{size})")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, '..', 'frontend')
    os.makedirs(output_dir, exist_ok=True)
    
    create_icon(192, os.path.join(output_dir, 'icon-192.png'))
    create_icon(512, os.path.join(output_dir, 'icon-512.png'))
