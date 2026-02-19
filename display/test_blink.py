import time
from lib.waveshare_epd.epd10in85 import EPD
from PIL import Image, ImageDraw, ImageFont

TEXTS = ["안녕 세상아", "Hello, World"]
FONT_PATH = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"

epd = EPD()

W, H = epd.width, epd.height

while True:
    for TEXT in TEXTS:
        epd.init()   # ⭐ 핵심: 매번 다시 초기화

        image = Image.new("1", (W, H), 255)
        draw = ImageDraw.Draw(image)

        test_size = 300
        font = ImageFont.truetype(FONT_PATH, test_size)
        bbox = draw.textbbox((0, 0), TEXT, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        scale = (W * 0.9) / text_w
        final_size = int(test_size * scale)

        font = ImageFont.truetype(FONT_PATH, final_size)
        bbox = draw.textbbox((0, 0), TEXT, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        x = (W - text_w) // 2
        y = (H - text_h) // 2

        draw.text((x, y), TEXT, font=font, fill=0)

        epd.display(epd.getbuffer(image))
        time.sleep(4)