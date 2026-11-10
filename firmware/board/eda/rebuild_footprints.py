#!/usr/bin/env python3
"""删掉上一轮的 12 套封装/器件（按 pcb_plan.json 里的 uuid），供 gen_footprints.py 重建。"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
PROJ_UUID = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"


def cli(*args, timeout=120):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    return json.loads(p.stdout[i:]) if i >= 0 else {"ok": False, "raw": p.stdout[-300:]}


plan = json.loads((EDA / "pcb_plan.json").read_text())
for e in plan:
    name = "EA_AGENT__" + e["symbol"] + "_PCB"
    if e.get("deviceUuid"):
        r = cli("lib", "device", "delete", "--uuid", e["deviceUuid"],
                "--library", PROJ_UUID, "--expected-name", name)
        print(f"del dev {name:22s} ok={r.get('ok')}")
    if e.get("footprintUuid"):
        r = cli("lib", "footprint", "delete", "--uuid", e["footprintUuid"],
                "--library", PROJ_UUID, "--expected-name", name)
        print(f"del fp  {name:22s} ok={r.get('ok')}")
