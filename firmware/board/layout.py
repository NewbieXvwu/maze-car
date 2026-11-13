#!/usr/bin/env python3
"""
洞洞板布线图生成器（55 × 37 孔实板尺寸）
  python layout.py            自检（孔位冲突、模块重叠、每个网络是否连通、和 ../car/config.h 的引脚是否一致），
                              然后自动找走线路径，生成 board.html 和仓库根目录的《迷宫小车主板布线.html》
坐标：x = 列，y = 行，都从元件面左上角的孔开始数，0 起；车头朝上。页面上显示时 +1（从 1 数）。
改布局只改这个文件里的数据，然后重新运行。
"""
import json, os, re, sys
from collections import defaultdict

import route

DEFAULT_ROUTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'route_final.json')
HERE = os.path.dirname(os.path.abspath(__file__))
COLS, ROWS = 55, 37                       # 实板：55 × 37 孔，约 14.0 × 9.4 cm

# ---------------------------------------------------------------- 元件
def column(x, y0, names):
    return [(n, x, y0 + i) for i, n in enumerate(names) if n]

ESP_L = ['3V3', '3V3·2', 'RST', '4', '5', '6', '7', '15', '16', '17', '18', '8', '3', '46',
         '9', '10', '11', '12', '13', '14', '5Vin', 'GND·L']
ESP_R = ['GND·T', 'TX', 'RX', '1', '2', '42', '41', '40', '39', '38', '37', '36', '35', '0',
         '45', '48', '47', '21', '20', '19', 'GND·B1', 'GND·B2']
HDR = ['VIN', 'GND', 'SCL', 'SDA', 'GPIO1', 'XSHUT']
MOTOR = ['M2', 'VCC', 'C2', 'C1', 'GND', 'M1']   # 编码器板丝印顺序

# kind: socket = 插排母的模块；pins = 排针/元件；pads = 直接焊线的焊点；area = 只是一块区域
COMPONENTS = {
    'ESP': dict(label='ESP32-S3（YD 板）', kind='socket', box=(22.45, 2.9, 33.55, 28.1), side='in',
                pins=column(23, 6, ESP_L) + column(33, 6, ESP_R),
                note='两排 22 针排母，间距 10 孔。天线在上方，下面不走线'),
    'TB': dict(label='TB6612', kind='socket', box=(10.4, 8.45, 17.6, 16.55), side='in',
               pins=column(17, 9, ['PWMA', 'AIN2', 'AIN1', 'STBY', 'BIN1', 'BIN2', 'PWMB', 'GND·C']) +
                    column(11, 9, ['VM', 'VCC', 'GND·P', 'AO1', 'AO2', 'BO2', 'BO1', 'GND·P2']),
               note='两排 8 针排母，间距 6 孔。芯片朝上，PWMA 那一排靠 ESP32、PWMA 在上'),
    'MPU': dict(label='MPU6050', kind='socket', box=(37.45, 8.4, 44.1, 16.75), side='r',
                pins=column(38, 9, ['VCC', 'GND', 'SCL', 'SDA', 'XDA', 'XCL', 'AD0', 'INT']),
                note='一排 8 针排母，模块板身朝右'),
    'HL': dict(label='左测距', kind='pins', box=(40.5, 18.5, 41.5, 24.5), side='l', pins=column(41, 19, HDR),
               note='1×6 直排针，接左侧 VL53L0X'),
    'HF': dict(label='前测距', kind='pins', box=(43.5, 18.5, 44.5, 24.5), side='l', pins=column(44, 19, HDR),
               note='1×6 直排针，接前方 VL53L0X'),
    'HR': dict(label='右测距', kind='pins', box=(46.5, 18.5, 47.5, 24.5), side='l', pins=column(47, 19, HDR),
               note='1×6 直排针，接右侧 VL53L0X'),
    'ML': dict(label='左电机线', kind='pads', box=(2.5, 16.5, 3.5, 22.5), side='l', lbl='above', pins=column(3, 17, MOTOR),
               note='左电机 6 根线直接焊进来，顺序同编码器板丝印'),
    'MR': dict(label='右电机线', kind='pads', box=(5.5, 20.5, 6.5, 26.5), side='r', lbl='below', pins=column(6, 21, MOTOR),
               note='右电机 6 根线直接焊进来'),
    'DIP': dict(label='拨码开关', kind='pins', box=(49.4, 27.4, 52.6, 31.6), side='r',
                pins=[('1', 50, 28), ('2', 51, 28), ("1'", 50, 31), ("2'", 51, 31)],
                note='2 位拨码：拨到 ON 时上下两脚接通'),
    'BTN': dict(label='启动键', kind='pins', box=(48.5, 1.5, 53.5, 4.5), side='r',
                pins=[('A', 49, 2), ('B', 52, 2), ('C', 49, 4), ('D', 52, 4)],
                note='6×6 轻触开关，四只脚稍微掰开对孔。只用对角两只脚（A、D），可选：板载 BOOT 键也能发车'),
    'XH': dict(label='电池', kind='pins', box=(0.25, 29.0, 2.1, 32.0), side='r',
               pins=[('+', 1, 30), ('−', 1, 31)], note='XH2.54 两针插座，上 + 下 −，插头别插反'),
    'M5P': dict(label='降压', kind='pads', box=None, side='r',
                pins=[('IN+', 4, 30), ('IN−', 4, 31), ('OUT+', 17, 30), ('OUT−', 17, 31)],
                note='四个焊盘给模块飞线用：先焊好四根短线再贴模块；IN 侧朝电池，OUT 侧朝 ESP，接反会烧模块'),
    'M5': dict(label='Mini560 贴这里', kind='area', box=(4.5, 29.5, 16.5, 36.5), side='in', pins=[], hard=True,
               note='模块不插孔，用双面胶或热熔胶平贴在这个框里；贴之前先把四根线焊到模块的 IN+ / IN− / OUT+ / OUT− 上，贴上后手伸不进去'),
}

