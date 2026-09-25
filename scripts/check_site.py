"""Headless check of the results page: light/dark x desktop/phone, failing on errors.

    uv run --directory ../polyfetch-scrape python ../feelings/scripts/check_site.py <out_dir> [url]

Uses polyfetch-scrape's patchright Chromium (see qte77/brand/ui-kit README). Fails on console
errors, page errors, failed requests or horizontal page scroll; saves one screenshot per variant.
"""

import sys

from patchright.sync_api import sync_playwright

OUT = sys.argv[1]
URL = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8137/"
VIEWPORTS = (("desktop", {"width": 1280, "height": 900}), ("phone", {"width": 390, "height": 844}))
problems = []

with sync_playwright() as p:
    browser = p.chromium.launch()
    for theme in ("light", "dark"):
        for name, viewport in VIEWPORTS:
            page = browser.new_page(viewport=viewport, device_scale_factor=1)
            where = f"{theme}/{name}"
            page.on("console", lambda m, w=where: m.type == "error" and problems.append(f"{w} console: {m.text}"))
            page.on("pageerror", lambda e, w=where: problems.append(f"{w} pageerror: {e}"))
            page.on("requestfailed", lambda r, w=where: problems.append(f"{w} request failed: {r.url}"))
            page.goto(f"{URL}?theme={theme}", wait_until="networkidle")
            page.wait_for_selector("#pilot table.results tbody tr")
            counts = {
                "sized": page.locator("#sized table.results tbody tr").count(),
                "pilot": page.locator("#pilot table.results tbody tr").count(),
                "sweep": page.locator("#sized table.sweep tbody tr").count(),
            }
            kpis = page.locator("#sized .kpis dd").all_inner_texts()
            axes = page.locator("[data-fill=axis-min]").all_inner_texts()
            overflow = page.evaluate("document.documentElement.scrollWidth > window.innerWidth")
            print(f"{where}: {counts} kpis={kpis} axis_starts={axes} horizontal_scroll={overflow}")
            if overflow:
                problems.append(f"{where}: page scrolls horizontally")
            page.screenshot(path=f"{OUT}/{theme}-{name}.png", full_page=True)
            page.close()
    page = browser.new_page()
    page.on("pageerror", lambda e: problems.append(f"toggle pageerror: {e}"))
    page.goto(f"{URL}?theme=light", wait_until="networkidle")
    page.click("#theme-toggle")
    print("theme after one click:", page.evaluate("document.documentElement.dataset.theme"))
    browser.close()

print("PROBLEMS:", problems or "none")
sys.exit(1 if problems else 0)
