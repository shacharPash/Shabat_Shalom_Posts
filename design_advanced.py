#!/usr/bin/env python3
"""
דוגמה 3: עיצוב מתקדם עם אפקטים (Wand/ImageMagick)
"""

try:
    from wand.image import Image as WandImage
    from wand.drawing import Drawing
    from wand.color import Color
    WAND_AVAILABLE = True
except ImportError:
    WAND_AVAILABLE = False
    print("Wand לא זמין, משתמש ב-PIL")

from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

def create_advanced_design_wand():
    """יצירת עיצוב מתקדם עם Wand"""
    if not WAND_AVAILABLE:
        return create_advanced_design_pil()
    
    width, height = 1080, 1080
    
    with WandImage(width=width, height=height, background=Color('#1a1a2e')) as img:
        with Drawing() as draw:
            # רקע גרדיאנט מתקדם
            draw.fill_color = Color('#16213e')
            draw.stroke_color = Color('#0f3460')
            draw.stroke_width = 2
            
            # יצירת גרדיאנט רדיאלי
            for i in range(10):
                radius = (i + 1) * 50
                alpha = 1.0 - (i * 0.1)
                draw.fill_color = Color(f'rgba(22, 33, 62, {alpha})')
                draw.circle((width//2, height//2), (width//2 + radius, height//2))
            
            # מסגרת עם אפקט זוהר
            draw.fill_color = Color('transparent')
            draw.stroke_color = Color('#ffd700')
            draw.stroke_width = 4
            draw.rectangle(left=50, top=50, right=width-50, bottom=height-50)
            
            # טקסט עם אפקטים
            draw.font_family = 'Arial'
            draw.font_size = 80
            draw.fill_color = Color('#ffffff')
            draw.text_alignment = 'center'
            
            # כותרת
            draw.text(width//2, 200, 'שבת שלום')
            
            # תאריך
            draw.font_size = 50
            draw.fill_color = Color('#ffd700')
            draw.text(width//2, 300, '26-27.09.2025')
            
            # פרשה
            draw.text(width//2, 380, 'פרשת וילך')
            
            draw(img)
        
        # הוספת אפקטי זוהר
        img.blur(radius=1, sigma=0.5)
        
        # שמירה כ-PIL Image
        img.format = 'png'
        blob = img.make_blob()
        
        from io import BytesIO
        pil_img = Image.open(BytesIO(blob))
        return pil_img

def create_advanced_design_pil():
    """יצירת עיצוב מתקדם עם PIL (fallback)"""
    width, height = 1080, 1080
    
    # רקע כהה עם גרדיאנט רדיאלי
    img = Image.new('RGB', (width, height), (26, 26, 46))
    draw = ImageDraw.Draw(img)
    
    # גרדיאנט רדיאלי מדומה
    center_x, center_y = width // 2, height // 2
    max_radius = min(width, height) // 2
    
    for radius in range(max_radius, 0, -20):
        alpha = int(255 * (1 - radius / max_radius) * 0.3)
        color = (22 + alpha//4, 33 + alpha//4, 62 + alpha//4)
        draw.ellipse([center_x - radius, center_y - radius, 
                     center_x + radius, center_y + radius], 
                    fill=color)
    
    # מסגרת זוהרת (מדומה)
    for i in range(5):
        offset = i * 2
        alpha = 255 - (i * 50)
        draw.rectangle([50 - offset, 50 - offset, width - 50 + offset, height - 50 + offset], 
                      outline=(255, 215, 0, alpha), width=2)
    
    # טקסט עם אפקט זוהר
    try:
        title_font = ImageFont.truetype("Arial.ttf", 80)
        subtitle_font = ImageFont.truetype("Arial.ttf", 50)
    except:
        title_font = ImageFont.load_default()
        subtitle_font = ImageFont.load_default()
    
    # כותרת עם זוהר
    title_text = "שבת שלום"
    title_bbox = draw.textbbox((0, 0), title_text, font=title_font)
    title_width = title_bbox[2] - title_bbox[0]
    title_x = (width - title_width) // 2
    
    # אפקט זוהר לטקסט
    for offset in range(5, 0, -1):
        alpha = 50 + (5 - offset) * 30
        draw.text((title_x + offset, 180 + offset), title_text, 
                 font=title_font, fill=(255, 215, 0, alpha))
    
    draw.text((title_x, 180), title_text, font=title_font, fill=(255, 255, 255))
    
    # תאריך
    date_text = "26-27.09.2025"
    date_bbox = draw.textbbox((0, 0), date_text, font=subtitle_font)
    date_width = date_bbox[2] - date_bbox[0]
    date_x = (width - date_width) // 2
    draw.text((date_x, 280), date_text, font=subtitle_font, fill=(255, 215, 0))
    
    # פרשה
    parsha_text = "פרשת וילך"
    parsha_bbox = draw.textbbox((0, 0), parsha_text, font=subtitle_font)
    parsha_width = parsha_bbox[2] - parsha_bbox[0]
    parsha_x = (width - parsha_width) // 2
    draw.text((parsha_x, 350), parsha_text, font=subtitle_font, fill=(255, 255, 255))
    
    # הוספת blur קל
    img = img.filter(ImageFilter.GaussianBlur(radius=0.5))
    
    return img

def create_advanced_design():
    """יצירת עיצוב מתקדם"""
    if WAND_AVAILABLE:
        return create_advanced_design_wand()
    else:
        return create_advanced_design_pil()

if __name__ == "__main__":
    img = create_advanced_design()
    img.save("design_advanced_example.png")
    print("נוצרה דוגמה: design_advanced_example.png")
