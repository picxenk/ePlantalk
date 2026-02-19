import time
import os
import sys

# Ensure library path is correct
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if os.path.exists(lib_path):
    sys.path.append(lib_path)

from waveshare_epd.epd10in85 import EPD
from PIL import Image, ImageDraw, ImageFont

# Constants
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
GRID_SIZE = 50
SMALL_FONT_SIZE = 24

def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        # Fallback to default if custom font not found
        return ImageFont.load_default()

def draw_grid(draw, width, height, step):
    """Draws a grid on the image for coordinate checking."""
    # Vertical lines
    for x in range(0, width, step):
        draw.line([(x, 0), (x, height)], fill=0, width=1)
        # Draw coordinate text every 2 steps to avoid clutter
        if x % (step * 2) == 0:
            font = get_font(12)
            draw.text((x + 2, 2), str(x), font=font, fill=0)

    # Horizontal lines
    for y in range(0, height, step):
        draw.line([(0, y), (width, y)], fill=0, width=1)
        if y % (step * 2) == 0:
            font = get_font(12)
            draw.text((2, y + 2), str(y), font=font, fill=0)

def main():
    epd = None
    try:
        epd = EPD()
        print("Init and Clear")
        epd.init()
        epd.Clear()

        width, height = epd.width, epd.height
        
        # --- 1. Draw Grid ---
        print("Drawing Grid...")
        image = Image.new('1', (width, height), 255)  # 255: White
        draw = ImageDraw.Draw(image)
        
        draw_grid(draw, width, height, GRID_SIZE)
        
        epd.display(epd.getbuffer(image))
        print("Grid displayed. Waiting 3 seconds...")
        time.sleep(3)

        # --- 2. Main Loop (Static Info) ---
        while True:
            print("Updating display with status info...")
            # Re-init is good practice for long running loops to ensure wakeup
            if epd: epd.init() 

            image = Image.new('1', (width, height), 255)
            draw = ImageDraw.Draw(image)

            font = get_font(SMALL_FONT_SIZE)
            text = "moisture: 0, light: 0"
            
            # Draw at top-left (10, 10)
            draw.text((10, 10), text, font=font, fill=0)
            
            if epd:
                epd.display(epd.getbuffer(image))
                print("Status updated. Sleeping for 60s...")
                epd.sleep()
            
            time.sleep(60)

    except IOError as e:
        print(e)
    except KeyboardInterrupt:    
        print("ctrl + c:")
        if epd:
            epd.init()
            epd.Clear()
            epd.sleep()
        exit()

if __name__ == '__main__':
    main()
