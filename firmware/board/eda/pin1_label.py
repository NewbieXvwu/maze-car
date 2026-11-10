#!/usr/bin/env python3
"""在每个模块的 1 脚旁边打一个丝印「1」，装配时不用数孔也不会插反。

放哪儿：模块丝印方框的外侧、正对 1 脚那一行（U7 例外，方框左边被 BT1 占了，
改放在方框正上方）。位置都用 `pcb.silk.list` 的 bbox 复核过，不压别家的框和字。

为什么不用圆点：12 个点里有 9 个正好落在走线上（视觉上像过孔），
而且模块方框比焊盘大一圈，画在框内的东西会被模块本体挡住。

用法:
  python3 pin1_label.py --dry-run   只算位置
  python3 pin1_label.py             落地（12 条丝印）
"""
import json
import subprocess
import sys

PLAN = "pcb_plan.json"
OUTLINE = "outline_devices.json"
DOC = "PCB1"
PROJECT = "maze-car"
LAYER_SILK_TOP = 3
FONT = 40
GAP = 40          # 「1」离方框边的距离（mil）
TEXT_W = 22       # 单字符宽（mil，40 号字经验值）

# 方框左边被别家占住、只能放上方的模块
ABOVE_ONLY = {"U7"}


def tx(g):
    return g * 100 + 100


def ty(g):
    return (33 - g) * 100 + 100


def main():
    dry = "--dry-run" in sys.argv
    mods = {m["designator"]: m for m in json.load(open(PLAN))}
    boxes = {e["designator"]: e for e in json.load(open(OUTLINE))}

    plans = []
    for des, m in mods.items():
        b = boxes[des]
        x0, y0, w, h = b["x"], b["y"], b["w"], b["h"]
        x1, y1 = x0 + w, y0 + h          # y1 = 顶边
        p1 = m["pins"][0]
        px, py = tx(p1["x"]), ty(p1["y"])

        if des in ABOVE_ONLY:
            ax, ay = px - 10, y1 + GAP + 20     # 锚点=文字左上角，往下长
            side = "上方"
        elif px < x0 + w / 2:
            ax, ay = x0 - GAP - TEXT_W, py + 20  # 方框左边外侧，字心对着一脚
            side = "左侧"
        else:
            ax, ay = x1 + GAP, py + 20          # 方框右边外侧
            side = "右侧"

        # 自检：不出板、不与任何模块方框重叠、不压焊盘
        problems = []
        if not (30 <= ax and ax + TEXT_W <= 3570 and 30 <= ay - FONT and ay <= 3470):
            problems.append("出界")
        for d2, b2 in boxes.items():
            if d2 == des:
                continue
            if ax < b2["x"] + b2["w"] and ax + TEXT_W > b2["x"] and \
               ay - FONT < b2["y"] + b2["h"] and ay > b2["y"]:
                problems.append(f"压 {d2} 方框")
        for d2, m2 in mods.items():
            for p in m2["pins"]:
                qx, qy = tx(p["x"]), ty(p["y"])
                if abs(qx - (ax + TEXT_W / 2)) < 45 and abs(qy - (ay - FONT / 2)) < 45:
                    problems.append(f"压 {d2}.{p['label']}")
        plans.append({"des": des, "pin1": p1["label"], "side": side,
                      "x": round(ax, 1), "y": round(ay, 1), "problems": problems})

    for p in plans:
        flag = "   <-- " + "; ".join(p["problems"]) if p["problems"] else ""
        print(f'{p["des"]:>4} 1脚={p["pin1"]:<6} 标在{p["side"]} ({p["x"]:.0f},{p["y"]:.0f}){flag}')

    bad = [p for p in plans if p["problems"]]
    if bad:
        print(f"\n{len(bad)} 个位置有问题")
        return 1
    if dry:
        print(f"\ndry-run: {len(plans)} 个标记，位置都干净")
        return 0

    ok = 0
    for p in plans:
        r = subprocess.run(
            ["easyeda", "pcb", "silk-add", "--doc", DOC, "--project", PROJECT,
             "--text", "1", "--x", str(p["x"]), "--y", str(p["y"]),
             "--font-size", str(FONT), "--line-width", "6"],
            capture_output=True, text=True)
        if '"ok": true' in r.stdout:
            ok += 1
        else:
            print(f'  {p["des"]} FAIL {r.stdout[-200:]}{r.stderr[-200:]}')
    print(f"\n「1」标记 created {ok}/{len(plans)}")
    return 0 if ok == len(plans) else 1


if __name__ == "__main__":
    sys.exit(main())
