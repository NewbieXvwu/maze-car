#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
按 cad/params.json 核对整车尺寸链与重心。

用法：  python3 cad/check.py
规则：  填了 measured 的项用实测值，没填的用 nominal。
退出码：0 = 全过；1 = 有 FAIL。
"""

import json
import pathlib
import sys

HERE = pathlib.Path(__file__).resolve().parent
P = json.loads((HERE / "params.json").read_text(encoding="utf-8"))


def g(section, key):
    d = P[section][key]
    m = d.get("measured")
    return float(m if m is not None else d["nominal"])


fails = []


def chk(name, ok, msg=""):
    print(("PASS  " if ok else "FAIL  ") + name + ("" if ok else "  —— " + msg))
    if not ok:
        fails.append(name)


# ---------------------------------------------------------------- 轮子 / 底板
axle_z = g("axle", "axle_z")
wheel_d = g("axle", "wheel_d")
wheel_top = axle_z + wheel_d / 2
plate_half_len = g("chassis", "plate_len") / 2
plate_half_wid = g("chassis", "plate_wid") / 2

chk("轴心离地 = 轮半径", abs(axle_z - wheel_d / 2) < 0.2,
    f"轴心 {axle_z} vs 半径 {wheel_d / 2}")

chk("底板离地 = 万向轮总高",
    abs(g("chassis", "ground_clearance") - g("caster", "height")) < 0.5,
    f"底板 {g('chassis','ground_clearance')} vs 万向轮 {g('caster','height')}")

inner = g("axle", "track") / 2 - g("axle", "wheel_w") / 2
chk("轮内侧面在底板外（不蹭板）", inner >= plate_half_wid + 0.3,
    f"轮内 {inner:.1f}，板边 {plate_half_wid:.1f}，余量 {inner - plate_half_wid:.1f}")

# ---------------------------------------------------------------- 万向轮 ×2
cast_base = g("caster", "base_d") / 2
for label, key in (("前", "x_front"), ("后", "x_rear")):
    cx = g("caster", key)
    chk(f"{label}万向轮不超出底板", abs(cx) + cast_base <= plate_half_len + 0.5,
        f"x={cx:+.1f}，底座边 {abs(cx) + cast_base:.1f}，板边 {plate_half_len:.1f}")
    chk(f"{label}万向轮不在驱动轮上", abs(cx) > wheel_d / 2 + cast_base,
        f"x={cx:+.1f}，轮缘 {wheel_d/2:.1f}，底座内边 {abs(cx) - cast_base:.1f}")

# ---------------------------------------------------------------- 主板 / 电池
chk("主板底面高于轮顶", g("pcb", "z") >= wheel_top + 2.0,
    f"主板 {g('pcb','z')}，轮顶 {wheel_top}")

bat_top = g("battery", "z0") + g("battery", "box_h")
chk("电池顶不顶主板", bat_top <= g("pcb", "z") - 1.0,
    f"电池顶 {bat_top}，主板底 {g('pcb','z')}")

motor_top = (g("chassis", "ground_clearance") + g("chassis", "plate_thk")
             + g("motor", "body_h"))
chk("电池坐在电机顶上（不悬空、不压电机）",
    abs(g("battery", "z0") - motor_top) < 0.5,
    f"电池底 {g('battery','z0')}，电机顶 {motor_top}")

bat_x0 = g("battery", "x0")
bat_x1 = bat_x0 + g("battery", "box_len")
bat_y0 = g("battery", "y0")
bat_y1 = bat_y0 + g("battery", "box_wid")
chk("电池在底板轮廓内",
    bat_x0 >= -plate_half_len and bat_x1 <= plate_half_len
    and bat_y0 >= -plate_half_wid and bat_y1 <= plate_half_wid,
    f"x {bat_x0:.1f}..{bat_x1:.1f}，y {bat_y0:.1f}..{bat_y1:.1f}，"
    f"板 x ±{plate_half_len:g} y ±{plate_half_wid:g}")

standoff_inner_y = g("pcb", "hole_dy") - g("chassis", "standoff_d") / 2
chk("电池不碰四根铜柱", bat_y1 <= standoff_inner_y and bat_y0 >= -standoff_inner_y,
    f"电池 y {bat_y0:.1f}..{bat_y1:.1f}，铜柱内边 ±{standoff_inner_y:.1f}")

chk("电池重心在驱动轮轴附近（±10mm）",
    abs((bat_x0 + bat_x1) / 2) <= 10.0,
    f"电池中心 x = {(bat_x0 + bat_x1) / 2:+.1f}")

# ---------------------------------------------------------------- 测距
lens_z = g("tof", "lens_z")
chk("镜头比轮顶高 10mm 以上", lens_z - wheel_top >= 10.0,
    f"镜头 {lens_z}，轮顶 {wheel_top}")
chk("镜头离地在 50–100mm", 50.0 <= lens_z <= 100.0, f"镜头 {lens_z}")

chk("侧测距偏离车轴不超过 60mm", abs(g("tof", "side_x")) <= 60.0,
    f"side_x = {g('tof','side_x')}（原规格 0，因主板遮挡改挂前龙门）")

# ---------------------------------------------------------------- 重心
m = {k: g("masses", k) for k in
     ("plate", "pcb", "battery", "motor", "wheel", "caster", "gantry", "tof")}
xs = {
    "plate": 0.0,
    "pcb": g("pcb", "x"),
    "battery": (bat_x0 + bat_x1) / 2,
    "motor": 0.0,
    "wheel": 0.0,
    "caster": (g("caster", "x_front") + g("caster", "x_rear")) / 2,
    "gantry": g("gantry", "post_x"),
    "tof": g("tof", "side_x"),
}
ws = {"plate": 1, "pcb": 1, "battery": 1, "motor": 2,
      "wheel": 2, "caster": 2, "gantry": 1, "tof": 3}

W = sum(m[k] * ws[k] for k in m)
cgx = sum(m[k] * ws[k] * xs[k] for k in m) / W

front_x = g("caster", "x_front")
rear_x = g("caster", "x_rear")
lo = min(front_x, rear_x, 0.0) + 8.0
hi = max(front_x, rear_x, 0.0) - 8.0
chk("重心落在四轮支撑面内（前后）", lo <= cgx <= hi,
    f"重心 x={cgx:.1f}，允许 {lo:.0f}..{hi:.0f}；偏出会前栽/后翻")

print(f"      重心 x = {cgx:+.1f} mm，整备质量 ≈ {W:.0f} g"
      f"（占位值，实测后重算）")

sys.exit(1 if fails else 0)
