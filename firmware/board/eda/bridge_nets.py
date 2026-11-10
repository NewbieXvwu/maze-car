#!/usr/bin/env python3
"""把被切成孤岛的电源网络在顶层用短线桥接起来。

背景：手焊布局图里的 44 根线是「点到点」的，GND 被分成 5 块、3V3 分成 2 块。
这些孤岛在模块内部同名脚相通的前提下是能用的，但板子本身不该依赖模块内部走线
来传地电流。这里在顶层（几乎全空）用 A* 补 5 根桥接线（11 段），把每块连成一整片。

用法：python3 bridge_nets.py [--dry-run]
"""
import json
import math
import subprocess
import sys
from collections import deque

STEP = 25                      # mil，寻路栅格
CLEAR = 6                      # mil，JLC 最小间距
W = 20                         # mil，桥接线宽（电源）
BOARD = (0, 0, 3600, 3500)
EDGE_KEEP = 30                 # mil，铜到板边
LAYER = 1                      # 顶层
PROJECT, DOC = "maze-car", "PCB1"

# 要连起来的「孤岛代表孔」（同网络的任意孔即可）
BRIDGES = [
    ("3V3", (1400, 3000), (1400, 2900)),
    ("GND", (2400, 1000), (2400, 900)),
    ("GND", (1400, 900),  (2400, 900)),
    ("GND", (400, 500),   (500, 1000)),
    ("GND", (2700, 2600), (2800, 1600)),
]


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def load_state():
    def call(a):
        ok, out = run(["easyeda", "call", a, "--doc", DOC, "--project", PROJECT])
        s = out[out.find("{"):]
        return json.JSONDecoder().raw_decode(s)[0]["result"]

    return call("pcb.via.list")["vias"], call("pcb.line.list")["lines"]


def seg_dist(p, a, b):
    px, py = p
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


def blocked(x, y, net, vias, lines):
    """该点能不能走 20 mil 的线：离异网铜要留够 6 mil。"""
    if not (BOARD[0] + EDGE_KEEP <= x <= BOARD[2] - EDGE_KEEP and
            BOARD[1] + EDGE_KEEP <= y <= BOARD[3] - EDGE_KEEP):
        return True
    for v in vias:
        if v["net"] == net:
            continue
        if math.hypot(x - v["x"], y - v["y"]) < W / 2 + CLEAR + v["diameter"] / 2:
            return True
    for l in lines:
        if l["net"] == net or l["layer"] != LAYER:
            continue
        if seg_dist((x, y), (l["startX"], l["startY"]), (l["endX"], l["endY"])) < \
                W / 2 + CLEAR + l["lineWidth"] / 2:
            return True
    return False


def astar(start, goal, net, vias, lines):
    def key(p):
        return (round(p[0]), round(p[1]))

    s, g = key(start), key(goal)
    openq = [(0, s)]
    came = {s: None}
    cost = {s: 0}
    while openq:
        openq.sort()
        _, cur = openq.pop(0)
        if cur == g:
            path = []
            while cur:
                path.append(cur)
                cur = came[cur]
            return path[::-1]
        for dx, dy in ((STEP, 0), (-STEP, 0), (0, STEP), (0, -STEP)):
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt == g:
                pass
            elif blocked(nxt[0], nxt[1], net, vias, lines):
                continue
            nc = cost[cur] + STEP
            if nc < cost.get(nxt, 1e18):
                cost[nxt] = nc
                came[nxt] = cur
                h = abs(nxt[0] - g[0]) + abs(nxt[1] - g[1])
                openq.append((nc + h, nxt))
    return None


def simplify(path):
    out = [path[0]]
    for i in range(1, len(path) - 1):
        px, py = path[i - 1]
        cx, cy = path[i]
        nx, ny = path[i + 1]
        if (cx - px, cy - py) != (nx - cx, ny - cy):
            out.append(path[i])
    out.append(path[-1])
    return out


def main():
    dry = "--dry-run" in sys.argv
    vias, lines = load_state()
    print(f"vias={len(vias)} lines={len(lines)}")
    made = []
    for net, a, b in BRIDGES:
        path = astar(a, b, net, vias, lines)
        if not path:
            print(f"!! {net} {a}->{b} 找不到路径")
            continue
        pts = simplify(path)
        pts[0], pts[-1] = tuple(a), tuple(b)
        length = sum(math.hypot(pts[i + 1][0] - pts[i][0], pts[i + 1][1] - pts[i][1])
                     for i in range(len(pts) - 1))
        print(f"{net:4} {a} -> {b}  {len(pts)-1} 段 {length:.0f} mil")
        for p1, p2 in zip(pts, pts[1:]):
            print(f"     {p1} -> {p2}")
            made.append((net, p1, p2))
        # 立刻把新线加进障碍集，避免下一根压上来
        for p1, p2 in zip(pts, pts[1:]):
            lines.append({"net": net, "layer": LAYER, "startX": p1[0], "startY": p1[1],
                          "endX": p2[0], "endY": p2[1], "lineWidth": W})
    if dry:
        print(f"[dry-run] 共 {len(made)} 段，未落盘")
        return
    ok_n = 0
    for net, p1, p2 in made:
        ok, out = run(["easyeda", "pcb", "track", "--doc", DOC, "--project", PROJECT,
                       "--x1", str(p1[0]), "--y1", str(p1[1]),
                       "--x2", str(p2[0]), "--y2", str(p2[1]),
                       "--width", str(W), "--net", net, "--layer", str(LAYER)])
        ok_n += 1 if ok else 0
        if not ok:
            print("FAIL", net, p1, p2, out[-160:])
    print(f"tracks created {ok_n}/{len(made)}")


if __name__ == "__main__":
    main()
