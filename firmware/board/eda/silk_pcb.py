#!/usr/bin/env python3
"""给 PCB 加丝印：每个模块的名称写在位号旁边，板边加标题。

为什么用英文：中文字形在 EasyEDA 里是 **G36 填充多边形**，实测笔画只有 0.075mm，
低于嘉立创 0.15mm 的丝印线宽下限，成品板上会糊；英文/数字走 0.1524mm 光圈的线条字，稳妥。
中文说明留在 docs/PCB下单与装配.md 里。

位置规则：名称紧跟在位号（封装自带的 designator）右边，同一行；BT1/U4/U5/U6 右边不够宽，
改写在位号正上方。位号本身也在这里统一改成 70 mil（手工改过不算数，重跑会丢）。落地后回读 bbox 对账，压字/出板直接报错。

用法:
  python3 silk_pcb.py --dry-run   只算位置并自检
  python3 silk_pcb.py             删掉旧文字后重新落地
"""
import json
import re
import subprocess
import sys

DOC = "PCB1"
PROJECT = "maze-car"
FONT = 70                  # 实测墨迹高 ≈ 0.0145×字号 ≈ 1.01mm（嘉立创 字高下限 1.0mm）
STROKE = 7                 # mil → 0.1778mm 光圈（嘉立创 下限 0.15mm）
GAP = 40                   # 名称离位号右边缘的距离
CHAR_W = 0.60              # 字宽 / 字号（英文实测）

# 模块名（位号→文字）；U7 的右移是因为 1 脚标记占了紧邻位号的位置
NAMES = {
    "U1": "ESP32-S3", "U2": "TB6612", "U3": "MPU6050",
    "U4": "TOF L", "U5": "TOF F", "U6": "TOF R",
    "J1": "MOTOR L", "J2": "MOTOR R", "SW1": "DIP SW", "SW2": "START",
    "BT1": "BAT", "U7": "5V REG",
}
SHIFT = {"U7": 150}        # U7 右移给 1 脚标记让位
ABOVE = {"BT1", "U4", "U5", "U6"}   # 写在位号正上方：这四个右边不够宽，会串到隔壁
ABOVE_GAP = 20             # 名称与位号的竖直间距（mil）
DY = {"J1": 12, "J2": 12}  # 这两个右边就是 1 脚标记，名称抬高一点避免压到

# 板边标题：(文字, x, 锚点y, 字号)
TITLES = [
    ("maze-car PCB", 200, 110, 70),
    ("2L 1.0mm hole 2026-11", 1600, 100, 70),
    ("NewbieXvwu", 3000, 100, 70),
]
BOARD_W, BOARD_H = 3600, 3500
EDGE = 30


def sh(args):
    r = subprocess.run(["easyeda"] + args, capture_output=True, text=True)
    return r.stdout


def load(out, what):
    i = out.find("{")
    if i < 0:
        raise SystemExit(f"{what} 没有 JSON 返回: {out[-300:]}")
    return json.JSONDecoder().raw_decode(out[i:])[0]


def silk_texts():
    return load(sh(["call", "pcb.silk.list", "--doc", DOC, "--project", PROJECT,
                    "--payload", '{"includeAttributes":true}']), "silk.list")["result"]["texts"]


def box_of(text, x, y, size):
    w = len(text) * size * CHAR_W
    return (x, y - size, x + w, y)      # 锚点=左上角


