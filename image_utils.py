"""
Image utility functions for poster generation.

This module provides image processing utilities including:
- Font loading and caching
- Image orientation fixing
- Background image fitting and cropping
- Text measurement and fitting
- Text drawing with stroke effects
- Watermark overlay
- GIF frame extraction and assembly
"""

import os
from typing import List, Optional, Tuple

import arabic_reshaper
from bidi.algorithm import get_display
from PIL import Image, ImageDraw, ImageFont


# ========= TEXT HELPERS =========
def fix_hebrew(text: str) -> str:
    """Convert Hebrew text to proper RTL display format."""
    if not text:
        return text
    return get_display(arabic_reshaper.reshape(text))


# ========= FONT LOADING =========
# Font cache to avoid reloading fonts repeatedly
# Cache stores: (size, bold) -> (font, is_bold)
_font_cache: dict[tuple[int, bool], tuple[ImageFont.FreeTypeFont, bool]] = {}

# Font file candidates (searched in order)
# Use absolute paths relative to this file's location for Vercel serverless compatibility
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
_FONT_CANDIDATES_BOLD = [
    os.path.join(_PROJECT_ROOT, "Alef-Bold.ttf"),
    os.path.join(_PROJECT_ROOT, "Alef-Regular.ttf"),
    "DejaVuSans.ttf",  # System fallback
]
_FONT_CANDIDATES_REGULAR = [
    os.path.join(_PROJECT_ROOT, "Alef-Regular.ttf"),
    "DejaVuSans.ttf",  # System fallback
]


def load_font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """
    Load a font with caching for performance.

    Args:
        size: Font size in points
        bold: Whether to use bold variant

    Returns:
        Loaded font object (with _is_bold attribute set)
    """
    cache_key = (size, bold)

    # Return cached font if available
    if cache_key in _font_cache:
        font, _ = _font_cache[cache_key]
        return font

    candidates = _FONT_CANDIDATES_BOLD if bold else _FONT_CANDIDATES_REGULAR

    for path in candidates:
        if os.path.isfile(path):
            try:
                font = ImageFont.truetype(path, size=size)
                # Store font with its bold state
                font._is_bold = bold  # type: ignore
                _font_cache[cache_key] = (font, bold)
                return font
            except Exception:
                continue

    # Fall back to default font (not cached as it's a different type)
    default_font = ImageFont.load_default()
    default_font._is_bold = False  # type: ignore
    return default_font


# ========= IMAGE HELPERS =========
# EXIF orientation tag and rotation values
_EXIF_ORIENTATION_TAG = 274
_ORIENTATION_ROTATIONS = {
    3: 180,
    6: 270,
    8: 90,
}


def fix_image_orientation(img: Image.Image) -> Image.Image:
    """
    Fix image orientation based on EXIF data.

    Many cameras store images in a default orientation and use EXIF metadata
    to indicate how the image should be rotated for display.

    Args:
        img: PIL Image object

    Returns:
        Image rotated to correct orientation
    """
    try:
        exif = img._getexif()
        if exif is not None:
            orientation = exif.get(_EXIF_ORIENTATION_TAG)
            rotation = _ORIENTATION_ROTATIONS.get(orientation)
            if rotation:
                img = img.rotate(rotation, expand=True)
    except (AttributeError, KeyError, TypeError):
        pass
    return img


def fit_background(
    image_path: str,
    size: Tuple[int, int] = (1080, 1080),
    crop_position: Optional[Tuple[float, float]] = None,
    flexible_aspect: bool = False,
) -> Image.Image:
    """
    Load and resize an image to fill the target size with customizable crop position.

    Args:
        image_path: Path to the image file
        size: Target size as (width, height). When flexible_aspect=True, this
              becomes the maximum size constraint.
        crop_position: Tuple of (x, y) as percentages (0.0 to 1.0) where
                       (0.5, 0.5) is center, (0.0, 0.0) is top-left,
                       (1.0, 1.0) is bottom-right. Default is center.
        flexible_aspect: If True, preserve the original aspect ratio within
                         constraints instead of forcing a fixed size.

    Returns:
        Resized and cropped PIL Image
    """
    img = Image.open(image_path).convert("RGB")

    # Fix orientation based on EXIF data
    img = fix_image_orientation(img)

    if flexible_aspect:
        # Use flexible aspect ratio mode
        return _fit_background_flexible(img, size, crop_position)
    else:
        # Original fixed-size mode
        return _fit_background_fixed(img, size, crop_position)


