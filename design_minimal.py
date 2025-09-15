#!/usr/bin/env python3
"""
דוגמה 4: עיצוב מינימליסטי אלגנטי
"""

from PIL import Image, ImageDraw, ImageFont
import math

def create_minimal_design():
    """יצירת עיצוב מינימליסטי אלגנטי"""
    width, height = 1080, 1080
    
    # צבעים מינימליסטיים
    bg_color = (248, 249, 250)  # לבן חם
    primary_color = (33, 37, 41)  # שחור רך
    accent_color = (0, 123, 255)  # כחול נקי
    secondary_color = (108, 117, 125)  # אפור
    
    # יצירת רקע
    img = Image.new('RGB', (width, height), bg_color)
    draw = ImageDraw.Draw(img)
    
    # קו דק עליון
    draw.rectangle([0, 0, width, 8], fill=accent_color)
    
    # פונטים
    try:
        title_font = ImageFont.truetype("Arial.ttf", 90)
        subtitle_font = ImageFont.truetype("Arial.ttf", 48)
        text_font = ImageFont.truetype("Arial.ttf", 42)
        small_font = ImageFont.truetype("Arial.ttf", 36)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
        small_font = ImageFont.load_default()
    
    # כותרת מינימליסטית
    title_text = "שבת שלום"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    
    draw.text((title_x, 150), title_text, font=title_font, fill=primary_color)
    
    # קו דק תחת הכותרת
    line_width = 200
    line_x = (width - line_width) // 2
    draw.rectangle([line_x, 270, line_x + line_width, 274], fill=accent_color)
    
    # תאריך
    date_text = "26-27.09.2025"
    date_bbox = draw.textbbox((0, 0), date_text, font=subtitle_font)
    date_width = date_bbox[2] - date_bbox[0]
    date_x = (width - date_width) // 2
    draw.text((date_x, 320), date_text, font=subtitle_font, fill=secondary_color)
    
    # פרשה
    parsha_text = "פרשת וילך"
    parsha_bbox = draw.textbbox((0, 0), parsha_text, font=subtitle_font)
    parsha_width = parsha_bbox[2] - parsha_bbox[0]
    parsha_x = (width - parsha_width) // 2
    draw.text((parsha_x, 390), parsha_text, font=subtitle_font, fill=primary_color)
    
    # אזור זמנים מינימליסטי
    times_y = 520
    
    # כותרת זמנים
    times_title = "זמנים"
    times_title_bbox = draw.textbbox((0, 0), times_title, font=text_font)
    times_title_width = times_title_bbox[2] - times_title_bbox[0]
    times_title_x = (width - times_title_width) // 2
    draw.text((times_title_x, times_y), times_title, font=text_font, fill=accent_color)
    
    # קו דק תחת "זמנים"
    small_line_width = 100
    small_line_x = (width - small_line_width) // 2
    draw.rectangle([small_line_x, times_y + 50, small_line_x + small_line_width, times_y + 52], 
                  fill=accent_color)
    
    # זמנים עם עיצוב נקי
    candle_text = "הדלקת נרות"
    candle_time = "17:51"
    havdalah_text = "הבדלה"
    havdalah_time = "19:05"
    
    # הדלקת נרות
    candle_y = times_y + 100
    draw.text((200, candle_y), candle_text, font=text_font, fill=primary_color)
    draw.text((width - 200 - 100, candle_y), candle_time, font=text_font, fill=accent_color)
    
    # קו דק בין הזמנים
    draw.rectangle([150, candle_y + 60, width - 150, candle_y + 61], fill=(200, 200, 200))
    
    # הבדלה
    havdalah_y = candle_y + 80
    draw.text((200, havdalah_y), havdalah_text, font=text_font, fill=primary_color)
    draw.text((width - 200 - 100, havdalah_y), havdalah_time, font=text_font, fill=accent_color)
    
    # עיגול דקורטיבי קטן
    circle_y = 850
    draw.ellipse([width//2 - 30, circle_y, width//2 + 30, circle_y + 60], 
                outline=accent_color, width=3)
    
    # נקודות דקורטיביות
    for i in range(3):
        x = width//2 - 20 + (i * 20)
        draw.ellipse([x, circle_y + 20, x + 8, circle_y + 28], fill=accent_color)
    
    return img

if __name__ == "__main__":
    img = create_minimal_design()
    img.save("design_minimal_example.png")
    print("נוצרה דוגמה: design_minimal_example.png")
