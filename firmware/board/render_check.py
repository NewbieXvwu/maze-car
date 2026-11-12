#!/usr/bin/env python3
"""开发用：把布线结果画成 PNG，方便对照检查（HTML 是给人用的，这个只是自检）。"""
import sys, os, json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle, Circle, FancyArrowPatch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import layout, route

COL = {'vbat': '#c0392b', 'v5': '#d35400', 'v33': '#e67e22', 'gnd': '#2c3e50', 'scl': '#8e44ad',
       'sda': '#2980b9', 'xshut': '#16a085', 'drv': '#27ae60', 'mot': '#7f8c8d', 'enc': '#f39c12', 'sw': '#b03060'}


def render(out, show_ids=True):
    errs, pins, owner = layout.check()
    assert not errs, errs
    hard, soft = route.keepouts(layout.COMPONENTS)
    hard.append((22.45, 2.9, 33.55, 5.4))
    ch = layout.chains()
    ws = [dict(id=i, net=c['net'], stoprefs=c['stops'], stops=[pins[r] for r in c['stops']]) for i, c in enumerate(ch)]
    xs = route.route_all(ws, layout.COLS, layout.ROWS, pins, hard, soft)
    fig, ax = plt.subplots(figsize=(22, 15), dpi=110)
    ax.set_aspect('equal'); ax.invert_yaxis()
    for x in range(layout.COLS):
        for y in range(layout.ROWS):
            ax.add_patch(Circle((x, y), 0.13, color='#d9d9d9', zorder=1))
    for (x0, y0, x1, y1) in hard:
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#b7c9b0', alpha=.55, edgecolor='#5a7a56', lw=.8, zorder=2))
    for c in layout.COMPONENTS.values():
        if c['box']:
            x0, y0, x1, y1 = c['box']
            ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor='#f0e6c8', alpha=.75, edgecolor='#8a7a4a', lw=1, zorder=3))
            ax.text((x0 + x1) / 2, (y0 + y1) / 2, c['label'], ha='center', va='center', fontsize=9, zorder=4)
    for w in ws:
        p = w['path']
        ax.plot([q[0] for q in p], [q[1] for q in p], color=COL[layout.GROUP[w['net']]], lw=2.0, solid_capstyle='round', zorder=5)
        if show_ids:
            mid = p[len(p) // 2]
            ax.text(mid[0], mid[1] - .35, str(w['id']), fontsize=7, color=COL[layout.GROUP[w['net']]], zorder=6)
    for ref, (x, y) in pins.items():
        ax.add_patch(Circle((x, y), 0.22, facecolor='#222', edgecolor='w', lw=.5, zorder=7))
    for k, a, b in xs:
        ax.add_patch(Circle((k[0] / 2, k[1] / 2), 0.45, facecolor='none', edgecolor='red', lw=1.2, zorder=8))
    ax.set_xlim(-1.5, layout.COLS + 1); ax.set_ylim(layout.ROWS + 1, -1.5)
    ax.set_xticks(range(0, layout.COLS, 5)); ax.set_yticks(range(0, layout.ROWS, 5))
    ax.grid(alpha=.15)
    ax.set_title(f'{layout.COLS}x{layout.ROWS}  {len(ws)} wires  crossings={len(xs)}  total={sum(w["length"] for w in ws)/1000:.2f}m')
    fig.tight_layout(); fig.savefig(out)
    print(out, 'crossings', len(xs), 'total', round(sum(w['length'] for w in ws) / 1000, 2))


if __name__ == '__main__':
    render(sys.argv[1] if len(sys.argv) > 1 else 'out/route-check.png')
