#!/usr/bin/env python3
"""
迷宫小车仿真器
  物理（电机、打滑、转向）和传感器（激光测距、陀螺仪、编码器）在 Python 里模拟；
  控制逻辑直接调用 ../firmware/car/brain.cpp —— 和上车烧录的是同一个文件。

用法：
  python sim.py                         随机迷宫，左手模式，弹窗看动画
  python sim.py --mode right --seed 7   右手模式，指定随机种子
  python sim.py --mode best             左右手都跑一遍，挑快的（模拟"看图选手"）
  python sim.py --mode learn            先用左手跑并学习，再回放
  python sim.py --batch 200             批量跑 200 个随机迷宫，统计成功率
  python sim.py --maze track_2026.txt   跑宣讲会公布的比赛赛道
  python sim.py --maze track_2026.txt --race   同上，打开比赛固件用的"已知赛道模式"
  python sim.py --maze maze_example.txt 跑你画的迷宫（格式见那个文件）
  python sim.py --png run.png           不弹窗，把轨迹存成图片
  python sim.py --mu 0.25               模拟很滑的地面（默认 0.5）

依赖：pip install numpy matplotlib；还需要一个 C++ 编译器（Mac 上运行 xcode-select --install）
"""
import argparse, ctypes, math, os, random, statistics, subprocess, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
BRAIN_DIR = os.path.join(HERE, '..', 'firmware', 'car')     # 大脑只有一份，放在固件目录里，仿真直接编译它

# ---------------------------------------------------------------- 编译并加载 brain.cpp
def load_brain():
    ext = '.dylib' if sys.platform == 'darwin' else ('.dll' if os.name == 'nt' else '.so')
    lib = os.path.join(HERE, 'libbrain' + ext)
    srcs = [os.path.join(BRAIN_DIR, f) for f in ('brain.cpp', 'brain.h')]
    if not os.path.exists(lib) or os.path.getmtime(lib) < max(map(os.path.getmtime, srcs)):
        cxx = os.environ.get('CXX', 'c++')
        subprocess.check_call([cxx, '-O2', '-std=c++17', '-shared', '-fPIC', srcs[0], '-o', lib])
    return ctypes.CDLL(lib)

class BrainParams(ctypes.Structure):
    _fields_ = [(n, ctypes.c_float) for n in (
        'cell_mm', 'wall_half_mm', 'side_y_mm', 'front_x_mm', 'vmax_mm_s', 'deadband_pwm',
        'cruise_mm_s', 'creep_mm_s', 'accel_mm_s2', 'brake_mm_s2', 'open_th_mm', 'edge_lag_mm',
        'debounce_mm', 'k_lat', 'max_corr_deg', 'k_head', 'k_hd', 'k_turn', 'k_td',
        'turn_pwm', 'turn_min_pwm', 'k_align', 'single_path', 'stop_turns', 'exit_run_mm')]

class Sense(ctypes.Structure):
    _fields_ = [(n, ctypes.c_float) for n in ('t_ms', 'dL', 'dF', 'dR', 'gyro_z', 'encL', 'encR')] + \
               [('fresh', ctypes.c_int)]

class Act(ctypes.Structure):
    _fields_ = [('pwmL', ctypes.c_float), ('pwmR', ctypes.c_float),
                ('state', ctypes.c_int), ('ndec', ctypes.c_int), ('last_decision', ctypes.c_char)]

BRAIN = load_brain()
MODES = {'left': 0, 'right': 1, 'replay': 2}
RACE = {'single_path': 1, 'stop_turns': 14}   # 比赛固件用的"已知赛道模式"（只适用于 track_2026.txt）