# 模块内部本来就连通的脚（自检连通性时算作已连）
INTERNAL = [('ESP.GND·L', 'ESP.GND·T'), ('ESP.GND·L', 'ESP.GND·B1'), ('ESP.GND·L', 'ESP.GND·B2'),
            ('ESP.3V3', 'ESP.3V3·2'), ('TB.GND·P', 'TB.GND·C'), ('TB.GND·P', 'TB.GND·P2'),
            ('M5P.IN−', 'M5P.OUT−')]

# ---------------------------------------------------------------- 网络（每个网络应该连通的脚）
NETS = {
    'VBAT': ['XH.+', 'M5P.IN+', 'TB.VM'],
    '5V': ['M5P.OUT+', 'ESP.5Vin'],
    '3V3': ['ESP.3V3', 'ESP.3V3·2', 'TB.VCC', 'MPU.VCC', 'HL.VIN', 'HF.VIN', 'HR.VIN', 'ML.VCC', 'MR.VCC'],
    'GND': ['ESP.GND·L', 'ESP.GND·T', 'ESP.GND·B1', 'ESP.GND·B2', 'TB.GND·P', 'TB.GND·C', 'MPU.GND',
            'HL.GND', 'HF.GND', 'HR.GND', 'ML.GND', 'MR.GND', "DIP.1'", "DIP.2'", 'BTN.D', 'XH.−',
            'M5P.IN−', 'M5P.OUT−'],
    'SCL': ['ESP.42', 'MPU.SCL', 'HL.SCL', 'HF.SCL', 'HR.SCL'],
    'SDA': ['ESP.41', 'MPU.SDA', 'HL.SDA', 'HF.SDA', 'HR.SDA'],
    'XSHUT_L': ['ESP.40', 'HL.XSHUT'], 'XSHUT_F': ['ESP.39', 'HF.XSHUT'], 'XSHUT_R': ['ESP.38', 'HR.XSHUT'],
    'PWMA': ['ESP.4', 'TB.PWMA'], 'AIN2': ['ESP.5', 'TB.AIN2'], 'AIN1': ['ESP.6', 'TB.AIN1'],
    'STBY': ['ESP.7', 'TB.STBY'], 'BIN1': ['ESP.15', 'TB.BIN1'], 'BIN2': ['ESP.16', 'TB.BIN2'],
    'PWMB': ['ESP.17', 'TB.PWMB'],
    'AO1': ['TB.AO1', 'ML.M1'], 'AO2': ['TB.AO2', 'ML.M2'], 'BO1': ['TB.BO1', 'MR.M1'], 'BO2': ['TB.BO2', 'MR.M2'],
    'ENC_L_C1': ['ESP.10', 'ML.C1'], 'ENC_L_C2': ['ESP.9', 'ML.C2'],
    'ENC_R_C1': ['ESP.14', 'MR.C1'], 'ENC_R_C2': ['ESP.13', 'MR.C2'],
    'DIP1': ['ESP.47', 'DIP.1'], 'DIP2': ['ESP.21', 'DIP.2'], 'BTN': ['ESP.2', 'BTN.A'],
}
GROUP = {'VBAT': 'vbat', '5V': 'v5', '3V3': 'v33', 'GND': 'gnd', 'SCL': 'scl', 'SDA': 'sda',
         'XSHUT_L': 'xshut', 'XSHUT_F': 'xshut', 'XSHUT_R': 'xshut',
         'PWMA': 'drv', 'AIN2': 'drv', 'AIN1': 'drv', 'STBY': 'drv', 'BIN1': 'drv', 'BIN2': 'drv', 'PWMB': 'drv',
         'AO1': 'mot', 'AO2': 'mot', 'BO1': 'mot', 'BO2': 'mot',
         'ENC_L_C1': 'enc', 'ENC_L_C2': 'enc', 'ENC_R_C1': 'enc', 'ENC_R_C2': 'enc',
         'DIP1': 'sw', 'DIP2': 'sw', 'BTN': 'sw'}

