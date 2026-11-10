#!/usr/bin/env python3
"""丝印自检：位置、重影、方向标记是否真指向 1 脚。

外部审查抓到的两类问题都在这里兜住：
  1) 文字出板 / 压位号 / 互相压字（silk-add 不校验边界）；
  2) 方向标记画错位置 —— 字在板内、看着没问题，但指着隔壁的孔。

判据：
  - 40 条可见文字，全部在板框内（留 30 mil）；
  - 任意两条文字 bbox 不相交；
  - 13 个标记（12 个 `1` + BT1 的 `+`/`-`）到它所属模块 1 号孔（BT1 的 `-` 到 2 号孔）
    的距离 < 200 mil，且该孔确实是该模块的 1 号（`-` 是 2 号）；
  - 12 个模块名要么在位号右侧同一行（左边缘离位号右边缘 0~250 mil），
    要么在位号正上方（左边缘对齐、竖直间距 ≤ 120 mil）——BT1/U6 用后者。

用法: python3 verify_silk.py
"""
import json
import math
import subprocess
import sys
from pathlib import Path

DOC = "PCB1"
PROJECT = "maze-car"
BOARD_W, BOARD_H, EDGE = 3600, 3500, 30
ROOT = Path(__file__).resolve().parent


def silk():
    out = subprocess.run(["easyeda", "call", "pcb.silk.list", "--doc", DOC,
                          "--project", PROJECT,
                          "--payload", '{"includeAttributes":true}'],
                         capture_output=True, text=True).stdout
    d = json.JSONDecoder().raw_decode(out[out.find("{"):])[0]["result"]["texts"]
    return [t for t in d if t.get("visible") and t["bbox"]["maxX"] > t["bbox"]["minX"]
            and t["bbox"]["maxY"] > t["bbox"]["minY"]]


def pins():
    plan = json.loads((ROOT / "pcb_plan.json").read_text(encoding="utf-8"))
    out = []
    for m in plan:
        for i, p in enumerate(m["pins"], 1):
            out.append({"des": m["designator"], "ref": str(i), "name": p["ref"].split(".")[-1],
                        "label": p["label"], "net": p["net"],
                        "x": p["x"] * 100 + 100, "y": (33 - p["y"]) * 100 + 100})
    return out


def main():
    texts = silk()
    P = pins()
    print(f"可见文字 {len(texts)} 条")
    bad = []
    EXPECT = 40          # 12 位号 + 12 模块名 + 3 板边标题 + 13 标记
    if len(texts) != EXPECT:
        bad.append(f"文字条数 {len(texts)}，应为 {EXPECT}"
                   f"（少了多半是 silk_pcb.py/pin1_label.py 没跑，或 place_outline.py 顺序错了）")

    for i, t in enumerate(texts):
        b = t["bbox"]
        if b["minX"] < EDGE or b["minY"] < EDGE or b["maxX"] > BOARD_W - EDGE or b["maxY"] > BOARD_H - EDGE:
            bad.append(f'出板/贴边: {t["text"]!r}')
        for u in texts[i + 1:]:
            c = u["bbox"]
            if (b["minX"] < c["maxX"] and b["maxX"] > c["minX"]
                    and b["minY"] < c["maxY"] and b["maxY"] > c["minY"]):
                bad.append(f'压字: {t["text"]!r} × {u["text"]!r}')

    marks = [t for t in texts if t["text"] in ("1", "+", "-", "\u2212")
             and not t.get("componentId")]
    for t in marks:
        b = t["bbox"]
        cx, cy = (b["minX"] + b["maxX"]) / 2, (b["minY"] + b["maxY"]) / 2
        p = min(P, key=lambda q: (q["x"] - cx) ** 2 + (q["y"] - cy) ** 2)
        dist = math.dist((cx, cy), (p["x"], p["y"]))
        want = {"1": "1", "+": "1", "-": "2", "\u2212": "2"}[t["text"]]
        if p["ref"] != want or dist > 200:
            bad.append(f'标记 {t["text"]!r} 落在 {p["des"]}.{p["ref"]} {dist:.0f} mil 处（应为 {want} 号孔）')
        else:
            print(f'  {t["text"]:>2} → {p["des"]}.{p["ref"]}({p["name"]}) {p["label"]:<12} {dist:5.0f} mil')

    designs = {t["text"]: t["bbox"] for t in texts if t.get("componentId")
               and t["bbox"]["maxX"] > t["bbox"]["minX"]}
    titles = {"maze-car PCB", "2L 1.0mm hole 2026-11", "NewbieXvwu"}
    names = [t for t in texts if not t.get("componentId")
             and t["text"] not in ("1", "+", "-", "\u2212") and t["text"] not in titles]
    for t in names:
        b = t["bbox"]
        side = [d for d in designs.values() if abs(d["maxY"] - b["maxY"]) < 20
                and 0 <= b["minX"] - d["maxX"] <= 250]
        above = [d for d in designs.values() if abs(d["minX"] - b["minX"]) < 12
                 and 0 < b["minY"] - d["maxY"] <= 120]
        if not side and not above:
            bad.append(f'名称 {t["text"]!r} 既不在位号右侧同一行，也不在位号正上方')

    print(f"标记 {len(marks)} 个、名称 {len(names)} 条")
    if bad:
        print("\n".join("  " + x for x in bad))
        print(f"结论：FAIL —— {len(bad)} 处问题")
        return 1
    print(f"结论：PASS —— {EXPECT} 条文字都在板内、无压字，标记都指向各自 1 脚")
    return 0


if __name__ == "__main__":
    sys.exit(main())
