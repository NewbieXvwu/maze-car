#!/usr/bin/env python3
"""
洞洞板栅格布线：在 0.5 孔距的网格上给每根线找一条路径。

规则（照着实物来）：
  · 焊点所在的那个孔不能穿线，线只能走两个孔中间（半整数坐标），所以路径上除端点外不出现整孔。
  · 模块本体的外框不能走线（排母塑料座、芯片板身都在元件面，焊接面被它们挡住）。
  · 同一根线不能和自己重合；两根线不能沿同一小格并排走（会短路级别地贴在一起）。
  · 异网可以垂直穿过同一个点 —— 实物上就是一根绝缘线拱过另一根，交点编号在图上标出来。
"""
import heapq
from collections import defaultdict

STEP = 0.5                     # 网格分辨率：半个孔距
TURN = 1.2                     # 拐一个弯的代价
CROSS = 70.0                   # 从别的线上面跨过去的代价
SOFT = 14.0                    # 从模块板身底下穿过的代价（焊缝看不见，尽量别这么走）
EDGE = 0.0


def key(p):
    return (int(round(p[0] * 2)), int(round(p[1] * 2)))


def pt(k):
    return (k[0] / 2.0, k[1] / 2.0)


class Grid:
    """hard: 物理上不能走的区域（天线禁布、贴板安装的降压模块）；
       soft: 模块板身下面 —— 实在要绕远才从底下过，代价高。"""
    def __init__(self, cols, rows, pins, hard, soft=()):
        self.cols, self.rows = cols, rows
        self.w, self.h = int(cols * 2) - 1, int(rows * 2) - 1
        self.pins = {key(p): ref for ref, p in pins.items()}
        self.boxes = list(hard)
        self.blocked = set()
        self.soft = set()
        for k in self.pins:
            self.blocked.add(k)
        for (x0, y0, x1, y1) in soft:
            for ix in range(int(round(x0 * 2)), int(round(x1 * 2)) + 1):
                for iy in range(int(round(y0 * 2)), int(round(y1 * 2)) + 1):
                    self.soft.add((ix, iy))
        for (x0, y0, x1, y1) in self.boxes:
            for ix in range(int(round(x0 * 2)), int(round(x1 * 2)) + 1):
                for iy in range(int(round(y0 * 2)), int(round(y1 * 2)) + 1):
                    self.blocked.add((ix, iy))
        self.edge_owner = {}       # frozenset(两点) -> wire id
        self.node_owner = defaultdict(set)

    def inside(self, k):
        return 0 <= k[0] <= self.w and 0 <= k[1] <= self.h

    def reserve(self, wid, path):
        ks = [key(p) for p in path]
        for a, b in zip(ks, ks[1:]):
            step = (int((b[0] > a[0]) - (b[0] < a[0])), int((b[1] > a[1]) - (b[1] < a[1])))
            k = a
            while k != b:
                nk = (k[0] + step[0], k[1] + step[1])
                self.edge_owner[frozenset((k, nk))] = wid
                self.node_owner[nk].add(wid)
                k = nk
            self.node_owner[a].add(wid)

    def astar(self, src, dst, wid, allow):
        """allow: 本根线允许落在上面的整孔（它自己的焊点）。"""
        s, t = key(src), key(dst)
        start = (s, -1)
        openq = [(abs(t[0] - s[0]) + abs(t[1] - s[1]), 0.0, s, -1)]
        best = {start: 0.0}
        prev = {}
        closed = set()
        D = ((1, 0), (-1, 0), (0, 1), (0, -1))
        while openq:
            f, g, cur, d = heapq.heappop(openq)
            if (cur, d) in closed:
                continue
            closed.add((cur, d))
            if cur == t:
                path = [cur]
                dd = d
                while (path[-1], dd) in prev:
                    node, dd = prev[(path[-1], dd)]
                    path.append(node)
                return [pt(k) for k in reversed(path)]
            for nd, (dx, dy) in enumerate(D):
                nxt = (cur[0] + dx, cur[1] + dy)
                if not self.inside(nxt):
                    continue
                if nxt in self.blocked and nxt not in allow:
                    continue
                if nxt[0] % 2 == 0 and nxt[1] % 2 == 0 and nxt not in allow:
                    continue                      # 整孔（列、行都是整数）不能压，只能走孔间
                if nxt == s and cur != s:
                    continue
                if self.edge_owner.get(frozenset((cur, nxt)), wid) != wid:
                    continue                      # 和别的线并排/重合
                cost = STEP
                if d >= 0 and nd != d:
                    cost += TURN
                others = self.node_owner.get(nxt, set()) - {wid}
                if others:
                    cost += CROSS
                if nxt in self.soft:
                    cost += SOFT
                ng = g + cost
                nh = abs(t[0] - nxt[0]) + abs(t[1] - nxt[1])
                k = (nxt, nd)
                if k in closed:
                    continue                      # 已定案，别再改它的父节点（否则回溯会成环）
                if ng < best.get(k, 1e9):
                    best[k] = ng
                    prev[(nxt, nd)] = (cur, d)
                    heapq.heappush(openq, (ng + nh, ng, nxt, nd))
        return None