# ---------------------------------------------------------------- 焊接步骤和每根线
STEPS = [
    dict(title='插座和排针', test='插上 ESP32，USB 线插 COM 口，串口敲 ?，能看到命令列表',
         desc='只焊插座，不接线。先按图把 ESP32 的两条 22 针排母对好孔焊上（第 23、33 列，第 6 行起），'
              '再焊 TB6612 两条 8 针排母、MPU6050 一条 8 针排母、三个 1×6 直排针、拨码开关、电池插座、启动键（可选）。'
              '排母先插在模块上，连模块一起放到板子上对孔焊，孔距自然对得上。'),
    dict(title='陀螺仪', test='i 能扫到 0x68；g 手转车 90°，读数约 +90',
         desc='4 根线。陀螺仪的 SCL、SDA 和 ESP32 在同一行，中间没有别的焊点，可以用剪下的排针脚在焊接面直接拉过去。'),
    dict(title='三个测距插座', test='插上三个 VL53L0X，i 扫到 0x30 0x31 0x32；d 读数随手挡变化',
         desc='15 根线：电源、地、SCL、SDA 各串一遍三个插座，再加三根 XSHUT。'
              '插座的脚序和 VL53L0X 模块一样（VIN GND SCL SDA GPIO1 XSHUT），用 6 根一排的杜邦线直插。'),
    dict(title='拨码和启动键', test='s 显示的拨码、按键状态和实际一致',
         desc='拨码 4 根 + 启动键 2 根。启动键可以不装——发车和急停用 ESP32 板上的 BOOT 键，'
              '遇到这种情况在页面工具栏勾上「没装启动键」，那两根会变成灰虚线、不计入统计。'),
    dict(title='电机驱动控制线', test='万用表通断档逐根量一遍：ESP32 的脚和 TB6612 的脚应该通，相邻两根不通',
         desc='9 根线。7 根控制线都在同一行、中间是空孔，最好焊。'),
    dict(title='电机和编码器', test='e：手往前滚轮子，读数为正、一圈约 +132 mm',
         desc='先把两根电机线的 6 个线头按丝印顺序焊进来（黑线 VCC、蓝线 GND，别按颜色猜），再接 12 根线。'
              'M1、M2 接反只是转向反，固件里改正负号就行。'),
    dict(title='电源', test='接电池前先量：VBAT 和 GND 之间不通。插电池开开关，量 ESP32 的 5Vin 约 5.0 V；再拔 USB 跑 m',
         desc='6 根线，再加降压模块自己的 4 根短线（IN+、IN−、OUT+、OUT− 焊到旁边四个点）。'
              '电池线最粗、电流最大，用整根线，别用剪短的杜邦线头。'),
]

