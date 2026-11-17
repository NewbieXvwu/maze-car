"""Export the car to out/model/{maze-car.glb,obj,stl} using the live viewer.

Run: python3 tools/export_model.py
GLB  : metres, Y-up (glTF convention)
OBJ  : millimetres, Z-up (CAD convention)
STL  : millimetres, Z-up (3D-print convention)
"""
import asyncio, base64, json, pathlib, sys
from playwright.async_api import async_playwright

OUT = pathlib.Path(__file__).resolve().parent.parent / "out" / "model"
URL = "http://localhost:8123/viewer/"

async def main():
    OUT.mkdir(parents=True, exist_ok=True)
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = await b.new_page(viewport={"width": 1200, "height": 900})
        pg.on("console", lambda m: print("  [console]", m.text) if m.type == "error" else None)
        await pg.goto(URL)
        await pg.wait_for_function("window.__READY === true", timeout=40000)
        stats = await pg.evaluate("() => window.__stats()")
        print("scene:", stats)
        for t, ext in (("glb", "glb"), ("obj", "obj"), ("stl", "stl")):
            b64 = await pg.evaluate("(t) => window.__export(t)", t)
            data = base64.b64decode(b64)
            f = OUT / f"maze-car.{ext}"
            f.write_bytes(data)
            print(f"  {f.name}: {len(data):,} bytes")
        # glb sanity
        g = (OUT / "maze-car.glb").read_bytes()
        magic, ver, total = int.from_bytes(g[0:4], "little"), int.from_bytes(g[4:8], "little"), int.from_bytes(g[8:12], "little")
        jlen = int.from_bytes(g[12:16], "little")
        j = json.loads(g[20:20 + jlen].decode("utf-8"))
        print(f"  GLB magic={magic:#x} version={ver} declared={total} actual={len(g)}")
        print(f"  nodes={len(j.get('nodes', []))} meshes={len(j.get('meshes', []))} "
              f"materials={len(j.get('materials', []))} textures={len(j.get('textures', []))} "
              f"accessors={len(j.get('accessors', []))} images={len(j.get('images', []))}")
        prims = sum(len(m['primitives']) for m in j.get('meshes', []))
        tris = 0
        for m in j.get('meshes', []):
            for pr in m['primitives']:
                idx = pr.get('indices')
                if idx is not None:
                    tris += j['accessors'][idx]['count'] // 3
        print(f"  primitives={prims} triangles={tris:,}")
        # bounding box from POSITION accessors (node transforms are identity except the root)
        mins = [1e9] * 3
        maxs = [-1e9] * 3
        for m in j.get('meshes', []):
            for pr in m['primitives']:
                acc = j['accessors'][pr['attributes']['POSITION']]
                for k in range(3):
                    mins[k] = min(mins[k], acc['min'][k]); maxs[k] = max(maxs[k], acc['max'][k])
        print("  bbox(min,max):", [round(v, 4) for v in mins], [round(v, 4) for v in maxs])
        await b.close()
    print("done")

asyncio.run(main())
