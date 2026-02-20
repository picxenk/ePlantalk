import time
import os
import sys
import subprocess
import json
import urllib.request
import random

# Ensure library path is correct
lib_path = os.path.join(os.path.dirname(__file__), 'lib')
if os.path.exists(lib_path):
    sys.path.append(lib_path)

from waveshare_epd.epd10in85 import EPD
from PIL import Image, ImageDraw, ImageFont

# Constants
SYSTEM_FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FONTS_DIR = os.path.join(PROJECT_ROOT, 'fonts')

FONT_MAP = {
    1: SYSTEM_FONT_PATH,
    2: os.path.join(FONTS_DIR, "GmarketSansTTFBold.ttf"),
    3: os.path.join(FONTS_DIR, "GmarketSansTTFMedium.ttf"),
    4: os.path.join(FONTS_DIR, "GmarketSansTTFLight.ttf"),
    5: os.path.join(FONTS_DIR, "RIDIBatang.otf")
}

GRID_SIZE = 50
SMALL_FONT_SIZE = 24
LOG_FONT_SIZE = 10
CONFIG_FILE = os.path.join(os.path.dirname(__file__), 'config.json')

# Global Font Cache
FONT_CACHE = {}

def load_config():
    if not os.path.exists(CONFIG_FILE):
        print("Error: config.json not found.")
        print("Please copy 'config.example.json' to 'config.json' and customize it.")
        sys.exit(1)
    
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def get_font_path(font_id):
    """Returns the absolute path for the given font ID."""
    return FONT_MAP.get(font_id, SYSTEM_FONT_PATH)

def get_font(size, font_path=None):
    if font_path is None:
        font_path = SYSTEM_FONT_PATH
    
    # Check cache first
    key = (font_path, size)
    if key in FONT_CACHE:
        return FONT_CACHE[key]

    try:
        font = ImageFont.truetype(font_path, size)
        FONT_CACHE[key] = font
        return font
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

def get_message_for_state(moisture, light, config):
    """
    Determines the state based on sensor values and returns a random message dictionary.
    Returns: {'text': str, 'font_id': int}
    """
    thresholds = config.get('thresholds', {})
    m_low = thresholds.get('moisture_low', 1.2)
    m_high = thresholds.get('moisture_high', 2.5)
    l_bright = thresholds.get('light_bright', 1.5)
    
    # Determine Moisture State
    if moisture < m_low:
        m_state = "dry"
    elif moisture < m_high: # Corrected logic: moisture >= m_low AND moisture < m_high
        m_state = "normal"
    else:
        m_state = "wet"
        
    # Determine Light State
    if light < l_bright:
        l_state = "dark"
    else:
        l_state = "bright"
        
    state_key = f"{m_state}_{l_state}"
    # print(f"Current State: {state_key} (Moisture: {moisture}, Light: {light})")
    
    messages_dict = config.get('messages', {})
    messages = messages_dict.get(state_key, [])
    
    default_font_id = config.get('default_font_id', 1)

    if not messages:
        return {"text": "...", "font_id": default_font_id}
        
    selected = random.choice(messages)
    
    # Handle string (legacy) or dict (new) format
    if isinstance(selected, str):
        return {"text": selected, "font_id": default_font_id}
    elif isinstance(selected, dict):
        return {
            "text": selected.get("text", "..."), 
            "font_id": selected.get("font_id", default_font_id)
        }
    
    return {"text": "Format Error", "font_id": default_font_id}