WIRES = [  # (步骤, 网络, 一端, 另一端)
    (2, '3V3', 'ESP.3V3·2', 'MPU.VCC'), (2, 'GND', 'ESP.GND·T', 'MPU.GND'),
    (2, 'SCL', 'ESP.42', 'MPU.SCL'), (2, 'SDA', 'ESP.41', 'MPU.SDA'),

    (3, '3V3', 'MPU.VCC', 'HL.VIN'), (3, '3V3', 'HL.VIN', 'HF.VIN'), (3, '3V3', 'HF.VIN', 'HR.VIN'),
    (3, 'GND', 'ESP.GND·B1', 'HL.GND'), (3, 'GND', 'HL.GND', 'HF.GND'), (3, 'GND', 'HF.GND', 'HR.GND'),
    (3, 'SCL', 'MPU.SCL', 'HL.SCL'), (3, 'SCL', 'HL.SCL', 'HF.SCL'), (3, 'SCL', 'HF.SCL', 'HR.SCL'),
    (3, 'SDA', 'MPU.SDA', 'HL.SDA'), (3, 'SDA', 'HL.SDA', 'HF.SDA'), (3, 'SDA', 'HF.SDA', 'HR.SDA'),
    (3, 'XSHUT_L', 'ESP.40', 'HL.XSHUT'), (3, 'XSHUT_F', 'ESP.39', 'HF.XSHUT'), (3, 'XSHUT_R', 'ESP.38', 'HR.XSHUT'),

    (4, 'DIP1', 'ESP.47', 'DIP.1'), (4, 'DIP2', 'ESP.21', 'DIP.2'),
    (4, 'GND', 'ESP.GND·B2', "DIP.1'"), (4, 'GND', "DIP.1'", "DIP.2'"),
    (4, 'BTN', 'ESP.2', 'BTN.A'), (4, 'GND', 'MPU.GND', 'BTN.D'),

    (5, 'PWMA', 'ESP.4', 'TB.PWMA'), (5, 'AIN2', 'ESP.5', 'TB.AIN2'), (5, 'AIN1', 'ESP.6', 'TB.AIN1'),
    (5, 'STBY', 'ESP.7', 'TB.STBY'), (5, 'BIN1', 'ESP.15', 'TB.BIN1'), (5, 'BIN2', 'ESP.16', 'TB.BIN2'),
    (5, 'PWMB', 'ESP.17', 'TB.PWMB'), (5, '3V3', 'ESP.3V3', 'TB.VCC'), (5, 'GND', 'ESP.GND·L', 'TB.GND·C'),

    (6, 'AO1', 'TB.AO1', 'ML.M1'), (6, 'AO2', 'TB.AO2', 'ML.M2'), (6, 'BO2', 'TB.BO2', 'MR.M2'), (6, 'BO1', 'TB.BO1', 'MR.M1'),
    (6, 'ENC_L_C2', 'ML.C2', 'ESP.9'), (6, 'ENC_L_C1', 'ML.C1', 'ESP.10'),
    (6, 'ENC_R_C2', 'MR.C2', 'ESP.13'), (6, 'ENC_R_C1', 'MR.C1', 'ESP.14'),
    (6, '3V3', 'TB.VCC', 'ML.VCC'), (6, '3V3', 'ML.VCC', 'MR.VCC'),
    (6, 'GND', 'ESP.GND·L', 'MR.GND'), (6, 'GND', 'MR.GND', 'ML.GND'),

    (7, 'VBAT', 'XH.+', 'M5P.IN+'), (7, 'VBAT', 'M5P.IN+', 'TB.VM'), (7, '5V', 'M5P.OUT+', 'ESP.5Vin'),
    (7, 'GND', 'XH.−', 'M5P.IN−'), (7, 'GND', 'XH.−', 'TB.GND·P'), (7, 'GND', 'M5P.OUT−', 'ESP.GND·L'),
]

