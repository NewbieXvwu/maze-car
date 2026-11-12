#!/usr/bin/env python3
"""GB first-angle general-assembly drawing of the maze car.

    python3 cad/drawing.py     # -> out/maze-car-drawing.svg (+ .png if rsvg-convert)

Reads the per-body meshes in out/parts and draws 主视图 / 俯视图 / 左视图 /
轴测图 with an A3 frame, title block and the dimension chain.
"""
import glob
import os
import struct
import subprocess

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PARTS = os.path.join(ROOT, 'out', 'parts')
OUT = os.path.join(ROOT, 'out', 'maze-car-drawing.svg')


def load_parts():
    meshes = []
    for f in sorted(glob.glob(os.path.join(PARTS, '*.stl'))):
        data = open(f, 'rb').read()
        n = struct.unpack('<I', data[80:84])[0]
        rec = np.frombuffer(data[84:84 + n * 50], dtype=np.uint8).reshape(n, 50)
        tri = rec[:, 12:48].copy().view('<f4').reshape(n, 3, 3).astype(np.float64)
        pos = tri.reshape(-1, 3)
        _, first, inv = np.unique(np.round(pos, 3), axis=0,
                                  return_index=True, return_inverse=True)
        meshes.append((os.path.basename(f)[:-4], pos[first], inv.reshape(-1, 3)))
    return meshes


def frame(eye, up):
    d = np.asarray(eye, float)
    d /= np.linalg.norm(d)
    r = np.cross(up, d)
    r /= np.linalg.norm(r)
    return d, r, np.cross(d, r)


def edges_of(pos, tri, d, thresh_deg=34.0):
    a, b, c = pos[tri[:, 0]], pos[tri[:, 1]], pos[tri[:, 2]]
    n = np.cross(b - a, c - a)
    ln = np.linalg.norm(n, axis=1)
    ln[ln == 0] = 1
    n = n / ln[:, None]
    emap = {}
    for k, (i0, i1, i2) in enumerate(tri):
        for i, j in ((i0, i1), (i1, i2), (i2, i0)):
            emap.setdefault((min(i, j), max(i, j)), []).append(k)
    cos_t = np.cos(np.deg2rad(thresh_deg))
    out = []
    for (i, j), fs in emap.items():
        if len(fs) == 1:
            out.append((i, j, 0))
        elif len(fs) >= 2:
            front = n[fs[0]] @ d > 0
            if n[fs[0]] @ n[fs[1]] < cos_t:
                out.append((i, j, 0))
            elif front != (n[fs[1]] @ d > 0):
                out.append((i, j, 1))
    return out


def render_lines(meshes, eye, up, W, H, pad=0.06, ss=2, tol=1.7):
    d, r, u = frame(eye, up)
    Wb, Hb = W * ss, H * ss
    qs = [np.stack([p @ r, p @ u, p @ d], axis=-1) for _, p, _ in meshes]
    allq = np.concatenate(qs).reshape(-1, 3)
    lo, hi = allq.min(0), allq.max(0)
    s = min(Wb * (1 - 2 * pad) / (hi[0] - lo[0]), Hb * (1 - 2 * pad) / (hi[1] - lo[1]))
    ox = Wb / 2 - (lo[0] + hi[0]) / 2 * s
    oy = Hb / 2 + (lo[1] + hi[1]) / 2 * s

    buf = np.full((Hb, Wb), -np.inf)
    pid = np.full((Hb, Wb), 255, np.uint8)
    for k_part, ((name, _, tri), q) in enumerate(zip(meshes, qs)):
        qt = q[tri]
        n = np.cross(qt[:, 1] - qt[:, 0], qt[:, 2] - qt[:, 0])
        for j in np.nonzero(n[:, 2] > 0)[0]:
            A, B, C = qt[j]
            x0, y0 = ox + A[0] * s, oy - A[1] * s
            x1, y1 = ox + B[0] * s, oy - B[1] * s
            x2, y2 = ox + C[0] * s, oy - C[1] * s
            xmin = max(0, int(np.floor(min(x0, x1, x2))))
            xmax = min(Wb - 1, int(np.ceil(max(x0, x1, x2))))
            ymin = max(0, int(np.floor(min(y0, y1, y2))))
            ymax = min(Hb - 1, int(np.ceil(max(y0, y1, y2))))
            if xmin > xmax or ymin > ymax:
                continue
            den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
            if abs(den) < 1e-9:
                continue
            xs = np.arange(xmin, xmax + 1) + 0.5
            ys = np.arange(ymin, ymax + 1) + 0.5
            px, py = np.meshgrid(xs, ys)
            w0 = ((y1 - y2) * (px - x2) + (x2 - x1) * (py - y2)) / den
            w1 = ((y2 - y0) * (px - x2) + (x0 - x2) * (py - y2)) / den
            w2 = 1 - w0 - w1
            inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            if not inside.any():
                continue
            z = w0 * A[2] + w1 * B[2] + w2 * C[2]
            sub = buf[ymin:ymax + 1, xmin:xmax + 1]
            upd = inside & (z > sub)
            sub[upd] = z[upd]
            pid[ymin:ymax + 1, xmin:xmax + 1][upd] = k_part

    segs = []
    for k_part, ((name, pos, tri), q) in enumerate(zip(meshes, qs)):
        sx = ox + q[:, 0] * s
        sy = oy - q[:, 1] * s
        qi = np.clip(np.round(sx).astype(int), 0, Wb - 1)
        qj = np.clip(np.round(sy).astype(int), 0, Hb - 1)
        for i, j, sil in edges_of(pos, tri, d):
            if not sil and not (np.isfinite(buf[qj[i], qi[i]]) or np.isfinite(buf[qj[j], qi[j]])):
                continue
            n = max(4, min(64, int(np.hypot(sx[i] - sx[j], sy[i] - sy[j]) / 3) + 2))
            ts = np.linspace(0, 1, n)
            x = sx[i] + (sx[j] - sx[i]) * ts
            y = sy[i] + (sy[j] - sy[i]) * ts
            z = q[i, 2] + (q[j, 2] - q[i, 2]) * ts
            xi = np.clip(np.round(x).astype(int), 0, Wb - 1)
            yi = np.clip(np.round(y).astype(int), 0, Hb - 1)
            bz = buf[yi, xi]
            if sil:
                vis = (pid[yi, xi] == 255) | (pid[yi, xi] == k_part)
            else:
                vis = (~np.isfinite(bz)) | (z >= bz - tol)
            k = 0
            while k < n:
                if vis[k]:
                    k2 = k
                    while k2 + 1 < n and vis[k2 + 1]:
                        k2 += 1
                    if k2 > k:
                        segs.append((x[k], y[k], x[k2], y[k2]))
                    k = k2 + 1
                else:
                    k += 1
    return segs, (s, ox, oy, (lo[0], hi[0], lo[1], hi[1]))


