#!/usr/bin/env python3
"""把 12 个"纯丝印封装"器件放到板上（坐标取模块框左下角）。"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
PROJ_UUID = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"
DOC = "PCB1"


def cli(*args, timeout=120):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    if i < 0:
        raise RuntimeError(f"{args[:2]}: {p.stdout}\n{p.stderr}")
    return json.loads(p.stdout[i:])


def find_device(name):
    r = cli("lib", "search", name, "--library", "project", "--limit", "30")
    items = (r.get("result") or {}).get("components") or []
    for it in items:
        if it.get("name") == name:
            return it.get("uuid")
    return None


SYM = {
    "ESP": "ESP32_S3_MOD", "TB": "TB6612_MOD", "MPU": "MPU6050_MOD",
    "HL": "VL53L0X_L_MOD", "HF": "VL53L0X_F_MOD", "HR": "VL53L0X_R_MOD",
    "ML": "MOTOR_L_CONN", "MR": "MOTOR_R_CONN", "DIP": "DIP_SW_2",
    "BTN": "START_BTN", "XH": "BATTERY", "M5P": "BUCK_5V",
}


def main():
    plan = json.loads((EDA / "outline_devices.json").read_text())
    ok = 0
    for p in plan:
        name = "EA_AGENT__" + SYM[p["cid"]] + "_OUTLINE"
        dev = find_device(name)
        if not dev:
            print(" no device for", p["cid"])
            continue
        r = cli("pcb", "add-component", "--doc", DOC, "--library", PROJ_UUID,
                "--uuid", dev, "--x", str(p["x"]), "--y", str(p["y"]),
                "--designator", p["designator"], "--unique-id", p["cid"],
                "--nets", "{}", "--layer", "1")
        print("", p["designator"], p["cid"], "placed" if r.get("ok") else json.dumps(r.get("error"), ensure_ascii=False)[:120])
        if r.get("ok"):
            ok += 1
    print("placed", ok, "/", len(plan))
    cli("pcb", "save", "--doc", DOC)


if __name__ == "__main__":
    main()
