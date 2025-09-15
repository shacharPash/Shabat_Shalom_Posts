#!/usr/bin/env python3
"""
דוגמה 2: עיצוב מסורתי עם דפוסים יהודיים
"""

from PIL import Image, ImageDraw, ImageFont
import math

def draw_star_of_david(draw, center_x, center_y, size, color, width=3):
    """ציור מגן דוד"""
    # משולש עליון
    points1 = [
        (center_x, center_y - size),
        (center_x - size * 0.866, center_y + size * 0.5),
        (center_x + size * 0.866, center_y + size * 0.5)
    ]
    
    # משולש תחתון
    points2 = [
        (center_x, center_y + size),
        (center_x - size * 0.866, center_y - size * 0.5),
        (center_x + size * 0.866, center_y - size * 0.5)
    ]
    
    draw.polygon(points1, outline=color, width=width)
    draw.polygon(points2, outline=color, width=width)

def draw_decorative_border(draw, width, height, color):
    """ציור מסגרת מעוטרת"""
    margin = 30
    
    # מסגרת חיצונית
    draw.rectangle([margin, margin, width-margin, height-margin], 
                  outline=color, width=8)
    
    # מסגרת פנימית
    inner_margin = margin + 20
    draw.rectangle([inner_margin, inner_margin, width-inner_margin, height-inner_margin], 
                  outline=color, width=4)
    
    # עיטורים בפינות
    corner_size = 40
    corners = [
        (margin + 20, margin + 20),  # שמאל עליון
        (width - margin - 60, margin + 20),  # ימין עליון
        (margin + 20, height - margin - 60),  # שמאל תחתון
        (width - margin - 60, height - margin - 60)  # ימין תחתון
    ]
    
    for x, y in corners:
        draw_star_of_david(draw, x + corner_size//2, y + corner_size//2, corner_size//3, color, 2)

def draw_candles(draw, x, y, color):
    """ציור נרות שבת"""
    candle_width = 15
    candle_height = 60
    flame_size = 8
    
    # נר ראשון
    draw.rectangle([x, y, x + candle_width, y + candle_height], fill=color)
    draw.ellipse([x - 2, y - flame_size, x + candle_width + 2, y + 2], fill=(255, 165, 0))
    
    # נר שני
    x2 = x + candle_width + 20
    draw.rectangle([x2, y, x2 + candle_width, y + candle_height], fill=color)
    draw.ellipse([x2 - 2, y - flame_size, x2 + candle_width + 2, y + 2], fill=(255, 165, 0))

def create_traditional_design():
    """יצירת עיצוב מסורתי"""
    width, height = 1080, 1080
    
    # צבעים מסורתיים
    bg_color = (245, 245, 220)  # בז' בהיר
    border_color = (139, 69, 19)  # חום
    text_color = (25, 25, 112)   # כחול כהה
    accent_color = (184, 134, 11)  # זהב כהה
    
    # יצירת רקע
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # מסגרת מעוטרת
    draw_decorative_border(draw, width, height, border_color)
    
    # מגן דוד מרכזי (רקע)
    draw_star_of_david(draw, width//2, height//2, 200, (200, 200, 200), 2)
    
    # פונטים
    try:
        title_font = ImageFont.truetype("Arial.ttf", 70)
        subtitle_font = ImageFont.truetype("Arial.ttf", 45)
        text_font = ImageFont.truetype("Arial.ttf", 35)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # כותרת עם עיטור
    title_text = "שבת שלום"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    
    # רקע לכותרת
    draw.rounded_rectangle([title_x - 20, 120, title_x + title_width + 20, 200], 
                          radius=15, fill=(255, 255, 255, 200), outline=border_color, width=2)
    
    draw.text((title_x, 140), title_text, font=title_font, fill=text_color)
    
    # תאריך
    date_text = "26-27.09.2025"
    date_bbox = draw.textbbox((0, 0), date_text, font=subtitle_font)
    date_width = date_bbox[2] - date_bbox[0]
    date_x = (width - date_width) // 2
    draw.text((date_x, 230), date_text, font=subtitle_font, fill=accent_color)
    
    # פרשה
    parsha_text = "פרשת וילך"
    parsha_bbox = draw.textbbox((0, 0), parsha_text, font=subtitle_font)
    parsha_width = parsha_bbox[2] - parsha_bbox[0]
    parsha_x = (width - parsha_width) // 2
    draw.text((parsha_x, 290), parsha_text, font=subtitle_font, fill=text_color)
    
    # נרות שבת
    draw_candles(draw, width//2 - 40, 350, border_color)
    
    # זמנים עם רקע מעוצב
    times_y = 650
    box_width = 600
    box_height = 200
    box_x = (width - box_width) // 2
    
    # רקע לזמנים
    draw.rounded_rectangle([box_x, times_y, box_x + box_width, times_y + box_height], 
                          radius=20, fill=(255, 255, 255, 230), outline=border_color, width=3)
    
    # זמנים
    candle_text = "הדלקת נרות: 17:51"
    havdalah_text = "הבדלה: 19:05"
    
    candle_bbox = draw.textbbox((0, 0), candle_text, font=text_font)
    candle_width = candle_bbox[2] - candle_bbox[0]
    candle_x = (width - candle_width) // 2
    
    havdalah_bbox = draw.textbbox((0, 0), havdalah_text, font=text_font)
    havdalah_width = havdalah_bbox[2] - havdalah_bbox[0]
    havdalah_x = (width - havdalah_width) // 2
    
    draw.text((candle_x, times_y + 40), candle_text, font=text_font, fill=text_color)
    draw.text((havdalah_x, times_y + 100), havdalah_text, font=text_font, fill=text_color)
    
    return img

if __name__ == "__main__":
    img = create_traditional_design()
    img.save("design_traditional_example.png")
    print("נוצרה דוגמה: design_traditional_example.png")
