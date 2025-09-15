#!/usr/bin/env python3
"""
דוגמה 5: עיצוב צבעוני עם אייקונים
"""

from PIL import Image, ImageDraw, ImageFont
import math

def draw_candle_icon(draw, x, y, size, flame_color=(255, 165, 0), candle_color=(139, 69, 19)):
    """ציור אייקון נר"""
    # גוף הנר
    candle_width = size // 3
    candle_height = size
    draw.rectangle([x, y, x + candle_width, y + candle_height], fill=candle_color)
    
    # להבה
    flame_size = size // 4
    flame_x = x + candle_width // 2
    flame_y = y - flame_size
    
    # להבה כאליפסה
    draw.ellipse([flame_x - flame_size//2, flame_y, 
                 flame_x + flame_size//2, flame_y + flame_size], fill=flame_color)
    
    # נקודת אור בלהבה
    draw.ellipse([flame_x - 2, flame_y + flame_size//3, 
                 flame_x + 2, flame_y + flame_size//3 + 4], fill=(255, 255, 255))

def draw_star_icon(draw, x, y, size, color):
    """ציור אייקון כוכב"""
    points = []
    for i in range(10):
        angle = math.pi * i / 5
        if i % 2 == 0:
            radius = size
        else:
            radius = size * 0.5
        
        px = x + radius * math.cos(angle - math.pi/2)
        py = y + radius * math.sin(angle - math.pi/2)
        points.append((px, py))
    
    draw.polygon(points, fill=color)

def draw_wine_cup(draw, x, y, size, color):
    """ציון כוס יין (לקידוש/הבדלה)"""
    # כוס
    cup_width = size
    cup_height = size // 2
    draw.ellipse([x, y, x + cup_width, y + cup_height], fill=color)
    
    # רגל הכוס
    stem_width = size // 6
    stem_height = size // 3
    stem_x = x + cup_width//2 - stem_width//2
    draw.rectangle([stem_x, y + cup_height, stem_x + stem_width, y + cup_height + stem_height], 
                  fill=color)
    
    # בסיס
    base_width = size // 2
    base_height = size // 8
    base_x = x + cup_width//2 - base_width//2
    draw.rectangle([base_x, y + cup_height + stem_height, 
                   base_x + base_width, y + cup_height + stem_height + base_height], 
                  fill=color)

def create_colorful_design():
    """יצירת עיצוב צבעוני עם אייקונים"""
    width, height = 1080, 1080
    
    # צבעים חמים וצבעוניים
    bg_color = (253, 251, 247)  # קרם חם
    primary_color = (74, 20, 140)  # סגול כהה
    accent_color = (255, 107, 107)  # אדום חם
    secondary_color = (54, 162, 235)  # כחול בהיר
    gold_color = (255, 193, 7)  # זהב
    
    # יצירת רקע עם גרדיאנט עדין
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # עיגולים דקורטיביים ברקע
    for i in range(5):
        alpha = 30 - (i * 5)
        color = (accent_color[0], accent_color[1], accent_color[2], alpha)
        radius = 200 + (i * 50)
        draw.ellipse([width//2 - radius, height//2 - radius, 
                     width//2 + radius, height//2 + radius], 
                    outline=color, width=2)
    
    # פונטים
    try:
        title_font = ImageFont.truetype("Arial.ttf", 85)
        subtitle_font = ImageFont.truetype("Arial.ttf", 50)
        text_font = ImageFont.truetype("Arial.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # כותרת עם רקע צבעוני
    title_text = "שבת שלום"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    
    # רקע לכותרת
    padding = 30
    draw.rounded_rectangle([title_x - padding, 130, title_x + title_width + padding, 220], 
                          radius=25, fill=primary_color)
    
    draw.text((title_x, 150), title_text, font=title_font, fill=(255, 255, 255))
    
    # כוכבים דקורטיביים ליד הכותרת
    draw_star_icon(draw, title_x - 80, 160, 20, gold_color)
    draw_star_icon(draw, title_x + title_width + 50, 160, 20, gold_color)
    
    # תאריך עם רקע
    date_text = "26-27.09.2025"
    date_bbox = draw.textbbox((0, 0), date_text, font=subtitle_font)
    date_width = date_bbox[2] - date_bbox[0]
    date_x = (width - date_width) // 2
    
    draw.rounded_rectangle([date_x - 20, 260, date_x + date_width + 20, 320], 
                          radius=15, fill=secondary_color)
    draw.text((date_x, 275), date_text, font=subtitle_font, fill=(255, 255, 255))
    
    # פרשה
    parsha_text = "פרשת וילך"
    parsha_bbox = draw.textbbox((0, 0), parsha_text, font=subtitle_font)
    parsha_width = parsha_bbox[2] - parsha_bbox[0]
    parsha_x = (width - parsha_width) // 2
    draw.text((parsha_x, 360), parsha_text, font=subtitle_font, fill=primary_color)
    
    # נרות שבת עם אייקונים
    candle_y = 450
    draw_candle_icon(draw, width//2 - 60, candle_y, 60)
    draw_candle_icon(draw, width//2 + 20, candle_y, 60)
    
    # זמנים עם אייקונים
    times_y = 600
    
    # רקע לזמנים
    draw.rounded_rectangle([100, times_y - 20, width - 100, times_y + 200], 
                          radius=20, fill=(255, 255, 255, 200), outline=accent_color, width=3)
    
    # הדלקת נרות
    candle_icon_x = 150
    draw_candle_icon(draw, candle_icon_x, times_y + 20, 40, (255, 140, 0), (139, 69, 19))
    draw.text((candle_icon_x + 80, times_y + 30), "הדלקת נרות: 17:51", 
             font=text_font, fill=primary_color)
    
    # הבדלה
    havdalah_y = times_y + 100
    draw_wine_cup(draw, candle_icon_x, havdalah_y + 10, 40, (128, 0, 128))
    draw.text((candle_icon_x + 80, havdalah_y + 20), "הבדלה: 19:05", 
             font=text_font, fill=primary_color)
    
    # עיטורים תחתונים
    bottom_y = 900
    for i in range(7):
        x = 200 + (i * 100)
        draw_star_icon(draw, x, bottom_y, 15, gold_color)
    
    return img

if __name__ == "__main__":
    img = create_colorful_design()
    img.save("design_colorful_example.png")
    print("נוצרה דוגמה: design_colorful_example.png")