def _fit_background_fixed(
    img: Image.Image,
    size: Tuple[int, int],
    crop_position: Optional[Tuple[float, float]] = None,
) -> Image.Image:
    """
    Original fixed-size background fitting logic.

    Scales and crops the image to exactly match the target size.
    """
    base_w, base_h = size

    # Scale to cover the target size
    scale = max(base_w / img.width, base_h / img.height)
    new_w = int(img.width * scale)
    new_h = int(img.height * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    # Use provided crop position or default to center (0.5, 0.5)
    crop_x, crop_y = crop_position if crop_position else (0.5, 0.5)

    # Clamp values to valid range [0.0, 1.0]
    crop_x = max(0.0, min(1.0, crop_x))
    crop_y = max(0.0, min(1.0, crop_y))

    # Calculate crop position based on percentage
    # The crop window can move from 0 to (new_dimension - base_dimension)
    max_left = new_w - base_w
    max_top = new_h - base_h

    left = int(max_left * crop_x)
    top = int(max_top * crop_y)

    img = img.crop((left, top, left + base_w, top + base_h))
    return img


# Flexible aspect ratio constraints
_MIN_WIDTH = 800
_MIN_HEIGHT = 1000
_MIN_ASPECT_RATIO = 0.67  # 2:3 (portrait limit)
_MAX_ASPECT_RATIO = 1.5   # 3:2 (landscape limit)
_MAX_DIMENSION = 1080


def _fit_background_flexible(
    img: Image.Image,
    max_size: Tuple[int, int],
    crop_position: Optional[Tuple[float, float]] = None,
) -> Image.Image:
    """
    Flexible aspect ratio background fitting.

    Preserves the original aspect ratio when it falls within acceptable bounds.
    Crops images that are too wide or too tall to acceptable ratios.

    Constraints:
    - Min width: 800px (final output)
    - Min height: 1000px (final output)
    - Aspect ratio: between 1:1.5 (portrait) and 1.5:1 (landscape)
    - Max dimension: 1080px on longest side
    """
    width, height = img.size
    aspect_ratio = width / height

    # Use provided crop position or default to center (0.5, 0.5)
    crop_x, crop_y = crop_position if crop_position else (0.5, 0.5)
    crop_x = max(0.0, min(1.0, crop_x))
    crop_y = max(0.0, min(1.0, crop_y))

    # Determine target dimensions based on aspect ratio constraints
    target_width = width
    target_height = height
    needs_crop = False

    if aspect_ratio > _MAX_ASPECT_RATIO:
        # Too wide (landscape) - crop to max landscape ratio
        target_width = int(height * _MAX_ASPECT_RATIO)
        target_height = height
        needs_crop = True
    elif aspect_ratio < _MIN_ASPECT_RATIO:
        # Too tall (portrait) - crop to max portrait ratio
        target_width = width
        target_height = int(width / _MIN_ASPECT_RATIO)
        needs_crop = True

    # Apply crop if needed to adjust aspect ratio
    if needs_crop:
        # Calculate crop position based on percentage
        max_left = width - target_width
        max_top = height - target_height

        left = int(max_left * crop_x)
        top = int(max_top * crop_y)

        img = img.crop((left, top, left + target_width, top + target_height))
        width, height = img.size

    # Resize to fit within max dimension while maintaining aspect ratio
    max_dim = max(max_size)
    if max(width, height) > max_dim:
        ratio = max_dim / max(width, height)
        new_width = int(width * ratio)
        new_height = int(height * ratio)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    # Ensure minimum dimensions (scale up if needed, which is rare)
    width, height = img.size
    if width < _MIN_WIDTH or height < _MIN_HEIGHT:
        # Scale up to meet minimum requirements
        scale = max(_MIN_WIDTH / width, _MIN_HEIGHT / height)
        new_width = int(width * scale)
        new_height = int(height * scale)
        img = img.resize((new_width, new_height), Image.LANCZOS)

    return img


def get_text_width(text: str, font: ImageFont.FreeTypeFont, rtl: bool = False) -> int:
    """
    Get the width of text rendered with the given font.

    Args:
        text: Text to measure
        font: Font to use
        rtl: Whether to apply RTL text processing

    Returns:
        Width in pixels
    """
    if rtl:
        text = fix_hebrew(text)
    bbox = font.getbbox(text)
    return bbox[2] - bbox[0]


def get_fitted_font(
    text: str,
    original_font: ImageFont.FreeTypeFont,
    max_width: int,
    rtl: bool = False,
    min_size: int = 20
) -> ImageFont.FreeTypeFont:
    """
    Get a font that fits the text within max_width.

    Iteratively reduces font size until text fits or min_size is reached.

    Args:
        text: Text to fit
        original_font: Starting font
        max_width: Maximum allowed width in pixels
        rtl: Whether to apply RTL text processing
        min_size: Minimum font size to use

    Returns:
        Font that fits the text (or min_size font if nothing fits)
    """
    current_size = original_font.size
    is_bold = getattr(original_font, '_is_bold', False)

    # Check if original font fits
    if get_text_width(text, original_font, rtl) <= max_width:
        return original_font

    # Find the largest font size that fits
    while current_size > min_size:
        current_size -= 2
        test_font = load_font(current_size, bold=is_bold)
        if get_text_width(text, test_font, rtl) <= max_width:
            return test_font

    # Return minimum size font if nothing fits
    return load_font(min_size, bold=is_bold)


def draw_text_with_stroke(draw, xy, text, font, fill, stroke_fill, stroke_width, anchor=None, rtl=False):
    """
    Draw text with a stroke (outline) effect.

    Args:
        draw: PIL ImageDraw object
        xy: Position tuple (x, y)
        text: Text to draw
        font: Font to use
        fill: Text fill color
        stroke_fill: Stroke color
        stroke_width: Width of the stroke
        anchor: Text anchor position
        rtl: Whether to apply RTL text processing
    """
    if rtl:
        text = fix_hebrew(text)
    draw.text(
        xy, text, font=font, fill=fill,
        stroke_width=stroke_width, stroke_fill=stroke_fill,
        anchor=anchor
    )


def overlay_watermark(
    img: Image.Image,
    watermark_path: str,
    size: int = 60,
    margin: int = 10,
    opacity: float = 0.5,
) -> Image.Image:
    """
    Overlay a watermark image on the bottom-right corner of the poster.

    Args:
        img: The poster image to add watermark to
        watermark_path: Path to the watermark image file
        size: Target width for the watermark (height auto-calculated)
        margin: Margin from the edges in pixels
        opacity: Opacity level (0.0 to 1.0)

    Returns:
        Image with watermark overlaid
    """
    if not os.path.isfile(watermark_path):
        # Watermark file not found, return original image
        return img

    try:
        # Load watermark image with transparency support
        watermark = Image.open(watermark_path).convert("RGBA")

        # Calculate new height maintaining aspect ratio
        aspect_ratio = watermark.height / watermark.width
        new_width = size
        new_height = int(size * aspect_ratio)

        # Resize watermark
        watermark = watermark.resize((new_width, new_height), Image.LANCZOS)

        # Apply opacity to the watermark
        if opacity < 1.0:
            # Split into channels and adjust alpha
            r, g, b, a = watermark.split()
            a = a.point(lambda x: int(x * opacity))
            watermark = Image.merge("RGBA", (r, g, b, a))

        # Calculate position (bottom-right with margin)
        W, H = img.size
        x = W - new_width - margin
        y = H - new_height - margin

        # Ensure img is in RGBA mode for compositing
        if img.mode != "RGBA":
            img = img.convert("RGBA")

        # Create a copy and paste watermark with transparency
        result = img.copy()
        result.paste(watermark, (x, y), watermark)

        # Convert back to RGB if original was RGB
        return result.convert("RGB")

    except Exception as e:
        # If anything goes wrong, return original image
        print(f"Warning: Could not overlay watermark: {e}")
        return img


# ========= GIF HELPERS =========
def is_animated_gif(image_path: str) -> bool:
    """
    Check if an image file is an animated GIF.

    Args:
        image_path: Path to the image file

    Returns:
        True if the file is an animated GIF with multiple frames, False otherwise
    """
    try:
        with Image.open(image_path) as img:
            return img.format == 'GIF' and getattr(img, 'is_animated', False)
    except Exception:
        return False


def extract_gif_frames(image_path: str) -> Tuple[List[Image.Image], List[int]]:
    """
    Extract all frames and their durations from an animated GIF.

    Args:
        image_path: Path to the GIF file

    Returns:
        Tuple of (frames, durations) where:
        - frames: List of PIL Image objects (one per frame)
        - durations: List of frame durations in milliseconds
    """
    frames = []
    durations = []

    with Image.open(image_path) as img:
        # Iterate through all frames
        try:
            while True:
                # Copy the frame to preserve it
                frame = img.copy()
                frames.append(frame)
                # Get duration for this frame (default 100ms if not specified)
                durations.append(img.info.get('duration', 100))
                img.seek(img.tell() + 1)
        except EOFError:
            pass

    return frames, durations


def assemble_gif(
    frames: List[Image.Image],
    durations: List[int],
) -> bytes:
    """
    Assemble processed frames into an animated GIF.

    Args:
        frames: List of processed PIL Image objects
        durations: List of frame durations in milliseconds

    Returns:
        GIF bytes ready to be saved or transmitted
    """
    from io import BytesIO

    if not frames:
        raise ValueError("No frames provided for GIF assembly")

    # Convert all frames to RGB mode for GIF compatibility
    # GIF requires palette mode (P), but save() handles conversion
    rgb_frames = []
    for frame in frames:
        if frame.mode == 'RGBA':
            # Convert RGBA to RGB directly - poster frames don't need transparency
            # Using direct conversion preserves white text better than compositing
            # with a white background (which would make white text invisible)
            rgb_frames.append(frame.convert('RGB'))
        elif frame.mode != 'RGB':
            rgb_frames.append(frame.convert('RGB'))
        else:
            rgb_frames.append(frame)

    # Save animated GIF
    output = BytesIO()
    rgb_frames[0].save(
        output,
        format='GIF',
        save_all=True,
        append_images=rgb_frames[1:] if len(rgb_frames) > 1 else [],
        duration=durations,
        loop=0,  # Infinite loop
        optimize=False,  # Avoid optimization issues with text
    )

    return output.getvalue()

