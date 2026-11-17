import asyncio, pathlib, sys
from playwright.async_api import async_playwright
OUT = pathlib.Path(__file__).resolve().parent.parent / "shots" / (sys.argv[1] if len(sys.argv) > 1 else "glbcheck")
OUT.mkdir(parents=True, exist_ok=True)
VIEWS = {"hero": (35, 18, 0.40), "front": (90, 8, 0.34), "top": (35, 84, 0.42),
         "left": (0, 10, 0.36), "pcb": (35, 70, 0.22)}
async def main():
    async with async_playwright() as p:
        b = await p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pg = await b.new_page(viewport={"width": 1200, "height": 900})
        pg.on("console", lambda m: print("  [console]", m.text) if m.type == "error" else None)
        await pg.goto("http://localhost:8123/tools/verify_glb.html")
        await pg.wait_for_function("window.__READY === true", timeout=60000)
        err = await pg.evaluate("() => window.__ERROR || null")
        if err:
            print("LOAD ERROR:", err); await b.close(); return
        print("GLB loaded:", await pg.evaluate("() => window.__info"))
        for name, (az, el, d) in VIEWS.items():
            await pg.evaluate("([a,e,d]) => window.__setCam(a,e,d)", [az, el, d])
            await pg.wait_for_timeout(250)
            await pg.screenshot(path=str(OUT / f"{name}.png"))
            print("shot", name)
        await b.close()
asyncio.run(main())
