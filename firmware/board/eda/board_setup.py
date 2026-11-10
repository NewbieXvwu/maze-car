#!/usr/bin/env python3
"""板框 + M3 安装孔。跑在 route_via.py 之后（`pcb clear` 会清掉孔，但保留板框）。

板框：3600×3500 mil、R120 圆角 → 91.44×88.90mm，正好塞进嘉立创 10×10cm 免费券。
安装孔：四角 3.2mm 孔、4mm 环，离板边 250 mil；net 留空，DRC 不会把它们算进任何网络。

用法:
  python3 board_setup.py            板框没有就画，缺的安装孔补上
  python3 board_setup.py --force    板框重建（先清空）
"""
import json
import subprocess
import sys

DOC = "PCB1"
PROJECT = "maze-car"
BOARD = (0, 0, 3600, 3500)      # 板框外接矩形，mil
CORNER_R = 120
M3_HOLE = 126                   # 3.2mm
M3_RING = 157                   # 4.0mm
M3_POS = [(250, 250), (3350, 250), (250, 3250), (3350, 3250)]


def sh(args):
    r = subprocess.run(["easyeda"] + args, capture_output=True, text=True)
    return r.stdout


def load(out):
    i = out.find('{')
    if i < 0:
        raise SystemExit("没有 JSON 返回: " + out[-300:])
    return json.JSONDecoder().raw_decode(out[i:])[0]


def main():
    force = "--force" in sys.argv

    got = load(sh(["pcb", "outline-get", "--doc", DOC, "--project", PROJECT]))
    has_outline = got.get("ok") and got.get("result", {}).get("centerlineBBox")

    if force or not has_outline:
        if has_outline:
            sh(["pcb", "outline-clear", "--doc", DOC, "--project", PROJECT])
        rect = ",".join(str(v) for v in BOARD)
        out = sh(["pcb", "outline-round", "--doc", DOC, "--project", PROJECT,
                  "--rect", rect, "--radius", str(CORNER_R)])
        print("板框:", "ok" if '"ok": true' in out else out[-200:])
    else:
        b = got["result"]["centerlineBBox"]
        print(f'板框已有: {b["maxX"] - b["minX"]}×{b["maxY"] - b["minY"]} mil，跳过')

    vias = load(sh(["pcb", "via-list", "--doc", DOC, "--project", PROJECT]))
    vias = vias.get("result", {}).get("vias", []) if vias.get("ok") else []
    have = {(round(v["x"]), round(v["y"])) for v in vias}

    added = 0
    for x, y in M3_POS:
        if (x, y) in have:
            continue
        out = sh(["pcb", "via", "--doc", DOC, "--project", PROJECT, "--x", str(x),
                  "--y", str(y), "--hole", str(M3_HOLE), "--diameter", str(M3_RING),
                  "--net", ""])
        if '"ok": true' in out:
            added += 1
        else:
            print(f"  ({x},{y}) FAIL {out[-200:]}")
    print(f"安装孔: 新增 {added} 个，共 {len(have) + added} 个孔")
    return 0


if __name__ == "__main__":
    sys.exit(main())
