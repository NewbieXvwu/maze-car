#!/usr/bin/env python3
"""Render out/parts/*.stl into the two figures referenced by ASSEMBLY.md.

    python3 cad/render.py            # -> out/render-views.png, out/render-iso.png

Parts are exported one body at a time (out/parts/<bodyId>-<name>.stl) and merged
into out/maze-car.stl; the per-part file names carry the colours.
"""
import glob
import math
import os
import struct

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = os.path.join(ROOT, 'out', 'parts')

# first match wins -- keep the specific keys above the generic ones
PALETTE = [
    ('底板', (176, 124, 96)),
    ('立柱', (196, 160, 82)),
    ('螺丝', (180, 184, 190)),
    ('减速箱', (58, 62, 70)),
    ('编码器', (86, 92, 102)),
    ('电机', (58, 62, 70)),
    ('轴', (190, 194, 200)),
    ('轮胎', (44, 46, 52)),
    ('轮毂', (150, 156, 164)),
    ('镜头', (20, 20, 24)),
    ('珠', (160, 166, 174)),
    ('万向轮', (70, 74, 82)),
    ('电池包', (96, 108, 128)),
    ('电池座', (52, 56, 62)),
    ('XH', (220, 220, 220)),
    ('主板', (44, 112, 72)),
    ('ESP', (72, 94, 122)),
    ('TB6612', (152, 94, 162)),
    ('MPU', (110, 160, 200)),
    ('排母', (60, 64, 70)),
    ('测距座', (60, 64, 70)),
    ('拨码', (190, 90, 70)),
    ('按键', (200, 200, 205)),
    ('Mini560', (70, 110, 150)),
    ('龙门', (198, 160, 104)),
    ('6P', (48, 50, 56)),
    ('测距', (62, 120, 190)),
]
LIGHT = np.array([0.40, -0.55, 0.75])
LIGHT = LIGHT / np.linalg.norm(LIGHT)


def color_of(name):
    for key, col in PALETTE:
        if key in name:
            return col
    return (150, 154, 160)


def load_parts():
    meshes = []
    for f in sorted(glob.glob(os.path.join(PARTS, '*.stl'))):
        data = open(f, 'rb').read()
        n = struct.unpack('<I', data[80:84])[0]
        rec = np.frombuffer(data[84:84 + n * 50], dtype=np.uint8).reshape(n, 50)
        tri = rec[:, 12:48].copy().view('<f4').reshape(n, 3, 3).astype(np.float64)
        meshes.append((os.path.basename(f)[:-4], tri))
    if not meshes:
        raise SystemExit('no parts in %s' % PARTS)
    return meshes


def frame(eye, up):
    d = np.asarray(eye, float)
    d /= np.linalg.norm(d)
    r = np.cross(up, d)
    r /= np.linalg.norm(r)
    u = np.cross(d, r)
    return d, r, u