# ---------------------------------------------------------------- 迷宫
class Maze:
    """H[r][c]: 第 r 行格子上方的墙；V[r][c]: 第 c 列格子左边的墙。entrance/exit = (边, 行或列)"""
    def __init__(self, rows, cols, H, V, entrance, exit_, cell=300.0, wall_half=3.0, rng=None, realism=True):
        self.rows, self.cols, self.H, self.V = rows, cols, H, V
        self.entrance, self.exit = entrance, exit_
        self.cell, self.wh = cell, wall_half
        rng = rng or random.Random(0)
        self.panels = []   # 每块墙板的中心线 (x1,y1,x2,y2)
        for r in range(rows + 1):
            for c in range(cols):
                if H[r][c]:
                    y = (rows - r) * cell
                    self._add_panel(c * cell, y, (c + 1) * cell, y, rng, realism)
        for r in range(rows):
            for c in range(cols + 1):
                if V[r][c]:
                    x = c * cell
                    self._add_panel(x, (rows - r) * cell, x, (rows - r - 1) * cell, rng, realism)
        P = np.array(self.panels)
        self.A, self.B = P[:, :2], P[:, 2:]
        # 射线检测用墙板的四条边（墙有厚度）
        edges = []
        for (x1, y1, x2, y2) in self.panels:
            d = np.array([x2 - x1, y2 - y1]); d /= np.linalg.norm(d)
            n = np.array([-d[1], d[0]]) * wall_half
            p1, p2 = np.array([x1, y1]), np.array([x2, y2])
            q = [p1 + n, p2 + n, p2 - n, p1 - n]
            for i in range(4):
                edges.append((*q[i], *q[(i + 1) % 4]))
        E = np.array(edges)
        self.EA, self.EB = E[:, :2], E[:, 2:] - E[:, :2]

    def _add_panel(self, x1, y1, x2, y2, rng, realism):
        d = np.array([x2 - x1, y2 - y1], float); L = np.linalg.norm(d); d /= L
        ext = [self.wh, self.wh]                       # 两端各伸出半个墙厚，转角处严丝合缝
        if realism:                                    # 真实纸板迷宫：接缝有缝，墙板有点歪
            for i in range(2):
                u = rng.random()
                if u < 0.15: ext[i] = -rng.uniform(1.5, 5)
                elif u < 0.20: ext[i] = -rng.uniform(7, 17)
            off = rng.uniform(-4, 4)
            rot = math.radians(rng.uniform(-1.0, 1.0))
        else:
            off, rot = 0.0, 0.0
        n = np.array([-d[1], d[0]])
        c = (np.array([x1, y1]) + np.array([x2, y2])) / 2 + n * off
        cr, sr = math.cos(rot), math.sin(rot)
        d = np.array([d[0] * cr - d[1] * sr, d[0] * sr + d[1] * cr])
        p1 = c - d * (L / 2 + ext[0]); p2 = c + d * (L / 2 + ext[1])
        self.panels.append((p1[0], p1[1], p2[0], p2[1]))

    def cell_center(self, r, c):
        return ((c + 0.5) * self.cell, (self.rows - r - 0.5) * self.cell)

    def start_pose(self):
        side, k = self.entrance
        if side == 'W': r, c, th = k, 0, 0.0
        elif side == 'E': r, c, th = k, self.cols - 1, math.pi
        elif side == 'N': r, c, th = 0, k, -math.pi / 2
        else: r, c, th = self.rows - 1, k, math.pi / 2
        x, y = self.cell_center(r, c)
        return x, y, th

    def escaped(self, x, y):
        """车中心是否已经从出口离开迷宫"""
        side, k = self.exit
        W, Hh, m = self.cols * self.cell, self.rows * self.cell, 60
        if side == 'E': return x > W + m
        if side == 'W': return x < -m
        if side == 'N': return y > Hh + m
        return y < -m

    def raycast(self, ox, oy, ang, maxd=2000.0):
        d = np.array([math.cos(ang), math.sin(ang)])
        e = self.EB
        den = d[0] * e[:, 1] - d[1] * e[:, 0]
        w = self.EA - np.array([ox, oy])
        with np.errstate(divide='ignore', invalid='ignore'):
            t = (w[:, 0] * e[:, 1] - w[:, 1] * e[:, 0]) / den
            u = (w[:, 0] * d[1] - w[:, 1] * d[0]) / den
        ok = (np.abs(den) > 1e-9) & (t > 0) & (u >= 0) & (u <= 1)
        return float(t[ok].min()) if ok.any() else maxd


