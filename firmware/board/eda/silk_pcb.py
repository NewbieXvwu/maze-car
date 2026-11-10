#!/usr/bin/env python3
"""给 PCB 加丝印：每个模块的名称 + 位号写在模块框上方，板边加标题。

板子上没有器件（模块排针孔是 via，不走库封装），丝印是唯一告诉装配者
"哪几个孔属于哪个模块"的线索。
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PROJECT = "maze-car"
DOC = "PCB1"
MARGIN = 100
ROW_MAX = 33
DESIGNATOR = {
    "ESP": "U1", "TB": "U2", "MPU": "U3", "HL": "U4", "HF": "U5", "HR": "U6",
    "ML": "J1", "MR": "J2", "DIP": "SW1", "BTN": "SW2", "XH": "BT1", "M5P": "U7",
}
SHORT = {
    "ESP": "ESP32-S3", "TB": "TB6612", "MPU": "MPU6050", "HL": "测距左",
    "HF": "测距前", "HR": "测距右", "ML": "电机左", "MR": "电机右",
    "DIP": "拨码开关", "BTN": "启动键", "XH": "电池", "M5P": "降压5V",
}


def cli(*args, timeout=120):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    if i < 0:
        raise RuntimeError(f"{args[:2]}: {p.stdout}\n{p.stderr}")
    return json.loads(p.stdout[i:])


def load_html():
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
    D = load_html()
    ok = fail = 0
    for c in D["components"]:
        cid = c["id"]
        if cid not in DESIGNATOR or not c.get("box"):
            continue
        x0, y0, x1, y1 = c["box"]
        cx = (x0 + x1) / 2 * 100 + MARGIN
        y_top = (ROW_MAX - y0) * 100 + MARGIN + 55
        text = f"{DESIGNATOR[cid]} {SHORT[cid]}"
        r = cli("pcb", "silk-add", "--doc", DOC, "--text", text,
                "--x", str(round(cx, 1)), "--y", str(round(y_top, 1)),
                "--font-size", "45", "--line-width", "6")
        if r.get("ok"):
            ok += 1
        else:
            fail += 1
            print(" silk FAIL", text, json.dumps(r.get("error"), ensure_ascii=False)[:150])
    print("silk labels:", ok, "fail:", fail)

    for text, x, y, size in [
        ("迷宫小车主板", 200, 60, 55),
        ("2层 1.0mm孔 2026-11", 1600, 60, 38),
        ("NewbieXvwu", 3000, 60, 38),
    ]:
        r = cli("pcb", "silk-add", "--doc", DOC, "--text", text, "--x", str(x),
                "--y", str(y), "--font-size", str(size), "--line-width", "6")
        print(" title:", text, r.get("ok"))
    cli("pcb", "save", "--doc", DOC)
    print("saved")


if __name__ == "__main__":
    main()
