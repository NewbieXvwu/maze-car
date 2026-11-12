#!/usr/bin/env python3
"""把当前布局导出成给外部模型用的题目包（problem.json + 参考候选 candidate.json）。"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import layout, route

errs, pins, owner = layout.check()
assert not errs, errs
hard, soft = route.keepouts(layout.COMPONENTS)
hard.append((22.45, 2.9, 33.55, 5.4))

chs = layout.chains()
wires = []
for i, ch in enumerate(chs):
    wires.append(dict(id=i, net=ch['net'], step=ch['step'],
                      stops=[list(pins[r]) for r in ch['stops']],
                      stop_labels=ch['stops']))

problem = dict(
    board=dict(cols=layout.COLS, rows=layout.ROWS, pitch_mm=2.54, unit='hole'),
    rules=dict(
        grid=0.5,
        summary=[
            "坐标 (x,y) 是孔位，0 到 cols-1 / rows-1；路径点必须是 0.5 的倍数，相邻两点只能水平或垂直相差 0.5。",
            "x、y 都是整数的点是孔。只有本根线 stops 里的孔可以落在路径上；其它整孔一律不能踩（那是别人的焊点或孔）。",
            "线只能走两个孔中间（半整数格），所以拐弯也都在半孔位置。",
            "不同线之间不能共用任何一段（0.5 长的小段），也不能并排贴在同一个格点上拐弯。",
            "同一根线不能重复经过同一个格点。",
            "hard 区域是绝对不能走的矩形；soft 区域是模块板身，能不进就不进，每进一格算 1 分惩罚。",
            "每根线必须从 stops[0] 出发，按顺序经过 stops 里的每个点。顺序不能改、端点不能改。",
            "评分按字典序：先比 crossings（不同网络两根线垂直穿过同一格点的次数），再比总长（毫米）。",
        ],
        output='{"wires":[{"id":0,"path":[[x,y],[x,y],...]}, ...]}',
    ),
    hard=[list(b) for b in hard],
    soft=[list(b) for b in soft],
    pins={k: list(v) for k, v in pins.items()},
    nets={k: v for k, v in layout.NETS.items()},
    wires=wires,
)
route_file = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ROUTE_JSON', '/tmp/route_ok.json')
saved = json.load(open(route_file, encoding='utf-8'))
byid0 = {w['id']: w for w in saved['wires']}
probe = [dict(id=i, net=c['net'], path=[tuple(p) for p in byid0[i]['path']]) for i, c in enumerate(chs)]
problem['baseline'] = dict(crossings=len(route.crossings(probe)),
                           length_mm=int(round(sum(byid0[i]['len'] for i in byid0))))
json.dump(problem, open(os.path.join(HERE, 'problem.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

# 参考候选：现在这版的路径
route_file = sys.argv[1] if len(sys.argv) > 1 else os.environ.get('ROUTE_JSON', '/tmp/route_ok.json')
saved = json.load(open(route_file, encoding='utf-8'))
byid = {w['id']: w for w in saved['wires']}
cand = dict(wires=[dict(id=w['id'], path=[[round(float(a), 1), round(float(b), 1)] for a, b in byid[w['id']]['path']])
                   for w in wires])
json.dump(cand, open(os.path.join(HERE, 'candidate.json'), 'w', encoding='utf-8'), ensure_ascii=False)
print('problem.json', len(wires), 'wires;', 'candidate.json 写好')
