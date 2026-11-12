#!/usr/bin/env python3
"""校验候选走线：python3 holecheck.py candidate.json [--png out.png]

只做检查，不改数据。分数按字典序：crossings（越少越好）→ 总长（越短越好）。
错误（error）会让方案不可用；警告（warn）只是提醒。
"""
import json, sys, os
from collections import defaultdict, Counter

HERE = os.path.dirname(os.path.abspath(__file__))


def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def to_g(p):
    return (round(float(p[0]) * 2), round(float(p[1]) * 2))


def on_grid(p):
    return abs(float(p[0]) * 2 - round(float(p[0]) * 2)) < 1e-6 and \
           abs(float(p[1]) * 2 - round(float(p[1]) * 2)) < 1e-6


def rect_cells(b):
    x0, y0, x1, y1 = b
    return {(ix, iy) for ix in range(int(round(x0 * 2)), int(round(x1 * 2)) + 1)
            for iy in range(int(round(y0 * 2)), int(round(y1 * 2)) + 1)}


def main():
    if len(sys.argv) < 2:
        print('用法: python3 holecheck.py candidate.json [--png out.png]'); return 2
    cand_path = sys.argv[1]
    png = sys.argv[3] if len(sys.argv) > 3 and sys.argv[2] == '--png' else None
    prob = load(os.path.join(HERE, 'problem.json'))
    cand = load(cand_path)

    cols, rows = prob['board']['cols'], prob['board']['rows']
    wires = {w['id']: w for w in prob['wires']}
    paths = {w['id']: w['path'] for w in cand['wires']}
    errors, warns = [], []

    hard = set()
    for b in prob['hard']:
        hard |= rect_cells(b)
    soft = set()
    for b in prob['soft']:
        soft |= rect_cells(b)

    missing = set(wires) - set(paths)
    extra = set(paths) - set(wires)
    if missing: errors.append(f'少了这些线: {sorted(missing)}')
    if extra: errors.append(f'多了不认识的线: {sorted(extra)}')

    edge_owner = {}
    node_owner = defaultdict(set)
    paths_g = {}
    total = 0.0
    soft_hits = 0
    all_pads = {to_g(s) for w in wires.values() for s in w['stops']}
    empty_pass = defaultdict(int)
    for wid, w in wires.items():
        p = paths.get(wid)
        if not p:
            continue
        if len(p) < 2:
            errors.append(f'线 {wid} 的点少于 2 个'); continue
        for q in p:
            if not on_grid(q):
                errors.append(f'线 {wid} 的点 {q} 不在 0.5 网格上')
        ks = [to_g(q) for q in p]
        own = {to_g(s) for s in w['stops']}
        # 把拐点展开成 0.5 一段的连续节点
        nodes = [ks[0]]
        ok = True
        for a, b in zip(ks, ks[1:]):
            if a[0] != b[0] and a[1] != b[1]:
                errors.append(f'线 {wid} 有一段不是水平/垂直：{a}->{b}'); ok = False; break
            dx = (b[0] > a[0]) - (b[0] < a[0]); dy = (b[1] > a[1]) - (b[1] < a[1])
            k = a
            while k != b:
                k = (k[0] + dx, k[1] + dy)
                nodes.append(k)
        if not ok:
            continue
        # 必经点：按顺序出现
        pos = 0
        for st in w['stops']:
            t = to_g(st)
            while pos < len(nodes) and nodes[pos] != t:
                pos += 1
            if pos >= len(nodes):
                errors.append(f'线 {wid} 没有按顺序经过焊点 {st}'); break
            pos += 1
        for nk, prev in zip(nodes[1:], nodes):
            total += 1.27
            if nk in hard:
                errors.append(f'线 {wid} 走进禁布区 {nk[0]/2},{nk[1]/2}')
            if nk in soft:
                soft_hits += 1
            if nk[0] % 2 == 0 and nk[1] % 2 == 0 and nk not in own:
                if nk in all_pads:
                    errors.append(f'线 {wid} 从别人的焊点 {nk[0]/2},{nk[1]/2} 上压过去了（会短路）')
                else:
                    empty_pass[wid] += 1
            if not (0 <= nk[0] <= (cols * 2 - 1) and 0 <= nk[1] <= (rows * 2 - 1)):
                errors.append(f'线 {wid} 出界 {nk[0]/2},{nk[1]/2}')
            e = frozenset((prev, nk))
            o = edge_owner.get(e)
            if o is not None and o != wid:
                errors.append(f'线 {wid} 和线 {o} 共用了一段（贴太近或重合）')
            else:
                edge_owner[e] = wid
                node_owner[nk].add(wid)
        paths_g[wid] = nodes

    # 自交：同一根线在同一格点同时有横段和竖段（进焊点后原路返回是允许的）
    for wid, w in wires.items():
        ks = paths_g.get(wid)
        if not ks: continue
        dirs = defaultdict(set)
        for a, b in zip(ks, ks[1:]):
            dirs[a].add('h' if a[1] == b[1] else 'v')
            dirs[b].add('h' if a[1] == b[1] else 'v')
        dupc = {k for k, c in Counter(ks).items() if c > 1}
        bad = [k for k, ds in dirs.items() if len(ds) > 1 and k in dupc]
        if bad:
            warns.append(f'线 {wid} 自己碰了一下自己（同网络，电气上没事）：{[(k[0]/2, k[1]/2) for k in bad[:3]]}')
            continue
        dup = [k for k, c in Counter(ks).items() if c > 1]
        if dup:
            own = {to_g(s) for s in w['stops']}
            real = [d for d in dup if d not in own]
            if real:
                warns.append(f'线 {wid} 重复经过同一点：{[(d[0]/2, d[1]/2) for d in real[:3]]}')

    # 交叉：两根不同网络的线垂直穿过同一格点
    hit = defaultdict(set)
    for wid, w in wires.items():
        ks = paths_g.get(wid)
        if not ks: continue
        for a, b in zip(ks, ks[1:]):
            if a[0] == b[0]:
                for iy in range(min(a[1], b[1]), max(a[1], b[1]) + 1):
                    hit[(a[0], iy)].add((wid, 'v'))
            else:
                for ix in range(min(a[0], b[0]), max(a[0], b[0]) + 1):
                    hit[(ix, a[1])].add((wid, 'h'))
    cross = []
    for k, lst in hit.items():
        per = defaultdict(set)
        for wid, o in lst:
            per[wid].add(o)
        if len(per) != 2:
            continue
        (a, oa), (b, ob) = per.items()
        if oa != ob and wires[a]['net'] != wires[b]['net']:
            cross.append((k, a, b))

    print('=' * 60)
    base = prob.get('baseline', {})
    print(f'跨线 crossings : {len(cross)}   （基线 {base.get("crossings", "?")}）')
    print(f'总长 length    : {total/1000:.2f} m   （基线 {base.get("length_mm", 0)/1000:.2f} m）')
    print(f'soft 区域占用  : {soft_hits} 格')
    if empty_pass:
        print(f'从空孔上压过    : {sum(empty_pass.values())} 次（{len(empty_pass)} 根线；空孔没接任何东西，不短路，只是线不贴通道走）')
    print(f'错误 {len(errors)} 条，警告 {len(warns)} 条')
    for e in errors[:20]:
        print('  ✗', e)
    for e in warns[:5]:
        print('  · 提示:', e)
    if len(errors) > 20:
        print(f'  … 还有 {len(errors) - 20} 条')
    if not errors:
        print('  ✓ 规则全部通过')

    if png:
        try:
            import matplotlib
            matplotlib.use('Agg')
            import matplotlib.pyplot as plt
            from matplotlib.patches import Rectangle, Circle
            fig, ax = plt.subplots(figsize=(20, 14), dpi=110)
            ax.set_aspect('equal'); ax.invert_yaxis()
            for x in range(cols):
                for y in range(rows):
                    ax.add_patch(Circle((x, y), 0.12, color='#dddddd', zorder=1))
            for b in prob['hard']:
                ax.add_patch(Rectangle((b[0], b[1]), b[2]-b[0], b[3]-b[1], facecolor='#b7c9b0', alpha=.6, zorder=2))
            for b in prob['soft']:
                ax.add_patch(Rectangle((b[0], b[1]), b[2]-b[0], b[3]-b[1], facecolor='#f0e6c8', alpha=.6, zorder=2))
            cmap = plt.get_cmap('tab20')
            for wid, w in wires.items():
                p = paths.get(wid)
                if not p: continue
                ax.plot([q[0] for q in p], [q[1] for q in p], color=cmap(wid % 20), lw=2, zorder=4, solid_capstyle='round')
            for k, a, b in cross:
                ax.add_patch(Circle((k[0]/2, k[1]/2), 0.45, fill=False, edgecolor='#e74c3c', lw=1.5, zorder=6))
            ax.set_xlim(-1, cols); ax.set_ylim(rows, -1)
            ax.set_title(f'crossings {len(cross)} · {total/1000:.2f} m')
            plt.tight_layout(); plt.savefig(png); print('图已存:', png)
        except Exception as ex:
            print('（画图跳过：%s）' % ex)
    return 0 if not errors else 1


if __name__ == '__main__':
    sys.exit(main())
