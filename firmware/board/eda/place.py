#!/usr/bin/env python3
"""把 12 个模块器件放到 P1，并逐个引脚打网络标记（power/gnd/net_label）。"""
import json, subprocess, pathlib, sys

HERE = pathlib.Path(__file__).parent
built = json.loads((HERE / "lib_built.json").read_text())
PROJ = built["project"]
DEVS = built["devices"]

# name -> (x, y, designator)
LAYOUT = {
    "BATTERY":        (140, 730, "BT1"),
    "BUCK_5V":        (140, 620, "U7"),
    "ESP32_S3_MOD":   (430, 520, "U1"),
    "TB6612_MOD":     (740, 600, "U2"),
    "MOTOR_L_CONN":   (740, 460, "J1"),
    "MOTOR_R_CONN":   (740, 340, "J2"),
    "MPU6050_MOD":    (1010, 720, "U3"),
    "VL53L0X_L_MOD":  (1010, 620, "U4"),
    "VL53L0X_F_MOD":  (1010, 530, "U5"),
    "VL53L0X_R_MOD":  (1010, 440, "U6"),
    "DIP_SW_2":       (430, 330, "SW1"),
    "START_BTN":      (430, 230, "SW2"),
}
POWER_NETS = {"VBAT", "5V", "3V3"}

def cli(*a, timeout=180):
    p = subprocess.run(["easyeda", *a, "--doc", "P1", "--project", "maze-car"],
                       capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": (p.stdout or "")[-300:] + (p.stderr or "")[-300:]}

manifest = {m["name"]: m for m in json.loads((HERE / "specs" / "manifest.json").read_text())}

placed = {}
for name, (x, y, des) in LAYOUT.items():
    r = cli("sch", "place", "--lib", PROJ, "--uuid", DEVS[name],
            "--x", str(x), "--y", str(y), "--designator", des)
    ok = r.get("ok")
    prim = (r.get("result") or {}).get("primitiveId")
    print(f"{'OK ' if ok and prim else 'ERR'} place {des:4s} {name:16s} {prim or json.dumps(r)[:200]}")
    if not (ok and prim):
        sys.exit(1)
    placed[name] = des

fails = []
total = 0
for name, m in manifest.items():
    des = placed[name]
    for p in m["pins"]:
        net = p["net"]
        kind = "net_label"   # 全部用网络名标签：网表按同名相连，视觉上也最干净
        side = "left" if p["pin"] in m["left"] else "right"
        r = cli("sch", "connect", "--pin", f"{des}:{p['pin']}", "--kind", kind,
                "--net", net, "--direction", side, "--offset", "40")
        total += 1
        if not r.get("ok"):
            fails.append((des, p["pin"], net, (r.get("error") or {}).get("message", "")[:60]))
    print(f"  {des} connected {len(m['pins'])} pins")

print(f"pins connected: {total - len(fails)}/{total}")
for f in fails:
    print("  FAIL", f)
(HERE / "placed.json").write_text(json.dumps(placed, indent=1, ensure_ascii=False))
