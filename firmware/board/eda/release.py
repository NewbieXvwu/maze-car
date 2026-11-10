#!/usr/bin/env python3
"""一条命令出交付包（导出 → 删重复钻带 → 四道验证 → 打印 sha256）。

为什么要脚本：手工顺序漏一步就会交付一个坏包。本项目踩过的坑：
  - 编辑器会自动保存，但 `export-gerber` 读到的是引擎里的旧状态 → 先 `pcb save`；
  - 4.1.97 会把 via 写两份钻孔文件，必须在打 zip 时删掉 `Drill_PTH_Through_Via.DRL`；
  - `--out` 已存在会直接报错，所以先用带时间戳的新名字，再覆盖成规范名。

用法:
  python3 release.py                # 导出 + 打包 + 验证（会覆盖 out/gerber/maze-car-gerber.zip）
  python3 release.py --no-export    # 不重导出、也不重新打包，只对现有 zip 跑验证
"""
import hashlib
import json
import re
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
EDA = ROOT / "firmware/board/eda"
OUT = ROOT / "out/gerber/maze-car-gerber.zip"
PROJECT = "maze-car"
DROP = "Drill_PTH_Through_Via.DRL"


def sh(*args, cwd=None):
    return subprocess.run(list(args), capture_output=True, text=True, cwd=cwd or ROOT)


def json_of(out, what):
    i = out.find("{")
    if i < 0:
        raise SystemExit(f"{what} 没有 JSON: {out[-300:]}")
    return json.JSONDecoder().raw_decode(out[i:])[0]


def window_id():
    d = json_of(sh("easyeda", "health").stdout, "health")
    return d["found"]["raw"]["windows"][0]["windowId"]


def pcb_uuid():
    out = sh("easyeda", "doc", "ls", "--project", PROJECT).stdout
    for ln in out.splitlines():
        if re.search(r"\bpcb\b", ln):
            m = re.search(r"([0-9a-f]{16})\s*$", ln.strip())
            if m:
                return m.group(1)
    raise SystemExit("没找到 PCB 文档，先 `easyeda doc ls --project maze-car` 看一下")


def export():
    print("== 保存")
    r = sh("easyeda", "pcb", "save", "--doc", "PCB1", "--project", PROJECT)
    if '"saved": true' not in r.stdout:
        raise SystemExit("保存失败: " + r.stdout[-300:] + r.stderr[-300:])
    tmp = ROOT / f"out/gerber/.export-{time.strftime('%Y%m%d-%H%M%S')}.zip"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    print("== 导出", tmp.name)
    r = sh("easyeda", "pcb", "export-gerber", "--window", window_id(),
           "--project", PROJECT, "--doc", pcb_uuid(), "--out", str(tmp), "--unit", "mm")
    if not tmp.exists():
        raise SystemExit("导出失败: " + (r.stdout[-400:] + r.stderr[-400:]))
    return tmp


def repack(src):
    print("== 重打包（删重复钻带）")
    tmp = OUT.with_suffix(".zip.tmp")
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:
        names = []
        for it in zin.infolist():
            if it.filename == DROP:
                continue
            zout.writestr(it, zin.read(it.filename))
            names.append(it.filename)
    shutil.move(str(tmp), str(OUT))
    print(f"   {len(names)} 个文件")


def verify():
    ok = True
    for cmd, label in (
        ([sys.executable, str(EDA / "audit_gerber.py"), str(OUT)], "audit_gerber"),
        ([sys.executable, str(EDA / "verify_silk.py")], "verify_silk"),
        ([sys.executable, str(EDA / "verify_gerber_nets.py"), str(OUT),
          str(EDA / "pcb_plan.json")], "verify_gerber_nets"),
        ([sys.executable, str(EDA / "verify_board.py")], "verify_board"),
    ):
        r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        tail = (r.stdout.strip().splitlines() or [""])[-1]
        print(f"== {label}: {tail}")
        if r.returncode != 0:
            print(r.stdout[-1500:], r.stderr[-800:])
            ok = False
    return ok


def main():
    if "--no-export" not in sys.argv:
        tmp = export()
        repack(tmp)
        tmp.unlink()
    else:
        print("== 跳过导出，直接用现有 zip")
    ok = verify()
    data = OUT.read_bytes()
    print(f"\n交付包 {OUT.relative_to(ROOT)}")
    print(f"  {len(zipfile.ZipFile(OUT).namelist())} 个文件, {len(data)} B")
    print(f"  sha256 {hashlib.sha256(data).hexdigest()}")
    print("结论：" + ("可以下单" if ok else "有问题，别下单"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
