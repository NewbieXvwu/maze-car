#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
底板 1:1 切割图：从 cad/params.json 生成 DXF(R12) 与 SVG。

用法：python3 cad/gen_plate_2d.py
输出：out/plate-1to1.dxf  out/plate-1to1.svg
单位：mm，原点在板中心（与整车坐标一致，X 前 / Y 左）。
"""

import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = ROOT / "out"
OUT.mkdir(exist_ok=True)

P = json.loads((HERE / "params.json").read_text(encoding="utf-8"))


def g(sec, key):
    d = P[sec][key]
    m = d.get("measured")
    return float(m if m is not None else d["nominal"])


L = g("chassis", "plate_len")
W = g("chassis", "plate_wid")
CH = g("chassis", "chamfer_edge")
HD = g("chassis", "plate_hole_d")
INSET = g("chassis", "plate_hole_inset")

hx = L / 2 - INSET
hy = W / 2 - INSET

# 外框：四角 1 mm 倒角，逆时针
poly = [
    (L / 2 - CH, -W / 2),
    (L / 2, -W / 2 + CH),
    (L / 2, W / 2 - CH),
    (L / 2 - CH, W / 2),
    (-L / 2 + CH, W / 2),
    (-L / 2, W / 2 - CH),
    (-L / 2, -W / 2 + CH),
    (-L / 2 + CH, -W / 2),
]

holes = [(hx, hy), (-hx, hy), (-hx, -hy), (hx, -hy)]

# ---------------------------------------------------------------- DXF R12
def dxf_line(x1, y1, x2, y2):
    return ("0\nLINE\n8\nCUT\n10\n%.4f\n20\n%.4f\n11\n%.4f\n21\n%.4f\n"
            % (x1, y1, x2, y2))


def dxf_circle(cx, cy, r):
    return "0\nCIRCLE\n8\nCUT\n10\n%.4f\n20\n%.4f\n40\n%.4f\n" % (cx, cy, r)


ents = []
for i in range(len(poly)):
    x1, y1 = poly[i]
    x2, y2 = poly[(i + 1) % len(poly)]
    ents.append(dxf_line(x1, y1, x2, y2))
for cx, cy in holes:
    ents.append(dxf_circle(cx, cy, HD / 2))

dxf = (
    "0\nSECTION\n2\nHEADER\n"
    "9\n$INSUNITS\n70\n4\n"
    "9\n$MEASUREMENT\n70\n1\n"
    "0\nENDSEC\n"
    "0\nSECTION\n2\nTABLES\n"
    "0\nTABLE\n2\nLAYER\n70\n1\n"
    "0\nLAYER\n2\nCUT\n70\n0\n62\n7\n6\nCONTINUOUS\n"
    "0\nENDTAB\n0\nENDSEC\n"
    "0\nSECTION\n2\nENTITIES\n"
    + "".join(ents)
    + "0\nENDSEC\n0\nEOF\n"
)
(OUT / "plate-1to1.dxf").write_text(dxf, encoding="ascii")

# ---------------------------------------------------------------- SVG
pad = 10
svg_w = L + 2 * pad
svg_h = W + 2 * pad

pts = " ".join("%.3f,%.3f" % (x, -y) for x, y in poly)
circles = "".join(
    '<circle cx="%.3f" cy="%.3f" r="%.3f"/>' % (cx, -cy, HD / 2) for cx, cy in holes
)

svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{svg_w}mm" height="{svg_h}mm"
     viewBox="0 0 {svg_w} {svg_h}">
  <rect width="100%" height="100%" fill="#ffffff"/>
  <g transform="translate({svg_w/2:.3f},{svg_h/2:.3f})" fill="none"
     stroke="#111111" stroke-width="0.15">
    <polygon points="{pts}"/>
    {circles}
  </g>
  <g font-family="Helvetica, Arial" font-size="3" fill="#666">
    <text x="{pad}" y="{pad - 3}">底板 1:1  {L:g} × {W:g} × 3 mm</text>
    <text x="{pad}" y="{svg_h - 3}">4 × Ø{HD:g} 孔，孔心距边 {INSET:g}；四角倒角 {CH:g}</text>
  </g>
</svg>
'''
(OUT / "plate-1to1.svg").write_text(svg, encoding="utf-8")

print(f"外框 {L} × {W}，{len(holes)} 个 Ø{HD} 孔，孔心 (±{hx:.2f}, ±{hy:.2f})")
print("写出 out/plate-1to1.dxf 与 out/plate-1to1.svg")