def render_z(meshes, eye, up, W, H, bg=(255, 255, 255), pad=0.07, ss=2, shadow=False):
    """Orthographic z-buffer render (per-triangle numpy raster)."""
    d, r, u = frame(eye, up)
    Wb, Hb = W * ss, H * ss
    qs = [np.stack([tri @ r, tri @ u, tri @ d], axis=-1) for _, tri in meshes]
    allq = np.concatenate(qs).reshape(-1, 3)
    lo, hi = allq.min(0), allq.max(0)
    s = min(Wb * (1 - 2 * pad) / (hi[0] - lo[0]), Hb * (1 - 2 * pad) / (hi[1] - lo[1]))
    ox = Wb / 2 - (lo[0] + hi[0]) / 2 * s
    oy = Hb / 2 + (lo[1] + hi[1]) / 2 * s

    def proj(q):
        return ox + q[..., 0] * s, oy - q[..., 1] * s

    base = Image.new('RGB', (Wb, Hb), bg)
    if shadow:
        sh = Image.new('L', (Wb, Hb), 0)
        sdr = ImageDraw.Draw(sh)
        for q in qs:
            sx, sy = proj(np.stack([q[..., 0], q[..., 1], np.zeros_like(q[..., 0])], -1))
            for i in range(len(q)):
                sdr.polygon([(sx[i, j], sy[i, j]) for j in range(3)], fill=70)
        sh = sh.filter(ImageFilter.GaussianBlur(9 * ss))
        base.paste(Image.new('RGB', (Wb, Hb), (120, 124, 136)), (0, 0),
                   sh.point(lambda v: int(v * 0.45)))

    img = np.asarray(base).copy()
    buf = np.full((Hb, Wb), -np.inf)
    for (name, _), q in zip(meshes, qs):
        base_col = np.array(color_of(name), float)
        n = np.cross(q[:, 1] - q[:, 0], q[:, 2] - q[:, 0])
        ln = np.linalg.norm(n, axis=1)
        ln[ln == 0] = 1
        lo_, hi_ = (0.42, 0.58) if not shadow else (0.50, 0.50)
        lam = lo_ + hi_ * np.clip((n / ln[:, None]) @ LIGHT, 0, None)
        for j in np.nonzero(n[:, 2] > 0)[0]:
            A, B, C = q[j]
            col = tuple(int(min(255, c * lam[j])) for c in base_col)
            x0, y0 = proj(A)
            x1, y1 = proj(B)
            x2, y2 = proj(C)
            xmin = max(0, int(min(x0, x1, x2)))
            xmax = min(Wb - 1, int(max(x0, x1, x2)) + 1)
            ymin = max(0, int(min(y0, y1, y2)))
            ymax = min(Hb - 1, int(max(y0, y1, y2)) + 1)
            if xmin >= xmax or ymin >= ymax:
                continue
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            xs = np.arange(xmin, xmax) + 0.5
            ys = np.arange(ymin, ymax) + 0.5
            px, py = np.meshgrid(xs, ys)
            w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
            w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not inside.any():
                continue
            z = w0 * A[2] + w1 * B[2] + w2 * C[2]
            sub = buf[ymin:ymax, xmin:xmax]
            subimg = img[ymin:ymax, xmin:xmax]
            upd = inside & (z > sub)
            sub[upd] = z[upd]
            subimg[upd] = col

    return Image.fromarray(img).resize((W, H), Image.LANCZOS)


def main():
    meshes = load_parts()
    W, H = 1000, 720
    views = [('TOP', (0, 0, 1), (0, 1, 0)),
             ('FRONT', (1, 0, 0), (0, 0, 1)),
             ('LEFT', (0, 1, 0), (0, 0, 1)),
             ('ISO', (0.85, -0.95, 0.75), (0, 0, 1))]
    font = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 26)
    small = ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 22)
    sheet = Image.new('RGB', (W * 2, H * 2 + 70), (255, 255, 255))
    for i, (nm, e, u) in enumerate(views):
        im = render_z(meshes, e, u, W, H)
        d = ImageDraw.Draw(im)
        d.text((20, 16), nm, fill=(40, 40, 44), font=font)
        sheet.paste(im, ((i % 2) * W, (i // 2) * H))
        if nm == 'TOP':
            ImageDraw.Draw(sheet).text((W - 190, 26), '车头 →', fill=(190, 60, 50), font=font)
    caption = ('迷宫小车参数化装配 · 单位 mm · 底板 140×82×3 · 四轮（2 驱动 + 前后万向轮）'
               ' · 轮距 90 · 轮 Ø42 · 18650 电池盒 · 电气层高 48')
    ImageDraw.Draw(sheet).text((20, H * 2 + 18), caption, fill=(70, 70, 76), font=small)
    sheet.save(os.path.join(ROOT, 'out', 'render-views.png'))

    hero = render_z(meshes, (0.82, -0.88, 0.92), (0, 0, 1), 1600, 1150,
                    bg=(247, 247, 249), shadow=True)
    ImageDraw.Draw(hero).text((40, 40), '四轮 · 2×18650 · 409 g', fill=(90, 94, 104),
                              font=ImageFont.truetype('/System/Library/Fonts/STHeiti Medium.ttc', 30))
    hero.save(os.path.join(ROOT, 'out', 'render-iso.png'))
    print('ok: out/render-views.png out/render-iso.png')


if __name__ == '__main__':
    main()
