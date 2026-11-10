#!/usr/bin/env python3
"""
把真车录下的一次运行（firmware/telemetry.py 存的 runs/*.csv）喂给电脑上的 brain.cpp，重放每一个决定。
  python replay_log.py runs/20261112_153000.csv          对比真车和电脑算出来的 PWM，报告第一次对不上的地方
  python replay_log.py runs/xxx.csv --png out.png        顺便画出三个测距、航向和决策随时间的变化
用途：真车哪里犯错了，就在电脑上复现那一刻；改了 brain.cpp 以后，也能拿真数据看新逻辑会怎么做。
"""
import argparse, ctypes, csv
import sim                      # 借用 sim.py 里编译好的大脑和结构体定义


def load(path):
    with open(path, encoding='utf-8') as fh:
        head = fh.readline().lstrip('#').strip().split(',')
        rows = list(csv.DictReader(fh))
    params = dict(kv.split('=') for kv in head if '=' in kv)
    return head[:2], {k: float(v) for k, v in params.items()}, rows


def replay(params, rows):
    p = sim.BrainParams(); sim.BRAIN.brain_default_params(ctypes.byref(p))
    for k, v in params.items(): setattr(p, k, v)
    sim.BRAIN.brain_init(ctypes.byref(p), 0)
    s, a = sim.Sense(), sim.Act()
    out = []
    for r in rows:
        s.t_ms = float(r['t_ms']); s.dL, s.dF, s.dR = float(r['dL']), float(r['dF']), float(r['dR'])
        s.fresh = int(r['fresh']); s.gyro_z = float(r['gyro_z'])
        s.encL, s.encR = float(r['encL']), float(r['encR'])
        sim.BRAIN.brain_step(ctypes.byref(s), ctypes.byref(a))
        out.append((a.pwmL, a.pwmR, a.state, a.ndec, a.last_decision.decode()))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('log')
    ap.add_argument('--png')
    args = ap.parse_args()
    tags, params, rows = load(args.log)
    out = replay(params, rows)
    first, worst = None, 0.0
    for i, (r, o) in enumerate(zip(rows, out)):
        d = max(abs(float(r['pwmL']) - o[0]), abs(float(r['pwmR']) - o[1]))
        worst = max(worst, d)
        if first is None and (d > 0.02 or int(r['state']) != o[2]):
            first = i
    print(f"{' / '.join(tags)}，{len(rows)} 行，{float(rows[-1]['t_ms']) / 1000:.2f} 秒")
    print('真车决策：', ''.join(r['dec'] for i, r in enumerate(rows) if i and r['ndec'] != rows[i - 1]['ndec']))
    print('电脑决策：', ''.join(o[4] for i, o in enumerate(out) if i and o[3] != out[i - 1][3]))
    if first is None:
        print(f'全程一致（PWM 最大差 {worst:.4f}）')
    else:
        r = rows[first]
        print(f"从 {float(r['t_ms']) / 1000:.2f} 秒开始对不上：真车 PWM {r['pwmL']}/{r['pwmR']} 状态 {r['state']}，"
              f"电脑 {out[first][0]:.4f}/{out[first][1]:.4f} 状态 {out[first][2]}。"
              '多半是车上烧的 brain.cpp 和这里的不是同一版。')
    if args.png:
        import matplotlib; matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Microsoft YaHei', 'SimHei', 'Noto Sans CJK SC', 'DejaVu Sans']
        t = [float(r['t_ms']) / 1000 for r in rows]
        fig, (a1, a2) = plt.subplots(2, 1, figsize=(12, 6), sharex=True)
        for k, c in (('dL', '#2e86de'), ('dF', '#c0392b'), ('dR', '#27ae60')):
            a1.plot(t, [float(r[k]) for r in rows], c, lw=1, label=k)
        a1.set_ylim(0, 600); a1.set_ylabel('测距 mm'); a1.legend(loc='upper right')
        a2.plot(t, [float(r['pwmL']) for r in rows], lw=1, label='pwmL')
        a2.plot(t, [float(r['pwmR']) for r in rows], lw=1, label='pwmR')
        for i, r in enumerate(rows):
            if i and r['ndec'] != rows[i - 1]['ndec']:
                for ax in (a1, a2): ax.axvline(t[i], color='#999', lw=.6)
                a1.text(t[i], 580, r['dec'], ha='center', va='top', fontsize=9)
        a2.set_ylabel('PWM'); a2.set_xlabel('秒'); a2.legend(loc='upper right')
        fig.tight_layout(); fig.savefig(args.png, dpi=120); print('已保存', args.png)