# config.h 里的宏 → 布局里对应的网络（自检两边的 GPIO 是否一致）
CONFIG_MAP = {'PIN_SDA': 'SDA', 'PIN_SCL': 'SCL', 'PIN_XSHUT_L': 'XSHUT_L', 'PIN_XSHUT_F': 'XSHUT_F',
              'PIN_XSHUT_R': 'XSHUT_R', 'PIN_PWMA': 'PWMA', 'PIN_AIN1': 'AIN1', 'PIN_AIN2': 'AIN2',
              'PIN_STBY': 'STBY', 'PIN_BIN1': 'BIN1', 'PIN_BIN2': 'BIN2', 'PIN_PWMB': 'PWMB',
              'PIN_ENC_LA': 'ENC_L_C1', 'PIN_ENC_LB': 'ENC_L_C2', 'PIN_ENC_RA': 'ENC_R_C1',
              'PIN_ENC_RB': 'ENC_R_C2', 'PIN_DIP1': 'DIP1', 'PIN_DIP2': 'DIP2', 'PIN_BTN': 'BTN'}
FORBIDDEN_GPIO = {'0', '3', '45', '46', '19', '20', '48'}   # 启动配置脚、USB、板载 RGB 灯


# ---------------------------------------------------------------- 自检
def check():
    errs = []
    pins, holes = {}, {}
    for c, d in COMPONENTS.items():
        for n, x, y in d['pins']:
            ref = f'{c}.{n}'
            pins[ref] = (x, y)
            if not (0 <= x < COLS and 0 <= y < ROWS): errs.append(f'{ref} 在板子外面 ({x},{y})')
            if (x, y) in holes: errs.append(f'{ref} 和 {holes[(x, y)]} 用了同一个孔 ({x},{y})')
            holes[(x, y)] = ref
    boxes = {c: d['box'] for c, d in COMPONENTS.items() if d['box']}
    names = list(boxes)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            A, B = boxes[a], boxes[b]
            if A[0] < B[2] and B[0] < A[2] and A[1] < B[3] and B[1] < A[3]:
                errs.append(f'{a} 和 {b} 的外框重叠')
    for ref, (x, y) in pins.items():
        for c, (x0, y0, x1, y1) in boxes.items():
            if c != ref.split('.')[0] and x0 < x < x1 and y0 < y < y1:
                errs.append(f'{ref} 被 {c} 盖住了')
    owner = {}
    for net, refs in NETS.items():
        for r in refs:
            if r not in pins: errs.append(f'网络 {net} 里的 {r} 不存在')
            if r in owner: errs.append(f'{r} 同时在 {owner[r]} 和 {net} 里')
            owner[r] = net
    for i, (step, net, a, b) in enumerate(WIRES):
        for r in (a, b):
            if r not in pins: errs.append(f'第 {i} 根线的 {r} 不存在')
            elif owner.get(r) != net: errs.append(f'第 {i} 根线标的是 {net}，但 {r} 属于 {owner.get(r)}')
    for net, refs in NETS.items():                     # 连通性：线 + 模块内部连接
        parent = {r: r for r in refs}
        def find(r):
            while parent[r] != r: parent[r] = parent[parent[r]]; r = parent[r]
            return r
        edges = [(a, b) for _, n, a, b in WIRES if n == net] + [e for e in INTERNAL if e[0] in parent and e[1] in parent]
        for a, b in edges:
            if a in parent and b in parent: parent[find(a)] = find(b)
        roots = {find(r) for r in refs}
        if len(roots) > 1:
            groups = {}
            for r in refs: groups.setdefault(find(r), []).append(r)
            errs.append(f'网络 {net} 没连通：' + ' | '.join(', '.join(g) for g in groups.values()))
    for net, refs in NETS.items():
        for r in refs:
            if r.startswith('ESP.') and r[4:] in FORBIDDEN_GPIO: errs.append(f'{net} 用了不该用的 GPIO{r[4:]}')
    cfg_path = os.path.join(HERE, '..', 'car', 'config.h')
    cfg = dict(re.findall(r'#define\s+(PIN_\w+)\s+(\d+)', open(cfg_path, encoding='utf-8').read()))
    for macro, net in CONFIG_MAP.items():
        gpio = [r[4:] for r in NETS[net] if r.startswith('ESP.')]
        if cfg.get(macro) != gpio[0]:
            errs.append(f'config.h 的 {macro} = {cfg.get(macro)}，布局里 {net} 接的是 GPIO{gpio[0]}')
    return errs, pins, owner


