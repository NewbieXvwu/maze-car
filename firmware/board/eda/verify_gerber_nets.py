#!/usr/bin/env python3
"""从导出的 Gerber 独立重建铜层连通性，核对网表（不看编辑器、不看 API 的 ok 字段）。

1. 把 GTL/GBL 里的焊盘（D03 闪光）和走线（D01 线段）读成几何。
2. 按"几何相接"连成图：同层焊盘↔线、线↔线；焊盘是镀通孔，正反两面天然相连。
3. 用 pcb_plan.json 的针脚→网络表核对：
   - 同一个网络的所有孔必须在同一片铜里（否则实测断路）；
   - 同一片铜里不能出现两个网络（否则实测短路）。

用法：python3 verify_gerber_nets.py [../.../maze-car-gerber.zip] [pcb_plan.json]
"""
import json
import math
import re
import sys
import zipfile
from collections import defaultdict

MIL = 0.0254          # mm per mil
GRID = 100            # mil per 2.54mm grid
COLS, ROWS = 35, 34   # 布线图格数（x 0..34, y 0..33，y 向下）


def parse_gerber(text):
    """返回 (pads, tracks)，单位 mm。pads=[(x,y,dia,layer)]，tracks=[(x1,y1,x2,y2,w,layer)]"""
    pads, tracks = [], []
    ap = {}
    cur = None
    last = None
    layer = None
    for raw in text.splitlines():
        s = raw.strip()
        m = re.match(r'G04 Layer: (.*)$', s)
        if m:
            layer = m.group(1).strip()
            continue
        m = re.match(r'%ADD(\d+)([A-Z]),([0-9.]+)', s)
        if m:
            ap[int(m.group(1))] = float(m.group(3))
            continue
        m = re.match(r'(?:G54)?D(\d+)\*$', s)   # 光圈选择：G54Dnn* 或 Dnn*
        if m:
            cur = int(m.group(1))
            continue
        m = re.match(r'(?:G0[13])?X(-?\d+)Y(-?\d+)D0([123])\*', s)
        if m:
            x, y, d = int(m.group(1)) / 1e5, int(m.group(2)) / 1e5, m.group(3)
            if d == '2':
                last = (x, y)
            elif d == '1':
                if last:
                    tracks.append((last[0], last[1], x, y, ap.get(cur, 0.0), layer))
                last = (x, y)
            else:
                dia = ap.get(cur, 0.0)
                if dia > 0:
                    pads.append((x, y, dia, layer))
                last = (x, y)
    return pads, tracks


def seg_pt_dist(px, py, x1, y1, x2, y2):
    dx, dy = x2 - x1, y2 - y1
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / L2))
    return math.hypot(px - (x1 + t * dx), py - (y1 + t * dy))


def _ccw(ax, ay, bx, by, cx, cy):
    return (cy - ay) * (bx - ax) > (by - ay) * (cx - ax)


def seg_seg_dist(x1, y1, x2, y2, a1, b1, a2, b2):
    if (_ccw(x1, y1, a1, b1, a2, b2) != _ccw(x2, y2, a1, b1, a2, b2)
            and _ccw(x1, y1, x2, y2, a1, b1) != _ccw(x1, y1, x2, y2, a2, b2)):
        return 0.0
    return min(seg_pt_dist(x1, y1, a1, b1, a2, b2),
               seg_pt_dist(x2, y2, a1, b1, a2, b2),
               seg_pt_dist(a1, b1, x1, y1, x2, y2),
               seg_pt_dist(a2, b2, x1, y1, x2, y2))


class UF:
    def __init__(self, n):
        self.p = list(range(n))

    def find(self, x):
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[ra] = rb


def pin_nets(plan_path):
    """布线图的格点坐标 -> (x_mil, y_mil) -> 网络"""
    plan = json.load(open(plan_path))
    out = {}
    for m in plan:
        for p in m['pins']:
            if not p['net']:
                continue
            gx = p['x'] * GRID + GRID
            gy = (ROWS - 1 - p['y']) * GRID + GRID
            out[(round(gx * MIL, 3), round(gy * MIL, 3))] = p['net']
    return out


def parse_drill(text):
    """Excellon：T01C1.00076 定义刀具，X5.08Y15.24 是十进制小数的毫米坐标。"""
    tools, cur, holes = {}, None, []
    for ln in text.splitlines():
        ln = ln.strip()
        m = re.match(r'^T(\d+)C([\d.]+)$', ln)
        if m:
            tools[m.group(1)] = float(m.group(2))
            continue
        m = re.match(r'^T(\d+)$', ln)
        if m:
            cur = m.group(1)
            continue
        m = re.match(r'^X(-?[\d.]+)Y(-?[\d.]+)$', ln)
        if m and cur:
            holes.append((float(m.group(1)), float(m.group(2)), tools.get(cur, 0.0)))
    return holes


