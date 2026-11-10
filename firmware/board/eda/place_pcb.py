#!/usr/bin/env python3
"""把 12 个模块放到 PCB 上（坐标来自手焊图的洞洞板网格），再按手焊图的 44 根线铺铜走线。

坐标变换：HTML 网格 (x, y) 是 y 向下；PCB 是 y 向上，所以 Y = (MAXROW - y) * 100 + MARGIN。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
DOC = "PCB1"
MARGIN = 100          # mil
COL_MAX = 34          # 0..34
ROW_MAX = 33          # 0..33
W_SIGNAL = 12         # mil
W_POWER = 25          # mil
POWER_NETS = {"VBAT", "5V", "3V3", "GND"}
CROSS_TOP_WIRES = {26, 5}   # HTML 里"跨线"的压线那根，改走顶层，不需要过孔

# 手焊图里需要走线的 44 根（wire id -> 见 HTML），从 HTML 读取


def cli(*args, timeout=180):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    if i < 0:
        raise RuntimeError(f"{args[:2]}: {p.stdout}\n{p.stderr}")
    return json.loads(p.stdout[i:])


def tx(x):
    return round(x * 100 + MARGIN, 1)


def ty(y):
    return round((ROW_MAX - y) * 100 + MARGIN, 1)


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

    # 1) 清空 PCB（保留板框）
    r = cli("pcb", "clear", "--doc", DOC)
    print("clear:", r.get("ok"), json.dumps(r.get("result"), ensure_ascii=False)[:120])

    # 2) 放 12 个器件
    for e in plan:
        x, y = tx(e["x"] / 100), ty(e["y"] / 100)
        r = cli("pcb", "add-component", "--doc", DOC, "--library", e["footprintUuid"][:0] or
                "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e",
                "--uuid", e["deviceUuid"], "--x", str(x), "--y", str(y),
                "--designator", e["designator"], "--unique-id", e["uniqueId"],
                "--nets", json.dumps(e["nets"], ensure_ascii=False), "--layer", "1")
        ok = r.get("ok")
        print(f"place {e['designator']:4s} ({x:7.1f},{y:7.1f}) ok={ok}",
              "" if ok else json.dumps(r.get("error"), ensure_ascii=False)[:160])

    # 3) 走线
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
            if not r.get("ok"):
                print("  track FAIL", w["id"], w["net"], json.dumps(r.get("error"), ensure_ascii=False)[:140])
            else:
                n_tr += 1
    print("tracks:", n_tr)

    cli("pcb", "save", "--doc", DOC)
    print("saved")


if __name__ == "__main__":
    main()
