#!/usr/bin/env python3
"""建 12 个模块符号 + 器件（工程库）。工程库令牌 = 工程 UUID。"""
import json, subprocess, pathlib, sys

PROJ = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"
HERE = pathlib.Path(__file__).parent
SPECS = HERE / "specs"

def cli(*args, timeout=180):
    p = subprocess.run(["easyeda", *args, "--project", "maze-car"],
                       capture_output=True, text=True, timeout=timeout)
    try:
        return json.loads(p.stdout)
    except Exception:
        return {"ok": False, "raw": p.stdout[-500:] + p.stderr[-500:]}

manifest = json.loads((SPECS / "manifest.json").read_text())
done = {}
for m in manifest:
    name = m["name"]
    r = cli("lib", "symbol", "create", "--name", name, "--scope", "project")
    uu = (r.get("result") or {}).get("uuid")
    if not uu:
        print(f"CREATE FAIL {name}: {json.dumps(r)[:300]}"); sys.exit(1)
    b = cli("lib", "symbol", "build", "--library", PROJ, "--uuid", uu,
            "--spec", str(SPECS / f"{name}.json"))
    res = b.get("result") or {}
    ok = bool(res.get("verified"))
    print(f"{'OK ' if ok else 'ERR'} {name:16s} sym={uu} pins={len(res.get('created',{}).get('pins',[]))}")
    if not ok:
        print("   ", json.dumps(b)[:400]); sys.exit(1)
    done[name] = uu

# 建器件
dev = {}
for m in manifest:
    name = m["name"]
    d = cli("lib", "device", "create", "--name", name, "--symbol-uuid", done[name],
            "--symbol-library", PROJ, "--designator", m["designator"],
            "--scope", "project", "--pcb=false", "--description", m["desc"])
    r = d.get("result") or {}
    du = r.get("uuid") or r.get("deviceUuid")
    print(f"{'OK ' if du else 'ERR'} device {name:16s} {du} {'' if du else json.dumps(d)[:300]}")
    if du:
        dev[name] = du

(HERE / "lib_built.json").write_text(json.dumps({"project": PROJ, "symbols": done, "devices": dev},
                                                indent=1))
print("symbols", len(done), "devices", len(dev))