def random_maze(rows, cols, braid, rng, **kw):
    H = [[True] * cols for _ in range(rows + 1)]
    V = [[True] * (cols + 1) for _ in range(rows)]
    def open_wall(r, c, d):   # d: 0 上 1 右 2 下 3 左
        if d == 0: H[r][c] = False
        elif d == 2: H[r + 1][c] = False
        elif d == 3: V[r][c] = False
        else: V[r][c + 1] = False
    DR = [(-1, 0), (0, 1), (1, 0), (0, -1)]
    seen = {(0, 0)}; stack = [(0, 0)]
    while stack:
        r, c = stack[-1]
        nb = [(d, r + DR[d][0], c + DR[d][1]) for d in range(4)]
        nb = [(d, rr, cc) for d, rr, cc in nb if 0 <= rr < rows and 0 <= cc < cols and (rr, cc) not in seen]
        if not nb: stack.pop(); continue
        d, rr, cc = rng.choice(nb)
        open_wall(r, c, d); seen.add((rr, cc)); stack.append((rr, cc))
    inner = [(r, c, d) for r in range(rows) for c in range(cols) for d in (1, 2)
             if (d == 1 and c < cols - 1 and V[r][c + 1]) or (d == 2 and r < rows - 1 and H[r + 1][c])]
    rng.shuffle(inner)
    for r, c, d in inner[:int(braid * len(inner))]:
        open_wall(r, c, d)
    ri, ro = rng.randrange(rows), rng.randrange(rows)
    V[ri][0] = False; V[ro][cols] = False
    return Maze(rows, cols, H, V, ('W', ri), ('E', ro), rng=rng, **kw)


def parse_maze(path, **kw):
    lines = [l.rstrip('\n') for l in open(path, encoding='utf-8') if l.strip() and not l.startswith('#')]
    rows, cols = (len(lines) - 1) // 2, (max(map(len, lines)) - 1) // 4
    lines = [l.ljust(4 * cols + 1) for l in lines]
    H = [[False] * cols for _ in range(rows + 1)]
    V = [[False] * (cols + 1) for _ in range(rows)]
    ent = ext = None
    for r in range(rows + 1):
        for c in range(cols):
            seg = lines[2 * r][4 * c + 1: 4 * c + 4]
            side = 'N' if r == 0 else ('S' if r == rows else None)
            if 'S' in seg and side: ent = (side, c)
            elif 'E' in seg and side: ext = (side, c)
            else: H[r][c] = '-' in seg
    for r in range(rows):
        for c in range(cols + 1):
            ch = lines[2 * r + 1][4 * c]
            side = 'W' if c == 0 else ('E' if c == cols else None)
            if ch == 'S' and side: ent = (side, r)
            elif ch == 'E' and side: ext = (side, r)
            else: V[r][c] = ch == '|'
    assert ent and ext, '迷宫外圈上要用 S 标出入口、E 标出出口'
    return Maze(rows, cols, H, V, ent, ext, **kw)