def simplify(path):
    ded = [path[0]]
    for p in path[1:]:
        if p != ded[-1]:
            ded.append(p)
    path = ded
    out = [path[0]]
    for p in path[1:]:
        if len(out) >= 2:
            a, b = out[-2], out[-1]
            same_x = a[0] == b[0] == p[0]
            same_y = a[1] == b[1] == p[1]
            mono = (same_x and (a[1] - b[1]) * (b[1] - p[1]) > 0) or \
                   (same_y and (a[0] - b[0]) * (b[0] - p[0]) > 0)
            if mono:
                out[-1] = p
                continue
        out.append(p)
    return out


def length_mm(path):
    return sum((abs(b[0] - a[0]) + abs(b[1] - a[1])) for a, b in zip(path, path[1:])) * 2.54


def keepouts(components):
    """返回 (hard, soft)：hard = 不能走；soft = 模块板身占的地方。"""
    hard, soft = [], []
    for c in components.values():
        if c.get('keep_hard'):
            hard += c['keep_hard']
        if c['box'] and c['kind'] in ('socket', 'pins', 'area'):
            (hard if c.get('hard') else soft).append(c['box'])
    return hard, soft


def crossings(wires):
    """两根线在同一个网格点上垂直穿过 —— 实物就是跨线。"""
    hit = defaultdict(set)
    for w in wires:
        ks = [key(p) for p in w['path']]
        for a, b in zip(ks, ks[1:]):
            if a[0] == b[0]:
                for iy in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    hit[(a[0], iy)].add((w['id'], 'v'))
            else:
                for ix in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                    hit[(ix, a[1])].add((w['id'], 'h'))
    nets = {w['id']: w.get('net') for w in wires}
    out = []
    for k, lst in hit.items():
        per = {}
        for wid, o in lst:
            per.setdefault(wid, set()).add(o)
        if len(per) != 2:
            continue
        (a, oa), (b, ob) = per.items()
        # 两根线都必须是“真的横穿”：方向不同，且各自都不是在这点结束/拐弯
        if oa != ob and nets.get(a) != nets.get(b):   # 同一网络的线互穿不算跨线
            out.append((k, a, b))
    out.sort()
    return out


def route_all(wires, cols, rows, pins, hard, soft=(), log=print):
    """wires: [{id, stoprefs:[ref...]}, ...]；原地补 path / length。"""
    g = Grid(cols, rows, pins, hard, soft)
    seq = sorted(wires, key=lambda w: len(w['stoprefs']))
    for w in seq:
        stops = [pins[r] for r in w['stoprefs']]
        allow = {key(p) for p in stops}
        path = [stops[0]]
        for a, b in zip(stops, stops[1:]):
            seg = g.astar(a, b, w['id'], allow)
            if seg is None:
                raise RuntimeError(f"{w['id']} {w['net']} {a}->{b} 找不到路径")
            path += seg[1:]
        path = simplify(path)
        g.reserve(w['id'], path)
        w['path'] = path
        w['length'] = length_mm(path)
    xs = crossings(wires)
    return xs


def route_once(wires, cols, rows, pins, hard, soft, order):
    g = Grid(cols, rows, pins, hard, soft)
    for w in order:
        stops = [pins[r] for r in w['stoprefs']]
        allow = {key(p) for p in stops}
        path = [stops[0]]
        for a, b in zip(stops, stops[1:]):
            seg = g.astar(a, b, w['id'], allow)
            if seg is None:
                return None
            path += seg[1:]
        path = simplify(path)
        g.reserve(w['id'], path)
        w['path'] = path
        w['length'] = length_mm(path)
    return crossings(wires)


def route_best(wires, cols, rows, pins, hard, soft=(), passes=40, seed=0, log=None):
    """多次随机顺序重布，取交叉最少的一版（保留每根线的最好结果）。"""
    import random
    rnd = random.Random(seed)
    best = None
    for i in range(passes):
        order = list(wires)
        if i == 0:
            order.sort(key=lambda w: -len(w['stoprefs']))
        elif i == 1:
            order.sort(key=lambda w: len(w['stoprefs']))
        else:
            rnd.shuffle(order)
        res = route_once(wires, cols, rows, pins, hard, soft, order)
        if res is None:
            continue
        if best is None or len(res) < len(best[0]):
            best = (list(res), [dict(w) for w in wires])
            if log:
                log(f"  pass {i}: 交叉 {len(res)}")
            if not res:
                break
    if best:
        for w, b in zip(wires, best[1]):
            w['path'], w['length'] = b['path'], b['length']
        return best[0]
    return None
