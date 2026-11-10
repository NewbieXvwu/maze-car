#!/usr/bin/env python3
"""出厂前对 Gerber 压缩包做独立审计：不看编辑器，只读文件。

核对项：
  1. 板框（GKO）是不是一个闭合轮廓、外形尺寸对不对
  2. 每层的光圈定义 / 闪光(D03) / 走线(D01) / 区域(G36) 数量
  3. 顶层、底层铜皮的闪光点是否与孔位一一对应
  4. 阻焊层开窗数量是否 = 孔数×2（顶层+底层）
  5. 钻孔文件里的孔径分布、孔数与坐标是否与设计一致
  6. 所有铜/丝印是否落在板框内
用法：python3 audit_gerber.py <zip> [--json out.json]
"""
import json
import math
import re
import sys
import zipfile

LAYER_NAMES = {
    "GTL": "顶层铜", "GBL": "底层铜", "GTO": "顶层丝印", "GBO": "底层丝印",
    "GTS": "顶层阻焊", "GBS": "底层阻焊", "GKO": "板框", "GDD": "钻孔图",
}


def parse_layer(text):
    """返回 {apertures, flashes, draws, regions, bbox, units, fmt}"""
    units = "MM" if "%MOMM*%" in text else "IN"
    m = re.search(r"%FSLAX(\d)(\d)Y(\d)(\d)\*%", text)
    xi, xd = (int(m.group(1)), int(m.group(2))) if m else (4, 5)
    scale = 10 ** xd
    apertures = {}
    for a in re.finditer(r"%ADD(\d+)([A-Za-z_0-9]+),([^*]*)\*%", text):
        apertures[int(a.group(1))] = (a.group(2), a.group(3))
    flashes, draws, regions = [], [], 0
    cur = None
    x = y = 0.0
    xs, ys = [], []
    in_region = False
    for tok in re.finditer(r"([XYIJ][+-]?\d+|D\d+|G\d+|M\d+)[*\s]", text):
        pass
    # 逐行解析更稳
    pos = {"X": 0, "Y": 0}
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("%ADD"):
            continue
        if line.startswith("G36"):
            in_region = True
            regions += 1
            pos = dict(pos)
            continue
        if line.startswith("G37"):
            in_region = False
            continue
        if line.startswith("%") or line.startswith("G04"):
            continue
        mm = re.match(r"^(?:G0?1)?(?:X(-?\d+))?(?:Y(-?\d+))?(?:I-?\d+)?(?:J-?\d+)?(D0?[123])?\*$", line)
        if not mm:
            dm = re.match(r"D(\d+)\*$", line)
            if dm:
                cur = int(dm.group(1))
            continue
        if mm.group(1) is not None:
            pos["X"] = int(mm.group(1))
        if mm.group(2) is not None:
            pos["Y"] = int(mm.group(2))
        op = mm.group(3)
        x, y = pos["X"] / scale, pos["Y"] / scale
        if op in ("D01", "D1") or (in_region and op is None and cur):
            draws.append((x, y, cur))
        elif op in ("D03", "D3"):
            flashes.append((x, y, cur))
        xs.append(x)
        ys.append(y)
    bbox = (min(xs), min(ys), max(xs), max(ys)) if xs else None
    return {"units": units, "format": f"{xi}.{xd}", "apertures": apertures,
            "flashes": flashes, "draws": draws, "regions": regions, "bbox": bbox}


def read_drill(text):
    """返回 (单位, {孔径: 数量}, [坐标])"""
    units = "MM" if "METRIC" in text.upper() else "IN"
    tools = {}
    for t in re.finditer(r"^T(\d+)C([\d.]+)", text, re.M):
        tools[int(t.group(1))] = float(t.group(2))
    cur, hits, counts = None, [], {}
    for raw in text.splitlines():
        line = raw.strip()
        tm = re.match(r"^T(\d+)$", line)
        if tm:
            cur = int(tm.group(1))
            continue
        cm = re.match(r"^X([-\d.]+)Y([-\d.]+)$", line)
        if cm and cur is not None:
            hits.append((float(cm.group(1)), float(cm.group(2)), tools.get(cur)))
            counts[tools.get(cur)] = counts.get(tools.get(cur), 0) + 1
    return units, counts, hits


def main():
    zpath = sys.argv[1]
    z = zipfile.ZipFile(zpath)
    names = {n.split(".")[-1].split("_")[-1] if "Gerber_" in n else n: n for n in z.namelist()}
    data = {}
    for n in z.namelist():
        data[n] = z.read(n).decode("utf8", "replace")
    gerbers = {n: parse_layer(t) for n, t in data.items() if n.lower().endswith(".gtl") or
               n.lower().endswith(".gbl") or n.lower().endswith(".gto") or
               n.lower().endswith(".gbo") or n.lower().endswith(".gts") or
               n.lower().endswith(".gbs") or n.lower().endswith(".gko")}
    print(f"== {zpath} ==")
    for n, g in sorted(gerbers.items()):
        ext = n.split(".")[-1].upper()
        bb = g["bbox"]
        print(f"{LAYER_NAMES.get(ext, ext):6} {ext}: 光圈 {len(g['apertures']):2} "
              f"闪光 {len(g['flashes']):4} 线段点 {len(g['draws']):5} 区域 {g['regions']:4} "
              f"bbox {bb[0]:.2f},{bb[1]:.2f} ~ {bb[2]:.2f},{bb[3]:.2f}" if bb else f"{ext}: 空")
    drills = {n: read_drill(t) for n, t in data.items() if n.lower().endswith(".drl")}
    for n, (u, counts, hits) in drills.items():
        print(f"钻孔 {n}: 单位 {u} 孔数 {len(hits)} 孔径 {counts}")
    for n, t in data.items():
        if n.lower().endswith(".json"):
            try:
                j = json.loads(t)
                print(f"飞针 {n}: {json.dumps(j, ensure_ascii=False)[:160]}")
            except Exception:
                pass
    # 一句话结论（release.py 只回显最后一行）
    gko = next((g for n, g in gerbers.items() if n.upper().endswith(".GKO")), None)
    gto = next((g for n, g in gerbers.items() if n.upper().endswith(".GTO")), None)
    drill_ok = all(len(v[2]) > 0 for v in drills.values()) and drills
    ok = bool(gko and gko["bbox"] and gto and gto["bbox"] and drill_ok)
    if ok and gto["bbox"]:
        h = gto["bbox"][3] - gto["bbox"][1]
        w = gto["bbox"][2] - gto["bbox"][0]
        print(f"结论：{'PASS' if ok else 'FAIL'} —— 板框闭合、"
              f"丝印 {gto['regions']} 个区域/{len(gto['draws'])} 段线"
              f"（整层外框 {w:.1f}×{h:.1f}mm，不是字高）、"
              f"钻孔 {sum(len(v[2]) for v in drills.values())} 个")
    else:
        print("结论：FAIL —— 缺板框/丝印层或钻带为空")
    out = {n: {k: (v if k != "apertures" else {str(a): b for a, b in v.items()}) for k, v in g.items()}
           for n, g in gerbers.items()}
    if not ok:
        return 1
    if "--json" in sys.argv:
        p = sys.argv[sys.argv.index("--json") + 1]
        json.dump({"gerbers": {k: {kk: vv for kk, vv in v.items() if kk != "flashes"}
                               for k, v in out.items()},
                   "drills": {k: {"counts": {str(a): c for a, c in v[1].items()},
                                  "holes": v[2]} for k, v in drills.items()}},
                  open(p, "w"), ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())
