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
WIFI_FONT_SIZE = 10
SENSOR_IP = "192.168.4.1"
TARGET_SSID_PREFIX = "ePlantalk"

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

def get_sensor_value(endpoint):
    """
    Fetches sensor data from ESP32.
    Endpoint should be 'moisture' or 'light'.
    Returns the 'value' from JSON or None if failed.
    """
    url = f"http://{SENSOR_IP}/sensor/{endpoint}"
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            if response.getcode() == 200:
                data = json.loads(response.read().decode())
                return data.get('value')
    except Exception as e:
        print(f"Error fetching {endpoint}: {e}")
    return None

def main():
    epd = None
    try:
        epd = EPD()
        print("Init...")
        epd.init()
        # epd.Clear() # Removed to match test_blink.py behavior and avoid potential hang

        width, height = epd.width, epd.height
        
        # --- 1. Draw Grid ---
        print("Drawing Grid...")
        image = Image.new('1', (width, height), 255)  # 255: White
        draw = ImageDraw.Draw(image)
        
        # Vertical lines
        print(f"Drawing vertical lines (step: {GRID_SIZE})...")
        for x in range(0, width, GRID_SIZE):
            draw.line([(x, 0), (x, height)], fill=0, width=1)
            if x % (GRID_SIZE * 2) == 0:
                font = get_font(12)
                draw.text((x + 2, 2), str(x), font=font, fill=0)

        # Horizontal lines
        print(f"Drawing horizontal lines (step: {GRID_SIZE})...")
        for y in range(0, height, GRID_SIZE):
            draw.line([(0, y), (width, y)], fill=0, width=1)
            if y % (GRID_SIZE * 2) == 0:
                font = get_font(12)
                draw.text((2, y + 2), str(y), font=font, fill=0)
        
        print("Sending buffer to display...")
        epd.display(epd.getbuffer(image))
        print("Grid displayed. Waiting 3 seconds...")
        time.sleep(3)

        # --- 2. Main Loop (Static Info) ---
        dummy_moisture = 0
        dummy_light = 0
        
        while True:
            print("Updating display with status info...")
            # Re-init is good practice for long running loops to ensure wakeup
            if epd: epd.init() 

            image = Image.new('1', (width, height), 255)
            draw = ImageDraw.Draw(image)

            # Get WiFi SSID
            ssid = get_wifi_ssid()
            
            # Determine values based on SSID
            final_moisture = 0
            final_light = 0
            
            is_connected_to_sensor = False
            if TARGET_SSID_PREFIX in ssid:
                print(f"Connected to {ssid}, fetching sensor data...")
                m_val = get_sensor_value("moisture")
                l_val = get_sensor_value("light")
                
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

            font = get_font(SMALL_FONT_SIZE)
            text = f"moisture: {final_moisture}, light: {final_light}"
            
            # Draw at top-left (10, 10)
            draw.text((10, 10), text, font=font, fill=0)

            # Draw WiFi SSID at top-right
            wifi_font = get_font(WIFI_FONT_SIZE)
            
            # Calculate text size to align right
            bbox = draw.textbbox((0, 0), ssid, font=wifi_font)
            text_w = bbox[2] - bbox[0]
            # text_h = bbox[3] - bbox[1]
            
            x_pos = width - text_w - 10 # 10px margin from right
            draw.text((x_pos, 10), ssid, font=wifi_font, fill=0)
            
            if epd:
                epd.display(epd.getbuffer(image))
                print(f"Status updated: {text} (SSID: {ssid}). Sleeping for 7s...")
                # epd.sleep() # Avoid sleep for fast updates to prevent re-init overhead/flashing
            
            time.sleep(7)

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
