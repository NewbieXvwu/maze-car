#!/usr/bin/env python3
"""给每个模块建一个"纯丝印"封装（只有矩形框线、没有焊盘），并建成器件放到板上。

原因：EasyEDA 的 Gerber 导出要求板上"至少有可读的器件"，而本板所有连接孔
都是用 via 打的（工程库封装写不进钻孔，见 README）。这些丝印封装既满足
导出前置条件，又给装配者画出每个模块的占位框。
"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware" / "board" / "eda"
PROJECT = "maze-car"
PROJ_UUID = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"
DOC = "PCB1"
MARGIN = 100
ROW_MAX = 33
SYM = {
    "ESP": "ESP32_S3_MOD", "TB": "TB6612_MOD", "MPU": "MPU6050_MOD",
    "HL": "VL53L0X_L_MOD", "HF": "VL53L0X_F_MOD", "HR": "VL53L0X_R_MOD",
    "ML": "MOTOR_L_CONN", "MR": "MOTOR_R_CONN", "DIP": "DIP_SW_2",
    "BTN": "START_BTN", "XH": "BATTERY", "M5P": "BUCK_5V",
}
DES = {
    "ESP": "U1", "TB": "U2", "MPU": "U3", "HL": "U4", "HF": "U5", "HR": "U6",
    "ML": "J1", "MR": "J2", "DIP": "SW1", "BTN": "SW2", "XH": "BT1", "M5P": "U7",
}
# M5P 在 HTML 里没有 box（4 个针脚在模块四角），手给一个框
EXTRA_BOX = {"M5P": (2.2, 27.2, 15.0, 29.9)}


def cli(*args, timeout=180):
    p = subprocess.run(["easyeda", *args, "--project", PROJECT],
                       capture_output=True, text=True, timeout=timeout)
    i = p.stdout.find("{")
    if i < 0:
        raise RuntimeError(f"{args[:2]}: {p.stdout}\n{p.stderr}")
    return json.loads(p.stdout[i:])


def load_html():
    """布线图数据：优先读仓库里的冻结副本 wiring_plan.json，没有才解析原始 HTML。"""
    frozen = __import__("pathlib").Path(__file__).resolve().parent / "wiring_plan.json"
    if frozen.exists():
        return json.loads(frozen.read_text(encoding="utf-8"))
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


def main():
    lib = json.loads((EDA / "lib_built.json").read_text())["symbols"]
    D = load_html()
    boxes = {c["id"]: c["box"] for c in D["components"] if c.get("box")}
    boxes.update(EXTRA_BOX)

    out = []
    for cid, sym in SYM.items():
        x0, y0g, x1, y1g = boxes[cid]
        ax = round(x0 * 100 + MARGIN, 1)
        ay = round((ROW_MAX - y1g) * 100 + MARGIN, 1)
        w = round((x1 - x0) * 100, 1)
        h = round((y1g - y0g) * 100, 1)
        spec = {"lines": [
            {"startX": 0, "startY": 0, "endX": w, "endY": 0, "width": 6, "layer": 3},
            {"startX": w, "startY": 0, "endX": w, "endY": h, "width": 6, "layer": 3},
            {"startX": w, "startY": h, "endX": 0, "endY": h, "width": 6, "layer": 3},
            {"startX": 0, "startY": h, "endX": 0, "endY": 0, "width": 6, "layer": 3},
        ]}
        name = sym + "_OUTLINE"
        r = cli("lib", "footprint", "create", "--name", name, "--scope", "project")
        fp = r["result"]["uuid"]
        sp = Path(f"/tmp/fp_{name}.json")
        sp.write_text(json.dumps(spec))
        r = cli("lib", "footprint", "build", "--uuid", fp, "--library", PROJ_UUID,
                "--spec", str(sp))
        built = bool(r.get("ok"))
        r = cli("lib", "device", "create", "--name", "EA_AGENT__" + name,
                "--symbol-uuid", lib[sym], "--symbol-library", PROJ_UUID,
                "--footprint-uuid", fp, "--footprint-library", PROJ_UUID,
                "--designator", DES[cid], "--scope", "project")
        dev = (r.get("result") or {}).get("uuid")
        if not dev:
            q = cli("lib", "search", "--query", name, "--library", "project")
            for item in (q.get("result") or {}).get("items", []):
                if item.get("name", "").endswith(name):
                    dev = item.get("uuid")
        print(f"{cid:4s} fp={fp} built={built} dev={dev} at ({ax},{ay}) {w}x{h}")
        out.append({"cid": cid, "designator": DES[cid], "fp": fp, "dev": dev,
                    "x": ax, "y": ay, "w": w, "h": h})

    (EDA / "outline_devices.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print("devices:", sum(1 for o in out if o["dev"]), "/", len(out))


if __name__ == "__main__":
    main()
