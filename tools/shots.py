#!/usr/bin/env python3
"""Render the viewer from scripted camera angles for visual QA.

Usage: python3 tools/shots.py [outdir] [--views hero,front,...]
"""
import asyncio
import json
import sys
from pathlib import Path

from playwright.async_api import async_playwright

ROOT = Path(__file__).resolve().parents[1]
URL = "http://localhost:8123/viewer/"
VIEWS = ["hero", "front", "left", "right", "top", "rear", "bottom", "detail"]

W, H = 1400, 1000


async def main(argv):
    outdir = Path(argv[1]) if len(argv) > 1 and not argv[1].startswith("--") else ROOT / "shots" / "latest"
    outdir.mkdir(parents=True, exist_ok=True)
    views = VIEWS
    if "--views" in argv:
        views = argv[argv.index("--views") + 1].split(",")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
        )
        page = await browser.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        logs = []
        page.on("console", lambda m: logs.append(f"[{m.type}] {m.text}"))
        page.on("pageerror", lambda e: logs.append(f"[pageerror] {e}"))
        await page.goto(URL, wait_until="load")
        try:
            await page.wait_for_function("window.__READY === true", timeout=25000)
            await page.evaluate("window.__hideUI && window.__hideUI(); window.__hideFloor && window.__hideFloor(true);")
        except Exception:
            print("NOT READY")
            print("\n".join(logs[-30:]))
            await page.screenshot(path=str(outdir / "_error.png"))
            await browser.close()
            return 1

        stats = await page.evaluate("window.__stats ? window.__stats() : null")
        bounds = await page.evaluate("window.__bounds ? window.__bounds() : null")
        print("stats:", json.dumps(stats))
        print("bounds:", json.dumps(bounds))

        for v in views:
            await page.evaluate(f"window.__setView({v!r}, true)")
            await page.wait_for_timeout(180)
            await page.screenshot(path=str(outdir / f"{v}.png"))
            print("shot", v)

        errs = [l for l in logs if l.startswith("[pageerror]") or l.startswith("[error]")]
        if errs:
            print("ERRORS:\n" + "\n".join(errs[:20]))
        await browser.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv)))
