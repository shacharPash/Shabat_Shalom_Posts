#!/usr/bin/env python3
"""
דוגמה 1: עיצוב מודרני עם גרדיאנטים וצללים
"""

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os
from datetime import date

def create_gradient_background(width, height, color1, color2, direction='vertical'):
    """יצירת רקע גרדיאנט"""
    base = Image.new('RGB', (width, height), color1)
    top = Image.new('RGB', (width, height), color2)
    
    if direction == 'vertical':
        # גרדיאנט אנכי
        mask = Image.new('L', (width, height))
        mask_draw = ImageDraw.Draw(mask)
        for y in range(height):
            alpha = int(255 * (y / height))
            mask_draw.rectangle([0, y, width, y+1], fill=alpha)
    else:
        # גרדיאנט אופקי
        mask = Image.new('L', (width, height))
        mask_draw = ImageDraw.Draw(mask)
        for x in range(width):
            alpha = int(255 * (x / width))
            mask_draw.rectangle([x, 0, x+1, height], fill=alpha)
    
    base.paste(top, mask=mask)
    return base

def add_text_with_shadow(draw, text, position, font, text_color, shadow_color, shadow_offset=(3, 3)):
    """הוספת טקסט עם צל"""
    x, y = position
    # צל
    draw.text((x + shadow_offset[0], y + shadow_offset[1]), text, font=font, fill=shadow_color)
    # טקסט עיקרי
    draw.text((x, y), text, font=font, fill=text_color)

def create_modern_design():
    """יצירת עיצוב מודרני"""
    width, height = 1080, 1080
    
    # צבעים מודרניים
    if True:  # שבת
        bg_color1 = (25, 42, 86)    # כחול כהה
        bg_color2 = (58, 96, 155)   # כחול בהיר
        accent_color = (255, 215, 0)  # זהב
    else:  # חג
        bg_color1 = (86, 25, 42)    # אדום כהה
        bg_color2 = (155, 58, 96)   # אדום בהיר
        accent_color = (255, 215, 0)  # זהב
    
    # יצירת רקע גרדיאנט
    img = create_gradient_background(width, height, bg_color1, bg_color2)
    draw = ImageDraw.Draw(img)
    
    # הוספת מסגרת מעוצבת
    border_width = 20
    draw.rectangle([border_width, border_width, width-border_width, height-border_width], 
                  outline=accent_color, width=4)
    
    # הוספת מסגרת פנימית
    inner_border = 60
    draw.rectangle([inner_border, inner_border, width-inner_border, height-inner_border], 
                  outline=accent_color, width=2)
    
    # טקסט עם צללים
    try:
        title_font = ImageFont.truetype("Arial.ttf", 80)
        subtitle_font = ImageFont.truetype("Arial.ttf", 50)
        text_font = ImageFont.truetype("Arial.ttf", 40)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
        text_font = ImageFont.load_default()
    
    # כותרת
    add_text_with_shadow(draw, "שבת שלום", (width//2 - 150, 150), 
                        title_font, (255, 255, 255), (0, 0, 0, 128))
    
    # תאריך
    add_text_with_shadow(draw, "26-27.09.2025", (width//2 - 120, 250), 
                        subtitle_font, accent_color, (0, 0, 0, 128))
    
    # פרשה
    add_text_with_shadow(draw, "פרשת וילך", (width//2 - 100, 320), 
                        subtitle_font, (255, 255, 255), (0, 0, 0, 128))
    
    # זמנים עם רקע מעוצב
    times_y = 450
    box_height = 400
    box_margin = 100
    
    # רקע לזמנים
    draw.rounded_rectangle([box_margin, times_y, width-box_margin, times_y+box_height], 
                          radius=20, fill=(255, 255, 255, 30), outline=accent_color, width=2)
    
    # זמנים
    add_text_with_shadow(draw, "הדלקת נרות: 17:51", (150, times_y + 50), 
                        text_font, (255, 255, 255), (0, 0, 0, 128))
    add_text_with_shadow(draw, "הבדלה: 19:05", (150, times_y + 120), 
                        text_font, (255, 255, 255), (0, 0, 0, 128))
    
    return img

if __name__ == "__main__":
    img = create_modern_design()
    img.save("design_modern_example.png")
    print("נוצרה דוגמה: design_modern_example.png")
