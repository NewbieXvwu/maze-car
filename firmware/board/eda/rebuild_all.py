#!/usr/bin/env python3
"""重建工程库里的 12 个模块符号+器件（先删后建），并核对落地。"""
import json, subprocess, pathlib
HERE = pathlib.Path(__file__).parent
PROJ = "0b4cef7a743d089a2ec5d694978c583f3a22fec3deba6e8e58ee68d5a5d2789e"
SPECS = HERE / "specs"
manifest = json.loads((SPECS / "manifest.json").read_text())

def cli(*a, timeout=180):
    p = subprocess.run(["easyeda", *a, "--project", "maze-car"], capture_output=True, text=True, timeout=timeout)
    try: return json.loads(p.stdout)
    except Exception: return {"ok": False, "raw": (p.stdout or "")[-200:]}

def api(code, timeout=90):
    p = subprocess.run(["easyeda", "debug", "exec", "--timeout", str(timeout), "--code", code,
                        "--project", "maze-car"], capture_output=True, text=True, timeout=timeout+30)
    try: return json.loads(p.stdout)["result"]["value"]
    except Exception: return {"err": (p.stdout or "")[-300:]}

# 1) 清掉旧符号/器件
syms = api(f"const r=[];const p=await eda.lib_Symbol.search('','project',[],undefined,100,1);"
           f"for(const s of p){{if(s.name.startsWith('EA_AGENT__'))r.push([s.uuid,s.name]);}}return r;")
devs = api("const r=[];const p=await eda.lib_Device.search('','project',[],undefined,100,1);"
           "for(const d of p){if(d.name.startsWith('EA_AGENT__'))r.push([d.uuid,d.name]);}return r;")
for du,_ in (devs if isinstance(devs,list) else []):
    api(f"try{{await eda.lib_Device.delete('{du}','{PROJ}');return 1}}catch(e){{return 0}}")
for su,_ in (syms if isinstance(syms,list) else []):
    api(f"try{{await eda.lib_Symbol.delete('{su}','{PROJ}');return 1}}catch(e){{return 0}}")
print(f"removed old: {len(devs)} devices, {len(syms)} symbols")

# 2) 重建
out = {"project": PROJ, "symbols": {}, "devices": {}}
for m in manifest:
    name = m["name"]
    r = cli("lib", "symbol", "create", "--name", name, "--scope", "project")
    uu = (r.get("result") or {}).get("uuid")
    if not uu: raise SystemExit(f"create fail {name}: {json.dumps(r)[:300]}")
    b = cli("lib", "symbol", "build", "--library", PROJ, "--uuid", uu, "--spec", str(SPECS/f"{name}.json"))
    res = b.get("result") or {}
    if not res.get("verified"): raise SystemExit(f"build fail {name}: {json.dumps(b)[:400]}")
    out["symbols"][name] = uu
print(f"symbols rebuilt: {len(out['symbols'])}")

for m in manifest:
    name = m["name"]
    d = cli("lib", "device", "create", "--name", name, "--symbol-uuid", out["symbols"][name],
            "--symbol-library", PROJ, "--designator", m["designator"], "--library", PROJ,
            "--pcb=false", "--description", m["desc"])
    # 已知假失败：以列表核对为准
for d in (api("return await eda.lib_Device.search('','project',[],undefined,100,1);") or []):
    nm = d["name"].replace("EA_AGENT__", "")
    if nm in {m["name"] for m in manifest}:
        out["devices"][nm] = d["uuid"]
print(f"devices verified: {len(out['devices'])}")
missing = {m['name'] for m in manifest} - set(out['devices'])
if missing: print("MISSING devices:", missing)
(HERE/"lib_built.json").write_text(json.dumps(out, indent=1, ensure_ascii=False))
