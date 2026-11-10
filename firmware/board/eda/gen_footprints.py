#!/usr/bin/env python3
"""从手焊布线图 (迷宫小车主板布线.html) 生成 12 个模块的 PCB 封装与器件。

坐标：HTML 1 格 = 2.54mm = 100mil，y 向下；PCB y 向上 → 焊盘 y 取负。
封装：焊盘编号按物理针脚 1..N（同网络的重复针脚各占一个号），焊盘 1 = 封装原点。
器件名加 _PCB2 后缀（旧的 _PCB 器件删不掉，见 README）。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
PROJ_UUID = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"
GRID = 100
DEV_SUFFIX = "_PCB2"
OLD_FP = {"BATTERY_PCB": "33e88cd892900fd1"}

MODULES = [
    ("BT1", "BATTERY", "XH"),
    ("U7", "BUCK_5V", "M5P"),
    ("U1", "ESP32_S3_MOD", "ESP"),
    ("U2", "TB6612_MOD", "TB"),
    ("U3", "MPU6050_MOD", "MPU"),
    ("U4", "VL53L0X_L_MOD", "HL"),
    ("U5", "VL53L0X_F_MOD", "HF"),
    ("U6", "VL53L0X_R_MOD", "HR"),
    ("J1", "MOTOR_L_CONN", "ML"),
    ("J2", "MOTOR_R_CONN", "MR"),
    ("SW1", "DIP_SW_2", "DIP"),
    ("SW2", "START_BTN", "BTN"),
]


def cli(*args, timeout=180):
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
    raise RuntimeError("D not found")


def sch_unique_ids():
    r = cli("sch", "read", "--doc", "P1")
    return {c["designator"]: c["uniqueId"] for c in r["result"]["components"]
            if c.get("componentType") == "part" and c.get("designator")}


def main():
    D = load_html()
    built = json.loads((EDA / "lib_built.json").read_text())
    uids = sch_unique_ids()
    comps = {c["id"]: c for c in D["components"]}
    plan = []

    for des, symname, cid in MODULES:
        comp = comps[cid]
        pins = comp["pins"]
        x0, y0 = pins[0]["x"], pins[0]["y"]
        pads, nets, labels = [], {}, {}
        for i, p in enumerate(pins, start=1):
            pads.append({
                "number": str(i),
                "x": round((p["x"] - x0) * GRID, 2),
                "y": round((y0 - p["y"]) * GRID, 2),
                "holeRadius": 0.5,
                "shape": ["ELLIPSE", 1.7, 1.7],
                "layer": 1,
            })
            labels[str(i)] = p.get("label", "")
            if p.get("net"):
                nets[str(i)] = p["net"]

        fp_name = f"{symname}_PCB"
        spec = EDA / "footprints" / f"{fp_name}.json"
        spec.parent.mkdir(exist_ok=True)
        spec.write_text(json.dumps({"pads": pads}, ensure_ascii=False, indent=1))

        # 清掉同名的旧封装（build 是追加语义，必须从空资产重来）
        old = OLD_FP.get(fp_name)
        if old:
            r = cli("lib", "footprint", "delete", "--uuid", old, "--library", PROJ_UUID,
                    "--expected-name", "EA_AGENT__" + fp_name)
            print(f"  drop old fp {fp_name} ok={r.get('ok')}")
        r = cli("lib", "footprint", "create", "--name", fp_name, "--scope", "project")
        fpuuid = r["result"]["uuid"]
        r = cli("lib", "footprint", "build", "--uuid", fpuuid, "--library", PROJ_UUID,
                "--spec", str(spec))
        if not r.get("ok") or not r.get("result", {}).get("verified"):
            print("FP FAIL", fp_name, json.dumps(r.get("error"), ensure_ascii=False))
            sys.exit(1)
        print(f"FP {fp_name:22s} {fpuuid} pads={len(pads)} nets={len(nets)}")

        symuuid = built["symbols"][symname]
        dev_name = fp_name + DEV_SUFFIX
        r = cli("lib", "device", "create", "--name", dev_name, "--symbol-uuid", symuuid,
                "--symbol-library", PROJ_UUID, "--footprint-uuid", fpuuid,
                "--footprint-library", PROJ_UUID, "--designator", des.rstrip("0123456789"),
                "--scope", "project")
        devuuid = (r.get("result") or {}).get("uuid")
        if not devuuid:
            s = cli("lib", "search", "--query", dev_name, "--library", "project", "--limit", "10")
            hit = [c for c in s["result"]["components"] if c["name"].endswith(dev_name)]
            devuuid = hit[0]["uuid"] if hit else None
        print(f"DEV {dev_name:22s} {devuuid}")
        plan.append({
            "designator": des, "symbol": symname, "module": cid,
            "footprintName": fp_name, "footprintUuid": fpuuid,
            "deviceName": dev_name, "deviceUuid": devuuid,
            "x": round(x0 * GRID, 2), "y": round(y0 * GRID, 2),
            "nets": nets, "labels": labels, "uniqueId": uids.get(des, ""),
            "pins": pins, "box": comp.get("box"),
        })

    (EDA / "pcb_plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1))
    print("wrote pcb_plan.json", len(plan))


if __name__ == "__main__":
    main()
