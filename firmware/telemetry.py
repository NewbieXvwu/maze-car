#!/usr/bin/env python3
"""
电脑端遥测：电脑连上车的 WiFi 热点（maze-car，密码见 car/secrets.h，没建就是 config.h 里的默认密码）后运行
  python telemetry.py
- 屏幕上实时显示三个测距、里程、状态和最近一次决策
- 每次发车自动存一个 runs/年月日_时分秒.csv，可以用 maze-sim/replay_log.py 在电脑上一字不差地回放
- 直接打字回车 = 给车发命令，和串口一样：go 发车、x 急停、p cruise_mm_s 450 改参数、save 存参数……
只用 Python 标准库，不用装任何东西。
"""
import os, socket, sys, threading, time

CAR = ('192.168.4.1', 4211)          # 车收命令的地址
COLS = 't_ms,dL,dF,dR,fresh,gyro_z,encL,encR,pwmL,pwmR,state,ndec,dec'

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
sock.bind(('', 4210))


def sender():
    for line in sys.stdin:
        if line.strip():
            sock.sendto(line.strip().encode(), CAR)


threading.Thread(target=sender, daemon=True).start()
os.makedirs('runs', exist_ok=True)
f, last_print = None, 0.0
print('等车的数据……（车开机后，电脑连 WiFi "maze-car"；打字回车 = 发命令）')
try:
    while True:
        data, _ = sock.recvfrom(4096)
        for line in data.decode('utf-8', 'replace').splitlines():
            if line.startswith('H,'):                       # 一次发车的开头：带着这次的全部参数
                if f: f.close()
                name = time.strftime('runs/%Y%m%d_%H%M%S.csv')
                f = open(name, 'w', encoding='utf-8')
                f.write('#' + line[2:] + '\n' + COLS + '\n')
                print('\n新的一次运行 →', name)
            elif line.startswith('D,'):                     # 每 10 ms 一行
                if f: f.write(line[2:] + '\n')
                if time.time() - last_print > 0.2:
                    last_print = time.time()
                    p = line.split(',')
                    print(f"\r {float(p[1]) / 1000:6.2f}s  左{p[2]:>5} 前{p[3]:>5} 右{p[4]:>5}  "
                          f"里程{(float(p[7]) + float(p[8])) / 2:7.0f}mm  状态{p[11]}  决策{p[12]}{p[13]}   ",
                          end='', flush=True)
            elif line:                                      # 车发来的文字（命令回复、停车原因）
                print('\n' + line, flush=True)
                if f and line.startswith('停车'): f.flush()
except KeyboardInterrupt:
    if f: f.close()
