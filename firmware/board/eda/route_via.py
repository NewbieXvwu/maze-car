#!/usr/bin/env python3
"""PCB 以" plating 孔 + 走线"方式落地：每个模块针脚位置放一个镀通孔（via），
再按手焊图的 44 根线走铜。

为什么用 via 而不是器件焊盘：工程库封装的 pad 写不进钻孔（hole），
EasyEDA 4.1.97 下带洞 pad 的 build 会挂死并回滚；via 是原生镀通孔，
钻孔 + 双面铜环，正好是模块排针要插的孔。
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
DOC = "PCB1"
MARGIN = 100
ROW_MAX = 33
HOLE = 39.4          # 1.0 mm
RING = 65.3          # 1.66 mm 外径（1.0mm 孔 + 0.33mm 环；留出 2.54 间距下的走线净空）
W_SIGNAL = 12
W_POWER = 20   # 0.5mm：2.54mm 栅格下 25mil 会贴着相邻孔只剩 4.9mil 净空
POWER_NETS = {"VBAT", "5V", "3V3", "GND"}
CROSS_TOP_WIRES = {26, 5}


def cli(*args, timeout=240):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    if i < 0:
        raise RuntimeError(f"{args[:2]}: {p.stdout}\n{p.stderr}")
    return json.loads(p.stdout[i:])


def tx(x_grid):
    return round(x_grid * 100 + MARGIN, 1)


def ty(y_grid):
    return round((ROW_MAX - y_grid) * 100 + MARGIN, 1)


def load_html():
    """布线图数据：优先读仓库里的冻结副本 wiring_plan.json，没有才解析原始 HTML。"""
    frozen = __import__("pathlib").Path(__file__).resolve().parent / "wiring_plan.json"
    if frozen.exists():
        return json.loads(frozen.read_text(encoding="utf-8"))
    s = (ROOT / "迷宫小车主板布线.html").read_text(encoding="utf-8")
    i = s.find("const D = ") + len("const D = ")
    depth = 0
    for j in range(i, len(s)):
        if s[j] == "{":
            depth += 1
        elif s[j] == "}":
            depth -= 1
            if depth == 0:
                return json.loads(s[i:j + 1])


def main():
    plan = json.loads((EDA / "pcb_plan.json").read_text())
    D = load_html()

    r = cli("pcb", "clear", "--doc", DOC)
    print("clear:", r.get("ok"))

    n_via = 0
    for e in plan:
        for i, p in enumerate(e["pins"]):
            x, y = tx(p["x"]), ty(p["y"])
            net = p.get("net") or ""
            r = cli("pcb", "via", "--doc", DOC, "--x", str(x), "--y", str(y),
                    "--hole", str(HOLE), "--diameter", str(RING), "--net", net)
            if r.get("ok"):
                n_via += 1
            else:
                print("  via FAIL", e["designator"], i + 1, json.dumps(r.get("error"), ensure_ascii=False)[:120])
    print("vias:", n_via)

    n_tr = 0
    for w in D["wires"]:
        layer = 1 if w["id"] in CROSS_TOP_WIRES else 2
        width = W_POWER if w["net"] in POWER_NETS else W_SIGNAL
        pts = [(tx(p[0]), ty(p[1])) for p in w["path"]]
        for a, b in zip(pts, pts[1:]):
            if a == b:
                continue
            r = cli("pcb", "track", "--doc", DOC, "--layer", str(layer),
                    "--x1", str(a[0]), "--y1", str(a[1]),
                    "--x2", str(b[0]), "--y2", str(b[1]),
                    "--width", str(width), "--net", w["net"])
            if r.get("ok"):
                n_tr += 1
            else:
                print("  track FAIL", w["id"], w["net"], json.dumps(r.get("error"), ensure_ascii=False)[:120])
    print("tracks:", n_tr)
    cli("pcb", "save", "--doc", DOC)
    print("saved")


if __name__ == "__main__":
    main()
