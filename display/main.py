import time
import os
import sys
import subprocess
import json
import urllib.request

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
LOG_FONT_SIZE = 10
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("Error: config.json not found.")
        print("Please copy 'config.example.json' to 'config.json' and customize it.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_font(size):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except IOError:
        # Fallback to default if custom font not found
        return ImageFont.load_default()

def get_wifi_ssid():
    try:
        # iwgetid -r prints only the SSID
        ssid = subprocess.check_output(['iwgetid', '-r']).decode('utf-8').strip()
        if not ssid:
            return "No WiFi"
        return ssid
    except Exception:
        return "WiFi Error"

def get_sensor_value(endpoint, sensor_ip):
    """
    Fetches sensor data from ESP32.
    Endpoint should be 'moisture' or 'light'.
    Returns the 'value' from JSON or None if failed.
    """
    url = f"http://{sensor_ip}/sensor/{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                return data.get('value')
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
    return None

def main():
    config = load_config()
    sensor_ip = config.get('sensor_ip', '192.168.4.1')
    target_ssid_prefix = config.get('target_ssid_prefix', 'ePlantalk')
    update_interval = config.get('update_interval', 7)
    
    # Display alignment configuration
    display_x_offset = config.get('display_x_offset', 0)
    display_y_offset = config.get('display_y_offset', 0)
    display_width = config.get('display_width', 1360)
    display_height = config.get('display_height', 480)

    epd = None
    try:
        epd = EPD()
        print("Init...")
        epd.init()
        # epd.Clear() # Removed to match test_blink.py behavior and avoid potential hang

        # Use configured dimensions instead of hardware full size for drawing area
        # width, height = epd.width, epd.height 
        width = display_width
        height = display_height
        
        # --- 1. Draw Grid on Hardware Canvas ---
        print("Drawing Grid on full hardware canvas...")
        
        full_width, full_height = epd.width, epd.height
        full_image = Image.new('1', (full_width, full_height), 255) # 255: White background
        full_draw = ImageDraw.Draw(full_image)

        # Draw grid on the full hardware area
        # Vertical lines
        for x in range(0, full_width, GRID_SIZE):
            full_draw.line([(x, 0), (x, full_height)], fill=0, width=1)
            if x % (GRID_SIZE * 2) == 0:
                font = get_font(12)
                full_draw.text((x + 2, 2), str(x), font=font, fill=0)

        # Horizontal lines
        for y in range(0, full_height, GRID_SIZE):
            full_draw.line([(0, y), (full_width, y)], fill=0, width=1)
            if y % (GRID_SIZE * 2) == 0:
                font = get_font(12)
                full_draw.text((2, y + 2), str(y), font=font, fill=0)
        
        # Draw thick border for the logical display area
        print(f"Drawing logical area border: {display_width}x{display_height} at ({display_x_offset}, {display_y_offset})")
        full_draw.rectangle(
            [
                (display_x_offset, display_y_offset), 
                (display_x_offset + display_width - 1, display_y_offset + display_height - 1)
            ], 
            outline=0, 
            width=3
        )

        epd.display(epd.getbuffer(full_image))
        print("Grid displayed. Waiting 3 seconds...")
        time.sleep(3)

        # --- 2. Main Loop (Static Info) ---
        dummy_moisture = 0
        dummy_light = 0
        
        while True:
            print("Updating display with status info...")
            # Re-init is good practice for long running loops to ensure wakeup
            if epd: epd.init() 

            # Create full image (hardware size)
            full_image = Image.new('1', (full_width, full_height), 255)
            
            # Create canvas for logical area
            canvas = Image.new('1', (display_width, display_height), 255)
            draw = ImageDraw.Draw(canvas)

            # Get WiFi SSID
            ssid = get_wifi_ssid()
            
            # Determine values based on SSID
            final_moisture = 0
            final_light = 0
            
            is_connected_to_sensor = False
            if target_ssid_prefix in ssid:
                print(f"Connected to {ssid}, fetching sensor data from {sensor_ip}...")
                m_val = get_sensor_value("moisture", sensor_ip)
                l_val = get_sensor_value("light", sensor_ip)
                
                if m_val is not None and l_val is not None:
                    final_moisture = m_val
                    final_light = l_val
                    is_connected_to_sensor = True
                else:
                    print("Failed to fetch sensor data, using dummy values.")
            
            if not is_connected_to_sensor:
                print("Using dummy values (incrementing).")
                final_moisture = dummy_moisture
                final_light = dummy_light
                # Increment dummy values
                dummy_moisture += 1
                dummy_light += 1
                
                # Show development mode message
                dev_font = get_font(100)
                dev_text = "식물의 마음을\n읽을 수 없어요."
                bbox = draw.textbbox((0, 0), dev_text, font=dev_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                # Center the text
                x = (display_width - text_w) // 2
                y = (display_height - text_h) // 2
                draw.text((x, y), dev_text, font=dev_font, fill=0, align="center")

            font = get_font(LOG_FONT_SIZE)
            text = f"moisture: {final_moisture}, light: {final_light}"
            
            # Draw at top-left (10, 10)
            draw.text((10, 10), text, font=font, fill=0)

            # Draw WiFi SSID at top-right
            wifi_font = get_font(LOG_FONT_SIZE)
            
            # Calculate text size to align right
            bbox = draw.textbbox((0, 0), ssid, font=wifi_font)
            text_w = bbox[2] - bbox[0]
            # text_h = bbox[3] - bbox[1]
            
            x_pos = width - text_w - 10 # 10px margin from right
            draw.text((x_pos, 10), ssid, font=wifi_font, fill=0)
            
            if epd:
                # Paste canvas onto full image
                full_image.paste(canvas, (display_x_offset, display_y_offset))
                epd.display(epd.getbuffer(full_image))
                print(f"Status updated: {text} (SSID: {ssid}). Sleeping for {update_interval}s...")
                # epd.sleep() # Avoid sleep for fast updates to prevent re-init overhead/flashing
            
            time.sleep(update_interval)

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