# ---------------------------------------------------------------- 拼连续总线
def chains():
    """把 WIRES 的逐段连接按网络串成尽量长的链：一棵线上的中间焊点就是 stops。"""
    by_step = {}
    for step, net, a, b in WIRES:
        by_step.setdefault(net, []).append((step, a, b))
    out = []
    def mk(net, path):
        return dict(net=net, step=min(stepof[(a, b)] for a, b in zip(path, path[1:])), stops=path)
    for net, edges in by_step.items():
        adj, stepof = defaultdict(list), {}
        for step, a, b in edges:
            adj[a].append(b); adj[b].append(a)
            stepof[(a, b)] = step; stepof[(b, a)] = step
        used = set()
        def take(start):
            path, cur = [start], start
            while True:
                nxt = [n for n in adj[cur] if (cur, n) not in used]
                if not nxt: break
                used.add((cur, nxt[0])); used.add((nxt[0], cur))
                cur = nxt[0]; path.append(cur)
            return path
        for start in [n for n in adj if len(adj[n]) == 1]:
            if any((start, n) not in used for n in adj[start]):
                out.append(mk(net, take(start)))
        for start in list(adj):
            while any((start, n) not in used for n in adj[start]):
                out.append(mk(net, take(start)))
    return out


# ---------------------------------------------------------------- 输出
def build(pins, owner):
    def pin_label(ref):
        c, n = ref.split('.', 1)
        n = n.split('·')[0]
        return ('IO' + n) if (c == 'ESP' and n.isdigit()) else n
    short = lambda ref: 'ESP32' if ref.startswith('ESP.') else COMPONENTS[ref.split('.')[0]]['label']

    comps = []
    for c, d in COMPONENTS.items():
        comps.append(dict(id=c, label=d['label'], kind=d['kind'], box=d['box'], side=d['side'], note=d['note'],
                          lbl=d.get('lbl', 'above'),
                          pins=[dict(ref=f'{c}.{n}', label=pin_label(f'{c}.{n}'), x=x, y=y, net=owner.get(f'{c}.{n}'))
                                for n, x, y in d['pins']]))
    wires = []
    for i, ch in enumerate(chains()):
        wires.append(dict(id=i, step=ch['step'], net=ch['net'], group=GROUP[ch['net']],
                          a=ch['stops'][0], b=ch['stops'][-1],
                          al=f"{short(ch['stops'][0])} {pin_label(ch['stops'][0])}",
                          bl=f"{short(ch['stops'][-1])} {pin_label(ch['stops'][-1])}",
                          labels=[f"{short(r)} {pin_label(r)}" for r in ch['stops']],
                          stoprefs=ch['stops'], stops=[pins[r] for r in ch['stops']],
                          pa=pins[ch['stops'][0]], pb=pins[ch['stops'][-1]]))
    hard, soft = route.keepouts(COMPONENTS)
    hard.append((22.45, 2.9, 33.55, 5.4))          # ESP32 天线区：下面不走线
    fixed = os.environ.get('ROUTE_JSON') or (DEFAULT_ROUTE if os.path.exists(DEFAULT_ROUTE) else None)
    xs = None
    if fixed:
        saved = json.load(open(fixed, encoding='utf-8'))
        byid = {w['id']: w for w in saved['wires']}
        bad = []
        for w in wires:
            s = byid.get(w['id'])
            if not s:
                bad.append((w['id'], '缺这根线'))
            elif s.get('stops') and [(round(p[0],3), round(p[1],3)) for p in s['stops']] != [(round(p[0],3), round(p[1],3)) for p in w['stops']]:
                bad.append((w['id'], '焊点变了'))
            else:
                w['path'] = [tuple(p) for p in s['path']]
                w['length'] = s.get('len') or route.length_mm(w['path'])
        if bad:
            print(f'  ! 固定走线 {os.path.basename(fixed)} 与当前网络不匹配 {bad[:3]}，改为重新布线', flush=True)
            for w in wires:
                w.pop('path', None)
                w.pop('length', None)
        else:
            print(f'  用固定走线 {os.path.basename(fixed)}（{len(wires)} 根）', flush=True)
            xs = route.crossings(wires)
    passes = int(os.environ.get('PASSES', '60'))
    route.CROSS = float(os.environ.get('CROSS', '300'))
    route.SOFT = float(os.environ.get('SOFT', '40'))
    if xs is None:
        xs = route.route_best(wires, COLS, ROWS, pins, hard, soft, passes=passes, seed=7,
                              log=lambda m: print(m, flush=True))
    if xs is None:
        raise SystemExit('走线找不到通路，检查禁布区或缩小元件')

    def cid(i):
        s, i = '', i + 1
        while i:
            i, r = divmod(i - 1, 26)
            s = chr(65 + r) + s
        return s
    per = defaultdict(list)
    for i, (k, a, b) in enumerate(xs):
        per[a].append(cid(i)); per[b].append(cid(i))
    for w in wires:
        w['crossings'] = per.get(w['id'], [])
    data = dict(cols=COLS, rows=ROWS, components=comps, wires=wires, steps=STEPS,
                nets=[dict(name=n, group=GROUP[n], pins=len(r)) for n, r in NETS.items()],
                crossings=[dict(id=cid(i), p=[k[0] / 2, k[1] / 2], over=a, under=b)
                           for i, (k, a, b) in enumerate(xs)],
                stats=dict(cross=len(xs), overlap=0,
                           total=sum(w['length'] for w in wires)))
    return data


