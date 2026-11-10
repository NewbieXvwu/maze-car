#!/usr/bin/env python3
"""给板上每个过孔开阻焊窗（正反两面）。

背景：`pcb via` 建出来的过孔默认「盖油」，GTS/GBS 里 0 个开窗 —— 模块排针
插进去后铜环被绿油盖住，焊不上。`pcb via` 没有开窗参数，`pcb_PrimitiveVia`
的 solderMaskExpansion 改了也不进 gerber（实测 4.1.97）。

可行做法：在阻焊层（5=顶层 6=底层）上画一个实心多边形，就是一块开窗。
半径 36 mil ≈ 0.91mm，比 65.4 mil 的孔环大 4 mil，四周留 28 mil 的阻焊桥。

用法：python3 mask_open.py
"""
import json
import math
import subprocess

LAYERS = (5, 6)          # 5 = Top Solder Mask, 6 = Bottom Solder Mask
RADIUS_MIL = 36.0
SIDES = 12
PROJECT = "maze-car"
DOC = "PCB1"


def run(args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.returncode == 0, r.stdout + r.stderr


def vias():
    ok, out = run(["easyeda", "call", "pcb.via.list", "--doc", DOC, "--project", PROJECT])
    if not ok:
        raise SystemExit("via.list failed: " + out[-400:])
    i = out.find("{")
    data, _ = json.JSONDecoder().raw_decode(out[i:])
    return data["result"]["vias"]


def existing_mask_fills():
    ids = []
    ok, out = run(["easyeda", "pcb", "fill", "list", "--doc", DOC, "--project", PROJECT])
    if not ok:
        return ids
    i = out.find("{")
    if i < 0:
        return ids
    try:
        data, _ = json.JSONDecoder().raw_decode(out[i:])
    except ValueError:
        return ids
    for f in data.get("result", {}).get("fills", []):
        if f.get("layer") in LAYERS:
            ids.append(f["primitiveId"])
    return ids


def ring(cx, cy, r=RADIUS_MIL, n=SIDES):
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        pts.append([round(cx + r * math.cos(a), 2), round(cy + r * math.sin(a), 2)])
    return json.dumps(pts)


def main():
    old = existing_mask_fills()
    if old:
        ok, out = run(["easyeda", "pcb", "fill", "delete", "--doc", DOC,
                       "--project", PROJECT, "--ids", ",".join(old)])
        print(f"deleted {len(old)} old mask fills: {ok}")

    v = vias()
    print(f"vias: {len(v)}")
    done = 0
    for item in v:
        for layer in LAYERS:
            ok, out = run(["easyeda", "pcb", "fill", "create", "--doc", DOC,
                           "--project", PROJECT, "--points", ring(item["x"], item["y"]),
                           "--layer", str(layer)])
            if ok:
                done += 1
            else:
                print("FAIL", item["primitiveId"], layer, out[-200:])
        if done % 40 == 0:
            print(f"  {done} openings", flush=True)
    print(f"openings created: {done} (expect {len(v) * len(LAYERS)})")


if __name__ == "__main__":
    main()