def main(zip_path, plan_path):
    pads, tracks, drills = [], [], []
    with zipfile.ZipFile(zip_path) as z:
        for name in z.namelist():
            up = name.upper()
            if up.endswith(('.GTL', '.GBL')):
                p, t = parse_gerber(z.read(name).decode('utf-8', 'ignore'))
                pads += p
                tracks += t
            elif up.endswith('.DRL'):
                drills += parse_drill(z.read(name).decode('utf-8', 'ignore'))

    n_pad = len(pads)
    uf = UF(n_pad + len(tracks))

    for pi, (px, py, pd, pl) in enumerate(pads):
        r = pd / 2
        for ti, (x1, y1, x2, y2, w, tl) in enumerate(tracks):
            if tl != pl:
                continue
            if (max(x1, x2) + w < px - r or min(x1, x2) - w > px + r
                    or max(y1, y2) + w < py - r or min(y1, y2) - w > py + r):
                continue
            if seg_pt_dist(px, py, x1, y1, x2, y2) <= r + w / 2 - 1e-6:
                uf.union(pi, n_pad + ti)

    for i in range(len(tracks)):
        x1, y1, x2, y2, w1, l1 = tracks[i]
        for j in range(i + 1, len(tracks)):
            a1, b1, a2, b2, w2, l2 = tracks[j]
            if l1 != l2:
                continue
            if (max(x1, x2) + w1 < min(a1, a2) or min(x1, x2) - w1 > max(a1, a2)
                    or max(y1, y2) + w1 < min(b1, b2) or min(y1, y2) - w1 > max(b1, b2)):
                continue
            if seg_seg_dist(x1, y1, x2, y2, a1, b1, a2, b2) <= (w1 + w2) / 2 - 1e-6:
                uf.union(n_pad + i, n_pad + j)

    # 镀通孔：同一坐标的上下层焊盘相连 —— 但只有在钻带里真有这个孔时才算
    by_xy = defaultdict(list)
    for pi, (x, y, d, l) in enumerate(pads):
        by_xy[(round(x, 3), round(y, 3))].append(pi)
    no_drill = []
    for (x, y), ids in by_xy.items():
        hit = [h for h in drills
               if abs(h[0] - x) <= 0.05 and abs(h[1] - y) <= 0.05]
        if not hit:
            no_drill.append((x, y))
            continue
        for k in ids[1:]:
            uf.union(ids[0], k)
    no_drill = sorted({(round(x / MIL, 1), round(y / MIL, 1)) for x, y in no_drill})

    nets = pin_nets(plan_path)
    pad_net = {}
    unmatched = []
    for pi, (x, y, d, l) in enumerate(pads):
        net = nets.get((round(x, 3), round(y, 3)))
        if net:
            pad_net[pi] = net
        elif len(by_xy[(round(x, 3), round(y, 3))]) == 2:
            # 只在第一层记一次
            if pads[by_xy[(round(x, 3), round(y, 3))][0]][3] == l:
                unmatched.append((x / MIL, y / MIL))

    comp_nets = defaultdict(set)
    net_comps = defaultdict(set)
    net_pads = defaultdict(list)
    for pi, net in pad_net.items():
        root = uf.find(pi)
        comp_nets[root].add(net)
        net_comps[net].add(root)
        net_pads[net].append(pi)

    shorts = {k: sorted(v) for k, v in comp_nets.items() if len(v) > 1}
    split = {k: len(v) for k, v in net_comps.items() if len(v) > 1}

    total_pads = len(by_xy)
    print(f'读入焊盘 {total_pads} 个（正反各一套）、走线 {len(tracks)} 段')
    print(f'有网络的焊盘 {len(set(by_xy) & set()) or len(net_pads)} 组，网络 {len(net_pads)} 个')
    print(f'未在网表里的焊盘（安装孔等）：{len(unmatched)}')
    print(f'钻带孔 {len(drills)} 个；缺钻孔的焊盘 {len(no_drill)}' + (f' {no_drill[:5]}' if no_drill else ''))
    # 空脚（无网络）被导线碰到 = 图上多接了东西
    floating_hit = []
    for pi, (x, y, d, l) in enumerate(pads):
        if (round(x, 3), round(y, 3)) in nets:
            continue
        for (x1, y1, x2, y2, w, tl) in tracks:
            if tl != l:
                continue
            if seg_pt_dist(x, y, x1, y1, x2, y2) <= d / 2 + w / 2 - 1e-6:
                floating_hit.append((round(x / MIL, 1), round(y / MIL, 1)))
                break
    print(f'被铜皮碰到的空脚：{len(set(floating_hit))}' + (f' {sorted(set(floating_hit))[:5]}' if floating_hit else ''))
    print(f'短路（一片铜含多个网络）：{len(shorts)}' + (f' {shorts}' if shorts else ''))
    print(f'同网络被切成多片铜：{len(split)}' + (f' {split}' if split else ''))
    ok = not shorts and not split and not no_drill and not floating_hit
    print('结论：' + ('PASS —— 制造文件里的铜与网表完全一致'
                   if ok else 'FAIL —— 上面的网络有问题，不能下单'))
    return 0 if ok else 1


if __name__ == '__main__':
    # 默认路径相对仓库根，从 eda/ 或仓库根跑都一样
    import pathlib
    root = pathlib.Path(__file__).resolve().parents[3]
    zp = sys.argv[1] if len(sys.argv) > 1 else str(root / 'out/gerber/maze-car-gerber.zip')
    pp = sys.argv[2] if len(sys.argv) > 2 else str(root / 'firmware/board/eda/pcb_plan.json')
    sys.exit(main(zp, pp))
