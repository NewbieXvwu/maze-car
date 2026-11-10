#!/usr/bin/env python3
"""按 firmware/board/netlist.md 生成 12 个模块符号规格 + 建库脚本。

坐标：1 raw = 0.254mm = 10mil；引脚间距 10 raw；引脚长 20 raw。
左列引脚 x=-(W/2+20) rotation 0；右列 x=+(W/2+20) rotation 180。
pinType 统一 Undefined（模块是排针，不做电源口判定，避免 ERC 冲突）。
"""
import json, pathlib

W = 60          # 符号本体宽（raw）
PITCH = 10
PINLEN = 20

# name, designator, 中文说明, 左列[(pin, net)], 右列[(pin, net)]
MODULES = [
    ("ESP32_S3_MOD", "U", "ESP32-S3 开发板模块 (YD-ESP32-S3)",
     [("3V3","3V3"),("5Vin","5V"),("GND","GND"),("IO42","SCL"),("IO41","SDA"),
      ("IO40","XSHUT_L"),("IO39","XSHUT_F"),("IO38","XSHUT_R"),("IO47","DIP1"),
      ("IO21","DIP2"),("IO2","BTN")],
     [("IO4","PWMA"),("IO5","AIN2"),("IO6","AIN1"),("IO7","STBY"),("IO15","BIN1"),
      ("IO16","BIN2"),("IO17","PWMB"),("IO9","ENC_L_C2"),("IO10","ENC_L_C1"),
      ("IO13","ENC_R_C2"),("IO14","ENC_R_C1")]),
    ("TB6612_MOD", "U", "TB6612FNG 双路电机驱动模块",
     [("VM","VBAT"),("VCC","3V3"),("GND","GND"),("AO1","AO1"),("AO2","AO2"),
      ("BO1","BO1"),("BO2","BO2")],
     [("PWMA","PWMA"),("AIN2","AIN2"),("AIN1","AIN1"),("STBY","STBY"),
      ("BIN1","BIN1"),("BIN2","BIN2"),("PWMB","PWMB")]),
    ("MPU6050_MOD", "U", "MPU6050 陀螺仪模块 (GY-521)",
     [("VCC","3V3"),("GND","GND")],
     [("SCL","SCL"),("SDA","SDA")]),
    ("VL53L0X_L_MOD", "U", "左测距模块 VL53L0X",
     [("VIN","3V3"),("GND","GND")],
     [("SCL","SCL"),("SDA","SDA"),("XSHUT","XSHUT_L")]),
    ("VL53L0X_F_MOD", "U", "前测距模块 VL53L0X",
     [("VIN","3V3"),("GND","GND")],
     [("SCL","SCL"),("SDA","SDA"),("XSHUT","XSHUT_F")]),
    ("VL53L0X_R_MOD", "U", "右测距模块 VL53L0X",
     [("VIN","3V3"),("GND","GND")],
     [("SCL","SCL"),("SDA","SDA"),("XSHUT","XSHUT_R")]),
    ("MOTOR_L_CONN", "J", "左电机+编码器接线",
     [("VCC","3V3"),("GND","GND")],
     [("M1","AO1"),("M2","AO2"),("C1","ENC_L_C1"),("C2","ENC_L_C2")]),
    ("MOTOR_R_CONN", "J", "右电机+编码器接线",
     [("VCC","3V3"),("GND","GND")],
     [("M1","BO1"),("M2","BO2"),("C1","ENC_R_C1"),("C2","ENC_R_C2")]),
    ("DIP_SW_2", "SW", "2 位拨码开关",
     [("1","DIP1"),("2","DIP2")],
     [("1'","GND"),("2'","GND")]),
    ("START_BTN", "SW", "启动按键",
     [("A","BTN")],
     [("D","GND")]),
    ("BATTERY", "BT", "电池（18650x2 或专用包）",
     [("+","VBAT")],
     [("-","GND")]),
    ("BUCK_5V", "U", "降压模块 mini560 5V",
     [("IN+","VBAT"),("IN-","GND")],
     [("OUT+","5V"),("OUT-","GND")]),
]

def spec(left, right):
    n = max(len(left), len(right))
    h = n * PITCH + 20
    hh, hw = h / 2, W / 2
    pins = []
    def col(items, x, rot):
        # 垂直居中：最上面一个 y = (len-1)*PITCH/2
        top = (len(items) - 1) * PITCH / 2
        for i, (pin, net) in enumerate(items):
            pins.append({"number": pin, "name": pin, "x": x,
                         "y": top - i * PITCH, "rotation": rot,
                         "length": PINLEN, "pinType": "Undefined"})
    # EasyEDA 约定：rotation = 引脚朝外方向（0=+x 右，180=-x 左）；(x,y) = 电气连接点
    col(left, -(hw + PINLEN), 180)
    col(right, (hw + PINLEN), 0)
    return {"outline": [-hw, -hh, hw, -hh, hw, hh, -hw, hh, -hw, -hh],
            "pins": pins}, h

if __name__ == "__main__":
    out = pathlib.Path(__file__).parent / "specs"
    out.mkdir(exist_ok=True)
    manifest = []
    for name, des, desc, left, right in MODULES:
        s, h = spec(left, right)
        (out / f"{name}.json").write_text(json.dumps(s, indent=1, ensure_ascii=False))
        manifest.append({"name": name, "designator": des, "desc": desc, "height": h,
                         "pins": [{"pin": p, "net": n} for p, n in left + right],
                         "left": [p for p, _ in left], "right": [p for p, _ in right]})
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False))
    print(f"{len(manifest)} modules, {sum(len(m['pins']) for m in manifest)} pins total")
    for m in manifest:
        print(f"  {m['name']:16s} {m['designator']:3s} h={m['height']:4.0f} pins={len(m['pins']):2d}")