def main():
    meshes = load_parts()
    W, H = 1400, 1000
    views = {'主视图': ((1, 0, 0), (0, 0, 1)),
             '俯视图': ((0, 0, 1), (0, 1, 0)),
             '左视图': ((0, 1, 0), (0, 0, 1)),
             '轴测图': ((0.85, -0.95, 0.75), (0, 0, 1))}
    data = {}
    for nm, (e, u) in views.items():
        segs, (s, ox, oy, bb) = render_lines(meshes, e, u, W, H, ss=2, tol=1.7)
        data[nm] = (segs, s, ox, oy, bb)

    def place(nm, x0, y0, k):
        segs, s, ox, oy, bb = data[nm]
        minx, maxx, miny, maxy = bb
        out = []
        for ax, ay, bx, by in segs:
            a = ((ax - ox) / s, (oy - ay) / s)
            b = ((bx - ox) / s, (oy - by) / s)
            out.append((x0 + (a[0] - minx) * k, y0 + (maxy - a[1]) * k,
                        x0 + (b[0] - minx) * k, y0 + (maxy - b[1]) * k))
        return out, (x0, y0, (maxx - minx) * k, (maxy - miny) * k)

    P = {}
    P['主视图'] = place('主视图', 45, 50, 1.0)
    P['左视图'] = place('左视图', 175, 50, 1.0)
    P['轴测图'] = place('轴测图', 322, 132, 0.52)
    P['俯视图'] = place('俯视图', 45, 145, 1.0)
    frames = {nm: frame(*eyeup) for nm, eyeup in views.items()}

    def sheet_pt(nm, p3):
        _, s_, ox_, oy_, bb = data[nm]
        x0, y0, w, h = P[nm][1]
        d_, r_, u_ = frames[nm]
        return x0 + (p3 @ r_ - bb[0]) * 1.0, y0 + (bb[3] - p3 @ u_) * 1.0

    L = []
    add = L.append
    add('<svg xmlns="http://www.w3.org/2000/svg" width="420mm" height="297mm" viewBox="0 0 420 297">')
    add('<rect width="420" height="297" fill="#ffffff"/>')
    add('<style>.v{fill:none;stroke:#1c1c20;stroke-width:.18;stroke-linejoin:round}'
        '.t{font-family:"STHeiti","Songti SC",sans-serif;fill:#1c1c20}'
        '.d{fill:none;stroke:#1c1c20;stroke-width:.14}'
        '.h{fill:none;stroke:#1c1c20;stroke-width:.5}</style>')
    add('<rect x="25" y="5" width="390" height="287" class="h"/>')

    for nm, (segs, rect) in P.items():
        add('<g class="v">' + ''.join(
            f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}"/>'
            for x1, y1, x2, y2 in segs) + '</g>')
    for nm, (segs, rect) in P.items():
        x0, y0, w, h = rect
        add(f'<text class="t" x="{x0 + w / 2:.1f}" y="{y0 - 3:.1f}" font-size="3.2" '
            f'text-anchor="middle">{nm}</text>')

    def hdim(y, x1, x2, label, tick=1.6, dy=-1.2):
        add(f'<line class="d" x1="{x1}" y1="{y}" x2="{x2}" y2="{y}"/>')
        for x in (x1, x2):
            add(f'<line class="d" x1="{x}" y1="{y - tick}" x2="{x}" y2="{y + tick}"/>')
        add(f'<text class="t" x="{(x1 + x2) / 2}" y="{y + dy}" font-size="2.8" '
            f'text-anchor="middle">{label}</text>')

    def vdim(x, y1, y2, label, tick=1.6):
        add(f'<line class="d" x1="{x}" y1="{y1}" x2="{x}" y2="{y2}"/>')
        for y in (y1, y2):
            add(f'<line class="d" x1="{x - tick}" y1="{y}" x2="{x + tick}" y2="{y}"/>')
        add(f'<text class="t" x="{x + 1.0}" y="{(y1 + y2) / 2 + 1}" font-size="2.8">{label}</text>')

    # 主视图: 总宽 100 / 总高 69
    x0, y0, w, h = P['主视图'][1]
    hdim(y0 + h + 8, x0, x0 + w, '100')
    vdim(x0 - 7, y0, y0 + h, '69')

    # 俯视图: 总长 140
    x0, y0, w, h = P['俯视图'][1]
    hdim(y0 + h + 7, x0, x0 + w, '140')

    # 左视图: 高度链 13 / 48 / 60.5
    x0, y0, w, h = P['左视图'][1]
    gy = y0 + h
    for i, (z, lab) in enumerate([(13, '13'), (48, '48'), (60.5, '60.5')]):
        xx = x0 + w + 8 + i * 8
        add(f'<line class="d" x1="{xx}" y1="{gy}" x2="{xx}" y2="{gy - z}"/>')
        for y in (gy, gy - z):
            add(f'<line class="d" x1="{xx - 1.6}" y1="{y}" x2="{xx + 1.6}" y2="{y}"/>')
        add(f'<text class="t" x="{xx + 1.2}" y="{gy - z + 1}" font-size="2.9">{lab}</text>')

    # 左视图: 轮 Ø42（轮下端面到地面）
    wx1, _ = sheet_pt('左视图', np.array([-21.0, 0, 21.0]))
    wx2, _ = sheet_pt('左视图', np.array([21.0, 0, 21.0]))
    hdim(gy + 6.5, min(wx1, wx2), max(wx1, wx2), 'Ø42', dy=-1.0)

    notes = [
        '技术要求：',
        '1. 图中尺寸单位为 mm，未注公差按 GB/T 1804-m。',
        '2. 底板 140×82×3，四角 M3 过孔 Ø3.2，孔距 ±39.37 / ±38.10。',
        '3. 四轮：左右驱动轮同轴（轮距 90，Ø42×7），车头/车尾各 1 只万向轮（球 Ø12）。',
        '4. 电池 2×18650 盒 77×40×20 骑在两电机顶上（z 26–46），主板 z48；整备约 409 g。',
        '5. 测距镜头高 60.5（前 x=+56，侧 y=±45，光锥 25°）；前后万向轮轴距 116。',
        '6. 省略隐藏线，实测尺寸以 cad/params.json 为准。',
    ]
    for i, t in enumerate(notes):
        add(f'<text class="t" x="45" y="{256 + i * 5.0}" font-size="2.9">{t}</text>')

    add('<rect x="215" y="237" width="200" height="55" class="h"/>')
    yy = 237
    for r in (15, 15, 15, 10):
        yy += r
        add(f'<line x1="215" y1="{yy}" x2="415" y2="{yy}" class="d"/>')
    add('<line x1="315" y1="237" x2="315" y2="292" class="d"/>')
    add('<text class="t" x="220" y="247" font-size="4.2">迷宫小车总装图</text>')
    add('<text class="t" x="220" y="257" font-size="2.8">Maze Car — General Assembly (4 wheels)</text>')
    add('<text class="t" x="320" y="247" font-size="2.8">图号 MC-ASM-02</text>')
    add('<text class="t" x="320" y="257" font-size="2.8">比例 1:1   幅面 A3</text>')
    add('<text class="t" x="220" y="271" font-size="2.8">投影法 第一角</text>')
    add('<text class="t" x="320" y="271" font-size="2.8">单位 mm</text>')
    add('<text class="t" x="220" y="284" font-size="2.8">设计 迷宫小车项目组</text>')
    add('<text class="t" x="320" y="284" font-size="2.8">2026-11-12</text>')
    add('</svg>')
    open(OUT, 'w').write('\n'.join(L))

    png = OUT[:-4] + '.png'
    try:
        subprocess.run(['rsvg-convert', '-d', '160', '-p', '160', '-o', png, OUT], check=True)
    except (OSError, subprocess.CalledProcessError) as e:
        print('svg ok, png skipped:', e)
    print('ok', OUT, png)


if __name__ == '__main__':
    main()
