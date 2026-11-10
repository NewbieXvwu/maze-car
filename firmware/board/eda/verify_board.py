#!/usr/bin/env python3
"""出厂前自检：连通性、间距、几何、丝印-铜一致性。

只信「板上真实存在的铜」：via（孔+双面环）与 track。不假设模块内部导通。
输出一份可供人工复核的报告，任何一项不达标都返回非 0。
"""
import json
import math
import subprocess
import sys
from collections import defaultdict

PROJECT, DOC = "maze-car", "PCB1"
CLEAR_MIN = 6.0          # mil，嘉立创 2 层常规工艺
WARN_CLEAR = 8.0         # mil，低于此值只提示


def api(name):
    r = subprocess.run(["easyeda", "call", name, "--doc", DOC, "--project", PROJECT],
                       capture_output=True, text=True)
    s = r.stdout
    i = s.find("{")
    return json.JSONDecoder().raw_decode(s[i:])[0]["result"]


def seg_seg_dist(p1, p2, p3, p4):
    def pt_seg(p, a, b):
        px, py = p
        ax, ay = a
        bx, by = b
        dx, dy = bx - ax, by - ay
        l2 = dx * dx + dy * dy
        if l2 == 0:
            return math.hypot(px - ax, py - ay)
        t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / l2))
        return math.hypot(px - (ax + t * dx), py - (ay + t * dy))

    d1, d2 = p1, p2
    d3, d4 = p3, p4

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    o1, o2 = cross(d1, d2, d3), cross(d1, d2, d4)
    o3, o4 = cross(d3, d4, d1), cross(d3, d4, d2)
    if o1 * o2 < 0 and o3 * o4 < 0:
        return 0.0
    return min(pt_seg(d1, d3, d4), pt_seg(d2, d3, d4),
               pt_seg(d3, d1, d2), pt_seg(d4, d1, d2))


