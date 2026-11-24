"""Extract vector glyph outlines from the Archivo variable font at fixed axis
values, so the composition can draw type as SVG paths (crisp under extreme
zooms, measurable for stroke draw-ons, and with separate contours so the
counter of a "0" can be used as a portal mask).

usage: python tools/glyphs.py assets/fonts/archivo-var.woff2 assets/data/glyphs.json
"""
import json
import sys

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.pens.recordingPen import RecordingPen
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC, OUT = sys.argv[1], sys.argv[2]

# (key, text, axes)
JOBS = [
    ("dial", "030", {"wght": 900, "wdth": 62}),
    ("album", "2000", {"wght": 900, "wdth": 125}),
    ("hash1", "#1", {"wght": 900, "wdth": 62}),
]


def contours_of(glyphset, name):
    """Return list of SVG path strings, one per contour, y flipped (y-down)."""
    rec = RecordingPen()
    glyphset[name].draw(rec)
    contours, cur = [], []
    for op, args in rec.value:
        cur.append((op, args))
        if op in ("closePath", "endPath"):
            contours.append(cur)
            cur = []
    out = []
    for c in contours:
        sp = SVGPathPen(glyphset)
        tp = TransformPen(sp, (1, 0, 0, -1, 0, 0))
        for op, args in c:
            getattr(tp, op)(*args)
        out.append(sp.getCommands())
    return out


def bbox_of(glyphset, name):
    from fontTools.pens.boundsPen import BoundsPen
    bp = BoundsPen(glyphset)
    glyphset[name].draw(bp)
    if bp.bounds is None:
        return None
    x0, y0, x1, y1 = bp.bounds
    return [x0, -y1, x1, -y0]  # y-down


result = {}
for key, text, axes in JOBS:
    font = TTFont(SRC)
    inst = instancer.instantiateVariableFont(font, axes)
    gs = inst.getGlyphSet()
    cmap = inst.getBestCmap()
    hmtx = inst["hmtx"]
    os2 = inst["OS/2"]
    glyphs = []
    for ch in text:
        gname = cmap[ord(ch)]
        adv, lsb = hmtx[gname]
        glyphs.append({
            "char": ch,
            "advance": adv,
            "contours": contours_of(gs, gname),
            "bbox": bbox_of(gs, gname),
        })
    result[key] = {
        "text": text,
        "axes": axes,
        "upm": inst["head"].unitsPerEm,
        "capHeight": getattr(os2, "sCapHeight", 700),
        "ascender": inst["hhea"].ascent,
        "descender": inst["hhea"].descent,
        "glyphs": glyphs,
    }
    print(key, text, [(g["char"], g["advance"], len(g["contours"]), g["bbox"]) for g in glyphs],
          "cap", result[key]["capHeight"])

with open(OUT, "w") as f:
    json.dump(result, f)
with open(OUT.replace(".json", ".js"), "w") as f:
    f.write("window.GLYPHS = " + json.dumps(result) + ";\n")
print("wrote", OUT)
