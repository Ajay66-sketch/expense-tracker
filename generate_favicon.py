from PIL import Image, ImageDraw, ImageFont

# --- Settings ---
size = (32, 32)              # Favicon size
bg_color = (30, 144, 255)    # Background color (blue)
text_color = (255, 255, 255) # Text color (white)
text = "E"                    # Letter to show in favicon
font_path = None              # Use default font
output_path = "favicon.ico"

# --- Create Image ---
img = Image.new("RGBA", size, bg_color)
draw = ImageDraw.Draw(img)

# --- Add Text ---
font_size = 24
if font_path:
    font = ImageFont.truetype(font_path, font_size)
else:
    font = ImageFont.load_default()

# --- Calculate text position to center using textbbox ---
bbox = draw.textbbox((0, 0), text, font=font)
text_width = bbox[2] - bbox[0]
text_height = bbox[3] - bbox[1]
position = ((size[0]-text_width)/2, (size[1]-text_height)/2)

draw.text(position, text, fill=text_color, font=font)

# --- Save as favicon.ico ---
img.save(output_path, format="ICO")
print(f"favicon saved as {output_path}")