def overlap(a, b):
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def main():
    dry = "--dry-run" in sys.argv
    texts = silk_texts()

    # 位号是封装自带的属性文字，默认 45mil/6mil——先统一改成 70/7（跟名称同号）。
    # 这一步必须写在脚本里：手工在编辑器里改过一次，重跑会丢。
    des_texts = [t for t in texts if t.get("key") == "Designator"]
    stale = [t for t in des_texts
             if t.get("fontSize") != FONT or t.get("lineWidth") != STROKE]
    if stale and not dry:
        code = "".join('await eda.pcb_PrimitiveString.modify("%s",{fontSize:%d,lineWidth:%d});'
                       % (t["primitiveId"], FONT, STROKE) for t in stale)
        sh(["debug", "exec", "--code", code])
        print(f"位号字号 {len(stale)} 个改成 {FONT}/{STROKE}")
        texts = silk_texts()
    elif stale:
        print(f"（dry-run）{len(stale)} 个位号会改成 {FONT}/{STROKE}")
        for t in stale:                       # 估算新 bbox，好让下面的自检按新尺寸算
            b = t["bbox"]
            b["maxX"] = b["minX"] + len(t["text"]) * FONT * CHAR_W
            b["maxY"] = b["minY"] + FONT
    designators = {t["text"]: t for t in texts
                   if t.get("componentId") and t["bbox"]["maxX"] > t["bbox"]["minX"]}
    missing = [d for d in NAMES if d not in designators]
    if missing:
        raise SystemExit("板上没有这些位号: " + ", ".join(missing)
                         + "\n→ 先跑 place_outline.py 把 12 个模块框放上去；"
                           "pcb clear 会把它们删掉。")
    holes = load(sh(["pcb", "via-list", "--doc", DOC, "--project", PROJECT]), "via.list")
    holes = [(v["x"], v["y"], v.get("diameter", 66) / 2) for v in holes["result"]["vias"]]

    plans = []
    for des, name in NAMES.items():
        d = designators[des]["bbox"]
        if des in ABOVE:
            x, y = d["minX"], d["maxY"] + ABOVE_GAP + FONT
        else:
            x, y = d["maxX"] + GAP + SHIFT.get(des, 0), d["maxY"] + DY.get(des, 0)
        plans.append({"des": des, "text": name, "x": x, "y": y, "size": FONT})
    for text, x, y, size in TITLES:
        plans.append({"des": "-", "text": text, "x": x, "y": y, "size": size})

    problems = []
    for i, p in enumerate(plans):
        b = box_of(p["text"], p["x"], p["y"], p["size"])
        p["box"] = b
        if b[0] < EDGE or b[1] < EDGE or b[2] > BOARD_W - EDGE or b[3] > BOARD_H - EDGE:
            problems.append(f'{p["text"]}: 出板 {tuple(round(v) for v in b)}')
        for des, t in designators.items():
            if des == p["des"]:
                continue
            db = t["bbox"]
            if overlap(b, (db["minX"], db["minY"], db["maxX"], db["maxY"])):
                problems.append(f'{p["text"]}: 压位号 {des}')
        for hx, hy, hr in holes:
            cx, cy = (b[0] + b[2]) / 2, (b[1] + b[3]) / 2
            if (hx > b[0] - hr and hx < b[2] + hr) and (hy > b[1] - hr and hy < b[3] + hr) \
               and not (hx < b[0] or hx > b[2] or hy < b[1] or hy > b[3]):
                pass  # 焊盘落在文字框内不算错（框是估算的），只统计不报错
        for q in plans:
            if q is p or "box" not in q:
                continue
            if overlap(b, q["box"]):
                problems.append(f'{p["text"]}: 压新文字 {q["text"]}')

    for p in plans:
        print(f'{p["des"]:>4} {p["text"]:<24} ({p["x"]:.0f},{p["y"]:.0f})')
    if problems:
        print("\n".join("  " + x for x in problems))
        return 1
    if dry:
        print(f"\ndry-run: {len(plans)} 条文字，位置都干净")
        return 0

    old = [t["primitiveId"] for t in texts if not t.get("componentId")]
    if old:
        sh(["debug", "exec", "--code",
            "await eda.pcb_PrimitiveString.delete(" + json.dumps(old) + ")"])
        print(f"删掉旧文字 {len(old)} 条")

    ok = 0
    for p in plans:
        out = sh(["pcb", "silk-add", "--doc", DOC, "--project", PROJECT,
                  "--text", p["text"], "--x", str(round(p["x"])), "--y", str(round(p["y"])),
                  "--font-size", str(p["size"]), "--line-width", str(STROKE)])
        if re.search(r'"ok":\s*true', out):
            ok += 1
        else:
            print(f'  {p["text"]} FAIL {out[-200:]}')
    print(f"\n文字 created {ok}/{len(plans)}")
    return 0 if ok == len(plans) else 1


if __name__ == "__main__":
    sys.exit(main())