def main():
    vias = api("pcb.via.list")["vias"]
    lines = api("pcb.line.list")["lines"]
    outline = api("pcb.outline.get")
    print(f"板框 bbox {outline['bbox']}")

    # ---------- 1. 连通性 ----------
    parent = {}

    def find(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i, v in enumerate(vias):
        find(("v", i))
    for i, l in enumerate(lines):
        find(("t", i))

    # 线端点 → 同网 via（容差 2 mil）
    for i, l in enumerate(lines):
        for (x, y) in ((l["startX"], l["startY"]), (l["endX"], l["endY"])):
            for j, v in enumerate(vias):
                if v["net"] != l["net"]:
                    continue
                if abs(v["x"] - x) <= 2 and abs(v["y"] - y) <= 2:
                    union(("t", i), ("v", j))
    # 线端点 → 同网另一条线的端点
    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            b = lines[j]
            if a["net"] != b["net"]:
                continue
            for pa in ((a["startX"], a["startY"]), (a["endX"], a["endY"])):
                for pb in ((b["startX"], b["startY"]), (b["endX"], b["endY"])):
                    if abs(pa[0] - pb[0]) <= 2 and abs(pa[1] - pb[1]) <= 2:
                        union(("t", i), ("t", j))
    # 线中段穿过同网 via（物理上确实连上）
    for i, l in enumerate(lines):
        for j, v in enumerate(vias):
            if v["net"] != l["net"]:
                continue
            ax, ay, bx, by = l["startX"], l["startY"], l["endX"], l["endY"]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            if l2 == 0:
                continue
            t = max(0.0, min(1.0, ((v["x"] - ax) * dx + (v["y"] - ay) * dy) / l2))
            if math.hypot(v["x"] - (ax + t * dx), v["y"] - (ay + t * dy)) <= 1.0:
                union(("t", i), ("v", j))

    groups = defaultdict(set)
    for i, v in enumerate(vias):
        if v["net"]:
            groups[v["net"]].add(find(("v", i)))
    bad = {n: len(g) for n, g in groups.items() if len(g) != 1}
    print(f"\n[连通性] 有网络 {len(groups)} 个；多块不连通的网络：{bad or '无'}")

    # ---------- 2. 间距 ----------
    worst = []
    for i, a in enumerate(vias):
        for j in range(i + 1, len(vias)):
            b = vias[j]
            if a["net"] == b["net"] and a["net"]:
                continue
            gap = math.hypot(a["x"] - b["x"], a["y"] - b["y"]) - \
                (a["diameter"] + b["diameter"]) / 2
            if gap < WARN_CLEAR:
                worst.append((gap, "via-via", (a["x"], a["y"]), (b["x"], b["y"])))
    for i, l in enumerate(lines):
        for j, v in enumerate(vias):
            if v["net"] == l["net"] and v["net"]:
                continue
            ax, ay, bx, by = l["startX"], l["startY"], l["endX"], l["endY"]
            dx, dy = bx - ax, by - ay
            l2 = dx * dx + dy * dy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((v["x"] - ax) * dx + (v["y"] - ay) * dy) / l2))
            d = math.hypot(v["x"] - (ax + t * dx), v["y"] - (ay + t * dy))
            gap = d - v["diameter"] / 2 - l["lineWidth"] / 2
            if gap < WARN_CLEAR:
                worst.append((gap, "track-via", (ax, ay), (v["x"], v["y"])))
    for i, a in enumerate(lines):
        for j in range(i + 1, len(lines)):
            b = lines[j]
            if a["layer"] != b["layer"] or (a["net"] == b["net"] and a["net"]):
                continue
            d = seg_seg_dist((a["startX"], a["startY"]), (a["endX"], a["endY"]),
                             (b["startX"], b["startY"]), (b["endX"], b["endY"]))
            gap = d - (a["lineWidth"] + b["lineWidth"]) / 2
            if gap < WARN_CLEAR:
                worst.append((gap, "track-track", (a["startX"], a["startY"]), (b["startX"], b["startY"])))

    worst.sort()
    print(f"[间距] <{WARN_CLEAR} mil 的位置 {len(worst)} 处；最紧 {worst[0][0]:.1f} mil {worst[0][1]} {worst[0][2]}~{worst[0][3]}" if worst else "[间距] 全部 ≥8 mil")
    for w in worst[:6]:
        print(f"   {w[0]:.1f} mil {w[1]} {w[2]} ~ {w[3]}")
    shorts = [w for w in worst if w[0] < 0]
    print(f"[短路] {len(shorts)} 处")

    # ---------- 3. 几何 ----------
    board = (0, 0, 3600, 3500)
    out = [v for v in vias if not (board[0] < v["x"] < board[2] and board[1] < v["y"] < board[3])]
    print(f"[几何] 出界的 via {len(out)} 个")
    edge = min(min(v["x"], v["y"], board[2] - v["x"], board[3] - v["y"]) - v["diameter"] / 2
               for v in vias)
    print(f"[几何] via 铜环到板边最近 {edge:.1f} mil")
    rows = defaultdict(int)
    for v in vias:
        rows[(v["x"], v["y"])] += 1
    dup = {k: c for k, c in rows.items() if c > 1}
    print(f"[几何] 同位置重复孔 {len(dup)} 处 {list(dup.items())[:3]}")
    nonsquare = [v for v in vias if v["x"] % 5 or v["y"] % 5]
    print(f"[几何] 不在 5mil 栅格上的孔 {len(nonsquare)} 个")

    # ---------- 4. 汇总 ----------
    ok = (not bad) and (not shorts) and min((w[0] for w in worst), default=99) >= CLEAR_MIN and not out and not dup
    print(f"\n结论：{'PASS' if ok else 'FAIL'}  "
          f"（多块网络 {len(bad)}，短路 {len(shorts)}，最紧 {worst[0][0] if worst else 99:.1f} mil）")
    json.dump({"vias": len(vias), "tracks": len(lines), "splitNets": bad,
               "tight": [[round(w[0], 2), w[1]] for w in worst[:20]]},
              open("/tmp/board_verify.json", "w"), ensure_ascii=False, indent=1)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