if __name__ == '__main__':
    errs, pins, owner = check()
    if errs:
        print('布局有问题：'); [print('  -', e) for e in errs]; sys.exit(1)
    data = build(pins, owner)
    tpl = open(os.path.join(HERE, 'routed_template.html'), encoding='utf-8').read()
    out = tpl.replace('/*BOARD_DATA*/null', json.dumps(data, ensure_ascii=False))
    for path in (os.path.join(HERE, 'board.html'),
                 os.path.join(HERE, '..', '..', '迷宫小车主板布线.html')):
        open(path, 'w', encoding='utf-8').write(out)
    print(f'自检通过：{len(COMPONENTS)} 个元件、{sum(1 for d in COMPONENTS.values() for _ in d["pins"])} 个焊点、'
          f'{len(NETS)} 个网络、{len(data["wires"])} 根线（{sum(1 for w in data["wires"] if len(w["stops"]) > 2)} 根连续总线）、'
          f'异网交叉 {data["stats"]["cross"]} 处，中心线总长 {data["stats"]["total"] / 1000:.2f} m')
    print('各步：' + ' '.join(f"{i + 1}:{sum(1 for w in WIRES if w[0] == i + 1)}段" for i in range(len(STEPS))))
    print('已生成 board.html 和 迷宫小车主板布线.html')
