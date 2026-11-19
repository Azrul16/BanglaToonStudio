"""Portable HarfBuzz + FreeType shaping when Pillow's RAQM is unavailable."""
from functools import lru_cache
import freetype
import uharfbuzz as hb
from PIL import Image, ImageColor


@lru_cache(maxsize=16)
def shaped_font(path, size):
    with open(path, "rb") as source:
        data = source.read()
    face = hb.Face(data)
    font = hb.Font(face)
    font.scale = (size*64, size*64)
    hb.ot_font_set_funcs(font)
    raster = freetype.Face(path)
    raster.set_pixel_sizes(0, size)
    return font, raster


def shape(text, font):
    if not text: return [], []
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf)
    return buf.glyph_infos, buf.glyph_positions


def length(text, face):
    font, _ = shaped_font(face.path, face.size)
    _, positions = shape(text, font)
    return sum(p.x_advance for p in positions)/64


@lru_cache(maxsize=128)
def text_layer(text, path, size, color):
    font, raster = shaped_font(path, size)
    infos, positions = shape(text, font)
    width = max(1, round(sum(p.x_advance for p in positions)/64)+size)
    layer = Image.new("RGBA", (width, size*3))
    x, baseline = size//2, size*1.5
    for info, pos in zip(infos, positions):
        raster.load_glyph(info.codepoint, freetype.FT_LOAD_RENDER)
        glyph = raster.glyph
        bitmap = glyph.bitmap
        if bitmap.width and bitmap.rows:
            mask = Image.frombytes("L", (bitmap.width, bitmap.rows), bytes(bitmap.buffer), "raw", "L", bitmap.pitch)
            ink = Image.new("RGBA", mask.size, ImageColor.getrgb(color)+(255,))
            ink.putalpha(mask)
            layer.alpha_composite(ink, (round(x+pos.x_offset/64+glyph.bitmap_left),
                                       round(baseline-pos.y_offset/64-glyph.bitmap_top)))
        x += pos.x_advance/64
    return layer, x-size//2


def draw_text(image, xy, text, face, color, anchor=None, spacing=8):
    x, y = xy
    lines = text.split("\n")
    for index, line in enumerate(lines):
        layer, width = text_layer(line, face.path, face.size, color)
        left = round(x-face.size//2 - (width/2 if anchor == "mm" else 0))
        top = round(y-face.size*.5 + index*(face.size+spacing) - (face.size/2 if anchor == "mm" else 0))
        image.paste(layer, (left, top), layer)
