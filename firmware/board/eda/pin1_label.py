#!/usr/bin/env python3
"""在每个模块的 1 脚旁边打一个丝印「1」，装配时不用数孔也不会插反。

放哪儿：模块丝印方框的外侧、正对 1 脚那一行（U7 例外，方框左边被 BT1 占了，
改放在方框正上方偏右，避开 BT1 的名字）。BT1 不写「1」，直接写「+」「-」，
因为电池座插反会烧板，正负极比针脚号重要。

为什么不用圆点：12 个点里有 9 个正好落在走线上（视觉上像过孔），
而且模块方框比焊盘大一圈，画在框内的东西会被模块本体挡住。

字号 70 mil（实测墨迹高 ≈1.01 mm）、笔画 8 mil = 0.20 mm（嘉立创丝印能力：字高 ≥1 mm、线宽 ≥0.15 mm）。

用法:
  python3 pin1_label.py --dry-run   只算位置
  python3 pin1_label.py             删掉旧标记后重新落地
"""
import json
import re
import subprocess
import sys

ROOT = __import__("pathlib").Path(__file__).resolve().parent
PLAN = ROOT / "pcb_plan.json"
OUTLINE = ROOT / "outline_devices.json"
DOC = "PCB1"
PROJECT = "maze-car"
FONT = 70
LINE_W = 8
GAP = 40           # 标记离方框边的距离（mil）
TEXT_W = 34        # 单字符宽（mil，60 号字经验值）
MARKS = {"1", "+", "-"}   # 由本脚本管理、重跑前会先删掉的丝印

# 1 脚不写「1」而写正负号的模块：{位号: {针脚号: 字符}}
POLARITY = {"BT1": {1: "+", 2: "-"}}

# 方框左边被别家占住、只能放上方（且往右挪，避开 BT1 的名字）的模块
ABOVE_ONLY = {"U7": 40}


def tx(g):
    return g * 100 + 100


def ty(g):
    return (33 - g) * 100 + 100


def sh(args):
    r = subprocess.run(["easyeda"] + args, capture_output=True, text=True)
    return r.stdout


def silk_list():
    out = sh(["call", "pcb.silk.list", "--doc", DOC, "--project", PROJECT,
              "--payload", '{"includeAttributes":true}'])
    i = out.find('{')
    if i < 0:
        raise SystemExit("读不到丝印列表: " + out[-300:])
    return json.loads(out[i:])["result"]["texts"]


def main():
    dry = "--dry-run" in sys.argv
    mods = {m["designator"]: m for m in json.load(open(PLAN))}
    boxes = {e["designator"]: e for e in json.load(open(OUTLINE))}
    texts = silk_list()
    text_boxes = [t for t in texts
                  if t["text"] not in MARKS and t.get("visible")
                  and not t.get("componentId")            # 只看板上独立文字，不看封装自带的
                  and t["bbox"]["maxX"] > t["bbox"]["minX"]   # 斜置文字的 bbox 不可信，跳过
                  and t["bbox"]["maxY"] > t["bbox"]["minY"]]

    plans = []
    for des, m in mods.items():
        b = boxes[des]
        x0, y0, w, h = b["x"], b["y"], b["w"], b["h"]
        x1, y1 = x0 + w, y0 + h          # y1 = 顶边
        pins = m["pins"]

        targets = []
        if des in POLARITY:
            for num, mark in POLARITY[des].items():
                p = pins[num - 1]
                targets.append((mark, p, "左侧", x0 - GAP - TEXT_W, ty(p["y"]) + FONT / 2))
        else:
            p = pins[0]
            px, py = tx(p["x"]), ty(p["y"])
            if des in ABOVE_ONLY:
                targets.append(("1", p, "上方", px - 10 + ABOVE_ONLY[des], y1 + GAP + FONT / 2))
            elif px < x0 + w / 2:
                targets.append(("1", p, "左侧", x0 - GAP - TEXT_W, py + FONT / 2))
            else:
                targets.append(("1", p, "右侧", x1 + GAP, py + FONT / 2))

        for mark, p, side, ax, ay in targets:
            problems = []
            bx0, bx1 = ax, ax + TEXT_W
            by0, by1 = ay - FONT, ay      # 锚点 = 文字左上角，往下长
            if not (30 <= bx0 and bx1 <= 3570 and 30 <= by0 and by1 <= 3470):
                problems.append("出界")
            for d2, b2 in boxes.items():
                if d2 == des:
                    continue
                if bx0 < b2["x"] + b2["w"] and bx1 > b2["x"] and \
                   by0 < b2["y"] + b2["h"] and by1 > b2["y"]:
                    problems.append(f"压 {d2} 方框")
            for d2, m2 in mods.items():
                for q in m2["pins"]:
                    qx, qy = tx(q["x"]), ty(q["y"])
                    if abs(qx - (bx0 + bx1) / 2) < 45 and abs(qy - (by0 + by1) / 2) < 45:
                        problems.append(f"压 {d2}.{q['label']}")
            for t in text_boxes:
                t0 = t["bbox"]
                if bx0 < t0["maxX"] and bx1 > t0["minX"] and by0 < t0["maxY"] and by1 > t0["minY"]:
                    problems.append(f'压字「{t["text"]}」')
            plans.append({"des": des, "mark": mark, "pin": p["label"], "side": side,
                          "x": round(ax, 1), "y": round(ay, 1), "problems": problems})

    for p in plans:
        flag = "   <-- " + "; ".join(p["problems"]) if p["problems"] else ""
        print(f'{p["des"]:>4} {p["pin"]:>5} 写{p["mark"]} 在{p["side"]} '
              f'({p["x"]:.0f},{p["y"]:.0f}){flag}')

    bad = [p for p in plans if p["problems"]]
    if bad:
        print(f"\n{len(bad)} 个位置有问题")
        return 1
    if dry:
        print(f"\ndry-run: {len(plans)} 个标记，位置都干净")
        return 0

    old = [t["primitiveId"] for t in texts
           if t["text"] in MARKS and t.get("layer") == 3 and not t.get("componentId")]
    if old:
        sh(["debug", "exec", "--code",
            "await eda.pcb_PrimitiveString.delete(" + json.dumps(old) + ")"])
        print(f"删掉旧标记 {len(old)} 条")

    ok = 0
    for p in plans:
        out = sh(["pcb", "silk-add", "--doc", DOC, "--project", PROJECT,
                  "--text", p["mark"], "--x", str(p["x"]), "--y", str(p["y"]),
                  "--font-size", str(FONT), "--line-width", str(LINE_W)])
        if re.search(r'"ok":\s*true', out):
            ok += 1
        else:
            print(f'  {p["des"]} FAIL {out[-200:]}')
    print(f"\n标记 created {ok}/{len(plans)}")
    return 0 if ok == len(plans) else 1


if __name__ == "__main__":
    sys.exit(main())