def draw_multiline_text(draw, text, box_width, box_height, font_path):
    """
    Draws text centered in the box, automatically wrapping lines and adjusting font size.
    """
    if not text:
        return

    # Start with a large font size and decrease until it fits
    font_size = 100
    min_font_size = 20
    
    final_lines = []
    final_font = None
    final_line_height = 0
    final_line_spacing = 0
    
    lines = [] # Initialize to avoid unbound error
    font = None

    while font_size >= min_font_size:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            font = ImageFont.load_default()
            # If default font, we can't resize. Just wrap and break.
            min_font_size = 1000 # Force break loop
            
        # Try to wrap text with current font size
        words = text.split()
        lines = []
        current_line = []
        
        # Simple word wrap
        for word in words:
            # Use current_line + [word] to test length
            # If empty current_line, just [word]
            if not current_line:
                test_line_str = word
            else:
                test_line_str = ' '.join(current_line + [word])
            
            bbox = draw.textbbox((0, 0), test_line_str, font=font)
            w = bbox[2] - bbox[0]
            
            if w <= box_width:
                current_line.append(word)
            else:
                if current_line:
                    lines.append(' '.join(current_line))
                    current_line = [word]
                else:
                    # Word itself is too long, just add it
                    lines.append(word)
                    current_line = []
        
        if current_line:
            lines.append(' '.join(current_line))
            
        # Check total height
        bbox_sample = draw.textbbox((0, 0), "Tg", font=font)
        h_line = bbox_sample[3] - bbox_sample[1]
        line_spacing = int(h_line * 0.2)
        total_height = len(lines) * h_line + (len(lines) - 1) * line_spacing
        
        if total_height <= box_height:
            # It fits! Save and break.
            final_lines = lines
            final_font = font
            final_line_height = h_line
            final_line_spacing = line_spacing
            break
            
        font_size -= 5
    
    # If loop finished without break (didn't fit even at min size), use min size results (last attempt)
    if not final_lines:
        final_lines = lines 
        final_font = font
        # If font was never loaded or lines empty (unlikely), set defaults
        if final_font is None:
             try:
                 final_font = ImageFont.truetype(font_path, min_font_size)
             except:
                 final_font = ImageFont.load_default()
        
        # Recalculate height for fallback
        bbox_sample = draw.textbbox((0, 0), "Tg", font=final_font)
        final_line_height = bbox_sample[3] - bbox_sample[1]
        final_line_spacing = int(final_line_height * 0.2)
        print("Warning: Text too long to fit perfectly, drawing with minimum size.")

    # Calculate total height for vertical centering
    total_text_height = len(final_lines) * final_line_height + (len(final_lines) - 1) * final_line_spacing
    start_y = (box_height - total_text_height) // 2
    
    current_y = start_y
    for line in final_lines:
        bbox = draw.textbbox((0, 0), line, font=final_font)
        w = bbox[2] - bbox[0]
        x = (box_width - w) // 2
        draw.text((x, current_y), line, font=final_font, fill=0)
        current_y += final_line_height + final_line_spacing

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
    show_log_messages = config.get('show_log_messages', True)

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
            text = "" # Initialize text variable safely
            
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
                dev_font = get_font(100, SYSTEM_FONT_PATH)
                text = "식물의 마음을\n읽을 수 없어요."
                bbox = draw.textbbox((0, 0), text, font=dev_font)
                text_w = bbox[2] - bbox[0]
                text_h = bbox[3] - bbox[1]
                
                # Center the text
                x = (display_width - text_w) // 2
                y = (display_height - text_h) // 2
                draw.text((x, y), text, font=dev_font, fill=0, align="center")
            
            else:
                # Connected to sensor: Show real message based on state
                message_data = get_message_for_state(final_moisture, final_light, config)
                text = message_data.get('text', '')
                font_id = message_data.get('font_id', 1)
                font_path = get_font_path(font_id)
                
                # Draw multiline text centered
                draw_multiline_text(draw, text, display_width, display_height, font_path)


            if show_log_messages:
                font = get_font(LOG_FONT_SIZE)
                log_text = f"moisture: {final_moisture}, light: {final_light}"
                
                # Draw at top-left (10, 10)
                draw.text((10, 10), log_text, font=font, fill=0)

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
                status_text = text if 'text' in locals() else "no log"
                print(f"Status updated: {status_text} (SSID: {ssid}). Sleeping for {update_interval}s...")
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
