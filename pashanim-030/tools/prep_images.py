"""Prepare the photo assets for the composition.

- background removal (rembg: BiRefNet-portrait for the selfie, ISNet for covers)
- edge feathering so arms cut by the source image boundary dissolve instead of
  ending in a hard line
- Lanczos upscales to the exact on-screen size + a light unsharp mask

usage: python tools/prep_images.py   (run from the project root, after fetch_assets.sh)
"""
import numpy as np
from PIL import Image, ImageFilter
from rembg import new_session, remove

RAW = "assets/img/raw"
OUT = "assets/img"


def smooth(e0, e1, x):
    t = np.clip((x - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def feather(img, left=0, right=0, top=0, bottom=0):
    a = np.asarray(img).astype(np.float32)
    h, w = a.shape[:2]
    xs = np.arange(w, dtype=np.float32)[None, :]
    ys = np.arange(h, dtype=np.float32)[:, None]
    m = np.ones((h, w), np.float32)
    if left:
        m *= smooth(0, left, xs)
    if right:
        m *= smooth(w, w - right, xs)
    if top:
        m *= smooth(0, top, ys)
    if bottom:
        m *= smooth(h, h - bottom, ys)
    a[..., 3] *= m
    return Image.fromarray(a.clip(0, 255).astype(np.uint8), "RGBA")


def upscale(img, size, sharpen=True):
    out = img.resize(size, Image.LANCZOS)
    if sharpen:
        if out.mode == "RGBA":
            rgb = out.convert("RGB").filter(ImageFilter.UnsharpMask(radius=2.0, percent=55, threshold=2))
            rgb.putalpha(out.getchannel("A"))
            out = rgb
        else:
            out = out.filter(ImageFilter.UnsharpMask(radius=2.0, percent=55, threshold=2))
    return out


def cut(session, path):
    return remove(Image.open(path).convert("RGB"), session=session, post_process_mask=True)


portrait_sess = new_session("birefnet-portrait")
general_sess = new_session("isnet-general-use")

# 1) Selfie -> cutout (S2 hero, S1 type fill) --------------------------------
src = Image.open(f"{RAW}/portrait.jpg").convert("RGB")
pc = cut(portrait_sess, f"{RAW}/portrait.jpg")
pc = feather(pc, left=300, right=210, bottom=260)
S = 1.25  # on-screen scale used by scene 2
size = (round(src.width * S), round(src.height * S))
upscale(pc, size).save(f"{OUT}/portrait_cut.png", optimize=True)
upscale(src, size).save(f"{OUT}/portrait.jpg", quality=95)
print("portrait", size)

# 2) Lounge Musik cover -> cutout (S7) ------------------------------------------
lc = cut(general_sess, f"{RAW}/lounge_musik.jpg")
lc = feather(lc, right=6, bottom=6)
upscale(lc, (1080, 1080)).save(f"{OUT}/lounge_cut.png", optimize=True)
upscale(Image.open(f"{RAW}/lounge_musik.jpg").convert("RGB"), (1080, 1080)).save(f"{OUT}/lounge_musik.jpg", quality=95)
print("lounge ok")

# 3) Himmel ueber Berlin cover -> sky plate + cutout (S8) ----------------------
hc = cut(general_sess, f"{RAW}/himmel.jpg")
hc = feather(hc, bottom=120, left=4, right=4)
upscale(hc, (1240, 1240)).save(f"{OUT}/himmel_cut.png", optimize=True)
upscale(Image.open(f"{RAW}/himmel.jpg").convert("RGB"), (1240, 1240), sharpen=False).save(f"{OUT}/himmel.jpg", quality=93)
print("himmel ok")

# 4) covers used as cards / tiles ----------------------------------------------
for name, px in [("album_2000", 720), ("airwaves", 520), ("sommergewitter", 160),
                 ("mittelmeer", 160), ("gruenewuerfelflow", 160)]:
    im = Image.open(f"{RAW}/{name}.jpg").convert("RGB")
    upscale(im, (px, px), sharpen=px > 400).save(f"{OUT}/{name}.jpg", quality=94)
    print(name, px)

# second-act covers: Hauseingang card (scene 2), Mittelmeer flip side (scene 5)
upscale(Image.open(f"{RAW}/hauseingang.jpg").convert("RGB"), (440, 440)).save(f"{OUT}/hauseingang.jpg", quality=94)
upscale(Image.open(f"{RAW}/mittelmeer.jpg").convert("RGB"), (600, 600)).save(f"{OUT}/mittelmeer_600.jpg", quality=94)

# thumbnails of the Lounge Musik cover for the hit board
Image.open(f"{RAW}/lounge_musik.jpg").convert("RGB").resize((160, 160), Image.LANCZOS).save(f"{OUT}/lounge_thumb.jpg", quality=94)

# 5) rooftop photo (kept for the type fill experiments)
Image.open(f"{RAW}/rooftop.jpg").convert("RGB").save(f"{OUT}/rooftop.jpg", quality=94)
print("done")

# 6) clean sky plate for scene 8: inpaint the figure out of the cover, then blur
import cv2  # noqa: E402  (ships with rembg)
cov = cv2.imread(f"{RAW}/himmel.jpg")
alpha = np.asarray(cut(general_sess, f"{RAW}/himmel.jpg"))[..., 3]
mask = (alpha > 8).astype(np.uint8) * 255
mask = cv2.dilate(mask, np.ones((41, 41), np.uint8))
small = cv2.resize(cov, (500, 500), interpolation=cv2.INTER_AREA)
msmall = cv2.resize(mask, (500, 500), interpolation=cv2.INTER_NEAREST)
filled = cv2.inpaint(small, msmall, 25, cv2.INPAINT_TELEA)
filled = cv2.resize(filled, (2000, 2000), interpolation=cv2.INTER_CUBIC)
filled = cv2.GaussianBlur(filled, (0, 0), 9)
cv2.imwrite(f"{OUT}/sky_plate.jpg", filled, [cv2.IMWRITE_JPEG_QUALITY, 92])
print("sky plate ok")