# ---------------------------------------------------------------- 小车（物理 + 传感器）
class Car:
    TRACK = 100.0                  # 轮距
    BODY = (-60, 60, -55, 55)      # 车身矩形（相对车轴中心）：后、前、右、左
    VMAX = 750.0                   # PWM=1 的车速
    DEADBAND = 0.06
    TAU = 0.05                     # 电机时间常数
    SENSORS = {'L': (0, 45, 90), 'F': (55, 0, 0), 'R': (0, -45, -90)}   # x, y, 朝向(度)

    def __init__(self, maze, rng, mu=0.5, gyro_bias=0.15):
        self.m, self.rng = maze, rng
        self.x, self.y, self.th = maze.start_pose()
        self.gain = [1 + rng.uniform(-0.06, 0.06), 1 + rng.uniform(-0.06, 0.06)]   # 两个电机不一样快
        self.mot = [0.0, 0.0]; self.gnd = [0.0, 0.0]; self.enc = [0.0, 0.0]
        self.amax = mu * 9810.0
        self.gyro_bias = rng.uniform(-gyro_bias, gyro_bias)   # 校准后残余的零漂（度/秒）
        self.w = 0.0
        bx0, bx1, by0, by1 = self.BODY
        pts = []
        for i in range(10):
            f = i / 10
            pts += [(bx0 + f * (bx1 - bx0), by0), (bx1, by0 + f * (by1 - by0)),
                    (bx1 - f * (bx1 - bx0), by1), (bx0, by1 - f * (by1 - by0))]
        self.body_pts = np.array(pts)

    def step(self, dt, pwmL, pwmR):
        for i, p in enumerate((pwmL, pwmR)):
            mag = max(0.0, abs(p) - self.DEADBAND) / (1 - self.DEADBAND)
            tgt = math.copysign(mag, p) * self.VMAX * self.gain[i]
            self.mot[i] += (tgt - self.mot[i]) * dt / self.TAU
            dg = self.mot[i] - self.gnd[i]                       # 抓地力不够时轮子打滑
            lim = self.amax * dt
            self.gnd[i] += max(-lim, min(lim, dg))
            self.enc[i] += self.mot[i] * dt                      # 编码器量的是电机侧，打滑时会多算
        v = (self.gnd[0] + self.gnd[1]) / 2
        self.w = (self.gnd[1] - self.gnd[0]) / self.TRACK
        self.th += self.w * dt
        self.x += v * math.cos(self.th) * dt
        self.y += v * math.sin(self.th) * dt

    def tof(self, name):
        sx, sy, sa = self.SENSORS[name]
        c, s = math.cos(self.th), math.sin(self.th)
        ox, oy = self.x + sx * c - sy * s, self.y + sx * s + sy * c
        a0 = self.th + math.radians(sa)
        d = min(self.m.raycast(ox, oy, a0 + math.radians(k)) for k in (-12.5, -6.25, 0, 6.25, 12.5))
        if d > 1200: return -1.0                                 # 超量程
        if self.rng.random() < 0.003: return self.rng.uniform(30, 1200)   # 偶发离谱值
        return d + self.rng.gauss(0, 3 + 0.02 * d)

    def gyro(self):
        return math.degrees(self.w) + self.gyro_bias + self.rng.gauss(0, 0.1)

    def collided(self):
        c, s = math.cos(self.th), math.sin(self.th)
        P = self.body_pts
        W = np.stack([self.x + P[:, 0] * c - P[:, 1] * s, self.y + P[:, 0] * s + P[:, 1] * c], 1)
        A, B = self.m.A, self.m.B
        AB = B - A
        L2 = (AB ** 2).sum(1)
        t = np.clip(((W[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        proj = A[None] + t[..., None] * AB[None]
        if (((W[:, None, :] - proj) ** 2).sum(2) < (self.m.wh + 0.5) ** 2).any(): return True
        # 墙的端头戳进车身
        for P2 in (A, B):
            dx, dy = P2[:, 0] - self.x, P2[:, 1] - self.y
            lx, ly = dx * c + dy * s, -dx * s + dy * c
            bx0, bx1, by0, by1 = self.BODY
            if ((lx > bx0) & (lx < bx1) & (ly > by0) & (ly < by1)).any(): return True
        return False

# ---------------------------------------------------------------- 跑一次
GYRO_BIAS = 0.15

def run(maze, mode, seed=0, mu=0.5, params=None, path=None, tmax=180.0, record=True):
    rng = random.Random(seed)
    car = Car(maze, rng, mu, GYRO_BIAS)
    p = BrainParams(); BRAIN.brain_default_params(ctypes.byref(p))
    p.cell_mm = maze.cell
    for k, v in (params or {}).items(): setattr(p, k, v)
    if path is not None: BRAIN.brain_set_path(path.encode())
    BRAIN.brain_init(ctypes.byref(p), MODES[mode])
    sense, act = Sense(), Act()
    dt, t = 0.005, 0.0
    tof_next = {'L': 0.000, 'F': 0.011, 'R': 0.022}
    last = {'L': -1.0, 'F': -1.0, 'R': -1.0}
    traj, decisions = [], []
    ndec = 0; result = '超时'; pwm = (0.0, 0.0); step = 0
    while t < tmax:
        if step % 2 == 0:                       # 大脑 100 Hz
            fresh = 0
            for i, n in enumerate('LFR'):
                if t >= tof_next[n]:
                    last[n] = car.tof(n); tof_next[n] += 0.033; fresh |= 1 << i
            sense.t_ms = t * 1000; sense.dL, sense.dF, sense.dR = last['L'], last['F'], last['R']
            sense.gyro_z = car.gyro(); sense.encL, sense.encR = car.enc; sense.fresh = fresh
            BRAIN.brain_step(ctypes.byref(sense), ctypes.byref(act))
            pwm = (act.pwmL, act.pwmR)
            if act.ndec != ndec:
                ndec = act.ndec; decisions.append((car.x, car.y, act.last_decision.decode()))
            if act.state == 3 and not maze.escaped(car.x, car.y):
                result = '中途停车'; break
        car.step(dt, *pwm)
        t += dt; step += 1
        if record and step % 4 == 0: traj.append((t, car.x, car.y, car.th, *last.values()))
        if step % 4 == 0 and car.collided(): result = '撞墙'; break
        if maze.escaped(car.x, car.y): result = '完赛'; break
    buf = ctypes.create_string_buffer(300)
    n = BRAIN.brain_get_path(buf, 300)
    learned = buf.value.decode() if (n > 0 and mode != 'replay') else ''
    return dict(result=result, time=t, traj=traj, decisions=decisions, learned=learned, mode=mode)

def run_mode(maze, mode, seed, mu, params=None):
    """返回要展示的那一次（或几次）运行"""
    if mode in ('left', 'right'):
        return [run(maze, mode, seed, mu, params)]
    if mode == 'best':
        a, b = run(maze, 'left', seed, mu, params), run(maze, 'right', seed, mu, params)
        ok = [r for r in (a, b) if r['result'] == '完赛']
        return [min(ok, key=lambda r: r['time'])] if ok else [a]
    if mode == 'learn':
        a, b = run(maze, 'left', seed, mu), run(maze, 'right', seed, mu)
        first = min((r for r in (a, b) if r['result'] == '完赛'), key=lambda r: r['time'], default=a)
        second = run(maze, 'replay', seed + 1, mu, path=first['learned'])
        return [first, second]
    raise ValueError(mode)

# ---------------------------------------------------------------- 画图
def draw(maze, runs, png=None, animate=False):
    import matplotlib
    if png: matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    plt.rcParams['font.sans-serif'] = ['PingFang SC', 'Heiti SC', 'Microsoft YaHei', 'SimHei',
                                       'Noto Sans CJK SC', 'WenQuanYi Zen Hei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    n = len(runs)
    fig, axes = plt.subplots(1, n, figsize=(6.2 * n, 6.4), squeeze=False)
    names = {'left': '左手', 'right': '右手', 'replay': '记忆回放'}
    for ax, r in zip(axes[0], runs):
        for (x1, y1, x2, y2) in maze.panels:
            ax.plot([x1, x2], [y1, y2], color='#a0784a', lw=3.2, solid_capstyle='butt')
        tr = np.array(r['traj'])
        if len(tr):
            sc = ax.scatter(tr[:, 1], tr[:, 2], c=tr[:, 0], cmap='viridis', s=2)
        for (x, y, d) in r['decisions']:
            ax.annotate(d, (x, y), color='#c0392b', fontsize=11, fontweight='bold',
                        ha='center', va='center',
                        bbox=dict(boxstyle='circle,pad=0.15', fc='white', ec='#c0392b', lw=1))
        sx, sy, _ = maze.start_pose()
        ax.plot(sx, sy, 'o', color='#2e86de', ms=9)
        ax.set_aspect('equal'); ax.axis('off')
        title = f"{names[r['mode']]}：{r['result']}，{r['time']:.1f} 秒"
        if r['learned'] and r['mode'] != 'replay': title += f"\n学到的路线：{r['learned'][1:] or '（无路口）'}"
        ax.set_title(title, fontsize=12)
    fig.tight_layout()
    if png:
        fig.savefig(png, dpi=130, bbox_inches='tight'); print('已保存', png)
        return
    if animate and runs[-1]['traj']:
        r = runs[-1]; ax = axes[0][-1]; tr = np.array(r['traj'])
        body = Polygon(np.zeros((4, 2)), closed=True, fc='#e67e22', ec='k', zorder=5); ax.add_patch(body)
        rays = [ax.plot([], [], color='#e74c3c', lw=1, alpha=.7)[0] for _ in range(3)]
        from matplotlib.animation import FuncAnimation
        bx0, bx1, by0, by1 = Car.BODY
        corners = np.array([(bx0, by0), (bx1, by0), (bx1, by1), (bx0, by1)])
        def upd(i):
            _, x, y, th, dl, df, dr = tr[i]
            c, s = math.cos(th), math.sin(th)
            body.set_xy(np.c_[x + corners[:, 0] * c - corners[:, 1] * s, y + corners[:, 0] * s + corners[:, 1] * c])
            for ln, (k, d) in zip(rays, zip('LFR', (dl, df, dr))):
                sx_, sy_, sa = Car.SENSORS[k]
                ox, oy = x + sx_ * c - sy_ * s, y + sx_ * s + sy_ * c
                a = th + math.radians(sa); d = d if d > 0 else 300
                ln.set_data([ox, ox + d * math.cos(a)], [oy, oy + d * math.sin(a)])
            return [body, *rays]
        ani = FuncAnimation(fig, upd, frames=range(0, len(tr), 2), interval=20, blit=True, repeat=False)
        fig._ani = ani
    plt.show()

# ---------------------------------------------------------------- 批量测试
def batch(n, size, braid, mu, seed0, cell=300.0):
    rows, cols = size
    stats = {m: [] for m in ('left', 'right', 'best', 'replay')}
    fails = []
    for k in range(n):
        seed = seed0 + k
        mz = random_maze(rows, cols, braid, random.Random(seed), cell=cell)
        a, b = run(mz, 'left', seed, mu, record=False), run(mz, 'right', seed, mu, record=False)
        stats['left'].append(a); stats['right'].append(b)
        ok = [r for r in (a, b) if r['result'] == '完赛']
        best = min(ok, key=lambda r: r['time']) if ok else a
        stats['best'].append(best)
        rp = run(mz, 'replay', seed + 1, mu, path=best['learned'], record=False) if ok else dict(result='没学到', time=0)
        stats['replay'].append(rp)
        for m, r in (('left', a), ('right', b), ('replay', rp)):
            if r['result'] != '完赛': fails.append((seed, m, r['result']))
    print(f'\n{n} 个随机 {rows}x{cols} 迷宫（格距 {cell:.0f} mm，打通 {braid:.0%} 的墙），地面摩擦系数 {mu}，陀螺仪零漂 ±{GYRO_BIAS}°/s')
    print(f"{'模式':<8}{'完赛率':>8}{'用时中位数':>12}")
    names = {'left': '左手', 'right': '右手', 'best': '看图选手', 'replay': '记忆回放'}
    for m, rs in stats.items():
        ok = [r['time'] for r in rs if r['result'] == '完赛']
        print(f"{names[m]:<8}{len(ok) / n:>8.0%}{(statistics.median(ok) if ok else 0):>10.1f} 秒")
    if fails:
        print('\n失败样例（种子, 模式, 原因）：', fails[:12])

# ---------------------------------------------------------------- 入口
if __name__ == '__main__':
    ap = argparse.ArgumentParser(description='迷宫小车仿真器')
    ap.add_argument('--mode', default='left', choices=['left', 'right', 'best', 'learn'])
    ap.add_argument('--maze', help='ASCII 迷宫文件')
    ap.add_argument('--size', default='5x5', help='随机迷宫大小，行x列')
    ap.add_argument('--braid', type=float, default=0.1, help='额外打通的墙的比例（制造环路）')
    ap.add_argument('--cell', type=float, default=300, help='格子间距（毫米）')
    ap.add_argument('--mu', type=float, default=0.5, help='地面摩擦系数')
    ap.add_argument('--gyro-bias', type=float, default=0.15, help='陀螺仪残余零漂上限（度/秒）')
    ap.add_argument('--seed', type=int, default=1)
    ap.add_argument('--batch', type=int, default=0)
    ap.add_argument('--png')
    ap.add_argument('--no-anim', action='store_true')
    ap.add_argument('--race', action='store_true', help='已知赛道模式：不找岔路，第 14 个弯后停车（只用于 track_2026.txt）')
    a = ap.parse_args()
    rows, cols = map(int, a.size.lower().split('x'))
    GYRO_BIAS = a.gyro_bias
    if a.batch:
        batch(a.batch, (rows, cols), a.braid, a.mu, a.seed, a.cell); sys.exit()
    rng = random.Random(a.seed)
    mz = parse_maze(a.maze, cell=a.cell, rng=rng) if a.maze else random_maze(rows, cols, a.braid, rng, cell=a.cell)
    runs = run_mode(mz, a.mode, a.seed, a.mu, RACE if a.race else None)
    for r in runs:
        print(f"{r['mode']}: {r['result']}  {r['time']:.2f} 秒  决策: {''.join(d for *_, d in r['decisions'])}  学到: {r['learned']}")
    draw(mz, runs, png=a.png, animate=not a.no_anim)
